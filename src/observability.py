"""Observability — 可观测性系统"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceSpan:
    """追踪跨度"""

    id: str
    name: str
    start_time: float
    end_time: float | None = None
    parent_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def finish(self):
        """结束跨度"""
        self.end_time = time.time()

    @property
    def duration(self) -> float | None:
        """持续时间"""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def add_event(self, name: str, attributes: dict[str, Any] | None = None):
        """添加事件"""
        self.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "parent_id": self.parent_id,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """追踪器"""

    def __init__(self):
        self.spans: dict[str, TraceSpan] = {}
        self._current_span: str | None = None

    def start_span(
        self,
        name: str,
        parent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        """开始跨度"""
        span_id = f"span_{len(self.spans)}"
        span = TraceSpan(
            id=span_id,
            name=name,
            start_time=time.time(),
            parent_id=parent_id or self._current_span,
            attributes=attributes or {},
        )
        self.spans[span_id] = span
        self._current_span = span_id
        return span_id

    def end_span(self, span_id: str):
        """结束跨度"""
        if span_id in self.spans:
            self.spans[span_id].finish()
            if self._current_span == span_id:
                self._current_span = self.spans[span_id].parent_id

    def add_event(self, span_id: str, name: str, attributes: dict[str, Any] | None = None):
        """添加事件"""
        if span_id in self.spans:
            self.spans[span_id].add_event(name, attributes)

    def get_trace(self, root_span_id: str) -> list[TraceSpan]:
        """获取追踪树"""
        trace = []
        to_visit = [root_span_id]

        while to_visit:
            span_id = to_visit.pop(0)
            if span_id in self.spans:
                span = self.spans[span_id]
                trace.append(span)
                # 查找子跨度
                for s in self.spans.values():
                    if s.parent_id == span_id:
                        to_visit.append(s.id)

        return trace

    def get_all_spans(self) -> list[TraceSpan]:
        """获取所有跨度"""
        return list(self.spans.values())

    def clear(self):
        """清除所有跨度"""
        self.spans.clear()
        self._current_span = None


@dataclass
class CostRecord:
    """成本记录"""

    timestamp: float
    operation: str
    tokens_used: int
    cost_usd: float
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """成本追踪器"""

    def __init__(self):
        self.records: list[CostRecord] = []
        self._total_cost: float = 0.0
        self._total_tokens: int = 0

    def record(
        self,
        operation: str,
        tokens: int,
        cost: float,
        model: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ):
        """记录成本"""
        record = CostRecord(
            timestamp=time.time(),
            operation=operation,
            tokens_used=tokens,
            cost_usd=cost,
            model=model,
            metadata=metadata or {},
        )
        self.records.append(record)
        self._total_cost += cost
        self._total_tokens += tokens

    @property
    def total_cost(self) -> float:
        """总成本"""
        return self._total_cost

    @property
    def total_tokens(self) -> int:
        """总 token 数"""
        return self._total_tokens

    def get_by_model(self) -> dict[str, float]:
        """按模型统计成本"""
        by_model: dict[str, float] = {}
        for record in self.records:
            by_model[record.model] = by_model.get(record.model, 0.0) + record.cost_usd
        return by_model

    def get_by_operation(self) -> dict[str, float]:
        """按操作统计成本"""
        by_op: dict[str, float] = {}
        for record in self.records:
            by_op[record.operation] = by_op.get(record.operation, 0.0) + record.cost_usd
        return by_op

    def clear(self):
        """清除记录"""
        self.records.clear()
        self._total_cost = 0.0
        self._total_tokens = 0


@dataclass
class QualityIssue:
    """质量问题"""

    timestamp: float
    issue_type: str  # goal_drift, hallucination, missed_action
    severity: str  # low, medium, high
    description: str
    context: dict[str, Any] = field(default_factory=dict)


class QualityDetector:
    """质量检测器"""

    def __init__(self):
        self.issues: list[QualityIssue] = []

    def detect_goal_drift(self, original_goal: str, current_action: str) -> bool:
        """检测目标漂移"""
        # 简单的关键词匹配
        original_words = set(original_goal.lower().split())
        current_words = set(current_action.lower().split())

        overlap = len(original_words & current_words)
        if overlap < len(original_words) * 0.3:
            description = f"Action '{current_action}' may be drifting from goal '{original_goal}'"
            self.issues.append(
                QualityIssue(
                    timestamp=time.time(),
                    issue_type="goal_drift",
                    severity="high",
                    description=description,
                )
            )
            return True
        return False

    def detect_hallucination(self, claim: str, sources: list[str]) -> bool:
        """检测幻觉"""
        # 简单的来源验证
        claim_words = set(claim.lower().split())
        source_text = " ".join(sources).lower()

        unsupported = [w for w in claim_words if w not in source_text and len(w) > 3]
        if len(unsupported) > len(claim_words) * 0.5:
            self.issues.append(
                QualityIssue(
                    timestamp=time.time(),
                    issue_type="hallucination",
                    severity="medium",
                    description=f"Claim may contain unsupported statements: {unsupported[:5]}",
                )
            )
            return True
        return False

    def detect_missed_action(self, expected: list[str], actual: list[str]) -> list[str]:
        """检测遗漏动作"""
        expected_set = set(expected)
        actual_set = set(actual)
        missed = list(expected_set - actual_set)

        if missed:
            self.issues.append(
                QualityIssue(
                    timestamp=time.time(),
                    issue_type="missed_action",
                    severity="medium",
                    description=f"Missed actions: {missed}",
                )
            )

        return missed

    def get_issues(self, severity: str | None = None) -> list[QualityIssue]:
        """获取问题"""
        if severity:
            return [i for i in self.issues if i.severity == severity]
        return self.issues

    def clear(self):
        """清除问题"""
        self.issues.clear()


class ObservabilitySystem:
    """可观测性系统"""

    def __init__(self):
        self.tracer = Tracer()
        self.cost_tracker = CostTracker()
        self.quality_detector = QualityDetector()

    def start_trace(self, name: str, attributes: dict[str, Any] | None = None) -> str:
        """开始追踪"""
        return self.tracer.start_span(name, attributes=attributes)

    def end_trace(self, trace_id: str):
        """结束追踪"""
        self.tracer.end_span(trace_id)

    def record_cost(self, operation: str, tokens: int, cost: float, model: str = "unknown"):
        """记录成本"""
        self.cost_tracker.record(operation, tokens, cost, model)

    def check_quality(self, goal: str, action: str, sources: list[str] | None = None):
        """检查质量"""
        self.quality_detector.detect_goal_drift(goal, action)
        if sources:
            self.quality_detector.detect_hallucination(action, sources)

    def get_report(self) -> dict[str, Any]:
        """获取报告"""
        return {
            "traces": len(self.tracer.get_all_spans()),
            "total_cost": self.cost_tracker.total_cost,
            "total_tokens": self.cost_tracker.total_tokens,
            "quality_issues": len(self.quality_detector.get_issues()),
            "high_severity_issues": len(self.quality_detector.get_issues("high")),
        }

    def clear(self):
        """清除所有数据"""
        self.tracer.clear()
        self.cost_tracker.clear()
        self.quality_detector.clear()
