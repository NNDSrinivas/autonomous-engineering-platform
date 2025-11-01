from __future__ import annotations
import time
from typing import Callable, Awaitable, Optional, Any


class CircuitBreaker:
    """
    Minimal async circuit breaker (half-open with success threshold).
    - open after `fail_threshold` failures within `window_sec`
    - stay open for `open_sec`, then half-open (1 trial)
    - close after `success_to_close` consecutive successes
    """

    def __init__(
        self,
        name: str,
        fail_threshold: int = 5,
        window_sec: int = 60,
        open_sec: int = 30,
        success_to_close: int = 2,
    ):
        self.name = name
        self.fail_threshold = fail_threshold
        self.window_sec = window_sec
        self.open_sec = open_sec
        self.success_to_close = success_to_close
        self._fails: list[float] = []
        self._state = "closed"  # closed | open | half-open
        self._next_try = 0.0
        self._half_success = 0

    def _prune(self):
        now = time.time()
        self._fails = [t for t in self._fails if now - t <= self.window_sec]

    def is_open(self) -> bool:
        now = time.time()
        if self._state == "open" and now >= self._next_try:
            self._state = "half-open"
            self._half_success = 0
        return self._state == "open"

    async def call(
        self,
        fn: Callable[[], Awaitable[Any]],
        fallback: Optional[Callable[[Exception], Awaitable[Any]]] = None,
    ) -> Any:
        now = time.time()
        # short-circuit
        if self._state == "open":
            if now < self._next_try:
                if fallback:
                    return await fallback(RuntimeError("circuit-open"))
                raise RuntimeError("circuit-open")
            # move to half-open
            self._state = "half-open"
            self._half_success = 0

        try:
            out = await fn()
            # success path
            if self._state == "half-open":
                self._half_success += 1
                if self._half_success >= self.success_to_close:
                    self._state = "closed"
                    self._fails.clear()
            return out
        except Exception as e:
            # record failure
            self._prune()
            self._fails.append(now)
            if len(self._fails) >= self.fail_threshold:
                self._state = "open"
                self._next_try = now + self.open_sec
            if fallback:
                return await fallback(e)
            raise
