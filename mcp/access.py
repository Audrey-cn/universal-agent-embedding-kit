"""MCP 工具级访问控制"""

from __future__ import annotations

from typing import Any


class ToolAccessControl:
    """工具级访问控制

    支持按客户端限制工具调用权限。
    默认策略：所有工具对所有客户端拒绝（_default_allow=False）。
    可通过 allow_tool_for_client() 显式授权客户端调用特定工具。

    安全设计：client_id 必须来自认证层（MCPAuth），不可由客户端自行声明。
    """

    def __init__(self):
        # tool_name -> set of allowed client_ids
        self._tool_policies: dict[str, set[str]] = {}
        # 默认策略：False 表示工具未配置策略时拒绝所有客户端（安全优先）
        self._default_allow = False

    def allow_tool(self, client_id: str, tool_name: str) -> bool:
        """检查客户端是否有权调用指定工具

        Args:
            client_id: 客户端标识
            tool_name: 工具名称

        Returns:
            True 表示允许调用，False 表示拒绝
        """
        if tool_name not in self._tool_policies:
            return self._default_allow

        return client_id in self._tool_policies[tool_name]

    def restrict_tool(self, tool_name: str, allowed_clients: list[str]) -> None:
        """限制工具只允许特定客户端调用

        Args:
            tool_name: 工具名称
            allowed_clients: 允许调用的客户端 ID 列表
        """
        self._tool_policies[tool_name] = set(allowed_clients)

    def allow_tool_for_client(self, tool_name: str, client_id: str) -> None:
        """授权特定客户端调用指定工具

        Args:
            tool_name: 工具名称
            client_id: 客户端标识
        """
        if tool_name not in self._tool_policies:
            self._tool_policies[tool_name] = set()
        self._tool_policies[tool_name].add(client_id)

    def allow_all_tools_for_client(self, tool_names: list[str], client_id: str) -> None:
        """授权客户端调用多个工具

        Args:
            tool_names: 工具名称列表
            client_id: 客户端标识
        """
        for name in tool_names:
            self.allow_tool_for_client(name, client_id)

    def open_tool(self, tool_name: str) -> None:
        """移除工具的限制策略，恢复为默认策略

        Args:
            tool_name: 工具名称
        """
        self._tool_policies.pop(tool_name, None)

    def set_default_allow(self, allow: bool) -> None:
        """设置默认策略

        Args:
            allow: True 表示默认允许所有工具，False 表示默认拒绝
        """
        self._default_allow = allow

    def get_policy(self, tool_name: str) -> dict[str, Any]:
        """获取工具的策略信息"""
        return {
            "tool": tool_name,
            "restricted": tool_name in self._tool_policies,
            "allowed_clients": (
                sorted(self._tool_policies[tool_name]) if tool_name in self._tool_policies else None
            ),
            "default_allow": self._default_allow,
        }
