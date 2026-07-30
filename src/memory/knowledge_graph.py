"""Knowledge Graph — 结构化记忆索引

将对话历史转化为可查询的知识图谱，实现 RESEARCH_PROPOSAL.md 命题1：
"将对话历史转化为可查询的知识图谱，而非线性文本"

支持：
- 实体节点（Entity）：决策、约束、错误、文件、任务等
- 关系边（Relation）：依赖、修改、引用、导致等
- 语义查询：按关系类型、实体类型、时间范围检索
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(Enum):
    """知识图谱实体类型"""
    DECISION = "decision"       # 决策
    CONSTRAINT = "constraint"   # 约束
    ERROR = "error"             # 错误
    FILE = "file"               # 文件
    TASK = "task"               # 任务
    REQUIREMENT = "requirement" # 需求
    PATTERN = "pattern"         # 模式/经验


class RelationType(Enum):
    """关系类型"""
    DEPENDS_ON = "depends_on"       # 依赖
    MODIFIES = "modifies"           # 修改
    REFERENCES = "references"       # 引用
    CAUSES = "causes"               # 导致
    RESOLVES = "resolves"           # 解决
    RELATES_TO = "relates_to"       # 相关
    PRECEDES = "precedes"           # 先于
    CONSTRAINS = "constrains"       # 约束


@dataclass
class Entity:
    """知识图谱实体"""
    id: str
    name: str
    entity_type: EntityType
    content: str = ""
    importance: float = 0.5
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id


@dataclass
class Relation:
    """知识图谱关系"""
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph:
    """知识图谱 — 结构化记忆索引

    设计目标（RESEARCH_PROPOSAL.md 命题1）：
    - 将对话历史转化为可查询的知识图谱
    - 支持按实体类型、关系类型、时间范围检索
    - 与向量搜索和关键词搜索形成混合查询
    """

    def __init__(self):
        self._entities: dict[str, Entity] = {}
        self._relations: list[Relation] = []
        # 索引：实体类型 -> 实体ID集合
        self._type_index: dict[EntityType, set[str]] = defaultdict(set)
        # 索引：源实体 -> 关系列表
        self._outgoing: dict[str, list[Relation]] = defaultdict(list)
        # 索引：目标实体 -> 关系列表
        self._incoming: dict[str, list[Relation]] = defaultdict(list)

    # ---- 实体管理 ----

    def add_entity(self, entity: Entity) -> None:
        """添加实体"""
        existing = self._entities.get(entity.id)
        if existing is not None and existing.entity_type != entity.entity_type:
            self._type_index[existing.entity_type].discard(entity.id)
        self._entities[entity.id] = entity
        self._type_index[entity.entity_type].add(entity.id)

    def get_entity(self, entity_id: str) -> Entity | None:
        """获取实体"""
        return self._entities.get(entity_id)

    def remove_entity(self, entity_id: str) -> bool:
        """删除实体及其关联关系"""
        if entity_id not in self._entities:
            return False
        entity = self._entities[entity_id]
        self._type_index[entity.entity_type].discard(entity_id)
        del self._entities[entity_id]
        # 删除关联关系
        self._relations = [
            r for r in self._relations
            if r.source_id != entity_id and r.target_id != entity_id
        ]
        self._rebuild_relation_indexes()
        return True

    def _rebuild_relation_indexes(self) -> None:
        """Rebuild adjacency indexes after relations are removed."""
        self._outgoing.clear()
        self._incoming.clear()
        for relation in self._relations:
            self._outgoing[relation.source_id].append(relation)
            self._incoming[relation.target_id].append(relation)

    # ---- 关系管理 ----

    def add_relation(self, relation: Relation) -> None:
        """添加关系"""
        if relation.source_id not in self._entities:
            raise KeyError(f"Source entity '{relation.source_id}' not found")
        if relation.target_id not in self._entities:
            raise KeyError(f"Target entity '{relation.target_id}' not found")
        self._relations.append(relation)
        self._outgoing[relation.source_id].append(relation)
        self._incoming[relation.target_id].append(relation)

    def get_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: RelationType | None = None,
    ) -> list[Relation]:
        """查询关系"""
        results = self._relations
        if source_id:
            results = [r for r in results if r.source_id == source_id]
        if target_id:
            results = [r for r in results if r.target_id == target_id]
        if relation_type:
            results = [r for r in results if r.relation_type == relation_type]
        return results

    # ---- 查询 ----

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """按类型获取实体"""
        ids = self._type_index.get(entity_type, set())
        return [self._entities[eid] for eid in ids if eid in self._entities]

    def get_neighbors(self, entity_id: str, depth: int = 1) -> list[Entity]:
        """获取实体的邻居（depth 跳内）"""
        if entity_id not in self._entities:
            return []
        visited: set[str] = {entity_id}
        frontier = {entity_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node_id in frontier:
                for rel in self._outgoing.get(node_id, []):
                    if rel.target_id not in visited:
                        next_frontier.add(rel.target_id)
                        visited.add(rel.target_id)
                for rel in self._incoming.get(node_id, []):
                    if rel.source_id not in visited:
                        next_frontier.add(rel.source_id)
                        visited.add(rel.source_id)
            frontier = next_frontier
        visited.discard(entity_id)
        return [self._entities[eid] for eid in visited if eid in self._entities]

    def search(
        self,
        query: str = "",
        entity_type: EntityType | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
        limit: int = 10,
    ) -> list[Entity]:
        """搜索实体（关键词 + 类型 + 标签过滤）"""
        candidates = list(self._entities.values())
        query_lower = query.lower().strip()

        if entity_type:
            candidates = [e for e in candidates if e.entity_type == entity_type]
        if tags:
            candidates = [e for e in candidates if any(t in e.tags for t in tags)]
        if min_importance > 0:
            candidates = [e for e in candidates if e.importance >= min_importance]
        if query_lower:
            candidates = [
                e for e in candidates
                if query_lower in e.name.lower() or query_lower in e.content.lower()
            ]

        candidates.sort(key=lambda e: e.importance, reverse=True)
        return candidates[:limit]

    def traverse(
        self,
        start_id: str,
        relation_type: RelationType | None = None,
        max_depth: int = 3,
    ) -> list[tuple[Entity, list[Relation]]]:
        """从起始实体遍历图谱，返回路径"""
        if start_id not in self._entities:
            return []
        result: list[tuple[Entity, list[Relation]]] = []
        visited: set[str] = {start_id}
        queue: list[tuple[str, list[Relation]]] = [(start_id, [])]

        while queue and len(result) < max_depth * 10:
            node_id, path = queue.pop(0)
            entity = self._entities.get(node_id)
            if entity and node_id != start_id:
                result.append((entity, path))

            for rel in self._outgoing.get(node_id, []):
                if relation_type and rel.relation_type != relation_type:
                    continue
                if rel.target_id not in visited:
                    visited.add(rel.target_id)
                    queue.append((rel.target_id, path + [rel]))

        return result

    # ---- 从记忆条目构建 ----

    def ingest_memory_entry(
        self,
        entry_id: str,
        content: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> Entity:
        """从记忆条目自动提取实体和关系"""
        entity = Entity(
            id=f"ent_{entry_id}",
            name=entry_id,
            entity_type=self._infer_entity_type(content, tags or []),
            content=content,
            importance=importance,
            tags=tags or [],
        )
        self.add_entity(entity)
        return entity

    def link_entities(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
    ) -> Relation:
        """连接两个实体"""
        relation = Relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
        )
        self.add_relation(relation)
        return relation

    def _infer_entity_type(self, content: str, tags: list[str]) -> EntityType:
        """从内容和标签推断实体类型"""
        content_lower = content.lower()
        tag_lower = [t.lower() for t in tags]

        # 决策相关
        if "decision" in tag_lower or "决定" in tag_lower:
            return EntityType.DECISION
        if any(kw in content_lower for kw in ["decide", "决定", "选择", "采用"]):
            return EntityType.DECISION

        # 约束相关
        if "constraint" in tag_lower or "约束" in tag_lower:
            return EntityType.CONSTRAINT
        if any(kw in content_lower for kw in ["constrain", "限制", "必须", "不能"]):
            return EntityType.CONSTRAINT

        # 错误相关
        if "error" in tag_lower or "错误" in tag_lower:
            return EntityType.ERROR
        if any(kw in content_lower for kw in ["error", "bug", "fail", "错误", "失败"]):
            return EntityType.ERROR

        # 文件相关
        if "file" in tag_lower or "文件" in tag_lower:
            return EntityType.FILE
        if any(kw in content_lower for kw in [".py", ".ts", ".js", ".go", "file:", "文件"]):
            return EntityType.FILE

        # 任务相关
        if "task" in tag_lower or "任务" in tag_lower:
            return EntityType.TASK

        # 需求相关
        if "requirement" in tag_lower or "需求" in tag_lower:
            return EntityType.REQUIREMENT

        return EntityType.PATTERN

    # ---- 统计信息 ----

    def stats(self) -> dict[str, Any]:
        """获取图谱统计信息"""
        type_counts = {t.value: len(ids) for t, ids in self._type_index.items()}
        return {
            "total_entities": len(self._entities),
            "total_relations": len(self._relations),
            "entity_types": type_counts,
            "relation_types": {
                rt.value: sum(1 for r in self._relations if r.relation_type == rt)
                for rt in RelationType
            },
        }

    def clear(self) -> None:
        """清空图谱"""
        self._entities.clear()
        self._relations.clear()
        self._type_index.clear()
        self._outgoing.clear()
        self._incoming.clear()
