"""Memory Persistence — 记忆持久化"""

from __future__ import annotations

import json
from pathlib import Path

from .interface import MemoryEntry, MemoryLayerType


class MemoryPersistence:
    """记忆持久化"""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, entries: list[MemoryEntry], layer_type: MemoryLayerType) -> None:
        """保存记忆条目"""
        file_path = self._get_file_path(layer_type)
        data = [self._entry_to_dict(entry) for entry in entries]
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load(self, layer_type: MemoryLayerType) -> list[MemoryEntry]:
        """加载记忆条目"""
        file_path = self._get_file_path(layer_type)
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text())
            return [self._dict_to_entry(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return []

    def save_all(self, layers: dict[MemoryLayerType, list[MemoryEntry]]) -> None:
        """保存所有层"""
        for layer_type, entries in layers.items():
            self.save(entries, layer_type)

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
        return MemoryEntry(
            id=data["id"],
            content=data["content"],
            layer=MemoryLayerType(data["layer"]),
            importance=data.get("importance", 0.5),
            timestamp=data.get("timestamp", 0.0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )
