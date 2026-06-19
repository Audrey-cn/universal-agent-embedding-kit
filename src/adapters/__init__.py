"""External Agent Adapter interfaces and local command adapter."""

from .command import CommandAgentAdapter
from .interface import AdapterRequest, AdapterRunResult
from .readiness import run_adapter_readiness

__all__ = [
    "AdapterRequest",
    "AdapterRunResult",
    "CommandAgentAdapter",
    "run_adapter_readiness",
]
