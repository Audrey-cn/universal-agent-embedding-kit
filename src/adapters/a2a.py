"""A2A Protocol — Agent-to-Agent 通信协议

RESEARCH_PROPOSAL.md 命题5（P2）核心组件：
"通用 Agent 协议：设计一个模型无关的代理通信协议，让任何模型都能参与"

设计目标：
- 模型无关的消息格式：Claude、GPT、Gemini、Llama 等任意模型均可使用
- 标准化的任务委派、结果报告、能力发现流程
- 支持跨供应商协作：不同模型执行不同子任务
- 可嵌入：作为 Python 库或独立协议使用

协议层次：
1. 消息层（Message）：标准化的消息格式
2. 会话层（Session）：多轮对话管理
3. 路由层（Router）：任务分发和能力匹配
4. 传输层（Transport）：消息序列化和传输
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# --------------------------------------------------------------------------- #
# 消息层
# --------------------------------------------------------------------------- #


class MessageRole(Enum):
    """消息角色"""

    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    VERIFIER = "verifier"
    ORCHESTRATOR = "orchestrator"


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELEGATED = "delegated"  # 已委派给其他 Agent


@dataclass
class A2AMessage:
    """A2A 协议标准消息

    模型无关的消息格式，任何 Agent 都可以发送和接收。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole = MessageRole.AGENT
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    # 任务委派相关
    task_id: str | None = None
    parent_message_id: str | None = None

    # 能力声明
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "parent_message_id": self.parent_message_id,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2AMessage:
        """从字典反序列化"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=MessageRole(data.get("role", "agent")),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            task_id=data.get("task_id"),
            parent_message_id=data.get("parent_message_id"),
            capabilities=data.get("capabilities", []),
        )

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> A2AMessage:
        """从 JSON 反序列化"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class A2ATask:
    """A2A 协议任务定义"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None  # Agent ID
    created_by: str | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    # 任务需求
    required_capabilities: list[str] = field(default_factory=list)
    priority: int = 0  # 0=normal, 1=high, 2=critical

    # 子任务
    parent_task_id: str | None = None
    sub_tasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "required_capabilities": self.required_capabilities,
            "priority": self.priority,
            "parent_task_id": self.parent_task_id,
            "sub_tasks": self.sub_tasks,
        }


# --------------------------------------------------------------------------- #
# 会话层
# --------------------------------------------------------------------------- #


@dataclass
class A2ASession:
    """A2A 协议会话

    管理多 Agent 之间的多轮对话。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    participants: list[str] = field(default_factory=list)  # Agent ID 列表
    messages: list[A2AMessage] = field(default_factory=list)
    tasks: dict[str, A2ATask] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def add_participant(self, agent_id: str, capabilities: list[str] | None = None) -> None:
        """添加参与者"""
        if agent_id not in self.participants:
            self.participants.append(agent_id)
        if capabilities:
            self.metadata.setdefault("agent_capabilities", {})
            self.metadata["agent_capabilities"][agent_id] = capabilities

    def add_message(self, message: A2AMessage) -> None:
        """添加消息"""
        self.messages.append(message)

    def create_task(
        self,
        description: str,
        required_capabilities: list[str] | None = None,
        priority: int = 0,
    ) -> A2ATask:
        """创建任务"""
        task = A2ATask(
            description=description,
            required_capabilities=required_capabilities or [],
            priority=priority,
        )
        self.tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> A2ATask | None:
        """获取任务"""
        return self.tasks.get(task_id)

    def update_task_status(self, task_id: str, status: TaskStatus, result: Any = None) -> None:
        """更新任务状态"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = status
            if result is not None:
                task.result = result
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "participants": self.participants,
            "messages": [m.to_dict() for m in self.messages],
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 路由层
# --------------------------------------------------------------------------- #


class CapabilityRouter:
    """能力路由器

    根据 Agent 的能力声明，将任务路由到最合适的 Agent。
    """

    def __init__(self):
        self._agents: dict[str, dict[str, Any]] = {}
        self._capability_index: dict[str, set[str]] = {}

    def register_agent(
        self,
        agent_id: str,
        capabilities: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """注册 Agent 及其能力"""
        self._agents[agent_id] = {
            "capabilities": capabilities,
            "metadata": metadata or {},
            "registered_at": time.time(),
        }
        for cap in capabilities:
            if cap not in self._capability_index:
                self._capability_index[cap] = set()
            self._capability_index[cap].add(agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """注销 Agent"""
        if agent_id in self._agents:
            for cap in self._agents[agent_id]["capabilities"]:
                if cap in self._capability_index:
                    self._capability_index[cap].discard(agent_id)
            del self._agents[agent_id]

    def find_agents(self, required_capabilities: list[str]) -> list[str]:
        """查找满足所有能力需求的 Agent

        Returns:
            满足所有需求的 Agent ID 列表
        """
        if not required_capabilities:
            return list(self._agents.keys())

        candidates = None
        for cap in required_capabilities:
            agents_with_cap = self._capability_index.get(cap, set())
            if candidates is None:
                candidates = agents_with_cap.copy()
            else:
                candidates &= agents_with_cap

        return list(candidates) if candidates else []

    def route_task(self, task: A2ATask) -> str | None:
        """将任务路由到最合适的 Agent

        Returns:
            最适合的 Agent ID，或 None
        """
        available = self.find_agents(task.required_capabilities)
        if not available:
            # 尝试放宽要求：匹配部分能力
            for cap in task.required_capabilities:
                partial = self._capability_index.get(cap, set())
                if partial:
                    return next(iter(partial))
            return None

        # 选择第一个匹配的（可以扩展为负载均衡）
        return available[0]

    def get_agent_capabilities(self, agent_id: str) -> list[str]:
        """获取 Agent 的能力列表"""
        agent = self._agents.get(agent_id)
        return agent["capabilities"] if agent else []

    def list_agents(self) -> list[dict[str, Any]]:
        """列出所有已注册的 Agent"""
        return [
            {"id": agent_id, "capabilities": info["capabilities"], "metadata": info["metadata"]}
            for agent_id, info in self._agents.items()
        ]


# --------------------------------------------------------------------------- #
# 传输层
# --------------------------------------------------------------------------- #


class A2ATransport:
    """A2A 协议传输层

    处理消息的序列化、传输和接收。
    支持多种传输方式：内存、文件、HTTP。
    """

    def __init__(self):
        self._handlers: dict[str, Callable[[A2AMessage], A2AMessage | None]] = {}

    def register_handler(
        self,
        message_type: str,
        handler: Callable[[A2AMessage], A2AMessage | None],
    ) -> None:
        """注册消息处理器"""
        self._handlers[message_type] = handler

    def send(self, message: A2AMessage) -> A2AMessage | None:
        """发送消息并等待响应"""
        msg_type = message.metadata.get("type", "default")
        handler = self._handlers.get(msg_type)
        if handler:
            return handler(message)
        return None

    def broadcast(self, message: A2AMessage) -> list[A2AMessage]:
        """广播消息到所有处理器"""
        responses = []
        for handler in self._handlers.values():
            try:
                response = handler(message)
                if response:
                    responses.append(response)
            except Exception:
                pass
        return responses

    @staticmethod
    def serialize(message: A2AMessage) -> str:
        """序列化消息为 JSON"""
        return message.to_json()

    @staticmethod
    def deserialize(data: str) -> A2AMessage:
        """反序列化 JSON 为消息"""
        return A2AMessage.from_json(data)


# --------------------------------------------------------------------------- #
# 编排器
# --------------------------------------------------------------------------- #


class A2AOrchestrator:
    """A2A 协议编排器

    协调多 Agent 协作的高层接口。
    整合了消息层、会话层、路由层和传输层。

    使用方式：
        orchestrator = A2AOrchestrator()

        # 注册 Agent
        orchestrator.register_agent("claude-1", ["coding", "review"])
        orchestrator.register_agent("gpt-1", ["testing", "documentation"])

        # 创建会话
        session = orchestrator.create_session(["claude-1", "gpt-1"])

        # 委派任务
        task = orchestrator.delegate_task(
            session_id=session.id,
            description="Implement login module",
            required_capabilities=["coding"],
        )
    """

    def __init__(self):
        self.router = CapabilityRouter()
        self.transport = A2ATransport()
        self._sessions: dict[str, A2ASession] = {}

    def register_agent(
        self,
        agent_id: str,
        capabilities: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """注册 Agent"""
        self.router.register_agent(agent_id, capabilities, metadata)

    def unregister_agent(self, agent_id: str) -> None:
        """注销 Agent"""
        self.router.unregister_agent(agent_id)

    def create_session(self, participants: list[str] | None = None) -> A2ASession:
        """创建会话"""
        session = A2ASession()
        if participants:
            for p in participants:
                caps = self.router.get_agent_capabilities(p)
                session.add_participant(p, caps)
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> A2ASession | None:
        """获取会话"""
        return self._sessions.get(session_id)

    def delegate_task(
        self,
        session_id: str,
        description: str,
        required_capabilities: list[str] | None = None,
        priority: int = 0,
    ) -> A2ATask | None:
        """委派任务到合适的 Agent

        Args:
            session_id: 会话 ID
            description: 任务描述
            required_capabilities: 需要的 Agent 能力
            priority: 任务优先级

        Returns:
            创建的任务，或 None（如果找不到合适的 Agent）
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        task = session.create_task(description, required_capabilities, priority)

        # 路由任务
        assigned = self.router.route_task(task)
        if assigned:
            task.assigned_to = assigned
            task.status = TaskStatus.DELEGATED

            # 发送委派消息
            msg = A2AMessage(
                role=MessageRole.ORCHESTRATOR,
                content=f"Task delegated: {description}",
                task_id=task.id,
                metadata={"type": "task_delegation", "session_id": session_id},
            )
            session.add_message(msg)

        return task

    def report_result(
        self,
        session_id: str,
        task_id: str,
        result: Any,
        success: bool = True,
    ) -> None:
        """报告任务结果"""
        session = self._sessions.get(session_id)
        if not session:
            return
        if session.get_task(task_id) is None:
            return

        status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        session.update_task_status(task_id, status, result)

        msg = A2AMessage(
            role=MessageRole.AGENT,
            content=f"Task result: {'success' if success else 'failure'}",
            task_id=task_id,
            metadata={"type": "task_result", "session_id": session_id, "success": success},
        )
        session.add_message(msg)

    def list_agents(self) -> list[dict[str, Any]]:
        """列出所有已注册的 Agent"""
        return self.router.list_agents()

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        """获取会话摘要"""
        session = self._sessions.get(session_id)
        if not session:
            return None

        tasks_summary = {}
        for task_id, task in session.tasks.items():
            tasks_summary[task_id] = {
                "description": task.description,
                "status": task.status.value,
                "assigned_to": task.assigned_to,
            }

        return {
            "session_id": session.id,
            "participants": session.participants,
            "message_count": len(session.messages),
            "task_count": len(session.tasks),
            "tasks": tasks_summary,
            "created_at": session.created_at,
        }
