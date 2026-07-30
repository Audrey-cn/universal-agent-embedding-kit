from __future__ import annotations

import math
import time

import pytest

from src.memory.decay import DecayConfig, ebbinghaus_decay, should_evict
from src.memory.knowledge_graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    Relation,
    RelationType,
)
from src.memory.token_budget import BudgetPool, TokenBudget, estimate_memory_tokens, estimate_tokens


def test_replacing_entity_removes_it_from_the_previous_type_index() -> None:
    """Changing an entity's type must not leave stale search results behind."""
    graph = KnowledgeGraph()
    graph.add_entity(Entity("same", "old", EntityType.ERROR))

    graph.add_entity(Entity("same", "new", EntityType.DECISION))

    assert graph.get_entities_by_type(EntityType.ERROR) == []
    assert [entity.name for entity in graph.get_entities_by_type(EntityType.DECISION)] == ["new"]


def test_removing_entity_removes_relations_from_neighbor_indexes() -> None:
    graph = KnowledgeGraph()
    graph.add_entity(Entity("source", "source", EntityType.TASK))
    graph.add_entity(Entity("removed", "removed", EntityType.FILE))
    graph.add_entity(Entity("target", "target", EntityType.FILE))
    graph.add_relation(Relation("source", "removed", RelationType.MODIFIES))
    graph.add_relation(Relation("removed", "target", RelationType.DEPENDS_ON))

    assert graph.remove_entity("removed") is True

    assert graph.get_neighbors("source", depth=2) == []
    assert graph.get_neighbors("target", depth=2) == []
    assert graph.get_relations() == []


def test_graph_query_traversal_and_stats_use_real_relations() -> None:
    graph = KnowledgeGraph()
    decision = graph.ingest_memory_entry("d1", "决定采用 DAG", 0.9, ["decision"])
    task = graph.ingest_memory_entry("t1", "implement workflow", 0.7, ["task"])
    file_entity = graph.ingest_memory_entry("f1", "src/workflow.py", 0.6, ["file"])
    graph.link_entities(decision.id, task.id, RelationType.PRECEDES)
    graph.link_entities(task.id, file_entity.id, RelationType.MODIFIES)

    assert [e.id for e in graph.search(entity_type=EntityType.DECISION)] == [decision.id]
    assert {e.id for e in graph.get_neighbors(task.id)} == {decision.id, file_entity.id}
    assert [e.id for e, _path in graph.traverse(decision.id)] == [task.id, file_entity.id]
    assert graph.stats()["total_relations"] == 2


def test_token_budget_notifies_at_threshold_and_tracks_snapshots() -> None:
    budget = TokenBudget(total_tokens=100, over_budget_threshold=0.5)
    notices: list[tuple[BudgetPool, int]] = []
    budget.register_callback(lambda pool, status: notices.append((pool, status.used)))

    budget.track_usage(BudgetPool.MEMORY, 12)
    assert notices == []
    budget.track_usage(BudgetPool.MEMORY, 1)

    assert notices == [(BudgetPool.MEMORY, 13)]
    snapshot = budget.get_status()
    assert snapshot.pools[BudgetPool.MEMORY].allocated == 25
    assert snapshot.over_budget_pools == [BudgetPool.MEMORY]
    assert snapshot.to_dict()["over_budget_pools"] == ["memory"]
    assert budget.get_history() == [snapshot]
    budget.clear_history()
    assert budget.get_history() == []


def test_token_budget_adjustment_and_reset_preserve_total_allocation() -> None:
    budget = TokenBudget(total_tokens=1000)
    budget.adjust_allocation(BudgetPool.MEMORY, 0.4)

    assert sum(budget.allocation.values()) == pytest.approx(1.0)
    assert budget.allocation[BudgetPool.MEMORY] == pytest.approx(0.4)
    budget.set_usage(BudgetPool.MEMORY, -5)
    assert budget.get_utilization(BudgetPool.MEMORY) == 0.0
    budget.set_usage(BudgetPool.MEMORY, 50)
    budget.reset_pool(BudgetPool.MEMORY)
    assert budget.get_utilization(BudgetPool.MEMORY) == 0.0


def test_decay_half_life_access_boost_and_eviction_boundaries() -> None:
    now = 1_000_000.0
    config = DecayConfig(half_life_days=10, access_boost=0.1, floor=0.01)
    score = ebbinghaus_decay(0.8, now - 10 * 86400, config=config, now=now)
    boosted = ebbinghaus_decay(
        0.8,
        now - 10 * 86400,
        access_count=2,
        config=config,
        now=now,
    )

    assert score == pytest.approx(0.4)
    assert boosted == pytest.approx(0.6)
    assert math.isclose(config.decay_rate, math.log(2) / 10)
    assert should_evict(1.0, time.time() - 31 * 86400, max_age_days=30) is True


def test_token_estimates_handle_mixed_text_and_entry_objects() -> None:
    class Entry:
        content = "hello world"

    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("中文") == 1
    assert estimate_memory_tokens([Entry(), "abcd"]) == 3

