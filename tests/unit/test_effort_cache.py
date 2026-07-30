from __future__ import annotations

from src.effort.cache import EffortCache, classify_with_cache, get_global_cache
from src.effort.interface import EffortLevel, EffortResult


def _result(level: EffortLevel) -> EffortResult:
    return EffortResult(level, 0.8, "dispatch", "verify", "reason", {"score": 0.4})


def test_zero_sized_cache_disables_storage_without_crashing() -> None:
    cache = EffortCache(max_size=0)

    cache.put("task", _result(EffortLevel.LOW))

    assert cache.get("task") is None
    assert cache.get_stats()["cache_size"] == 0


def test_cache_normalizes_exact_matches_and_evicts_least_recently_used() -> None:
    cache = EffortCache(max_size=2)
    low = _result(EffortLevel.LOW)
    high = _result(EffortLevel.HIGH)
    cache.put("  Fix   Login ", low)
    cache.put("write tests", high)

    assert cache.get("fix login") is low
    cache.put("third task", _result(EffortLevel.MEDIUM))

    assert cache.get("write tests") is None
    assert cache.get("fix login") is low
    assert cache.get_stats()["hit_count"] == 2


def test_cache_reuses_only_similar_tasks_and_rejects_oversized_descriptions() -> None:
    cache = EffortCache(similarity_threshold=0.5)
    result = _result(EffortLevel.MEDIUM)
    cache.put("fix login validation", result)

    assert cache.get("fix login validation carefully") is result
    assert cache.get("write release notes") is None
    cache.put("x" * 10001, result)
    assert cache.get_stats()["cache_size"] == 1


def test_feedback_calibrates_repeated_underestimation_and_clear_resets_state() -> None:
    cache = EffortCache()
    for _ in range(10):
        cache.record_feedback("hard task", EffortLevel.LOW, 0.9, was_accurate=False)

    assert cache.get_calibrated_level(EffortLevel.LOW) == EffortLevel.MEDIUM
    stats = cache.get_stats()
    assert stats["feedback_count"] == 10
    assert stats["feedback_accuracy"] == 0.0
    cache.clear()
    assert cache.get_calibrated_level(EffortLevel.LOW) == EffortLevel.LOW
    assert cache.get_stats()["feedback_count"] == 0


def test_classify_with_cache_returns_the_same_result_for_the_same_description() -> None:
    cache = get_global_cache()
    cache.clear()

    first = classify_with_cache("update one documentation file")
    second = classify_with_cache("update one documentation file")

    assert second is first
    assert cache.get_stats()["hit_count"] == 1
