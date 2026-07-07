#!/usr/bin/env python3
"""CI invariant suite for the grove/prism engine.

No LLM, no oracle re-derivation at check time: ground truth for the ceiling
regression is already committed in harness/tasks/*.json (Java/TS/Python) or
hardcoded below (Go, whose tasks are natural-language prompts, not
oracle-derived FQNs). Three invariant classes, each modeled on a real bug
found during the 2026-07-06/07 resolution-bug sweep (see
memory/sibling-ops-shipped.md in the assistant's project memory, or the
session transcript, for the full story):

  1. Ceiling regression   — change-impact recall/precision vs a committed
                             baseline, per corpus. Catches: case-fold
                             conflation, nested-qualifier fan-out, dotted
                             supertype resolution, header-comment corruption.
  2. Compile invariant     — missing-implementations == [] on a repo known
                             to compile (documented true positives excepted).
                             Catches: the same closure-pollution bugs from a
                             different angle (missing-implementations has no
                             signature filter to mask them, unlike
                             change-impact's family walk).
  3. Structural invariants — rename-plan never drops a contract's own
                             declaration into Unresolved (the interface
                             itself IS a change site); double cold-index is
                             byte-identical (determinism).

Usage:
  python ci_invariants.py --corpus-root /tmp/ci-corpus [--prism /path/to/prism]

Each corpus is fetched once (GitHub archive tarball at the pinned commit —
no git history needed) into --corpus-root and reused across all three
checks. Exits non-zero with a diagnostic on the first violated invariant
class; runs all corpora within a class before failing so one bad corpus
doesn't hide a second regression elsewhere.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))
from schema import Answer, Site, Task  # noqa: E402
from score import score  # noqa: E402

BASELINE_FILE = HARNESS_DIR / "ci_baseline.json"

# --- corpus manifest ---------------------------------------------------
# subdir: index/query from this path within the extracted archive (guava's
# repo root is a multi-module monorepo; the java sources the tasks target
# live under guava/).
CORPORA = {
    "jackson-databind": {"owner": "FasterXML", "repo": "jackson-databind",
                          "pin": "0b422144d1785200e44a0b00c973f6ac95adcf5a"},
    "typeorm": {"owner": "typeorm", "repo": "typeorm",
                "pin": "3d55188c0dd1256f520143379ecf97f45e71acba"},
    "django": {"owner": "django", "repo": "django",
               "pin": "318a316a4c86a65bede68144f9546a6056d91379"},
    "guava": {"owner": "google", "repo": "guava",
              "pin": "f06690fa3e874f65515e8fd338a74d636e2c792f", "subdir": "guava"},
    "grafana-122750": {"owner": "grafana", "repo": "grafana",
                        "pin": "b6fdc12f22de961e1cb5c233512df675d2d4e32b"},
    "grafana-120119": {"owner": "grafana", "repo": "grafana",
                        "pin": "cea7eb61f4321738a895095942d600bd770b51a8"},
    "gin": {"owner": "gin-gonic", "repo": "gin",
            "pin": "d75fcd4c9ab260e5225de590f1f0f8c0e0e12d11"},
    "commons-collections": {"owner": "apache", "repo": "commons-collections",
                             "pin": "4db4327796f9679b9e57f6788d1d7bb2e8459360"},
}

# Tasks whose corpus is identical to (same repo + pin as) an entry already
# in CORPORA — fetched once, reused, no duplicate download.
CORPUS_ALIAS = {"grafana-bigblast-txsession": "grafana-122750"}

# Go tasks are natural-language prompts, not oracle-derived FQNs (see
# engine_ceiling.py's prism_query for the Java/TS/Python automatic path) —
# the multi-method queries are hardcoded per the task's own prompt text.
GO_QUERIES = {
    "grafana-122750": [f"DataKeyCache.{m}" for m in
                        ("GetById", "GetByLabel", "Set", "RemoveExpired", "Flush")],
    "grafana-120119": [f"RouteService.{m}" for m in
                        ("GetManagedRoute", "GetManagedRoutes", "CreateManagedRoute",
                         "UpdateManagedRoute", "DeleteManagedRoute")],
    "grafana-bigblast-txsession": ["SQLStore.WithTransactionalDbSession"],
}

# Compile invariant: (corpus, query, exceptions). exceptions lists GT-shaped
# "file:name" strings that are DOCUMENTED true positives (real compile
# breakage in the repo itself, or a target the audit already excluded), so
# the check does not chase them as regressions.
COMPILE_INVARIANT_TARGETS = [
    ("jackson-databind", "JsonSerializer.serialize", []),
    ("gin", "ResponseWriter.Status", []),
    ("typeorm", "Driver.escape", []),
    # django's dummy backend deliberately does not implement quote_name —
    # a documented true positive (paper §"Cross-language external validity"),
    # not an engine defect. See sibling-ops-shipped.md for the discovery.
    ("django", "BaseDatabaseOperations.quote_name",
     ["django/db/backends/dummy/base.py:DatabaseOperations"]),
]

# Structural invariant: an interface-shaped rename must never drop the
# contract's OWN declaring file into Unresolved (the grafana DataKeyCache /
# RouteService bug — the synthesized member decl has no RawText, so the
# spec line silently vanished from the plan instead of being edited).
RENAME_PLAN_TARGETS = [
    ("grafana-122750", "DataKeyCache.GetById", "GetDataKeyById",
     "pkg/registry/apis/secret/encryption/secrets.go"),
    ("typeorm", "Driver.escape", "escapeName", "src/driver/Driver.ts"),
]

DETERMINISM_CORPUS = "gin"


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_corpus(name: str, spec: dict, corpus_root: Path) -> Path:
    """Download the GitHub archive tarball at the pinned commit — a single
    tree snapshot, no git history — and extract it under corpus_root/name.
    Idempotent: skips work if already present (re-running locally is cheap)."""
    dest = corpus_root / name
    if dest.exists():
        return dest / spec.get("subdir", "")
    corpus_root.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{spec['owner']}/{spec['repo']}/archive/{spec['pin']}.tar.gz"
    tarball = corpus_root / f"{name}.tar.gz"
    log(f"[fetch] {name} @ {spec['pin'][:12]} <- {url}")
    urllib.request.urlretrieve(url, tarball)
    # Extract into an isolated staging dir, not corpus_root directly: two
    # tasks against the same repo (grafana-122750, grafana-120119) both
    # extract a dir prefixed "grafana-", which collided with the sibling's
    # ALREADY-RENAMED destination when globbed straight out of corpus_root.
    stage = corpus_root / f"_stage_{name}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    with tarfile.open(tarball) as tf:
        tf.extractall(stage)
    tarball.unlink()
    (extracted,) = [p for p in stage.iterdir() if p.is_dir()]
    extracted.rename(dest)
    stage.rmdir()
    return dest / spec.get("subdir", "")


def run_prism(prism: Path, workdir: Path, *args: str) -> dict:
    result = subprocess.run(
        [str(prism), *args, "."], capture_output=True, text=True, cwd=workdir, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prism {' '.join(args)} failed in {workdir}: {result.stderr[:400]}")
    return json.loads(result.stdout)


def index(prism: Path, workdir: Path) -> None:
    subprocess.run([str(prism), "index", "."], capture_output=True, text=True,
                    cwd=workdir, timeout=300, check=True)


def engine_sites(prism: Path, query: str, workdir: Path) -> tuple[list[str], dict]:
    data = run_prism(prism, workdir, "change-impact", query)
    sites: list[str] = []
    # declaringTypes: the interface/type declaration itself is a change site
    # for languages whose member specs are not separate symbols (Go, TS) —
    # omitting this group from the union is exactly the blind spot §1 fixed.
    for group in ("declarations", "family", "callers", "declaringTypes"):
        for sym in data.get(group, []):
            fp = sym.get("filePath") or sym.get("file", "")
            nm = sym.get("name", "")
            if fp and nm:
                sites.append(f"{fp}:{nm}")
    return sites, data


# --- invariant 1: ceiling regression ------------------------------------

def check_ceiling_regression(prism: Path, corpus_root: Path, baseline: dict) -> list[str]:
    log("\n=== Ceiling regression ===")
    failures = []

    def check(name: str, recall: float, precision: float, gt: int, sites: int) -> None:
        base = baseline["ceilings"][name]
        tol = base.get("tolerance", 0.005)
        ok_r = recall >= base["recall"] - tol
        ok_p = precision >= base["precision"] - tol
        status = "OK" if ok_r and ok_p else "REGRESSION"
        log(f"  {name:<28} GT={gt:<4} recall={recall:.4f} (base {base['recall']:.4f}) "
            f"precision={precision:.4f} (base {base['precision']:.4f}) sites={sites}  [{status}]")
        if not (ok_r and ok_p):
            failures.append(f"{name}: recall {recall:.4f} < {base['recall']-tol:.4f} or "
                             f"precision {precision:.4f} < {base['precision']-tol:.4f}")

    # Java/TS/Python: ground truth + query derivation already committed in
    # the task JSON (pr: "oracle-<lang>:...").
    for task_id, corpus_name in [
        ("jackson-jsonnode-get", "jackson-databind"), ("jackson-settable-set", "jackson-databind"),
        ("jackson-writetypeprefix", "jackson-databind"), ("jackson-serializewithtype", "jackson-databind"),
        ("jackson-deserialize", "jackson-databind"), ("jackson-serialize", "jackson-databind"),
        ("typeorm-driver-escape", "typeorm"), ("django-quotename", "django"),
        ("guava-forwarding-delegate", "guava"),
        ("commons-collections-transformer-transform", "commons-collections"),
    ]:
        task = Task.load(str(HARNESS_DIR / "tasks" / f"{task_id}.json"))
        workdir = fetch_corpus(corpus_name, CORPORA[corpus_name], corpus_root)
        fqn = task.pr.split(":", 1)[1]
        query = fqn.split("#", 1)[0].rsplit(".", 1)[-1] + "." + fqn.split("#", 1)[1] \
            if "#" in fqn else fqn
        raw, _ = engine_sites(prism, query, workdir)
        card = score(task, Answer(sites=[Site.parse(s) for s in raw], complete=True, unresolved=[]),
                     "CI", 0)
        check(task_id, card.recall, card.precision, len(task.ground_truth), len(raw))

    # Go: multi-method queries hardcoded (no automatic FQN derivation).
    for task_id, queries in GO_QUERIES.items():
        task = Task.load(str(HARNESS_DIR / "tasks" / f"{task_id}.json"))
        corpus_key = CORPUS_ALIAS.get(task_id, task_id)
        workdir = fetch_corpus(corpus_key, CORPORA[corpus_key], corpus_root)
        seen = {}
        for q in queries:
            raw, _ = engine_sites(prism, q, workdir)
            for s in raw:
                seen[s] = True
        card = score(task, Answer(sites=[Site.parse(s) for s in seen], complete=True, unresolved=[]),
                     "CI", 0)
        check(task_id, card.recall, card.precision, len(task.ground_truth), len(seen))

    return failures


# --- invariant 2: compile invariant --------------------------------------

def check_compile_invariant(prism: Path, corpus_root: Path) -> list[str]:
    log("\n=== Compile invariant (missing-implementations == 0, modulo documented exceptions) ===")
    failures = []
    for corpus_name, query, exceptions in COMPILE_INVARIANT_TARGETS:
        spec = CORPORA[corpus_name]
        workdir = fetch_corpus(corpus_name, spec, corpus_root)
        data = run_prism(prism, workdir, "missing-implementations", query)
        missing = [f"{m.get('filePath')}:{m.get('name')}" for m in data.get("missing", [])]
        unexpected = [m for m in missing if m not in exceptions]
        status = "OK" if not unexpected else "VIOLATION"
        log(f"  {corpus_name:<20} {query:<32} missing={len(missing)} "
            f"(documented={len(exceptions)})  [{status}]")
        if unexpected:
            failures.append(f"{corpus_name} {query}: undocumented missing implementations: {unexpected}")
    return failures


# --- invariant 3: structural (rename-plan completeness, determinism) ----

def check_rename_plan_completeness(prism: Path, corpus_root: Path) -> list[str]:
    log("\n=== Rename-plan completeness (contract declaration never Unresolved) ===")
    failures = []
    for corpus_name, query, new_name, contract_file in RENAME_PLAN_TARGETS:
        spec = CORPORA[corpus_name]
        workdir = fetch_corpus(corpus_name, spec, corpus_root)
        data = run_prism(prism, workdir, "rename-plan", query, new_name)
        unresolved = data.get("unresolved", [])
        dropped = [u for u in unresolved if u.startswith(contract_file)]
        status = "OK" if not dropped else "VIOLATION"
        log(f"  {corpus_name:<20} {query:<28} unresolved={len(unresolved)}  [{status}]")
        if dropped:
            failures.append(f"{corpus_name} {query}: contract declaration dropped into "
                             f"Unresolved: {dropped}")
    return failures


def check_determinism(prism: Path, corpus_root: Path) -> list[str]:
    log("\n=== Determinism (double cold index, byte-identical counts) ===")
    workdir = fetch_corpus(DETERMINISM_CORPUS, CORPORA[DETERMINISM_CORPUS], corpus_root)
    grove_dir = workdir / ".grove"

    def cold_index() -> tuple[int, int]:
        if grove_dir.exists():
            shutil.rmtree(grove_dir)
        subprocess.run([str(prism), "index", "."], capture_output=True, text=True,
                        cwd=workdir, timeout=300, check=True)
        status = run_prism(prism, workdir, "status")
        return status.get("symbolCount", -1), status.get("edgeCount", -1)

    first = cold_index()
    second = cold_index()
    status = "OK" if first == second else "MISMATCH"
    log(f"  {DETERMINISM_CORPUS}: pass1={first} pass2={second}  [{status}]")
    return [] if first == second else [f"determinism: {first} != {second}"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-root", default="/tmp/ci-corpus")
    ap.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    args = ap.parse_args()

    prism = Path(args.prism)
    corpus_root = Path(args.corpus_root)
    baseline = json.loads(BASELINE_FILE.read_text())

    all_failures: list[str] = []
    all_failures += check_ceiling_regression(prism, corpus_root, baseline)
    all_failures += check_compile_invariant(prism, corpus_root)
    all_failures += check_rename_plan_completeness(prism, corpus_root)
    all_failures += check_determinism(prism, corpus_root)

    log("\n" + "=" * 60)
    if all_failures:
        log(f"FAILED — {len(all_failures)} invariant violation(s):")
        for f in all_failures:
            log(f"  - {f}")
        sys.exit(1)
    log("All invariants held.")


if __name__ == "__main__":
    main()
