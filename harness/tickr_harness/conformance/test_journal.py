"""t3_journal: the JSONL tick journal."""
import json
import os

import pytest

from tickr.journal import Journal
from tickr.models import Tick

T1 = Tick(symbol="AAPL", ts=1700000000, price=100.5, volume=42)
T2 = Tick(symbol="MSFT", ts=1700000060, price=99.25, volume=7)


@pytest.mark.turn("t3_journal")
def test_journal_round_trips_ticks_in_order(tmp_path):
    journal = Journal(str(tmp_path / "j.jsonl"))
    journal.record(T1)
    journal.record(T2)
    assert journal.replay() == [T1, T2]
    journal.close()


@pytest.mark.turn("t3_journal")
def test_journal_replayed_ticks_have_exact_field_values(tmp_path):
    journal = Journal(str(tmp_path / "j.jsonl"))
    tick = Tick(symbol="GOOG", ts=17, price=123.456789, volume=3)
    journal.record(tick)
    replayed = journal.replay()[0]
    assert replayed.symbol == "GOOG"
    assert replayed.ts == 17
    assert replayed.price == pytest.approx(123.456789, abs=1e-6)
    assert replayed.volume == 3
    journal.close()


@pytest.mark.turn("t3_journal")
def test_journal_creates_the_file_and_writes_one_line_per_record(tmp_path):
    path = tmp_path / "j.jsonl"
    journal = Journal(str(path))
    assert not path.exists() or path.read_text() == ""
    journal.record(T1)
    journal.record(T2)
    journal.close()
    assert path.exists()
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2


@pytest.mark.turn("t3_journal")
def test_journal_line_is_json_with_the_pinned_key_order(tmp_path):
    path = tmp_path / "j.jsonl"
    journal = Journal(str(path))
    journal.record(T1)
    journal.close()
    line = path.read_text().splitlines()[0].strip()
    assert line == json.dumps({"symbol": "AAPL", "ts": 1700000000,
                               "price": 100.5, "volume": 42})
    assert (line.index('"symbol"') < line.index('"ts"') < line.index('"price"')
            < line.index('"volume"'))


@pytest.mark.turn("t3_journal")
def test_journal_missing_file_replays_as_empty(tmp_path):
    path = tmp_path / "nope.jsonl"
    assert not os.path.exists(path)
    assert Journal(str(path)).replay() == []


@pytest.mark.turn("t3_journal")
def test_journal_skips_blank_lines(tmp_path):
    path = tmp_path / "j.jsonl"
    journal = Journal(str(path))
    journal.record(T1)
    journal.close()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n")
        fh.write("   \n")
        fh.write(json.dumps({"symbol": "MSFT", "ts": 1700000060,
                             "price": 99.25, "volume": 7}) + "\n")
        fh.write("\n")
    assert Journal(str(path)).replay() == [T1, T2]


@pytest.mark.turn("t3_journal")
def test_journal_close_is_idempotent(tmp_path):
    journal = Journal(str(tmp_path / "j.jsonl"))
    journal.record(T1)
    journal.close()
    journal.close()
    journal.close()


@pytest.mark.turn("t3_journal")
def test_journal_replay_works_after_close(tmp_path):
    journal = Journal(str(tmp_path / "j.jsonl"))
    journal.record(T1)
    journal.record(T2)
    journal.close()
    assert journal.replay() == [T1, T2]
    journal.close()
    assert journal.replay() == [T1, T2]


@pytest.mark.turn("t3_journal")
def test_journal_appends_rather_than_truncating(tmp_path):
    path = str(tmp_path / "j.jsonl")
    first = Journal(path)
    first.record(T1)
    first.close()
    second = Journal(path)
    second.record(T2)
    second.close()
    assert Journal(path).replay() == [T1, T2]


@pytest.mark.turn("t3_journal")
def test_journal_empty_file_replays_as_empty(tmp_path):
    path = tmp_path / "j.jsonl"
    path.write_text("")
    assert Journal(str(path)).replay() == []
