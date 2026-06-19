"""Adaptive Context Manager — 自适应上下文管理器"""

from .compression import ContextCompressor
from .extraction import KeyInfoExtractor
from .interface import ContextManager, MemoryEntry, MemoryLayer, MemoryQuery
from .layers import L1CurrentContext, L2TaskContext, L3PersistentContext
from .monitor import UtilizationMonitor
from .persistence import MemoryPersistence
from .query import MemoryQueryEngine
from .service import MemoryService

__all__ = [
    "MemoryLayer",
    "MemoryEntry",
    "MemoryQuery",
    "ContextManager",
    "L1CurrentContext",
    "L2TaskContext",
    "L3PersistentContext",
    "ContextCompressor",
    "KeyInfoExtractor",
    "UtilizationMonitor",
    "MemoryPersistence",
    "MemoryQueryEngine",
    "MemoryService",
]
