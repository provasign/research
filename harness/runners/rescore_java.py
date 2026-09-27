"""Rescore a finished run's Java cells from the saved agent diffs, with the
current java_eval (fixed surefire parser) and current task F2P/P2P lists.
Writes <results_dir>/java_rescore.json; resumable."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scoring"))
import run_e2e  # noqa: E402

HARNESS = Path(__file__).resolve().parent.parent
ARMS = {"native": "baseline", "prism": "prism_init"}


def main(results_dir: str, model: str = "sonnet"):
    rd = Path(results_dir)
    rows = json.loads((rd / "results.json").read_text())
    out_p = rd / "java_rescore.json"
    out = json.loads(out_p.read_text()) if out_p.exists() else {}
    for x in rows:
        if x["lang"] != "java":
            continue
        task = json.loads((HARNESS / "tasks/e2e" / f"{x['task']}.json").read_text())
        for arm, file_arm in ARMS.items():
            key = f"{x['task']}|{arm}"
            if key in out:
                continue
            diff = (HARNESS / "results/e2e" / f"{x['task']}.{model}.{file_arm}.diff").read_text()
            try:
                res = run_e2e._score(task, diff)
            except Exception as e:  # keep going; record the failure
                res = {"resolved": None, "error": f"{type(e).__name__}: {e}"[:300]}
            out[key] = {"old": x[arm]["resolved"], "new": res.get("resolved"), "detail": res}
            out_p.write_text(json.dumps(out, indent=1))
            print(f"{key} old={x[arm]['resolved']} new={res.get('resolved')}", flush=True)
    print("RESCORE DONE", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
