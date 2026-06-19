"""Stateful memory service for CLI/API/MCP entrypoints."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .compression import ContextCompressor
from .interface import MemoryEntry, MemoryLayer, MemoryLayerType, MemoryQuery
from .layers import L1CurrentContext, L2TaskContext, L3PersistentContext
from .persistence import MemoryPersistence
from .query import MemoryQueryEngine


class MemoryService:
    """Small stateful facade over the layered memory primitives."""

    def __init__(self, storage_path: Path | str | None = None, autoload: bool = True):
        self.storage_path = Path(storage_path or ".uaek/memory")
        self.persistence = MemoryPersistence(self.storage_path)
        self.layers: dict[MemoryLayerType, MemoryLayer] = {
            MemoryLayerType.L1_CURRENT: L1CurrentContext(),
            MemoryLayerType.L2_TASK: L2TaskContext(),
            MemoryLayerType.L3_PERSISTENT: L3PersistentContext(),
        }
        self.compressor = ContextCompressor()
        if autoload:
            self.restore()

    def add(
        self,
        content: str,
        layer: str | MemoryLayerType = "l1",
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        entry_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a memory entry and return a serializable representation."""
        layer_type = self.resolve_layer(layer)
        entry = MemoryEntry(
            id=entry_id or self._new_entry_id(),
            content=content,
            layer=layer_type,
            importance=float(importance),
            timestamp=time.time(),
            metadata=metadata or {},
            tags=tags or [],
        )
        self.layers[layer_type].add(entry)
        return self.entry_to_dict(entry)

    def query(
        self,
        query: str,
        layer: str | MemoryLayerType | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Query memory entries across all layers or one selected layer."""
        selected_layer = self.resolve_layer(layer) if layer else None
        layers = [self.layers[selected_layer]] if selected_layer else list(self.layers.values())
        engine = MemoryQueryEngine(layers)
        results = engine.search(
            MemoryQuery(
                query=query,
                layer=selected_layer,
                tags=tags or [],
                min_importance=float(min_importance),
                limit=int(limit),
            )
        )
        return {
            "query": query,
            "layer": self.layer_to_short(selected_layer) if selected_layer else None,
            "results": [self.entry_to_dict(entry) for entry in results],
            "total": len(results),
        }

    def compress(
        self,
        layer: str | MemoryLayerType | None = None,
        target_ratio: float = 0.5,
    ) -> dict[str, Any]:
        """Compress selected memory layers with the existing compressor."""
        target_layers = [self.resolve_layer(layer)] if layer else list(self.layers.keys())
        before = sum(len(self.layers[layer_type]) for layer_type in target_layers)

        for layer_type in target_layers:
            entries = list(self.layers[layer_type].entries.values())
            compressed = self.compressor.compress(entries, target_ratio=target_ratio)
            self.layers[layer_type].entries = {entry.id: entry for entry in compressed}

        after = sum(len(self.layers[layer_type]) for layer_type in target_layers)
        return {
            "layer": self.layer_to_short(target_layers[0]) if layer else None,
            "target_ratio": target_ratio,
            "before": before,
            "after": after,
            "status": "compressed",
        }

    def persist(self) -> dict[str, Any]:
        """Persist all memory layers."""
        self.persistence.save_all(
            {layer_type: list(layer.entries.values()) for layer_type, layer in self.layers.items()}
        )
        return {"status": "persisted", "storage_path": str(self.storage_path), **self.stats()}

    def restore(self) -> dict[str, Any]:
        """Restore all memory layers from storage."""
        loaded = self.persistence.load_all()
        for layer_type, entries in loaded.items():
            self.layers[layer_type].entries = {entry.id: entry for entry in entries}
        return {"status": "restored", "storage_path": str(self.storage_path), **self.stats()}

    def clear(self, clear_storage: bool = True) -> dict[str, Any]:
        """Clear in-memory state, and storage by default."""
        for layer in self.layers.values():
            layer.clear()
        if clear_storage:
            self.persistence.clear()
        return {"status": "cleared", **self.stats()}

    def stats(self) -> dict[str, Any]:
        """Return layer counts."""
        layers = {
            self.layer_to_short(layer_type): len(layer) for layer_type, layer in self.layers.items()
        }
        return {"layers": layers, "total": sum(layers.values())}

    def resolve_layer(self, layer: str | MemoryLayerType | None) -> MemoryLayerType:
        """Resolve public layer identifiers."""
        if isinstance(layer, MemoryLayerType):
            return layer
        mapping = {
            "l1": MemoryLayerType.L1_CURRENT,
            "l1_current": MemoryLayerType.L1_CURRENT,
            "l2": MemoryLayerType.L2_TASK,
            "l2_task": MemoryLayerType.L2_TASK,
            "l3": MemoryLayerType.L3_PERSISTENT,
            "l3_persistent": MemoryLayerType.L3_PERSISTENT,
        }
        key = str(layer or "l1").lower()
        if key not in mapping:
            raise ValueError(f"Unknown memory layer: {layer}")
        return mapping[key]

    def layer_to_short(self, layer_type: MemoryLayerType | None) -> str | None:
        if layer_type is None:
            return None
        return {
            MemoryLayerType.L1_CURRENT: "l1",
            MemoryLayerType.L2_TASK: "l2",
            MemoryLayerType.L3_PERSISTENT: "l3",
        }[layer_type]

    def entry_to_dict(self, entry: MemoryEntry) -> dict[str, Any]:
        """Serialize a MemoryEntry."""
        return {
            "id": entry.id,
            "content": entry.content,
            "layer": self.layer_to_short(entry.layer),
            "importance": entry.importance,
            "timestamp": entry.timestamp,
            "metadata": entry.metadata,
            "tags": entry.tags,
        }

    def _new_entry_id(self) -> str:
        total = sum(len(layer) for layer in self.layers.values())
        return f"mem_{int(time.time() * 1000)}_{total}"
