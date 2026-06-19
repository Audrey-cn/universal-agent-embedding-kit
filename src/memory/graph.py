"""Knowledge Graph — 知识图谱"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    """实体"""

    id: str
    name: str
    entity_type: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type,
            "properties": self.properties,
        }


@dataclass
class Relation:
    """关系"""

    id: str
    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relation_type,
            "properties": self.properties,
        }


class KnowledgeGraph:
    """知识图谱"""

    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.relations: dict[str, Relation] = {}
        self._index: dict[str, set[str]] = {}  # entity_id -> set of relation_ids

    def add_entity(self, entity: Entity):
        """添加实体"""
        self.entities[entity.id] = entity
        if entity.id not in self._index:
            self._index[entity.id] = set()

    def add_relation(self, relation: Relation):
        """添加关系"""
        if relation.source_id not in self.entities:
            raise KeyError(f"Source entity {relation.source_id} not found")
        if relation.target_id not in self.entities:
            raise KeyError(f"Target entity {relation.target_id} not found")

        self.relations[relation.id] = relation
        self._index[relation.source_id].add(relation.id)
        self._index[relation.target_id].add(relation.id)

    def get_entity(self, entity_id: str) -> Entity | None:
        """获取实体"""
        return self.entities.get(entity_id)

    def get_relation(self, relation_id: str) -> Relation | None:
        """获取关系"""
        return self.relations.get(relation_id)

    def get_entity_relations(self, entity_id: str) -> list[Relation]:
        """获取实体的所有关系"""
        relation_ids = self._index.get(entity_id, set())
        return [self.relations[rid] for rid in relation_ids if rid in self.relations]

    def get_neighbors(self, entity_id: str) -> list[Entity]:
        """获取邻居实体"""
        neighbors = []
        for relation in self.get_entity_relations(entity_id):
            if relation.source_id == entity_id:
                neighbor = self.entities.get(relation.target_id)
            else:
                neighbor = self.entities.get(relation.source_id)
            if neighbor:
                neighbors.append(neighbor)
        return neighbors

    def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> list[list[str]]:
        """查找路径"""
        if start_id not in self.entities or end_id not in self.entities:
            return []

        paths = []
        visited = set()

        def dfs(current_id: str, path: list[str]):
            if len(path) > max_depth + 1:
                return
            if current_id == end_id:
                paths.append(path[:])
                return

            visited.add(current_id)
            for neighbor in self.get_neighbors(current_id):
                if neighbor.id not in visited:
                    path.append(neighbor.id)
                    dfs(neighbor.id, path)
                    path.pop()
            visited.discard(current_id)

        dfs(start_id, [start_id])
        return paths

    def remove_entity(self, entity_id: str) -> bool:
        """删除实体及其关系"""
        if entity_id not in self.entities:
            return False

        # 删除相关关系
        relation_ids = self._index.get(entity_id, set()).copy()
        for rid in relation_ids:
            if rid in self.relations:
                del self.relations[rid]

        # 从其他实体的索引中移除
        for other_id in self._index:
            self._index[other_id].discard(rid)

        # 删除实体
        del self.entities[entity_id]
        del self._index[entity_id]

        return True

    def remove_relation(self, relation_id: str) -> bool:
        """删除关系"""
        if relation_id not in self.relations:
            return False

        relation = self.relations[relation_id]
        self._index[relation.source_id].discard(relation_id)
        self._index[relation.target_id].discard(relation_id)
        del self.relations[relation_id]

        return True

    def search_entities(self, query: str, entity_type: str | None = None) -> list[Entity]:
        """搜索实体"""
        results = []
        query_lower = query.lower()

        for entity in self.entities.values():
            if entity_type and entity.entity_type != entity_type:
                continue
            if query_lower in entity.name.lower() or query_lower in str(entity.properties).lower():
                results.append(entity)

        return results

    def get_entity_types(self) -> list[str]:
        """获取所有实体类型"""
        return list(set(e.entity_type for e in self.entities.values()))

    def get_relation_types(self) -> list[str]:
        """获取所有关系类型"""
        return list(set(r.relation_type for r in self.relations.values()))

    def statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "entity_types": len(self.get_entity_types()),
            "relation_types": len(self.get_relation_types()),
        }
