#!/usr/bin/env python3
"""Fail-fast A/B gate: baseline prism binary vs candidate, agentic bed.

The release gate for BEHAVIOR changes (result shapes, sizes, routing,
steering, schemas): unit suites and ci_invariants catch engine regressions
free, but only a paid agentic run catches "the agent stopped getting usable
results". This gate is built to fail FAST and cheap:

  - tasks run cheapest-first, one paired cell at a time
  - HARD-FAIL immediately (nonzero exit) when the candidate errors where the
    baseline succeeded, or its recall drops >0.15 on any task
  - aggregate FAIL when mean recall drops >0.05 over the bed
  - cache identity includes task, corpus pin, model, CLI, binary, steering,
    tool config, and harness/scorer source; all attempts are retained

Honest scope: this small, noisy Haiku bed is a regression smoke test.
Its retry policy is an operational rule, not a statistical significance
test. A PASS means "not broken by this gate", never "proven better" or
"cheaper than native tools". Quality still uses the final candidate attempt;
the preserved attempts and inclusive costs do not remove that selection bias.

Usage:
  python ab_gate.py --baseline ~/bin/prism --candidate ../prism/bin/prism \
      [--model haiku] [--limit N] [--out runs/ab-gate]
Exit 0 = PASS, 1 = FAIL, 2 = harness error.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_agentic_mcp as bed  # noqa: E402
from schema import Task  # noqa: E402
from score import SCORER_VERSION  # noqa: E402
import usage_account  # noqa: E402

# Cheapest-first by measured wall time (2026-08-28 bed run).
TASKS = [
    "tasks/jackson-jsonnode-get.json",
    "tasks/jackson-settable-set.json",
    "tasks/typeorm-driver-escape.json",
    "tasks/django-quotename.json",
    "tasks/jackson-writetypeprefix.json",
    "tasks/guava-forwarding-delegate.json",
    "tasks/jackson-serialize.json",
    "tasks/grafana-checkhealth-impact.json",
    "tasks/grafana-querydata-impact.json",
]

HARD_RECALL_DROP = 0.15   # any single task
MEAN_RECALL_DROP = 0.05   # over the whole bed
# Billed cost, candidate/baseline, as AGGREGATE paired cost (sum over the
# same pairs), not a mean of per-pair ratios — a mean of ratios lets one
# cheap-baseline pair dominate. Until 2026-09-05 the gate had no cost
# criterion at all — a candidate costing 2x with flat recall PASSED. 1.25
# is the "big break" threshold this bed's ~50%/cell noise can detect; this
# gate is a smoke test ("not broken"). --require-cheaper compares against
# released Prism, NOT a native-tools baseline or a product superiority test.
COST_RATIO_MAX = 1.25


def binary_sha(path: str) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:8]


def arm_for(binary: str, tag: str) -> str:
    """Register an ab_agentic_mcp arm bound to a specific prism binary."""
    cfg = bed.CFG_DIR / f"gate-{tag}.json"
    cfg.parent.mkdir(exist_ok=True)
    # No alwaysLoad: the shipped install (prism init) leaves the tools
    # deferred, so the gate must pay the same ToolSearch discovery turn a
    # real session pays (proposal §8.1).
    cfg.write_text(json.dumps({"mcpServers": {"prism": {
        "type": "stdio", "command": str(Path(binary).resolve()),
        "args": ["mcp"]}}}))
    name = f"gate-{tag}"
    bed.ARMS[name] = dict(bed.ARMS["prism"], mcp=str(cfg))
    return name


def is_degenerate(rec: dict) -> bool:
    """True when the CLI returned cleanly but did no real work — a transient
    rate-limit/quota response returns valid JSON with turns=1, cost=0,
    tokens=0 rather than raising, so it never hits run_arm's except path and
    was silently averaged in as a zero recall delta (observed 2026-08-29:
    3/9 cells degenerate on BOTH arms in one run, masked by the mean-delta
    math into an apparent clean PASS). Not cached — degenerate cells must
    re-run, never be treated as a real result."""
    return (rec.get("turns") == 1 and (rec.get("cost_usd") or 0) == 0
            and (rec.get("tokens_in") or 0) == 0 and "error" not in rec)


def cell_manifest(arm: str, task: Task, corpus: Path, model: str, binary: str) -> dict:
    commit = subprocess.run(["git", "-C", str(corpus), "rev-parse", "--verify", f"{task.pin}^{{commit}}"],
                            check=True, capture_output=True, text=True).stdout.strip()
    spec = bed.ARMS[arm]
    source = Path(__file__).resolve().parent
    return {
        "manifest_version": 1, "task": asdict(task), "corpus_commit": commit,
        "model": model, "cli_version": usage_account.claude_version(),
        "binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
        "scorer_version": SCORER_VERSION, "usage_version": usage_account.USAGE_VERSION,
        "guidance": spec["guidance"], "contract": bed.CONTRACT,
        "allowed_tools": spec["allowed"],
        "mcp": json.loads(Path(spec["mcp"]).read_text()) if spec["mcp"] else None,
        "source_sha256": {name: hashlib.sha256((source/name).read_bytes()).hexdigest()
                          for name in ("ab_gate.py", "ab_agentic_mcp.py", "schema.py", "score.py", "usage_account.py")},
    }


def record_attempt(path: Path, rec: dict, previous: list[dict]) -> dict:
    """Write immutable raw evidence before replacing the canonical pointer."""
    attempt = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.attempt.json")
    with attempt.open("x") as f:
        json.dump(rec, f, indent=2, allow_nan=False)
    rec["attempts"] = previous + [{"record": attempt.name, **{
        k: rec.get(k) for k in ("invocation_id", "cost_usd", "tokens_request", "tokens_out", "error", "measurement_error")}}]
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x") as f:
        json.dump(rec, f, indent=2, allow_nan=False)
    os.replace(temporary, path)
    return rec


def attempt_total(rec: dict, field: str, invocation_id: str | None = None) -> float | int | None:
    """Sum stored attempts for this exact manifest across gate invocations."""
    attempts = rec.get("attempts", [rec])
    if invocation_id is not None:
        attempts = [a for a in attempts if a.get("invocation_id") == invocation_id]
        if not attempts:
            return 0
    values = [a.get(field) for a in attempts]
    if not values or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        return None
    return sum(values)


def measurement_total(rec: dict, field: str) -> float | int | None:
    """Cost of the selected measurement's invocation, not its manifest history."""
    invocation_id = rec.get("invocation_id")
    if not invocation_id:
        return None
    attempts = rec.get("attempts", [rec])
    if not any(a.get("invocation_id") == invocation_id for a in attempts):
        return None
    return attempt_total(rec, field, invocation_id)


class RunAccounting:
    """Persist newly incurred spend after each attempt, including fail-fast exits."""

    def __init__(self, out: Path, settings: dict):
        self.id = uuid.uuid4().hex
        directory = out / "invocations"
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{self.id}.json"
        self.attempts = {}
        self.cells = {}
        self.record = {"invocation_id": self.id, "started_at": time.time(),
                       "settings": settings, "status": "running"}
        self.save()

    def capture(self, rec: dict):
        key = f"{rec.get('task')}:{rec.get('arm')}"
        for attempt in rec.get("attempts", []):
            if attempt.get("invocation_id") == self.id:
                self.attempts[attempt["record"]] = attempt
        self.cells[key] = {
            "manifest": rec.get("manifest"),
            "measurement_invocation_id": rec.get("invocation_id"),
            "reused": rec.get("invocation_id") != self.id,
            "new_cost_usd": attempt_total(rec, "cost_usd", self.id),
            "measurement_cost_usd": measurement_total(rec, "cost_usd"),
        }
        self.save()

    def totals(self):
        if not self.attempts:
            return {"cost_usd": 0, "tokens_request": 0, "tokens_out": 0}
        return {field: attempt_total({"attempts": list(self.attempts.values())}, field)
                for field in ("cost_usd", "tokens_request", "tokens_out")}

    def save(self):
        self.record.update(attempts=list(self.attempts.values()), cells=self.cells,
                           new_spend=self.totals())
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.record, indent=2, allow_nan=False))
        os.replace(temporary, self.path)

    def finish(self, code: int):
        self.record.update(status={0: "pass", 1: "fail", 2: "harness_error"}[code],
                           exit_code=code, finished_at=time.time())
        self.save()
        totals = self.totals()
        cost = totals["cost_usd"]
        formatted = f"${cost:.4f}" if cost is not None else "unknown"
        print(f"This invocation: new spend {formatted}; request tokens "
              f"{totals['tokens_request']}; output tokens {totals['tokens_out']}; "
              f"new attempts {len(self.attempts)}. Record: {self.path}")
        return code


def run_cell(arm: str, task: Task, corpus: Path, model: str,
             out: Path, binary: str, sha: str, *, fresh: bool = False,
             accounting: RunAccounting | None = None) -> dict:
    invocation_id = accounting.id if accounting else uuid.uuid4().hex
    manifest = cell_manifest(arm, task, corpus, model, binary)
    identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
    f = out / f"{task.id}.{identity}.json"
    previous = []
    if f.exists():
        cached = json.loads(f.read_text())
        previous = cached.get("attempts", [])
        if (not fresh and not is_degenerate(cached) and not cached.get("measurement_error")
                and cached.get("manifest") == manifest and cached.get("invocation_id")):
            if accounting:
                accounting.capture(cached)
            return cached
    # A fresh snapshot per attempt: never checkout/index the shared corpus,
    # and never expose the gold commit through its object store.
    for attempt in range(2):
        with tempfile.TemporaryDirectory(prefix="prism-gate-") as directory:
            parent = Path(directory)
            snapshot = parent / "repo"
            snapshot.mkdir()
            archive = parent / "source.tar"
            subprocess.run(["git", "-C", str(corpus), "archive", "-o", str(archive), manifest["corpus_commit"]],
                           check=True, capture_output=True)
            subprocess.run(["tar", "-xf", str(archive), "-C", str(snapshot)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(snapshot), "init", "--quiet"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(snapshot), "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(snapshot), "-c", "user.name=Prism gate", "-c", "user.email=gate@localhost",
                            "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "base"],
                           check=True, capture_output=True)
            subprocess.run([binary, "index", str(snapshot)], check=True, capture_output=True, timeout=900)
            failure = None
            try:
                rec = bed.run_arm(arm, task, snapshot, model)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                failure = exc
                rec = {"error": str(exc), "measurement_error": "agent ended without aggregate usage"}
            rec.update(task=task.id, arm=arm, model=model, binary_sha=sha, manifest=manifest,
                       invocation_id=invocation_id,
                       corpus_snapshot=str(snapshot))
            record_attempt(f, rec, previous)
            if accounting:
                accounting.capture(rec)
            previous = rec["attempts"]
            if failure:
                raise failure
        if not is_degenerate(rec) or attempt == 1:
            break
        print("  degenerate cell (turns=1, cost=$0) - one fresh retry")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--limit", type=int, default=len(TASKS))
    ap.add_argument("--out", default="runs/ab-gate")
    ap.add_argument("--fresh", action="store_true", help="Measure both arms anew instead of reusing cached cells")
    ap.add_argument("--require-cheaper", action="store_true",
                    help="FAIL unless the candidate's aggregate billed cost is below the baseline's")
    args = ap.parse_args()
    if not 1 <= args.limit <= len(TASKS):
        ap.error(f"--limit must be between 1 and {len(TASKS)}")

    out = Path(args.out)
    print("Accounting: this invocation's new spend includes its retries; cached cells "
          "are reused at $0 new spend. Efficiency comparisons use each selected "
          "measurement's invocation, never lifetime manifest totals.")
    out.mkdir(parents=True, exist_ok=True)
    accounting = RunAccounting(out, vars(args))
    finish = accounting.finish
    b_sha, c_sha = binary_sha(args.baseline), binary_sha(args.candidate)
    if b_sha == c_sha:
        print(f"note: baseline == candidate ({b_sha}) — pipeline probe mode")
    b_arm = arm_for(args.baseline, "base")
    c_arm = arm_for(args.candidate, "cand")

    drops, pdrops, cand_tok, base_tok = [], [], 0, 0
    cand_cost = base_cost = 0.0  # summed over pairs where both cells have a cost
    unpriced = 0  # pairs excluded from the cost sum — reported, never silent
    planned = len(TASKS[: args.limit])
    for tp in TASKS[: args.limit]:
        task = Task.load(tp)
        corpus = Path(task.workdir or task.repo)
        if not corpus.exists():
            print(f"SKIP {task.id}: corpus absent")
            continue
        try:
            b = run_cell(b_arm, task, corpus, args.model, out, args.baseline, b_sha,
                         fresh=args.fresh, accounting=accounting)
            c = run_cell(c_arm, task, corpus, args.model, out, args.candidate, c_sha,
                         fresh=args.fresh, accounting=accounting)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f"HARNESS ERROR: {task.id}: {exc}")
            return finish(2)
        if b.get("measurement_error") or c.get("measurement_error") or "error" in b:
            print(f"HARNESS ERROR: {task.id}: baseline failed or usage is incomplete")
            return finish(2)
        if is_degenerate(b) or is_degenerate(c):
            print(f"HARNESS ERROR: {task.id} still degenerate after retry "
                  f"(base_turns={b.get('turns')} cand_turns={c.get('turns')}) "
                  "— infra issue, not a quality signal. Fix infra and re-run.")
            return finish(2)

        def hard_fails(cand: dict) -> str:
            if "error" in cand and "error" not in b:
                return f"candidate errored where baseline succeeded ({cand['error'][:120]})"
            br_, cr_ = b.get("recall"), cand.get("recall")
            if br_ is not None and cr_ is not None and cr_ < br_ - HARD_RECALL_DROP:
                return f"recall {br_} -> {cr_} (drop > {HARD_RECALL_DROP})"
            return ""

        reason = hard_fails(c)
        if reason:
            # One fresh candidate retry is this smoke gate's operational
            # rule. It is not proof that a surviving failure is noise-free
            # or that a passing retry establishes non-inferiority.
            print(f"{task.id:30} HARD-FAIL candidate ({reason}) — one fresh retry")
            try:
                c = run_cell(c_arm, task, corpus, args.model, out, args.candidate, c_sha,
                             fresh=True, accounting=accounting)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                print(f"HARNESS ERROR: retry failed: {exc}")
                return finish(2)
            if is_degenerate(c) or c.get("measurement_error"):
                print("HARNESS ERROR: retry degenerate or usage incomplete")
                return finish(2)
            reason = hard_fails(c)
            if reason:
                print(f"HARD FAIL (reproduced): {reason} on {task.id}")
                return finish(1)
        br, cr = b.get("recall"), c.get("recall")
        bp, cp = b.get("precision"), c.get("precision")
        bc, cc = measurement_total(b, "cost_usd"), measurement_total(c, "cost_usd")
        # Request tokens = every category the model was shown (uncached +
        # cache write + cache read); the old tokens_in dropped cache writes.
        bt, ct = measurement_total(b, "tokens_request"), measurement_total(c, "tokens_request")
        if any(v is None for v in (bc, cc, bt, ct)):
            print(f"HARNESS ERROR: {task.id}: attempt cost/tokens unknown; comparison incomplete")
            return finish(2)
        for label, rec, cost, tokens in (("base", b, bc, bt), ("cand", c, cc, ct)):
            new_cost = attempt_total(rec, "cost_usd", accounting.id)
            state = "fresh" if rec.get("invocation_id") == accounting.id else "reused"
            print(f"{task.id:30} {label} R={rec.get('recall')} P={rec.get('precision')} "
                  f"{state}; new spend ${new_cost:.4f}; "
                  f"measurement request tokens={tokens}, cost=${cost:.4f} "
                  f"(measurement run {rec.get('invocation_id')})")
        if br is not None and cr is not None:
            drops.append(br - cr)
        if bp is not None and cp is not None:
            pdrops.append(bp - cp)
        if bc > 0 and cc > 0:
            base_cost += bc
            cand_cost += cc
        else:
            unpriced += 1
        cand_tok += ct or 0
        base_tok += bt or 0

    if len(drops) != planned or len(pdrops) != planned or unpriced:
        print(f"HARNESS ERROR: incomplete bed ({len(drops)}/{planned} scored, {unpriced} unpriced)")
        return finish(2)
    mean_drop = sum(drops) / len(drops)
    tok_delta = (cand_tok - base_tok) / max(base_tok, 1) * 100
    cost_ratio = cand_cost / base_cost if base_cost > 0 else None
    mean_pdrop = sum(pdrops) / len(pdrops) if pdrops else 0.0
    # completed/planned and the stop reason are part of the result: a
    # fail-fast run that stopped early must never read as a full-bed PASS.
    print(f"\ncompleted {len(drops)}/{planned} pairs; mean recall delta={-mean_drop:+.3f} "
          f"mean precision delta={-mean_pdrop:+.3f} request tokens {tok_delta:+.0f}% "
          f"selected measurement cost ${cand_cost:.2f} vs ${base_cost:.2f} = "
          + (f"{cost_ratio:.2f}x" if cost_ratio else "n/a")
          + (f" ({unpriced} pair(s) unpriced — cost comparison incomplete)" if unpriced else ""))
    if mean_drop > MEAN_RECALL_DROP:
        print(f"FAIL: mean recall drop {mean_drop:.3f} > {MEAN_RECALL_DROP}")
        return finish(1)
    if cost_ratio is not None and cost_ratio > COST_RATIO_MAX:
        print(f"FAIL: aggregate billed cost ratio {cost_ratio:.2f} > {COST_RATIO_MAX}")
        return finish(1)
    if args.require_cheaper and (cost_ratio is None or cost_ratio >= 1.0):
        print(f"FAIL: --require-cheaper and aggregate cost ratio is "
              f"{cost_ratio:.2f}x (needs < 1.00)" if cost_ratio else
              "FAIL: --require-cheaper but no paired costs recorded")
        return finish(1)
    print("PASS (not-broken; subtle effects need a full study)"
          + (" — and cheaper in aggregate" if args.require_cheaper else ""))
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
