"""Incremental Verification — 增量验证引擎

RESEARCH_PROPOSAL.md 命题3（P0）核心组件：
"增量验证：不是每次都完整验证，而是只验证变更部分"

设计目标：
- 文件变更检测：基于哈希指纹追踪文件变化
- 依赖图分析：确定变更影响范围，只验证受影响的文件
- 缓存复用：未变更文件的验证结果直接复用
- 成本优化：在保证质量的前提下降低验证成本 30-50%
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .interface import VerificationResult, VerificationType, verify


@dataclass
class FileFingerprint:
    """文件指纹"""

    path: Path
    hash: str
    last_verified: float = 0.0
    last_result: VerificationResult | None = None


@dataclass
class DependencyGraph:
    """文件依赖图

    记录文件之间的导入/依赖关系，用于确定变更影响范围。
    """

    # 文件 -> 依赖它的文件集合
    dependents: dict[str, set[str]] = field(default_factory=dict)
    # 文件 -> 它依赖的文件集合
    dependencies: dict[str, set[str]] = field(default_factory=dict)

    def add_dependency(self, source: str, target: str) -> None:
        """添加依赖关系：source 依赖 target"""
        if source not in self.dependencies:
            self.dependencies[source] = set()
        self.dependencies[source].add(target)

        if target not in self.dependents:
            self.dependents[target] = set()
        self.dependents[target].add(source)

    def affected_by(self, changed_files: set[str]) -> set[str]:
        """计算变更影响的所有文件（变更文件 + 它们的传递依赖者）"""
        affected = set(changed_files)
        queue = list(changed_files)

        while queue:
            current = queue.pop(0)
            for dependent in self.dependents.get(current, set()):
                if dependent not in affected:
                    affected.add(dependent)
                    queue.append(dependent)

        return affected

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependencies": {k: list(v) for k, v in self.dependencies.items()},
            "dependents": {k: list(v) for k, v in self.dependents.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DependencyGraph:
        g = cls()
        for src, targets in data.get("dependencies", {}).items():
            for tgt in targets:
                g.add_dependency(src, tgt)
        return g

    @classmethod
    def from_directory(cls, root: Path, glob_pattern: str = "**/*.py") -> DependencyGraph:
        """从目录扫描 Python 文件，自动构建依赖图"""
        g = cls()
        py_files = {}
        for f in root.glob(glob_pattern):
            if f.is_file():
                rel = str(f.relative_to(root))
                py_files[rel] = f

        # 解析每个文件的导入
        for rel_path, abs_path in py_files.items():
            try:
                imports = _extract_imports(abs_path)
                for imp in imports:
                    # 尝试匹配本地文件
                    module_path = imp.replace(".", "/") + ".py"
                    if module_path in py_files:
                        g.add_dependency(rel_path, module_path)
                    # 也尝试匹配 __init__.py
                    init_path = imp.replace(".", "/") + "/__init__.py"
                    if init_path in py_files:
                        g.add_dependency(rel_path, init_path)
            except Exception:
                pass

        return g


def _extract_imports(filepath: Path) -> list[str]:
    """从 Python 文件中提取本地导入"""
    import ast

    imports = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imports.append(node.module)
    except Exception:
        pass
    return imports


class IncrementalVerifier:
    """增量验证器

    使用方式：
        verifier = IncrementalVerifier(project_root)
        verifier.build_dependency_graph()
        result = verifier.verify_changed("src/my_module.py")
    """

    def __init__(self, project_root: Path | str, cache_path: Path | str | None = None):
        self.project_root = Path(project_root)
        self._cache_path = (
            Path(cache_path) if cache_path else self.project_root / ".uaek" / "verify_cache"
        )
        self._fingerprints: dict[str, FileFingerprint] = {}
        self._dependency_graph: DependencyGraph | None = None
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._load_cache()

    # ------------------------------------------------------------------ #
    # 指纹管理
    # ------------------------------------------------------------------ #

    def compute_hash(self, filepath: Path) -> str:
        """计算文件 SHA256 哈希"""
        return hashlib.sha256(filepath.read_bytes()).hexdigest()

    def _fingerprint_path(self, filepath: Path) -> str:
        """获取文件的相对路径（用于指纹查找）"""
        try:
            return str(filepath.resolve().relative_to(self.project_root.resolve()))
        except ValueError:
            return str(filepath)

    def get_fingerprint(self, filepath: Path) -> FileFingerprint | None:
        key = self._fingerprint_path(filepath)
        return self._fingerprints.get(key)

    def update_fingerprint(
        self, filepath: Path, result: VerificationResult | None = None
    ) -> FileFingerprint:
        """更新文件指纹（通常在验证后调用）"""
        import time

        key = self._fingerprint_path(filepath)
        fp = FileFingerprint(
            path=filepath,
            hash=self.compute_hash(filepath),
            last_verified=time.time(),
            last_result=result,
        )
        self._fingerprints[key] = fp
        self._save_cache()
        return fp

    def has_changed(self, filepath: Path) -> bool:
        """检查文件是否变更"""
        existing = self.get_fingerprint(filepath)
        if existing is None:
            return True
        return self.compute_hash(filepath) != existing.hash

    def detect_changes(self, paths: list[Path] | None = None) -> set[str]:
        """检测变更的文件

        Args:
            paths: 要检查的文件列表（默认：所有已追踪的文件）

        Returns:
            变更文件的相对路径集合
        """
        if paths is None:
            # 检查所有已追踪文件
            changed = set()
            for key, fp in list(self._fingerprints.items()):
                if not fp.path.exists():
                    changed.add(key)
                elif self.has_changed(fp.path):
                    changed.add(key)
            return changed

        changed = set()
        for p in paths:
            if p.exists() and self.has_changed(p):
                changed.add(self._fingerprint_path(p))
        return changed

    # ------------------------------------------------------------------ #
    # 依赖图
    # ------------------------------------------------------------------ #

    def build_dependency_graph(self, glob_pattern: str = "**/*.py") -> DependencyGraph:
        """构建依赖图"""
        self._dependency_graph = DependencyGraph.from_directory(self.project_root, glob_pattern)
        return self._dependency_graph

    @property
    def dependency_graph(self) -> DependencyGraph:
        if self._dependency_graph is None:
            self._dependency_graph = self.build_dependency_graph()
        return self._dependency_graph

    # ------------------------------------------------------------------ #
    # 增量验证
    # ------------------------------------------------------------------ #

    def verify_changed(
        self,
        changed_files: list[Path] | None = None,
        verification_types: list[VerificationType] | None = None,
    ) -> dict[str, VerificationResult]:
        """增量验证：只验证变更文件及其影响范围

        Args:
            changed_files: 变更的文件列表（默认：自动检测）
            verification_types: 验证类型列表（默认：[TEST, LINT]）

        Returns:
            {文件路径: 验证结果} 字典
        """
        if verification_types is None:
            verification_types = [VerificationType.TEST, VerificationType.LINT]

        # 1. 检测变更
        if changed_files is None:
            changed_keys = self.detect_changes()
        else:
            changed_keys = self.detect_changes(changed_files)

        if not changed_keys:
            return {}

        # 2. 计算影响范围（变更文件 + 传递依赖者）
        affected = self.dependency_graph.affected_by(changed_keys)

        # 3. 只验证受影响范围内的文件
        results: dict[str, VerificationResult] = {}
        for file_key in affected:
            filepath = self.project_root / file_key
            if not filepath.exists():
                continue

            # 如果文件未变更且之前验证通过，复用缓存
            fp = self.get_fingerprint(filepath)
            if fp and not self.has_changed(filepath) and fp.last_result and fp.last_result.passed:
                results[file_key] = fp.last_result
                continue

            # 运行验证
            for vtype in verification_types:
                result = verify(filepath, verification_type=vtype)
                results[file_key] = result
                # 更新指纹
                self.update_fingerprint(filepath, result)

        return results

    def verify_all(
        self,
        verification_types: list[VerificationType] | None = None,
    ) -> dict[str, VerificationResult]:
        """全量验证（首次运行或缓存失效时）"""
        if verification_types is None:
            verification_types = [VerificationType.TEST, VerificationType.LINT]

        results: dict[str, VerificationResult] = {}
        for py_file in self.project_root.glob("**/*.py"):
            if py_file.is_file():
                for vtype in verification_types:
                    result = verify(py_file, verification_type=vtype)
                    results[self._fingerprint_path(py_file)] = result
                    self.update_fingerprint(py_file, result)

        return results

    # ------------------------------------------------------------------ #
    # 缓存持久化
    # ------------------------------------------------------------------ #

    def _cache_file(self) -> Path:
        return self._cache_path / "fingerprints.json"

    def _dep_graph_file(self) -> Path:
        return self._cache_path / "dep_graph.json"

    def _save_cache(self) -> None:
        """保存指纹缓存"""
        data = {}
        for key, fp in self._fingerprints.items():
            data[key] = {
                "hash": fp.hash,
                "last_verified": fp.last_verified,
                "passed": fp.last_result.passed if fp.last_result else None,
            }
        self._cache_file().write_text(json.dumps(data, indent=2))

        # 保存依赖图
        if self._dependency_graph:
            self._dep_graph_file().write_text(
                json.dumps(self._dependency_graph.to_dict(), indent=2)
            )

    def _load_cache(self) -> None:
        """加载指纹缓存"""
        cache_file = self._cache_file()
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                for key, info in data.items():
                    fp = FileFingerprint(
                        path=self.project_root / key,
                        hash=info["hash"],
                        last_verified=info.get("last_verified", 0.0),
                    )
                    self._fingerprints[key] = fp
            except Exception:
                pass

        # 加载依赖图
        dep_file = self._dep_graph_file()
        if dep_file.exists():
            try:
                data = json.loads(dep_file.read_text())
                self._dependency_graph = DependencyGraph.from_dict(data)
            except Exception:
                pass

    def clear_cache(self) -> None:
        """清除所有缓存"""
        self._fingerprints.clear()
        self._dependency_graph = None
        if self._cache_file().exists():
            self._cache_file().unlink()
        if self._dep_graph_file().exists():
            self._dep_graph_file().unlink()

    def stats(self) -> dict[str, Any]:
        """获取增量验证统计信息"""
        total = len(self._fingerprints)
        cached = sum(
            1 for fp in self._fingerprints.values() if fp.last_result and fp.last_result.passed
        )
        return {
            "total_tracked": total,
            "cached_passed": cached,
            "cache_hit_rate": cached / max(1, total),
            "dependency_graph_nodes": (
                len(self.dependency_graph.dependencies) if self._dependency_graph else 0
            ),
        }
