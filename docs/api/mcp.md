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
- `uaek_memory_delete`
- `uaek_memory_compress`

Workflow tools are stateful within one `MCPServer` instance:

1. `uaek_workflow_create`
2. `uaek_workflow_add_task`
3. `uaek_workflow_execute`

Memory tools are also stateful within one server instance and use the shared `MemoryService` facade.

## Idle timeout (automatic release)

The server automatically exits after a configurable period of inactivity to prevent
memory leaks from orphaned processes:

| Setting | Mechanism | Default |
|---|---|---|
| `--idle-timeout SECONDS` | CLI argument to `python -m mcp.server` | `300` (5 minutes) |
| `UAEK_MCP_IDLE_TIMEOUT` | Environment variable | `300` (5 minutes) |
| `idle_timeout=0` | Disables idle timeout | — |

The server exits on the first idle check that exceeds the timeout (1-second polling
granularity). The exit reason is logged to stderr (`[uaek-mcp] shutdown: ...`) for
diagnosis.

### Exit paths (in priority order)

1. `shutdown` method (MCP JSON-RPC request, with or without `id`)
2. SIGTERM / SIGINT signal (graceful shutdown)
3. Idle timeout (no requests received within the configured window)
4. stdin EOF (pipe closed by host)

### Example

```bash
# 30-second idle timeout
UAEK_MCP_IDLE_TIMEOUT=30 python -m mcp.server

# Disable idle timeout
python -m mcp.server --idle-timeout 0
```
