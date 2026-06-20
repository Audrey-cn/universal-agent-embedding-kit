# UAEK MCP Tools

`mcp/server.py` exposes a simplified MCP-compatible server object for tests and host integration.

It can also run as a newline-delimited JSON-RPC stdio process:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"shutdown","params":{}}' \
  | python -m mcp.server
```

Each input line receives one JSON response line on stdout. The server exits after `shutdown`.

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
