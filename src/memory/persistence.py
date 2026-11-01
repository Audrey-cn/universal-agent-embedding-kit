"""Memory Persistence — 记忆持久化"""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .interface import MemoryEntry, MemoryLayerType


class MemoryPersistence:
    """记忆持久化"""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize service snapshots across processes; OS releases locks on exit."""
        with (self.storage_path / ".memory.lock").open("a+b") as lock_file:
            if sys.platform != "win32" and os.name == "posix":
                try:
                    import fcntl
                except ImportError as exc:
                    raise RuntimeError(
                        "Memory storage locking is unavailable on this platform"
                    ) from exc

                def acquire() -> None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release() -> None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

            elif sys.platform == "win32":
                try:
                    import msvcrt
                except ImportError as exc:
                    raise RuntimeError(
                        "Memory storage locking is unavailable on this platform"
                    ) from exc

                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)

                def acquire() -> None:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)

                def release() -> None:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

            else:
                raise RuntimeError("Memory storage locking is unavailable on this platform")

            deadline = time.monotonic() + 1.0
            while True:
                try:
                    acquire()
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Memory storage is busy; retry later") from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                release()

    def revision(self) -> tuple[str | None, ...]:
        """Fingerprint layer bytes while the caller holds the storage lock."""
        revisions: list[str | None] = []
        for layer_type in MemoryLayerType:
            try:
                content = self._get_file_path(layer_type).read_bytes()
            except FileNotFoundError:
                revisions.append(None)
            else:
                revisions.append(hashlib.sha256(content).hexdigest())
        return tuple(revisions)

    def save(self, entries: list[MemoryEntry], layer_type: MemoryLayerType) -> None:
        """保存记忆条目"""
        file_path = self._get_file_path(layer_type)
        self._save_serialized(self._serialize_entries(entries), file_path)

    def _serialize_entries(self, entries: list[MemoryEntry]) -> str:
        """Validate candidates with the loader's schema before touching any layer."""
        try:
            data = [self._entry_to_dict(entry) for entry in entries]
            serialized, _ = self._validated_data(data)
            return serialized
        except (AttributeError, TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ValueError(f"invalid memory entries: {exc}") from exc

    def _save_serialized(self, serialized: str, file_path: Path) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.storage_path,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(serialized)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, file_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def load(self, layer_type: MemoryLayerType) -> list[MemoryEntry]:
        """加载记忆条目"""
        file_path = self._get_file_path(layer_type)
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            _, entries = self._validated_data(data)
            return entries
        except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ValueError(f"corrupt memory file: {file_path}") from exc

    def save_all(self, layers: dict[MemoryLayerType, list[MemoryEntry]]) -> None:
        """Validate and serialize every candidate layer before replacing the first."""
        prepared = [
            (self._get_file_path(layer_type), self._serialize_entries(entries))
            for layer_type, entries in layers.items()
        ]
        for file_path, serialized in prepared:
            self._save_serialized(serialized, file_path)

    def _validated_data(self, data: list) -> tuple[str, list[MemoryEntry]]:
        if not isinstance(data, list):
            raise ValueError("expected a list of memory entries")
        entries = [self._dict_to_entry(entry) for entry in data]
        if len({entry.id for entry in entries}) != len(entries):
            raise ValueError("duplicate memory entry ids")
        serialized = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
        serialized.encode("utf-8")
        return serialized, entries

    def load_all(self) -> dict[MemoryLayerType, list[MemoryEntry]]:
        """加载所有层"""
        result = {}
        for layer_type in MemoryLayerType:
            result[layer_type] = self.load(layer_type)
        return result

    def delete(self, layer_type: MemoryLayerType) -> bool:
        """删除指定层"""
        file_path = self._get_file_path(layer_type)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def clear(self) -> None:
        """清除所有持久化数据"""
        for layer_type in MemoryLayerType:
            self.delete(layer_type)

    def _get_file_path(self, layer_type: MemoryLayerType) -> Path:
        """获取文件路径"""
        if not isinstance(layer_type, MemoryLayerType):
            raise ValueError("invalid memory layer type")
        return self.storage_path / f"{layer_type.value}.json"

    def _entry_to_dict(self, entry: MemoryEntry) -> dict:
        """将条目转换为字典"""
        return {
            "id": entry.id,
            "content": entry.content,
            "layer": entry.layer.value,
            "importance": entry.importance,
            "timestamp": entry.timestamp,
            "metadata": entry.metadata,
            "tags": entry.tags,
        }

    def _dict_to_entry(self, data: dict) -> MemoryEntry:
        """将字典转换为条目"""
        if not isinstance(data, dict):
            raise ValueError("expected a memory entry object")
        if not isinstance(data.get("id"), str) or not isinstance(data.get("content"), str):
            raise ValueError("memory entry id and content must be strings")
        for field, default in (("importance", 0.5), ("timestamp", 0.0)):
            value = data.get(field, default)
            try:
                finite = type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"memory entry {field} must be a finite number")
        if not isinstance(data.get("metadata", {}), dict):
            raise ValueError("memory entry metadata must be an object")
        tags = data.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError("memory entry tags must be a list of strings")
        return MemoryEntry(
            id=data["id"],
            content=data["content"],
            layer=MemoryLayerType(data["layer"]),
            importance=data.get("importance", 0.5),
            timestamp=data.get("timestamp", 0.0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )
