from rillwatch.drift import Monitor, Policy
from rillwatch.simulator import Simulator


def test_baseline_excludes_boundary_and_recent_samples():
    m = Monitor(Policy(baseline_seconds=2, minimum_samples=2, persistence=1))
    sim = Simulator(corruption=0)
    for i, t in enumerate([0, 1, 2, 3]):
        r = sim.record(0, t)
        r["confidence_score"] = 0.9 if t < 2 else 0.1
        m.add(r, t)
    s = m.states["leak_detector"]
    assert s["baseline"]["confidence"] == 0.9
    assert all(r[0] >= 2 for r in s["recent"])


def test_persistence_cooldown_and_idle_expiry():
    m = Monitor(
        Policy(
            baseline_seconds=2,
            recent_seconds=10,
            minimum_samples=2,
            persistence=2,
            cooldown_seconds=60,
        )
    )
    r = Simulator(corruption=0).record(0, 0)
    for t in [0, 1]:
        r["confidence_score"] = 0.9
        m.add(r, t)
    for t in [2, 3]:
        r["confidence_score"] = 0.1
        m.add(r, t)
    assert not m.check(4)
    alerts = m.check(5)
    assert any(a["metric"] == "confidence_score" for a in alerts)
    assert not m.check(6)
    assert not m.check(20)
    assert not m.states["leak_detector"]["streak"]


def test_low_rate_baseline_stays_insufficient_and_bounded():
    m = Monitor(Policy(baseline_seconds=1, minimum_samples=50, capacity=50))
    r = Simulator(corruption=0).record(0, 0)
    m.add(r, 0)
    for i in range(1, 1000):
        m.add(r, i)
    assert not m.check(1000)
    assert len(m.states["leak_detector"]["recent"]) <= 50
    assert m.states["leak_detector"]["baseline"]["n"] == 1


def test_high_rate_capacity_is_observable():
    m = Monitor(Policy(baseline_seconds=1, minimum_samples=2, capacity=5))
    r = Simulator(corruption=0).record(0, 0)
    for i in range(20):
        m.add(r, i / 100)
    for i in range(20):
        m.add(r, 1 + i / 100)
    assert m.cap_evictions > 0
    assert len(m.states["leak_detector"]["recent"]) == 5
