"""DAG — 有向无环图"""

from __future__ import annotations

from .interface import Task


class CycleError(Exception):
    """循环依赖错误"""

    pass


class DAG:
    """有向无环图"""

    def __init__(self):
        self.nodes: dict[str, Task] = {}
        self.edges: dict[str, set[str]] = {}  # node_id -> set of dependent node_ids

    def add_node(self, task: Task) -> None:
        """添加节点"""
        if task.id in self.nodes:
            raise ValueError(f"Node {task.id} already exists")
        self.nodes[task.id] = task
        self.edges[task.id] = set()

    def add_edge(self, from_id: str, to_id: str) -> None:
        """添加边（from_id 必须在 to_id 之前完成）"""
        if from_id not in self.nodes:
            raise KeyError(f"Node {from_id} not found")
        if to_id not in self.nodes:
            raise KeyError(f"Node {to_id} not found")
        self.edges[from_id].add(to_id)

    def get_dependencies(self, node_id: str) -> set[str]:
        """获取节点的依赖（必须在此节点之前完成的节点）"""
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id} not found")
        return {n for n, deps in self.edges.items() if node_id in deps}

    def get_dependents(self, node_id: str) -> set[str]:
        """获取依赖此节点的节点"""
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id} not found")
        return self.edges.get(node_id, set())

    def has_cycle(self) -> bool:
        """检查是否有循环依赖"""
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for dependent in self.edges.get(node_id, set()):
                if dependent not in visited:
                    if dfs(dependent):
                        return True
                elif dependent in rec_stack:
                    return True

            rec_stack.discard(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def validate(self) -> None:
        """验证 DAG（检查循环依赖）"""
        if self.has_cycle():
            raise CycleError("DAG contains cycle")

    def topological_sort(self) -> list[str]:
        """拓扑排序"""
        self.validate()

        visited = set()
        order = []

        def dfs(node_id: str):
            visited.add(node_id)
            for dependent in self.edges.get(node_id, set()):
                if dependent not in visited:
                    dfs(dependent)
            order.append(node_id)

        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id)

        return list(reversed(order))

    def get_root_nodes(self) -> set[str]:
        """获取根节点（没有依赖的节点）"""
        all_dependents = set()
        for deps in self.edges.values():
            all_dependents.update(deps)
        return set(self.nodes.keys()) - all_dependents

    def get_leaf_nodes(self) -> set[str]:
        """获取叶子节点（没有依赖者的节点）"""
        return {n for n, deps in self.edges.items() if not deps}

    def get_ready_nodes(self, completed: set[str]) -> set[str]:
        """获取可以执行的节点（所有依赖都已完成）"""
        ready = set()
        for node_id in self.nodes:
            if node_id in completed:
                continue
            deps = self.get_dependencies(node_id)
            if deps.issubset(completed):
                ready.add(node_id)
        return ready

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes
