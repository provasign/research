"""run_e2e build environment: Java parent pin + per-cell Maven repo chain,
JS/TS install command and package-manager env, node_modules out of the diff."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS / "runners"))
sys.argv = sys.argv[:1]
import run_e2e  # noqa: E402
import java_eval  # noqa: E402

POM = """<project>
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>tools.jackson</groupId>
    <artifactId>jackson-base</artifactId>
    <version>{v}-SNAPSHOT</version>
  </parent>
  <artifactId>jackson-databind</artifactId>
  <version>{v}-SNAPSHOT</version>
</project>
"""


def git(wt, *a):
    return subprocess.run(["git", "-C", str(wt), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                          capture_output=True, text=True, check=True).stdout


def repo_with_pom(v="3.2.0"):
    wt = Path(tempfile.mkdtemp())
    git(wt, "init", "-q")
    (wt / "pom.xml").write_text(POM.format(v=v))
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "base")
    return wt, git(wt, "rev-parse", "HEAD").strip()


def fake_m2(release=None, snapshot=None):
    m2 = Path(tempfile.mkdtemp())
    d = m2 / "repository/tools/jackson/jackson-base"
    if release:
        (d / release).mkdir(parents=True)
        (d / release / f"jackson-base-{release}.pom").write_text("<project/>")
    if snapshot:
        (d / f"{snapshot}-SNAPSHOT").mkdir(parents=True)
        (d / f"{snapshot}-SNAPSHOT" / f"jackson-base-{snapshot}-20260701.150156-2.pom").write_text("<project/>")
    return m2


class JavaPinTests(unittest.TestCase):
    def test_pin_is_committed_so_the_agent_diff_stays_empty(self):
        wt, base = repo_with_pom()
        task = {"lang": "java", "test_modules": []}
        self.assertTrue(run_e2e._pin_java_worktree(wt, task))
        self.assertIn("<version>3.2.0</version>\n  </parent>", (wt / "pom.xml").read_text())
        self.assertEqual(git(wt, "rev-parse", "HEAD~1").strip(), base)
        self.assertEqual(git(wt, "status", "--porcelain"), "")
        self.assertEqual(run_e2e._agent_diff(wt, task), "")

    def test_unreleased_snapshot_parent_is_kept(self):
        wt, _ = repo_with_pom("3.3.0")
        self.assertFalse(java_eval._pin_snapshot_parent(wt, fake_m2(snapshot="3.3.0")))
        self.assertIn("3.3.0-SNAPSHOT</version>\n  </parent>", (wt / "pom.xml").read_text())
        wt, _ = repo_with_pom("3.3.0")
        self.assertTrue(java_eval._pin_snapshot_parent(wt, fake_m2(release="3.3.0", snapshot="3.3.0")))
        wt, _ = repo_with_pom("3.3.0")
        self.assertTrue(java_eval._pin_snapshot_parent(wt, fake_m2()))  # nothing cached: pin as before

    def test_non_java_task_is_untouched(self):
        wt, _ = repo_with_pom()
        self.assertFalse(run_e2e._pin_java_worktree(wt, {"lang": "go"}))
        self.assertIn("-SNAPSHOT</version>\n  </parent>", (wt / "pom.xml").read_text())


class JavaEnvTests(unittest.TestCase):
    def test_per_cell_repo_chained_onto_seed_and_scorer_cache(self):
        wt, base = repo_with_pom()
        env, rt = run_e2e._agent_env(wt, {"lang": "java", "base_commit": base})
        head = run_e2e._cell_m2(wt)
        self.assertIn(f"-Dmaven.repo.local={head}", env["MAVEN_OPTS"])
        self.assertIn(f"-Dmaven.repo.local.tail={run_e2e.AGENT_M2_SEED},{run_e2e.SCORER_M2_REPO}",
                      env["MAVEN_OPTS"])
        self.assertIn("-nsu", env["MAVEN_ARGS"])
        self.assertIn("-Drat.skip=true", env["MAVEN_ARGS"])
        self.assertTrue(head.is_dir())
        run_e2e._remove_worktree(wt)
        self.assertFalse(head.exists())

    def test_non_java_env_has_no_maven_repo(self):
        wt, base = repo_with_pom()
        env, _ = run_e2e._agent_env(wt, {"lang": "go", "repo": "x/y", "base_commit": base})
        self.assertNotIn("maven.repo.local", env.get("MAVEN_OPTS", ""))
        self.assertFalse(run_e2e._cell_m2(wt).exists())


class NodeTests(unittest.TestCase):
    def test_install_cmd_is_the_scorers_on_host_paths(self):
        self.assertEqual(run_e2e._node_install_cmd("honojs/hono"), "bun install --frozen-lockfile")
        z = run_e2e._node_install_cmd("colinhacks/zod")
        self.assertTrue(z.startswith("pnpm install --frozen-lockfile "))
        self.assertIn(f"--store-dir {run_e2e.AGENT_PNPM_STORE}", z)
        self.assertIn("--filter . --filter zod", z)
        self.assertNotIn("/pnpm-store", z)

    def test_agent_env_points_package_managers_at_the_agent_stores(self):
        wt, base = repo_with_pom()
        env, _ = run_e2e._agent_env(wt, {"lang": "ts", "repo": "colinhacks/zod", "base_commit": base})
        self.assertEqual(env["npm_config_store_dir"], str(run_e2e.AGENT_PNPM_STORE))
        self.assertEqual(env["npm_config_manage_package_manager_versions"], "false")
        self.assertEqual(env["BUN_INSTALL_CACHE_DIR"], str(run_e2e.AGENT_BUN_CACHE))

    def test_preinstall_skips_other_languages(self):
        self.assertEqual(run_e2e._preinstall_node(Path("/nonexistent"), {"lang": "java"}), {})

    def test_node_modules_never_enter_the_diff(self):
        wt, _ = repo_with_pom()
        nm = wt / "packages/zod/node_modules/x"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x")
        (wt / "src.ts").write_text("export const a = 1\n")
        diff = run_e2e._agent_diff(wt, {"test_modules": []})
        self.assertIn("src.ts", diff)
        self.assertNotIn("node_modules", diff)


if __name__ == "__main__":
    unittest.main()
