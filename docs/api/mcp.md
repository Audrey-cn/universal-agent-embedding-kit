# UAEK MCP Tools

`mcp/server.py` exposes a simplified MCP-compatible server object for tests and host integration.

Registered tools:

- `uaek_verify`
- `uaek_effort`
- `uaek_workflow_create`
- `uaek_workflow_add_task`
- `uaek_workflow_execute`
- `uaek_memory_add`
- `uaek_memory_query`
- `uaek_memory_compress`

Workflow tools are stateful within one `MCPServer` instance:

1. `uaek_workflow_create`
2. `uaek_workflow_add_task`
3. `uaek_workflow_execute`

Memory tools are also stateful within one server instance and use the shared `MemoryService` facade.
