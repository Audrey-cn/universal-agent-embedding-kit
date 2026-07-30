from __future__ import annotations

from src.adapters.a2a import (
    A2AMessage,
    A2AOrchestrator,
    A2ATask,
    A2ATransport,
    CapabilityRouter,
    MessageRole,
    TaskStatus,
)


def test_message_round_trip_preserves_protocol_fields() -> None:
    message = A2AMessage(
        id="message-1",
        role=MessageRole.VERIFIER,
        content="verified",
        metadata={"type": "result"},
        timestamp=123.0,
        task_id="task-1",
        capabilities=["review"],
    )

    restored = A2ATransport.deserialize(A2ATransport.serialize(message))

    assert restored.to_dict() == message.to_dict()


def test_router_requires_all_capabilities_before_using_partial_fallback() -> None:
    router = CapabilityRouter()
    router.register_agent("coder", ["code"], {"cost": "low"})
    router.register_agent("reviewer", ["review"])
    router.register_agent("full", ["code", "review"])

    assert router.find_agents(["code", "review"]) == ["full"]
    assert router.route_task(A2ATask(required_capabilities=["code", "review"])) == "full"
    assert router.route_task(A2ATask(required_capabilities=["missing", "review"])) in {
        "reviewer",
        "full",
    }
    router.unregister_agent("reviewer")
    assert router.get_agent_capabilities("reviewer") == []


def test_transport_routes_by_message_type_and_isolates_broadcast_failures() -> None:
    transport = A2ATransport()
    transport.register_handler(
        "ping",
        lambda message: A2AMessage(role=MessageRole.AGENT, content=f"pong:{message.content}"),
    )
    transport.register_handler(
        "broken", lambda _message: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    message = A2AMessage(content="hello", metadata={"type": "ping"})

    assert transport.send(message).content == "pong:hello"  # type: ignore[union-attr]
    assert [response.content for response in transport.broadcast(message)] == ["pong:hello"]
    assert transport.send(A2AMessage(metadata={"type": "unknown"})) is None


def test_orchestrator_delegates_and_records_a_terminal_result() -> None:
    orchestrator = A2AOrchestrator()
    orchestrator.register_agent("coder", ["code"])
    session = orchestrator.create_session(["coder"])

    task = orchestrator.delegate_task(session.id, "implement", ["code"], priority=2)

    assert task is not None
    assert task.assigned_to == "coder"
    assert task.status is TaskStatus.DELEGATED
    orchestrator.report_result(session.id, task.id, {"commit": "abc"})
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"commit": "abc"}
    summary = orchestrator.get_session_summary(session.id)
    assert summary is not None
    assert summary["tasks"][task.id]["status"] == "completed"
    assert summary["message_count"] == 2


def test_orchestrator_does_not_record_result_for_unknown_task() -> None:
    orchestrator = A2AOrchestrator()
    session = orchestrator.create_session()

    orchestrator.report_result(session.id, "missing", "ghost")

    assert session.messages == []
