# Mount UAEK into your agent (recipes)

UAEK is a **discipline layer, not a brain**. Mounting it does not replace your
model or run tasks for you; it gives any MCP-capable (or stdio-JSON-RPC) agent
runtime a set of sharper tools: adversarial verification, effort routing,
layered memory, and workflow execution. The host model stays the executor —
UAEK changes how it *verifies, sizes, and remembers* its work.

After any recipe below, you should see **9 tools** including `uaek_verify`,
`uaek_effort`, `uaek_workflow_*`, and `uaek_memory_*`.

## Prerequisite: install the `uaek-mcp` executable

From a source checkout (see the README quickstart), or minimally:

```bash
git clone https://github.com/Audrey-cn/universal-agent-embedding-kit.git
cd universal-agent-embedding-kit
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Verify the entrypoint exists and responds:

```bash
uaek --version
```

> If your host shows **"Connected · tools fetch failed"**, check that you are
> running a build that includes the burst-stdio fix (2026-11, `run_stdio` raw
> line assembly). Older builds hang when a host sends `initialize` and
> `tools/list` in one write burst.

## Recipe A — Claude Code

```bash
claude mcp add uaek -- uaek-mcp
```

Then in the session ask: *"Classify the effort for: migrate the auth schema"*
— Claude Code should call `uaek_effort`. Check from the shell with
`claude mcp list` (expect `uaek ... Connected`).

To pin the interpreter explicitly (e.g. multiple Python installs), replace
`uaek-mcp` with the absolute path, such as
`/full/path/to/universal-agent-embedding-kit/.venv/bin/uaek-mcp`.

## Recipe B — Generic MCP client (JSON config)

Most clients (Cursor, Cline, Windsurf, OpenClaw-style harnesses, desktop MCP
apps) accept a server block in the shape of the portable template shipped in
[`mcp/config.json`](../../mcp/config.json):

```json
{
  "name": "uaek",
  "type": "stdio",
  "command": "uaek-mcp",
  "args": [],
  "env": { "UAEK_MCP_IDLE_TIMEOUT": "300" }
}
```

`UAEK_MCP_IDLE_TIMEOUT` is seconds; the server self-exits after that much
inactivity (set `0` to disable) so orphaned processes do not linger.

## Recipe C — Hermes Agent

In `~/.hermes/config.yaml`, under the `mcp_servers:` section:

```yaml
mcp_servers:
  uaek:
    command: /full/path/to/universal-agent-embedding-kit/.venv/bin/uaek-mcp
    args: []
    env:
      UAEK_MCP_IDLE_TIMEOUT: "300"
    enabled: true
```

Restart Hermes, then ask the agent to run `uaek_effort` on one of your real
tasks. (Hermes also supports `tools.exclude` to trim the tool surface, e.g.
dropping `uaek_memory_delete`.)

## Recipe D — Your own runtime (newline JSON-RPC over stdio)

For agents that do not speak MCP natively, the server is a line-delimited
JSON-RPC process:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"uaek_effort","arguments":{"task_description":"重构认证模块并迁移数据库"}}}' \
  '{"jsonrpc":"2.0","id":4,"method":"shutdown","params":{}}' \
  | python -m mcp.server
```

Each request with an `id` gets exactly one JSON response line. An HTTP API
variant lives in [`docs/api/http.md`](../api/http.md).

## Five-minute first outcome

1. **Effort routing** — have your mounted agent call `uaek_effort` on a task
   you are actually doing today. Read the dispatch phrase and verification
   depth it proposes.
2. **Adversarial verification** — point `uaek_verify` (type `test`,
   `fresh_context: true`) at a real artifact in your repo, or run it in a
   checkout: `uaek verify src -t test`. Compare the result with the model's
   own "looks done" claim — that gap is the product.

## Honest boundaries

- Tools are deterministic services; they do not monitor your agent loop
  automatically. The host model must be prompted (or naturally inclined) to
  call them.
- Workflow and memory tools are stateful per server instance; a restart resets
  in-memory state (persisted memory lives in the configured store).
- `verify` actions execute commands against the artifact path you supply
  (see `SECURITY.md`). Mount accordingly on shared machines.
- Claims about effectiveness are in the README's evidence table with their
  rungs; nothing here is externally validated yet (rung ⑤ is open work).
