#!/usr/bin/env python3
"""Deterministic change-impact regression gate.

For each task, archive the pinned corpus commit into an isolated repository,
index it, issue one ``prism change-impact`` call, and score the returned sites
with the same scorer used by the agent A/B gate. This establishes the engine
ceiling before spending money on agent trials.

The task's ``pr`` field must use ``oracle:<query>`` to record the exact query
under test. Keeping the query in task metadata prevents the ground truth from
silently choosing its own winning anchor.

This gate proves that one deterministic Prism call contains an accurate,
bounded answer. It does not prove that an agent will choose that call or stop
after it, so passing it is necessary but does not replace repeated agent runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import Answer, Site, Task  # noqa: E402
from score import SCORER_VERSION, score  # noqa: E402

COMPLETE_SCOPES = {"closed", "project-local"}


def run_capped(cmd: list[str], cwd: str | Path | None = None, timeout: int = 180):
    """Run with file capture so Prism's ledger daemon cannot hold pipes open."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        process = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=err)
        try:
            rc = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError(f"timeout after {timeout}s: {' '.join(cmd[:3])}")
        out.seek(0)
        err.seek(0)
        return (
            rc,
            out.read().decode(errors="replace"),
            err.read().decode(errors="replace"),
        )


def task_anchor(task: Task) -> str:
    """Return the explicit, reviewable one-call query stored with the task."""
    source, separator, target = task.pr.partition(":")
    if not separator or not source.startswith("oracle") or not target.strip():
        raise ValueError(
            f"{task.id}: pr must be 'oracle[-kind]:<change-impact query>', got {task.pr!r}"
        )
    target = target.strip()
    if "#" in target:
        type_name, member = target.split("#", 1)
        return f"{type_name.rsplit('.', 1)[-1]}.{member}"
    return target


def binary_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as binary:
        for block in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def corpus_snapshot(task: Task, prism: str) -> Iterator[Path]:
    """Yield a clean repository containing exactly ``task.pin``.

    ``git archive`` deliberately severs the snapshot from the corpus object
    store. Neither uncommitted corpus changes nor later commits can leak into
    the measurement.
    """
    corpus = Path(task.repo).expanduser().resolve()
    if not corpus.is_dir():
        raise RuntimeError(f"{task.id}: corpus does not exist: {corpus}")
    commit = subprocess.run(
        ["git", "-C", str(corpus), "rev-parse", "--verify", f"{task.pin}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    if commit != task.pin and not commit.startswith(task.pin):
        raise RuntimeError(f"{task.id}: pin resolved to unexpected commit {commit}")

    with tempfile.TemporaryDirectory(prefix="prism-impact-oracle-") as directory:
        parent = Path(directory)
        snapshot = parent / "repo"
        snapshot.mkdir()
        archive = parent / "source.tar"
        subprocess.run(
            ["git", "-C", str(corpus), "archive", "-o", str(archive), commit],
            check=True,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["tar", "-xf", str(archive), "-C", str(snapshot)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "-C", str(snapshot), "init", "--quiet"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(snapshot), "add", "-A"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git", "-C", str(snapshot),
                "-c", "user.name=Prism impact oracle",
                "-c", "user.email=impact-oracle@localhost",
                "-c", "core.hooksPath=/dev/null",
                "-c", "commit.gpgsign=false",
                "commit", "--quiet", "-m", "pinned corpus",
            ],
            check=True,
            capture_output=True,
        )
        rc, out, err = run_capped([prism, "index", str(snapshot)], timeout=900)
        if rc != 0:
            raise RuntimeError(f"{task.id}: index failed: {(err or out)[:500]}")
        yield snapshot


def change_impact(prism: str, cwd: str | Path, query: str) -> dict:
    """Return deduplicated sites and fidelity metadata from one call."""
    rc, out, err = run_capped(
        [prism, "change-impact", query, ".", "--format", "json"], cwd=cwd
    )
    payload = out if out.strip() else err
    response_bytes = len(payload.encode())
    if rc != 0:
        raise RuntimeError(f"change-impact failed: {(err or out)[:500]}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"change-impact returned non-JSON: {out[:300]}") from exc
    if data.get("error") and not any(
        data.get(group) for group in
        ("declarations", "family", "callers", "supers", "declaringTypes")
    ):
        raise RuntimeError(f"change-impact error: {str(data['error'])[:500]}")

    sites: list[Site] = []
    seen: set[Site] = set()
    group_counts: dict[str, int] = {}
    scored_groups = ("declarations", "family", "callers", "supers")
    for group in (*scored_groups, "declaringTypes"):
        group_counts[group] = len(data.get(group) or [])
        if group not in scored_groups:
            continue
        for symbol in data.get(group) or []:
            site = Site(
                relpath=symbol.get("filePath") or symbol.get("file") or "",
                symbol=symbol.get("name") or "",
            )
            if site.relpath and site.symbol and site not in seen:
                seen.add(site)
                sites.append(site)
    declaring_type_sites = []
    for symbol in data.get("declaringTypes") or []:
        site = Site(
            relpath=symbol.get("filePath") or symbol.get("file") or "",
            symbol=symbol.get("name") or "",
        )
        if site.relpath and site.symbol:
            declaring_type_sites.append(str(site))

    return {
        "sites": sites,
        "declaring_type_sites": declaring_type_sites,
        "response_bytes": response_bytes,
        "completeness": data.get("completeness", ""),
        "has_heuristic_refs": bool(data.get("hasHeuristicRefs")),
        "overrides_external": bool(data.get("overridesExternal")),
        "external_supers": data.get("externalSupers") or [],
        "group_counts": group_counts,
        "reported_total_sites": data.get("totalSites"),
        "warning": data.get("warning", ""),
    }


def threshold_failures(row: dict, min_recall: float, min_precision: float,
                       max_bytes: int) -> list[str]:
    failures = []
    if row["recall"] < min_recall:
        failures.append(f"recall {row['recall']:.4f} < {min_recall:.4f}")
    if row["precision"] < min_precision:
        failures.append(f"precision {row['precision']:.4f} < {min_precision:.4f}")
    if row["response_bytes"] > max_bytes:
        failures.append(f"payload {row['response_bytes']} > {max_bytes} bytes")
    if row["completeness"] not in COMPLETE_SCOPES:
        failures.append(f"completeness is {row['completeness']!r}")
    return failures


def evaluate(task: Task, prism: str, snapshot: Path, *, min_recall: float,
             min_precision: float, max_bytes: int) -> dict:
    query = task_anchor(task)
    impact = change_impact(prism, snapshot, query)
    answer = Answer(
        sites=impact.pop("sites"),
        complete=impact["completeness"] in COMPLETE_SCOPES,
        unresolved=[],
    )
    card = score(task, answer, "impact-oracle", 0)
    row = {
        "task": task.id,
        "corpus_pin": task.pin,
        "query": query,
        "scorer_version": SCORER_VERSION,
        **impact,
        **card.to_dict(),
    }
    row["failures"] = threshold_failures(row, min_recall, min_precision, max_bytes)
    row["status"] = "fail" if row["failures"] else "pass"
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    parser.add_argument("--output", default="impact-oracle.json")
    parser.add_argument("--min-recall", type=float, default=0.99)
    parser.add_argument("--min-precision", type=float, default=0.90)
    parser.add_argument("--max-bytes", type=int, default=65_536)
    parser.add_argument("tasks", nargs="+")
    args = parser.parse_args(argv)

    prism = str(Path(args.prism).expanduser().resolve())
    if not Path(prism).is_file():
        parser.error(f"Prism binary does not exist: {prism}")

    rows = []
    try:
        for task_path in args.tasks:
            task = Task.load(task_path)
            with corpus_snapshot(task, prism) as snapshot:
                row = evaluate(
                    task,
                    prism,
                    snapshot,
                    min_recall=args.min_recall,
                    min_precision=args.min_precision,
                    max_bytes=args.max_bytes,
                )
            rows.append(row)
            failures = "; ".join(row["failures"])
            suffix = f"  FAIL: {failures}" if failures else "  PASS"
            print(
                f"{task.id:30} query={row['query']!r:18} "
                f"R={row['recall']:.4f} P={row['precision']:.4f} "
                f"F1={row['f1']:.4f} bytes={row['response_bytes']:6}{suffix}",
                flush=True,
            )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 2

    artifact = {
        "schema_version": 1,
        "prism_binary": prism,
        "prism_sha256": binary_sha256(prism),
        "thresholds": {
            "min_recall": args.min_recall,
            "min_precision": args.min_precision,
            "max_bytes": args.max_bytes,
            "accepted_completeness": sorted(COMPLETE_SCOPES),
        },
        "rows": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(artifact, indent=2) + "\n")
    temporary.replace(output)
    return 1 if any(row["failures"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
