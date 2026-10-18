"""Per-host rate limiter (sliding-window token bucket).

Blocks the calling thread until a token is available for the given host.
Thread-safe. Unknown hosts use a configurable default rate.

Rates below 1 req/s are supported: the window stretches to 1/rate seconds so
the budget is exactly one token per interval.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, defaults: dict[str, float], default_rate: float = 10.0) -> None:
        if default_rate <= 0:
            raise ValueError("default_rate must be positive")
        for h, r in defaults.items():
            if r <= 0:
                raise ValueError(f"rate for {h!r} must be positive, got {r}")
        self._rates: dict[str, float] = dict(defaults)
        self._default = default_rate
        self._history: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def configure(self, host: str, rate: float) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        with self._lock:
            self._rates[host] = rate

    def _budget(self, host: str) -> tuple[float, int]:
        """Return (window_seconds, max_tokens_in_window)."""
        rate = self._rates.get(host, self._default)
        window = max(1.0, 1.0 / rate)
        max_tokens = max(1, round(rate * window))
        return window, max_tokens

    def acquire(self, host: str) -> None:
        while True:
            with self._lock:
                window, max_tokens = self._budget(host)
                history = self._history[host]
                now = time.monotonic()
                threshold = now - window
                while history and history[0] <= threshold:
                    history.popleft()
                if len(history) < max_tokens:
                    history.append(now)
                    return
                wait = history[0] + window - now
            if wait > 0:
                time.sleep(wait)
