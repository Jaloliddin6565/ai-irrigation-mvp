from app.core.cache import TTLCache


def test_set_then_get_returns_value_immediately() -> None:
    cache: TTLCache = TTLCache(clock=lambda: 0.0)
    cache.set("key", "value", ttl_seconds=10)
    assert cache.get("key") == "value"


def test_miss_returns_none_and_counts_as_a_miss() -> None:
    cache: TTLCache = TTLCache(clock=lambda: 0.0)
    assert cache.get("missing") is None
    assert cache.misses == 1
    assert cache.hits == 0


def test_expired_entry_is_not_returned() -> None:
    now = [0.0]
    cache: TTLCache = TTLCache(clock=lambda: now[0])
    cache.set("key", "value", ttl_seconds=5)
    now[0] = 5.0  # exactly at expiry -> treated as expired
    assert cache.get("key") is None


def test_entry_just_before_expiry_is_still_returned() -> None:
    now = [0.0]
    cache: TTLCache = TTLCache(clock=lambda: now[0])
    cache.set("key", "value", ttl_seconds=5)
    now[0] = 4.999
    assert cache.get("key") == "value"


def test_distinct_keys_are_independent() -> None:
    cache: TTLCache = TTLCache(clock=lambda: 0.0)
    cache.set("a", 1, ttl_seconds=10)
    cache.set("b", 2, ttl_seconds=10)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_zero_or_negative_ttl_does_not_store_anything() -> None:
    cache: TTLCache = TTLCache(clock=lambda: 0.0)
    cache.set("key", "value", ttl_seconds=0)
    assert cache.get("key") is None
    assert len(cache) == 0


def test_hits_and_misses_are_tracked() -> None:
    cache: TTLCache = TTLCache(clock=lambda: 0.0)
    cache.set("key", "value", ttl_seconds=10)
    cache.get("key")
    cache.get("missing")
    assert cache.hits == 1
    assert cache.misses == 1


def test_clear_removes_all_entries() -> None:
    cache: TTLCache = TTLCache(clock=lambda: 0.0)
    cache.set("key", "value", ttl_seconds=10)
    cache.clear()
    assert len(cache) == 0


def test_set_overwrites_a_previous_expired_entry() -> None:
    now = [0.0]
    cache: TTLCache = TTLCache(clock=lambda: now[0])
    cache.set("key", "old", ttl_seconds=1)
    now[0] = 5.0
    cache.set("key", "new", ttl_seconds=10)
    assert cache.get("key") == "new"
