"""A conservative, in-memory TTL cache for normalized provider responses.

MVP scope: process-local, in-memory, keyed by an explicit tuple the caller
builds (never a credential, token, or raw header). This is deliberately the
simplest thing that can work for a single backend process — the interface
(`get`/`set`, a plain key -> value contract) is intentionally small so it can
be swapped for a Redis- or database-backed cache later without touching
provider code, which only ever calls `get`/`set`.

Determinism note: this cache does NOT run a background eviction thread. An
expired entry is simply not returned by `get` (checked lazily, using an
injectable clock so tests are deterministic) and is overwritten on the next
`set` for that key. A `set` immediately followed by a `get` for the same key
always returns what was just set, regardless of TTL, so caching can never
be the reason two back-to-back identical calls diverge.

Failure isolation: a cache failure (e.g. an unhashable key) must never break
an analysis — callers should treat this cache as best-effort and fall
through to a live fetch on any lookup miss, which is the normal `get`
contract (returns None) rather than raising.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class _Entry(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """Simple in-memory cache with per-entry time-to-live.

    `clock` defaults to `time.monotonic` but is injectable for deterministic
    tests (expiry, "just before"/"just after" boundary behaviour) without
    real sleeps.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._store: dict[K, _Entry[V]] = {}
        self._clock = clock
        self.hits = 0
        self.misses = 0

    def get(self, key: K) -> V | None:
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if self._clock() >= entry.expires_at:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry.value

    def set(self, key: K, value: V, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            self._store.pop(key, None)
            return
        self._store[key] = _Entry(value=value, expires_at=self._clock() + ttl_seconds)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
