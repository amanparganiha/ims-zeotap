"""
Lightweight throughput counter.
Printed to console every 5 seconds by the background task in main.py.
"""
import asyncio
import logging
import time
from threading import Lock

log = logging.getLogger(__name__)


class _SignalCounter:
    def __init__(self):
        self._count = 0
        self._lock = Lock()
        self._window_start = time.monotonic()

    def inc(self, n: int = 1):
        with self._lock:
            self._count += n

    def snapshot(self) -> tuple[int, float]:
        """Returns (total_since_last_snapshot, elapsed_seconds) and resets."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._window_start
            count = self._count
            self._count = 0
            self._window_start = now
        return count, elapsed


signal_counter = _SignalCounter()


async def throughput_reporter():
    """Background task: prints signals/sec to console every 5 seconds."""
    while True:
        await asyncio.sleep(5)
        count, elapsed = signal_counter.snapshot()
        rate = count / elapsed if elapsed > 0 else 0
        log.info("📊 Throughput: %.1f signals/sec  (%d in last %.1fs)", rate, count, elapsed)
