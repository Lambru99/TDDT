from __future__ import annotations

import threading
import time

import pytest

from tddt.core.rate_limit import RateLimiter


def test_acquire_within_rate_does_not_block():
    rl = RateLimiter({"fast.example": 10.0})
    start = time.monotonic()
    for _ in range(5):
        rl.acquire("fast.example")
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_acquire_blocks_when_exhausted():
    rl = RateLimiter({"slow.example": 2.0})
    start = time.monotonic()
    for _ in range(4):
        rl.acquire("slow.example")
    elapsed = time.monotonic() - start
    assert elapsed >= 1.0
    assert elapsed < 2.0  # not 2 full seconds; the 4th acquire fits in the 2nd second


def test_unknown_host_uses_default_rate():
    rl = RateLimiter({}, default_rate=10.0)
    start = time.monotonic()
    for _ in range(5):
        rl.acquire("unknown.example")
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_subhertz_rate():
    """A host configured at 2 req/s with 3 acquires blocks after the burst."""
    rl = RateLimiter({"burst.example": 2.0})
    start = time.monotonic()
    for _ in range(3):
        rl.acquire("burst.example")
    elapsed = time.monotonic() - start
    assert elapsed >= 1.0


def test_thread_safe_serializes_at_rate():
    """10 threads x 5 acquires at 20 req/s on same host should take ~2s
    (20 in first second, 20 in second, 10 in third → window-bounded)."""
    rl = RateLimiter({"shared.example": 20.0})
    done: list[float] = []
    lock = threading.Lock()

    def worker():
        for _ in range(5):
            rl.acquire("shared.example")
        with lock:
            done.append(time.monotonic())

    start = time.monotonic()
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - start
    assert elapsed >= 2.0
    assert elapsed < 4.0


def test_independent_hosts_do_not_interfere():
    rl = RateLimiter({"a.example": 1.0, "b.example": 10.0})
    start = time.monotonic()
    # Fast host doesn't inherit slow host's budget.
    for _ in range(5):
        rl.acquire("b.example")
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_configure_adds_rate_at_runtime():
    rl = RateLimiter({})
    rl.configure("api.example", 2.0)
    start = time.monotonic()
    for _ in range(3):
        rl.acquire("api.example")
    elapsed = time.monotonic() - start
    assert elapsed >= 1.0


@pytest.mark.parametrize("rate", [0.5, 1.0, 2.0, 5.0])
def test_fairness_approximate_rate(rate: float):
    """Average spacing between acquires should respect rate within a tolerance."""
    rl = RateLimiter({"param.example": rate})
    n = max(3, int(rate * 2))
    times: list[float] = []
    for _ in range(n):
        rl.acquire("param.example")
        times.append(time.monotonic())
    span = times[-1] - times[0]
    expected_min_span = (n - 1 - rate) / rate - 0.1  # the first `rate` fit instantly
    assert span >= max(0, expected_min_span)
