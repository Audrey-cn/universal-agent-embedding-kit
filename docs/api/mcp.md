# UAEK MCP Tools

`mcp/server.py` exposes a simplified MCP-compatible server object for tests and host integration.

## Install and configure a host

Install UAEK before adding it to an MCP host. From a source checkout, use an
editable install during development:

```bash
python -m pip install -e .
```

Then configure the host to launch the installed `uaek-mcp` command. The portable
template in [`mcp/config.json`](../../mcp/config.json) keeps the idle timeout in
its environment metadata and does not depend on a checkout location. Host-specific
GUI settings, such as where the host stores its MCP configuration, remain the
host's responsibility.

It can also run as a newline-delimited JSON-RPC stdio process:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"shutdown","params":{}}' \
  | python -m mcp.server
```

Requests with an `id` receive one JSON response line on stdout. The retained 0.3
behavior for no-id inputs is method-dependent: recognized methods emit their usual
response with `"id": null`, while an unknown no-id method is silent. The server exits
after `shutdown`, including a no-id `shutdown` after writing its `id:null` response.

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
UAEK_MCP_IDLE_TIMEOUT=30 uaek-mcp

# Disable idle timeout
uaek-mcp --idle-timeout 0
```

For compatibility, both `python -m mcp` and `python -m mcp.server` remain
supported after installation.
