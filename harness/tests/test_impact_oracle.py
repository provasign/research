"""Deterministic tests for the change-impact ceiling gate."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import impact_oracle as oracle  # noqa: E402
from schema import Site, Task  # noqa: E402


def task(**changes):
    values = dict(
        id="impact-task",
        repo="/tmp/repo",
        lang="go",
        pin="abc123",
        pr="oracle:Handler.Run",
        task_type="impact",
        prompt="Change Handler.Run",
        ground_truth=[Site("pkg/handler.go", "Run")],
    )
    values.update(changes)
    return Task(**values)


def test_anchor_is_explicit_metadata_not_ground_truth():
    assert oracle.task_anchor(task()) == "Handler.Run"
    assert oracle.task_anchor(task(
        pr="oracle-spoon:com.example.JsonNode#get(int)"
    )) == "JsonNode.get(int)"
    assert oracle.task_anchor(task(
        pr="oracle-py:BaseDatabaseOperations.quote_name"
    )) == "BaseDatabaseOperations.quote_name"
    with pytest.raises(ValueError, match=r"oracle\[-kind\]"):
        oracle.task_anchor(task(pr="#123"))


def test_change_impact_deduplicates_and_preserves_fidelity(monkeypatch):
    payload = {
        "completeness": "project-local",
        "hasHeuristicRefs": True,
        "overridesExternal": True,
        "externalSupers": ["sdk.Handler"],
        "totalSites": 2,
        "family": [
            {"filePath": "pkg/handler.go", "name": "Run"},
            {"filePath": "pkg/handler.go", "name": "Run"},
        ],
        "callers": [{"filePath": "pkg/caller.go", "name": "Call"}],
    }
    encoded = json.dumps(payload)
    monkeypatch.setattr(oracle, "run_capped", lambda *a, **k: (0, encoded, ""))
    result = oracle.change_impact("prism", "/tmp", "Run")
    assert result["sites"] == [Site("pkg/handler.go", "Run"), Site("pkg/caller.go", "Call")]
    assert result["response_bytes"] == len(encoded.encode())
    assert result["has_heuristic_refs"] is True
    assert result["overrides_external"] is True
    assert result["external_supers"] == ["sdk.Handler"]
    assert result["group_counts"] == {
        "declarations": 0,
        "family": 2,
        "callers": 1,
        "declaringTypes": 0,
    }


def test_thresholds_gate_recall_precision_payload_and_completeness():
    row = {"recall": 0.98, "precision": 0.89, "response_bytes": 70_000,
           "completeness": "callers-only"}
    failures = oracle.threshold_failures(row, 0.99, 0.90, 65_536)
    assert len(failures) == 4
    assert oracle.threshold_failures(
        {"recall": 1.0, "precision": 0.95, "response_bytes": 100,
         "completeness": "project-local"},
        0.99, 0.90, 65_536,
    ) == []


def test_snapshot_uses_pinned_commit_and_checks_index(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=corpus, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=corpus, check=True)
    subprocess.run(["git", "config", "user.email", "test@localhost"], cwd=corpus, check=True)
    source = corpus / "value.txt"
    source.write_text("pinned\n")
    subprocess.run(["git", "add", "-A"], cwd=corpus, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "pin"], cwd=corpus, check=True)
    pin = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=corpus, check=True, capture_output=True, text=True
    ).stdout.strip()
    source.write_text("working tree leak\n")

    calls = []
    monkeypatch.setattr(
        oracle,
        "run_capped",
        lambda command, **kwargs: (calls.append(command) or (0, "", "")),
    )
    with oracle.corpus_snapshot(task(repo=str(corpus), pin=pin), "/bin/prism") as snapshot:
        assert (snapshot / "value.txt").read_text() == "pinned\n"
        assert (snapshot / ".git").is_dir()
    assert calls and calls[0][1] == "index"


def test_index_failure_is_a_harness_error(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=corpus, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=corpus, check=True)
    subprocess.run(["git", "config", "user.email", "test@localhost"], cwd=corpus, check=True)
    (corpus / "x").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=corpus, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "pin"], cwd=corpus, check=True)
    pin = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=corpus, check=True, capture_output=True, text=True
    ).stdout.strip()
    monkeypatch.setattr(oracle, "run_capped", lambda *a, **k: (1, "", "bad index"))
    with pytest.raises(RuntimeError, match="index failed"):
        with oracle.corpus_snapshot(task(repo=str(corpus), pin=pin), "/bin/prism"):
            pass
