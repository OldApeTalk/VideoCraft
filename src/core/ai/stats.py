"""Thread-safe call statistics (in-memory, per-provider counters).

Mirrors the old AIRouter._stats dict + _record() method, extracted so the
router doesn't own lock handling directly.
"""

import copy
import threading
from datetime import datetime


class Stats:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict = {}

    def init_providers(self, names: list[str]) -> None:
        """Seed empty entries for the given provider names (idempotent)."""
        with self._lock:
            for name in names:
                self._data.setdefault(name, self._empty_entry())

    def record(self, provider: str, *, success: bool, error: str | None = None) -> None:
        with self._lock:
            entry = self._data.setdefault(provider, self._empty_entry())
            entry["calls"] += 1
            entry["last_used"] = datetime.now().isoformat(timespec="seconds")
            if not success:
                entry["errors"] += 1
                entry["last_error"] = error

    def snapshot(self) -> dict:
        """Return a deep copy of current stats (safe to iterate outside lock)."""
        with self._lock:
            return copy.deepcopy(self._data)

    def drop(self, provider: str) -> None:
        """Remove stats for a provider that was deleted from config."""
        with self._lock:
            self._data.pop(provider, None)

    @staticmethod
    def _empty_entry() -> dict:
        return {"calls": 0, "errors": 0, "last_error": None, "last_used": None}
