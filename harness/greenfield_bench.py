"""Greenfield benchmark: does Prism help an agent BUILD a new app, not just
navigate an existing one?

Two-phase task per trial:
  Phase 1 (scaffold): the agent builds a small multi-file app from scratch,
    creating its OWN call graph (functions defined in one file, called from
    others) — no pre-existing fan-out for a graph tool to exploit.
  Phase 2 (self-refactor): AFTER inspecting what the agent built, the
    harness picks a real function the agent itself created with >=2 distinct
    caller files, and asks the agent (same session, --continue) to change
    its signature and update every call site.

This converts the open-ended "build an app" question into a scoreable
change-impact question — except the graph being tested is entirely
self-authored, mid-session, with no human reviewer. That is the actual
greenfield claim: does the agent forget its OWN call sites, and does having
Prism in the loop (gate + prepare) prevent it.

Scoring is independent of Prism: a plain arg-count comparison at each call
site of the target function, before vs after phase 2 (same technique as
verify's own base-contract param matching, applied here as a THIRD-PARTY
grader — it does not run through the engine being measured).

Two arms, same model: MASON (Prism: prepare + completeness gate) vs
MASON_NO_ENGINE=1 (pure grep/read/write agent, no graph, no gate).

Usage: python greenfield_bench.py --model ollama:qwen3-coder:30b --trials 3 --arms prism,noprism
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

MASON = str(Path.home() / "bin" / "mason")
OUT = Path(__file__).parent / "runs" / "greenfield"
OUT.mkdir(parents=True, exist_ok=True)

SCAFFOLD_SMALL = """Build a small Python library-management app in this directory, split into layers, each its own file:

1. models.py — a Book class (title, isbn, available) and a Member class (member_id, name).
2. repository.py — plain functions using in-memory lists (no database) to add/find books and members.
3. service.py — business logic: functions to check out a book to a member and to return a book. These MUST call the repository.py functions rather than reimplementing the logic.
4. cli.py — a simple command-line entry point (a main() function is enough, no need for real argv parsing) that calls the service.py functions to demonstrate checking out and returning a book.
5. test_app.py — a few tests (plain assert statements or unittest, your choice) that exercise checkout and return THROUGH the service layer functions (not by calling repository.py directly).

Keep function signatures consistent between where they're defined and where they're called. When done, run the tests with `python -m pytest test_app.py` or `python test_app.py` and confirm they pass. Report which functions you defined and where each is called from."""

# MEDIUM/LARGE deliberately MANDATE a shared function used from a target
# number of distinct files — fan-out becomes a controlled independent
# variable instead of an emergent accident, so the tipping-point sweep
# measures fan-out size, not "which function the model happened to reuse."

SCAFFOLD_MEDIUM = """Build a Python library-management app in this directory, split into layers, each its own file:

1. models.py — Book (title, isbn, available), Member (member_id, name), Loan (book_isbn, member_id, due_date).
2. repository.py — in-memory-list functions to add/find books, members, and loans.
3. events.py — define ONE function `log_event(event_type: str, member_id: str, details: str)` that appends a record to an in-memory log list (or prints it — your choice of implementation, but it must be a single real function, not a no-op).
4. service.py — functions: checkout_book, return_book, renew_loan. Each of these MUST call repository.py for data access AND MUST call events.log_event(...) to record what happened.
5. fines.py — a function calculate_fine(loan) for overdue loans, and apply_fine(member_id, amount) which MUST also call events.log_event(...).
6. notifications.py — a function notify_member(member_id, message) that MUST also call events.log_event(...) when a notification is sent, and MUST itself be called from service.py's checkout_book and return_book (to notify the member) and from fines.py's apply_fine (to notify about the fine).
7. cli.py — a command-line entry point (main() is enough) that calls the service.py and fines.py functions to demonstrate checkout, return, renew, and an overdue fine scenario.
8. test_app.py — tests exercising checkout, return, renew, and the fine flow THROUGH the service/fines layer (not by calling repository.py directly).

The `log_event` function must end up called from checkout_book, return_book, renew_loan, apply_fine, and notify_member — that is a real requirement, not optional. Keep signatures consistent everywhere a function is called. When done, run the tests and confirm they pass. Report every function you defined and every file that calls log_event and notify_member."""

SCAFFOLD_LARGE = """Build a Python library-management system in this directory, split into layers, each its own file:

1. models.py — Book, Member, Loan, Fine (member_id, amount, paid) — plain classes.
2. repository.py — in-memory-list functions to add/find/update books, members, loans, and fines.
3. audit.py — define ONE function `log_event(event_type: str, member_id: str, details: str)` (in-memory log list or print).
4. auth.py — define ONE function `validate_member(member_id: str) -> bool` that checks the member exists and has no unpaid fines over a limit. This function MUST be called as the FIRST thing inside every one of: checkout_book, return_book, renew_loan, register_member, pay_fine (i.e. 5 distinct call sites across the service files below) — it is a required guard, not optional.
5. service.py — checkout_book, return_book, renew_loan, register_member. Each MUST call repository.py for data, MUST call auth.validate_member(...) as the guard, and MUST call audit.log_event(...) to record the action.
6. fines.py — calculate_fine(loan), pay_fine(member_id, amount), apply_fine(member_id, amount). pay_fine MUST call auth.validate_member(...) and audit.log_event(...); apply_fine MUST call audit.log_event(...) and notifications.notify_member(...).
7. notifications.py — notify_member(member_id, message), called from service.py's checkout_book and return_book, and from fines.py's apply_fine — MUST itself call audit.log_event(...) when it sends a notification.
8. reports.py — a function overdue_report() that scans loans via repository.py and, for each overdue loan, calls fines.calculate_fine(...) and audit.log_event(...).
9. cli.py — a command-line entry point (main() is enough) demonstrating register_member, checkout, return, renew, an overdue fine, paying a fine, and running overdue_report.
10. test_app.py — tests exercising the full flow (register, checkout, return, fine, pay) THROUGH the service/fines layer.

Two functions have MANDATORY multi-file fan-out and this is a real requirement: `auth.validate_member` must be called from checkout_book, return_book, renew_loan, register_member, and pay_fine (5 call sites across service.py and fines.py). `audit.log_event` must be called from checkout_book, return_book, renew_loan, register_member, pay_fine, apply_fine, notify_member, and overdue_report (8 call sites across 4+ files). Keep signatures consistent everywhere. When done, run the tests and confirm they pass. Report every function you defined and every file that calls validate_member and log_event."""

SCAFFOLD_TINY = """Build a tiny Python app in this directory, 4 files:

1. models.py — a Book class (title, isbn, available).
2. log.py — define ONE function `log_action(action: str, detail: str)` that appends to an in-memory list (or prints). It must be a single real function, not a no-op.
3. service.py — checkout_book(book, member_name) and return_book(book) functions that operate on a Book (in-memory, no repository layer — just mutate the Book object directly). BOTH functions MUST call log.log_action(...) to record what happened.
4. cli.py — a small main() that calls checkout_book and return_book to demonstrate the flow, and ALSO calls log.log_action(...) directly once (e.g. to log that the app started).
5. test_app.py — a couple of tests exercising checkout_book and return_book.

The `log_action` function must end up called from service.py (twice) and cli.py (at least once) — a real requirement. Keep signatures consistent. When done, run the tests and confirm they pass. Report which functions you defined and where each is called from, especially log_action."""

SCAFFOLD_XLARGE = """Build a Python library-management system in this directory, split into layers, each its own file:

1. models.py — Book, Member, Loan, Fine, Reservation (member_id, book_isbn) — plain classes.
2. repository.py — in-memory-list functions to add/find/update books, members, loans, fines, and reservations.
3. audit.py — define ONE function `log_event(event_type: str, member_id: str, details: str)` (in-memory log list or print). This function MUST be called from checkout_book, return_book, renew_loan, register_member, pay_fine, apply_fine, notify_member, overdue_report, cancel_reservation, AND fulfill_reservation — 10 distinct call sites across at least 6 files. This is a real requirement.
4. auth.py — define ONE function `validate_member(member_id: str) -> bool`, the guard called as the FIRST thing inside checkout_book, return_book, renew_loan, register_member, pay_fine, and reserve_book — 6 distinct call sites across service.py, fines.py, and reservations.py.
5. service.py — checkout_book, return_book, renew_loan, register_member. Each calls repository.py, auth.validate_member(...), and audit.log_event(...).
6. fines.py — calculate_fine(loan), pay_fine(member_id, amount), apply_fine(member_id, amount).
7. notifications.py — notify_member(member_id, message), called from service.py's checkout_book/return_book, fines.py's apply_fine, and reservations.py's fulfill_reservation.
8. reservations.py — reserve_book(member_id, isbn), cancel_reservation(reservation_id), fulfill_reservation(reservation_id) — each calls repository.py, and reserve_book calls auth.validate_member(...).
9. reports.py — overdue_report() and reservation_report(), each scanning via repository.py.
10. cli.py — a command-line entry point (main() is enough) demonstrating the full flow including a reservation.
11. test_app.py — tests exercising the full flow through the service/fines/reservations layers.

Two functions have MANDATORY multi-file fan-out (a real requirement, not optional): `audit.log_event` must be called from the 10 sites listed above across 6+ files; `auth.validate_member` must be called from the 6 sites listed above across 3 files. Keep signatures consistent everywhere. When done, run the tests and confirm they pass. Report every function you defined and every file that calls validate_member and log_event."""

TIERS = {"tiny": SCAFFOLD_TINY, "small": SCAFFOLD_SMALL, "medium": SCAFFOLD_MEDIUM,
         "large": SCAFFOLD_LARGE, "xlarge": SCAFFOLD_XLARGE}
TIER_MANDATED_FILES = {"tiny": 3, "small": 5, "medium": 8, "large": 10, "xlarge": 11}

REFACTOR_TMPL = """The `{fn}` function in {defn_file} needs a new REQUIRED parameter: `request_id: str`, inserted as the FIRST parameter (for logging/tracing — every call must now pass a request id string, e.g. "req-1").

Update:
- the function's definition in {defn_file}
- EVERY call site anywhere in this codebase that calls `{fn}(...)` — including production code and tests

Do not leave any caller on the old signature. When done, run the tests again and confirm they still pass."""

ARG_COUNT_RE = None  # computed per-call, see arg_count()


def sh(*a, cwd=None, timeout=None, env=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def run_mason(workdir: Path, prompt: str, model: str, no_engine: bool, cont: bool, max_turns=40, timeout=1800):
    import os
    env = os.environ.copy()
    if no_engine:
        env["MASON_NO_ENGINE"] = "1"
    args = [MASON, "--yes", "--no-tui", "--json", "--model", model, "--max-turns", str(max_turns), "--dir", str(workdir)]
    if cont:
        args.append("--continue")
    args.append(prompt)
    t0 = time.monotonic()
    r = sh(*args, timeout=timeout, env=env)
    wall = time.monotonic() - t0
    try:
        j = json.loads(r.stdout)
    except Exception:
        j = {"ok": False, "error": (r.stdout + r.stderr)[-500:]}
    j["wall_s"] = round(wall, 1)
    return j


DEF_RE = re.compile(r"^\s*def\s+(\w+)\s*\(([^)]*)\)")


def arg_count(paramtext: str) -> int:
    paramtext = paramtext.strip()
    if not paramtext:
        return 0
    # A trailing top-level comma (near-universal in multi-line/black-style
    # calls: `f(\n    a,\n    b,\n)`) must not count as a 4th argument —
    # measured: it inflated every multi-line call's count by one.
    if paramtext.endswith(","):
        paramtext = paramtext[:-1].rstrip()
    if not paramtext:
        return 0
    depth, n = 0, 1
    for c in paramtext:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            n += 1
    return n


def scan_defs(workdir: Path):
    """name -> [(file, paramcount)] for every top-level `def name(...)` in *.py."""
    out = {}
    for f in workdir.rglob("*.py"):
        rel = str(f.relative_to(workdir))
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        for ln in text.splitlines():
            m = DEF_RE.match(ln)
            if m:
                out.setdefault(m.group(1), []).append((rel, arg_count(m.group(2))))
    return out


# (?<!\w) only, NOT (?<![\w.]) — a qualified call (`service.checkout_book(`)
# is a REAL call site and must count; excluding '.' from the lookbehind was
# rejecting every qualified call (measured: silently zeroed all call sites
# for Sonnet's code, which used `import x; x.func()` throughout, vs the
# local model's more frequent bare `from x import func; func()` style that
# happened to survive the bug). Still correctly rejects `my_checkout_book(`
# (preceded by a word char) as a different identifier.
CALL_RE_TMPL = r"(?<!\w){name}\s*\("


def _extract_call_args(text: str, open_paren_idx: int) -> str:
    """Walk from an opening '(' to its matching ')' ACROSS THE WHOLE TEXT (not
    one line) and return the raw argument text. A call spanning multiple
    lines (very common once a refactor adds an argument and the formatter
    wraps it) must still resolve correctly — a walker bounded to one line
    silently truncates at end-of-line with depth>0, and arg_count() on the
    truncated fragment previously returned 0 for EVERY such call, both
    before and after a refactor, which is worse than a missed data point:
    0==0 reads as 'unchanged' and produces a FALSE forgotten verdict on a
    site that was actually fixed correctly (measured: reports.py's
    log_event call, reformatted to 4 lines by black-style wrapping when the
    new request_id argument was added, scored [0] before and after and was
    wrongly flagged forgotten in 3/4 real Sonnet large-tier trials)."""
    depth = 0
    for i in range(open_paren_idx, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren_idx + 1:i]
    return text[open_paren_idx + 1:]  # unterminated — best effort


def scan_call_sites(workdir: Path, name: str):
    """file -> [arg_count at each call of name(...)], excluding the `def
    name(` declaration line. Whole-file scan — a call's parens may span
    multiple lines."""
    call_re = re.compile(CALL_RE_TMPL.format(name=re.escape(name)))
    out = {}
    for f in workdir.rglob("*.py"):
        rel = str(f.relative_to(workdir))
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        # Precompute which line each character index falls on, to exclude
        # matches that land on a `def name(` declaration line.
        decl_lines = {i for i, ln in enumerate(text.splitlines())
                      if DEF_RE.match(ln) and DEF_RE.match(ln).group(1) == name}
        line_starts = [0]
        for ln in text.splitlines(keepends=True):
            line_starts.append(line_starts[-1] + len(ln))
        import bisect
        for m in call_re.finditer(text):
            line_no = bisect.bisect_right(line_starts, m.start()) - 1
            if line_no in decl_lines:
                continue
            open_idx = m.end() - 1  # at the '('
            args_text = _extract_call_args(text, open_idx)
            out.setdefault(rel, []).append(arg_count(args_text))
    return out


def _selftest_scan_call_sites():
    """Guard against silently reintroducing a call-site scanning bug —
    every case here was a REAL false result measured in this harness."""
    import tempfile as _tf
    with _tf.TemporaryDirectory() as d:
        wd = Path(d)
        (wd / "a.py").write_text(
            "import audit\n"
            "\n"
            "def f():\n"
            "    audit.log_event(\n"
            "        \"a\",\n"
            "        \"b\",\n"
            "        \"c\",\n"
            "        \"d\",\n"
            "    )\n"
            "    audit.log_event(\"x\", \"y\")\n"
            "    my_log_event(\"nope\")\n"
        )
        got = scan_call_sites(wd, "log_event")
        assert got.get("a.py") == [4, 2], f"multi-line + qualified-call scan broken: {got}"
    print("scan_call_sites self-test: PASS", file=sys.stderr)


_selftest_scan_call_sites()




def score_phase2(workdir: Path, target: str, before_callers: dict):
    after = scan_call_sites(workdir, target)
    fixed_files, forgotten_files = [], []
    for f, before_counts in before_callers.items():
        base = min(before_counts)  # the pre-refactor arity
        after_counts = after.get(f, [])
        # "fixed" if every call in this file that still resembles the old
        # call has grown by exactly one arg (the new request_id); a file
        # with NO calls left is also fine (caller removed/rewritten).
        if not after_counts:
            fixed_files.append(f)
            continue
        if all(ac > base for ac in after_counts):
            fixed_files.append(f)
        elif any(ac == base for ac in after_counts):
            forgotten_files.append(f)
        else:
            fixed_files.append(f)
    return fixed_files, forgotten_files


PREFERRED_TARGETS = {"log_event", "validate_member", "notify_member"}


def pick_target_preferred(workdir: Path):
    """Prefer a MANDATED high-fan-out function (log_event/validate_member) if
    the scaffold produced one with >=2 caller files; else fall back to
    whichever function has the most sites (small tier, no mandated fn)."""
    defs = scan_defs(workdir)
    candidates = []
    for name, decls in defs.items():
        if len(decls) != 1:
            continue
        defn_file, _ = decls[0]
        calls = scan_call_sites(workdir, name)
        callers = {f: acs for f, acs in calls.items() if f != defn_file}
        if len(callers) < 2:
            continue
        n_sites = sum(len(v) for v in callers.values())
        candidates.append((name, defn_file, callers, n_sites))
    if not candidates:
        return None
    preferred = [c for c in candidates if c[0] in PREFERRED_TARGETS]
    pool = preferred if preferred else candidates
    return max(pool, key=lambda c: c[3])


def run_trial(model: str, arm: str, tier: str, trial: int, max_turns: int):
    no_engine = arm == "noprism"
    tag = f"{model.replace(':','_').replace('/','_')}.{tier}.{arm}.t{trial}"
    outfile = OUT / f"{tag}.json"
    if outfile.exists():
        print(f"cached {outfile.name}", flush=True); return json.loads(outfile.read_text())

    workdir = Path(tempfile.mkdtemp(prefix=f"greenfield-{tag}-"))
    sh("git", "init", "-q", cwd=workdir)
    sh("git", "-C", str(workdir), "config", "user.email", "t@t")
    sh("git", "-C", str(workdir), "config", "user.name", "t")

    rec = {"model": model, "arm": arm, "tier": tier, "trial": trial, "workdir": str(workdir)}
    p1 = run_mason(workdir, TIERS[tier], model, no_engine, cont=False, max_turns=max_turns)
    rec["phase1"] = {"ok": p1.get("ok"), "wall_s": p1.get("wall_s"),
                      "tokens_in": (p1.get("usage") or {}).get("inputTokens"),
                      "tokens_out": (p1.get("usage") or {}).get("outputTokens")}
    if not p1.get("ok"):
        rec["error"] = "phase1 failed: " + str(p1.get("error"))[:300]
        outfile.write_text(json.dumps(rec, indent=1))
        print(f"{tag}: PHASE1 FAILED {rec['error']}", flush=True)
        return rec

    target = pick_target_preferred(workdir)
    if target is None:
        rec["error"] = "no usable target found after phase 1 (no function with >=2 caller files)"
        outfile.write_text(json.dumps(rec, indent=1))
        print(f"{tag}: NO TARGET — {rec['error']}", flush=True)
        return rec
    name, defn_file, before_callers, n_sites = target
    rec["target"] = {"fn": name, "definedIn": defn_file, "callerFiles": list(before_callers.keys()), "totalSites": n_sites}

    prompt2 = REFACTOR_TMPL.format(fn=name, defn_file=defn_file)
    p2 = run_mason(workdir, prompt2, model, no_engine, cont=True, max_turns=max_turns)
    rec["phase2"] = {"ok": p2.get("ok"), "wall_s": p2.get("wall_s"),
                      "tokens_in": (p2.get("usage") or {}).get("inputTokens"),
                      "tokens_out": (p2.get("usage") or {}).get("outputTokens")}

    fixed, forgotten = score_phase2(workdir, name, before_callers)
    rec["fixedFiles"] = fixed
    rec["forgottenFiles"] = forgotten
    rec["completeness"] = round(len(fixed) / max(1, len(fixed) + len(forgotten)), 3)
    rec["totalTokens"] = (rec["phase1"]["tokens_in"] or 0) + (rec["phase1"]["tokens_out"] or 0) + \
                          (rec["phase2"]["tokens_in"] or 0) + (rec["phase2"]["tokens_out"] or 0)
    rec["totalWallS"] = round((rec["phase1"]["wall_s"] or 0) + (rec["phase2"]["wall_s"] or 0), 1)

    # Measured codebase size (the real x-axis) — captured before cleanup.
    py_files = [f for f in workdir.rglob("*.py") if ".git" not in f.parts]
    rec["codebaseFiles"] = len(py_files)
    rec["codebaseLOC"] = sum(len(f.read_text(errors="replace").splitlines()) for f in py_files)

    outfile.write_text(json.dumps(rec, indent=1))
    print(f"{tag}: target={name} sites={n_sites} completeness={rec['completeness']} "
          f"forgotten={forgotten} tokens={rec['totalTokens']} wall={rec['totalWallS']}s", flush=True)
    shutil.rmtree(workdir, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ollama:qwen3-coder:30b")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--arms", default="prism,noprism")
    ap.add_argument("--tiers", default="small,medium,large")
    ap.add_argument("--max-turns", type=int, default=40)
    a = ap.parse_args()
    for tier in a.tiers.split(","):
        for arm in a.arms.split(","):
            for t in range(1, a.trials + 1):
                run_trial(a.model, arm, tier, t, a.max_turns)
    print("done", flush=True)


if __name__ == "__main__":
    main()
