import json
import sqlite3

import pytest

from rillwatch.engine import Engine
from rillwatch.framing import Frame, Framer
from rillwatch.simulator import Simulator
from rillwatch.storage import Store


def test_every_fragment_boundary():
    raw = '{"text":"آب"}\n{}\n'.encode()
    for boundary in range(len(raw) + 1):
        f = Framer()
        frames = f.feed(raw[:boundary]) + f.feed(raw[boundary:])
        assert [r.raw for r in frames] == raw.rstrip(b"\n").split(b"\n")
        assert not f.finish()


def test_oversize_resynchronizes_and_stays_bounded():
    f = Framer(8)
    assert f.feed(b"x" * 100)[0].error == "frame_too_large"
    assert len(f.buffer) <= 8
    assert not f.feed(b"x" * 100)
    assert [r.raw for r in f.feed(b"\n{}\n")] == [b"{}"]


def test_disconnect_quarantines_partial():
    f = Framer()
    f.feed(b'{"a":')
    assert f.finish()[0].error == "incomplete_frame"
    assert f.feed(b"{}\n")[0].raw == b"{}"


def test_restart_and_duplicate_idempotence(tmp_path):
    path = tmp_path / "events.sqlite"
    s = Store(path)
    raw = Simulator(corruption=0).line(0, 0).strip()
    assert s.ingest("a", "epoch", 0, 0, raw)[0]
    assert not s.ingest("a", "epoch", 0, 0, raw)[0]
    s.close()
    s = Store(path)
    assert s.counts() == {"clean": 1}
    assert not s.ingest("a", "epoch", 0, 0, raw)[0]
    assert s.ingest("a", "next_epoch", 0, 1, raw)[0]
    s.close()


def test_transaction_rolls_back_on_failure(tmp_path):
    s = Store(tmp_path / "events.sqlite")
    s.db.execute(
        "CREATE TRIGGER fail BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'disk-like failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="disk-like failure"):
        s.ingest("a", "e", 0, 0, b"{}")
    assert s.counts() == {}
    s.close()


def test_idle_timers_and_partial_window(tmp_path):
    s = Store(tmp_path / "events.sqlite")
    engine = Engine(s, run_id="test")
    engine.tick(61)
    engine.finish(65)
    reports = [json.loads(r[0]) for r in s.db.execute("SELECT payload FROM reports")]
    assert [r["window_seconds"] for r in reports] == [20, 20, 20, 5]
    assert all(r["window_total"] == 0 for r in reports)
    assert reports[-1]["partial"]
    s.close()


def test_record_at_boundary_belongs_to_next_window(tmp_path):
    s = Store(tmp_path / "events.sqlite")
    engine = Engine(s)
    engine.ingest("a", "e", 0, 20, Frame(Simulator(corruption=0).line(0, 20).strip()))
    engine.finish(21)
    reports = [json.loads(r[0]) for r in s.db.execute("SELECT payload FROM reports")]
    assert [r["window_total"] for r in reports] == [0, 1]
    assert reports[-1]["active_stations"] == 1
    s.close()


def test_storage_failure_not_mislabeled_bad(tmp_path):
    s = Store(tmp_path / "events.sqlite")
    engine = Engine(s)
    s.close()
    with pytest.raises(sqlite3.ProgrammingError):
        engine.ingest("a", "e", 0, 0, Frame(b"{}"))
    assert engine.total == 0 and engine.bad == 0


def test_duplicate_identity_with_different_payload_fails(tmp_path):
    s = Store(tmp_path / "events.sqlite")
    s.ingest("a", "e", 0, 0, b"{}")
    with pytest.raises(ValueError, match="identity collision"):
        s.ingest("a", "e", 0, 1, b"[]")
    assert s.counts() == {"bad": 1}
    s.close()
