"""Git-style Context Operations — Git 式上下文操作"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ContextCommit:
    """上下文提交"""

    id: str
    message: str
    timestamp: float
    parent_id: str | None
    snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
        }


@dataclass
class ContextBranch:
    """上下文分支"""

    name: str
    head_commit_id: str | None
    created_at: float


class ContextController:
    """上下文控制器"""

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path
        self.commits: dict[str, ContextCommit] = {}
        self.branches: dict[str, ContextBranch] = {}
        self.current_branch: str = "main"
        self.staged_changes: dict[str, Any] = {}

        # 初始化主分支
        self.branches["main"] = ContextBranch(
            name="main",
            head_commit_id=None,
            created_at=time.time(),
        )

    def commit(self, message: str, context: dict[str, Any]) -> str:
        """提交上下文"""
        # 生成提交 ID
        commit_id = hashlib.sha256(
            f"{message}{time.time()}{json.dumps(context, sort_keys=True)}".encode()
        ).hexdigest()[:8]

        # 获取父提交
        parent_id = self.branches[self.current_branch].head_commit_id

        # 创建提交
        commit = ContextCommit(
            id=commit_id,
            message=message,
            timestamp=time.time(),
            parent_id=parent_id,
            snapshot=context.copy(),
        )

        self.commits[commit_id] = commit
        self.branches[self.current_branch].head_commit_id = commit_id
        self.staged_changes.clear()

        return commit_id

    def get_current_context(self) -> dict[str, Any] | None:
        """获取当前上下文"""
        branch = self.branches[self.current_branch]
        if branch.head_commit_id:
            commit = self.commits.get(branch.head_commit_id)
            if commit:
                return commit.snapshot
        return None

    def create_branch(self, name: str) -> bool:
        """创建分支"""
        if name in self.branches:
            return False

        self.branches[name] = ContextBranch(
            name=name,
            head_commit_id=self.branches[self.current_branch].head_commit_id,
            created_at=time.time(),
        )
        return True

    def switch_branch(self, name: str) -> bool:
        """切换分支"""
        if name not in self.branches:
            return False
        self.current_branch = name
        return True

    def merge(self, source_branch: str, message: str = "Merge") -> str | None:
        """合并分支"""
        if source_branch not in self.branches:
            return None

        source = self.branches[source_branch]

        if not source.head_commit_id:
            return None

        # 简单合并：使用源分支的上下文
        source_commit = self.commits.get(source.head_commit_id)
        if not source_commit:
            return None

        return self.commit(message, source_commit.snapshot)

    def log(self, limit: int = 10) -> list[dict[str, Any]]:
        """查看提交历史"""
        branch = self.branches[self.current_branch]
        if not branch.head_commit_id:
            return []

        history: list[dict[str, Any]] = []
        current_id: str | None = branch.head_commit_id

        while current_id and len(history) < limit:
            commit = self.commits.get(current_id)
            if not commit:
                break
            history.append(commit.to_dict())
            current_id = commit.parent_id

        return history

    def diff(self, commit_id1: str, commit_id2: str) -> dict[str, Any]:
        """比较两个提交"""
        commit1 = self.commits.get(commit_id1)
        commit2 = self.commits.get(commit_id2)

        if not commit1 or not commit2:
            return {"error": "Commit not found"}

        # 简单的差异计算
        added = {}
        removed = {}
        changed = {}

        for key in commit2.snapshot:
            if key not in commit1.snapshot:
                added[key] = commit2.snapshot[key]
            elif commit1.snapshot[key] != commit2.snapshot[key]:
                changed[key] = {
                    "old": commit1.snapshot[key],
                    "new": commit2.snapshot[key],
                }

        for key in commit1.snapshot:
            if key not in commit2.snapshot:
                removed[key] = commit1.snapshot[key]

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    def get_branches(self) -> list[str]:
        """获取所有分支"""
        return list(self.branches.keys())

    def get_current_branch(self) -> str:
        """获取当前分支"""
        return self.current_branch

    def statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "commits": len(self.commits),
            "branches": len(self.branches),
            "current_branch": self.current_branch,
            "staged_changes": len(self.staged_changes),
        }
