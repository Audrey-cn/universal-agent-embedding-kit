"""External Agent Adapter interfaces and local command adapter."""

from .a2a import (
    A2AMessage,
    A2AOrchestrator,
    A2ASession,
    A2ATask,
    A2ATransport,
    CapabilityRouter,
    MessageRole,
    TaskStatus,
)
from .command import CommandAgentAdapter
from .interface import AdapterRequest, AdapterRunResult
from .readiness import run_adapter_readiness

__all__ = [
    "AdapterRequest",
    "AdapterRunResult",
    "CommandAgentAdapter",
    "run_adapter_readiness",
    "A2AMessage",
    "A2AOrchestrator",
    "A2ASession",
    "A2ATask",
    "A2ATransport",
    "CapabilityRouter",
    "MessageRole",
    "TaskStatus",
]
