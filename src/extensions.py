"""Extension Features — 扩展功能"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskTemplate:
    """任务模板"""

    name: str
    description: str
    tasks: list[dict[str, Any]]
    default_effort: str = "medium"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "tasks": self.tasks,
            "default_effort": self.default_effort,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskTemplate:
        """从字典创建"""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            tasks=data.get("tasks", []),
            default_effort=data.get("default_effort", "medium"),
            tags=data.get("tags", []),
        )

    def save(self, path: Path):
        """保存到文件"""
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> TaskTemplate:
        """从文件加载"""
        data = json.loads(path.read_text())
        return cls.from_dict(data)


class TemplateLibrary:
    """模板库"""

    def __init__(self, templates_dir: Path | None = None):
        self.templates_dir = templates_dir
        self.templates: dict[str, TaskTemplate] = {}

        # 内置模板
        self._register_builtin_templates()

        # 从目录加载模板
        if templates_dir and templates_dir.exists():
            self._load_from_directory(templates_dir)

    def _register_builtin_templates(self):
        """注册内置模板"""
        # 功能开发模板
        self.templates["feature-development"] = TaskTemplate(
            name="feature-development",
            description="标准功能开发流程",
            tasks=[
                {"id": "research", "name": "调研", "effort": "medium"},
                {"id": "design", "name": "设计", "effort": "high", "dependencies": ["research"]},
                {"id": "implement", "name": "实现", "effort": "high", "dependencies": ["design"]},
                {"id": "test", "name": "测试", "effort": "medium", "dependencies": ["implement"]},
                {"id": "document", "name": "文档", "effort": "low", "dependencies": ["implement"]},
            ],
            tags=["feature", "development"],
        )

        # 代码重构模板
        self.templates["refactoring"] = TaskTemplate(
            name="refactoring",
            description="代码重构流程",
            tasks=[
                {"id": "analyze", "name": "分析", "effort": "medium"},
                {"id": "plan", "name": "计划", "effort": "high", "dependencies": ["analyze"]},
                {"id": "refactor", "name": "重构", "effort": "high", "dependencies": ["plan"]},
                {"id": "test", "name": "测试", "effort": "medium", "dependencies": ["refactor"]},
                {"id": "cleanup", "name": "清理", "effort": "low", "dependencies": ["test"]},
            ],
            tags=["refactoring", "maintenance"],
        )

        # Bug 修复模板
        self.templates["bug-fix"] = TaskTemplate(
            name="bug-fix",
            description="Bug 修复流程",
            tasks=[
                {"id": "reproduce", "name": "复现", "effort": "medium"},
                {"id": "diagnose", "name": "诊断", "effort": "high", "dependencies": ["reproduce"]},
                {"id": "fix", "name": "修复", "effort": "high", "dependencies": ["diagnose"]},
                {"id": "verify", "name": "验证", "effort": "medium", "dependencies": ["fix"]},
            ],
            tags=["bug", "fix"],
        )

        # 代码审查模板
        self.templates["code-review"] = TaskTemplate(
            name="code-review",
            description="代码审查流程",
            tasks=[
                {"id": "read", "name": "阅读代码", "effort": "medium"},
                {"id": "analyze", "name": "分析问题", "effort": "high", "dependencies": ["read"]},
                {
                    "id": "suggest",
                    "name": "提出建议",
                    "effort": "medium",
                    "dependencies": ["analyze"],
                },
                {"id": "report", "name": "生成报告", "effort": "low", "dependencies": ["suggest"]},
            ],
            tags=["review", "quality"],
        )

    def _load_from_directory(self, directory: Path):
        """从目录加载模板"""
        for template_file in directory.glob("*.json"):
            try:
                template = TaskTemplate.load(template_file)
                self.templates[template.name] = template
            except Exception:
                pass

    def get(self, name: str) -> TaskTemplate | None:
        """获取模板"""
        return self.templates.get(name)

    def list_templates(self) -> list[dict[str, Any]]:
        """列出所有模板"""
        return [
            {"name": t.name, "description": t.description, "tags": t.tags}
            for t in self.templates.values()
        ]

    def add(self, template: TaskTemplate):
        """添加模板"""
        self.templates[template.name] = template

    def remove(self, name: str) -> bool:
        """删除模板"""
        if name in self.templates:
            del self.templates[name]
            return True
        return False

    def save_to_directory(self, directory: Path):
        """保存到目录"""
        directory.mkdir(parents=True, exist_ok=True)
        for template in self.templates.values():
            template.save(directory / f"{template.name}.json")


@dataclass
class WorkflowReport:
    """工作流报告"""

    workflow_id: str
    start_time: float
    end_time: float
    tasks: list[dict[str, Any]]
    success: bool
    errors: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """持续时间"""
        return self.end_time - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "duration": round(self.duration, 4),
            "success": self.success,
            "tasks": self.tasks,
            "errors": self.errors,
        }

    def save(self, path: Path):
        """保存到文件"""
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))


class ReportGenerator:
    """报告生成器"""

    def generate_workflow_report(self, workflow_result) -> WorkflowReport:
        """生成工作流报告"""
        tasks = []
        for task in workflow_result.tasks:
            tasks.append(
                {
                    "id": task.id,
                    "name": task.name,
                    "status": task.status.value,
                    "result": str(task.result) if task.result else None,
                    "error": str(task.error) if task.error else None,
                }
            )

        errors = [str(e) for e in workflow_result.errors]

        return WorkflowReport(
            workflow_id=workflow_result.workflow_id,
            start_time=0.0,  # 简化处理
            end_time=workflow_result.duration,
            tasks=tasks,
            success=workflow_result.success,
            errors=errors,
        )

    def generate_summary(self, reports: list[WorkflowReport]) -> dict[str, Any]:
        """生成摘要"""
        total = len(reports)
        success = sum(1 for r in reports if r.success)
        failed = total - success

        return {
            "total_workflows": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0.0,
            "avg_duration": sum(r.duration for r in reports) / total if total > 0 else 0.0,
        }
