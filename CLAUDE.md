# fable-research (UAEK)

Project type: `python`. Reuses the shared **devkit** at `../devkit`.
The historical wiring was manual, not bootstrapped via copier, so `copier update`
is not used. `link-devkit.sh` contains Windows PowerShell HardLink/Junction calls;
do not rerun it unchanged on macOS.

## Shared tooling

The historical Windows wiring used hardlinks for `code-reviewer` and `code-explorer`
under `.claude/agents/`, and a junction for `knowledge-management` under `.claude/skills/`.
This macOS checkout has no `.claude/` wiring. Current TRAE access uses global MCP
servers and guide skills; consult devkit on demand through them or read its files directly.

## Knowledge base

Before solving something that might already be known, consult the shared KB:
`grep -ri "<term>" ../devkit/kb/` and read `../devkit/kb/INDEX.md`, or use
`devkit_resolve_task` to route knowledge reuse through `knowledge-management`.
`../devkit/handbook/Index.md` catalogs thick reference manuals — consult on demand, do not preload.

## Client integration (Trae CN)

Global configuration, discovery, and the specified read-only call checked on 2026-10-18 (no repo-local `.trae/` files):

- Global skill `universal-agent-embedding-kit-guide` — symlinked into `~/.trae-cn/skills/` (live link to this repo's `.mimocode/skills/universal-agent-embedding-kit-guide`) and visible in the local TRAE Agent slash skill list.
- MCP server `uaek` — local macOS Trae CN 3.4.4 uses the global JSON file `~/Library/Application Support/Trae CN/User/mcp.json`; 设置 → MCP → 手动添加 can also manage it. Merge this entry into the existing `mcpServers` object:
  `{"mcpServers":{"uaek":{"command":"<repo>/.venv/bin/uaek-mcp","args":[],"env":{"UAEK_MCP_IDLE_TIMEOUT":"0"}}}}`
- `UAEK_MCP_IDLE_TIMEOUT=0` disables UAEK's idle shutdown; TRAE manages the connection lifecycle.
- Verified: `.venv/bin/uaek-mcp` initializes over stdio and advertises 9 tools (`uaek_verify`, `uaek_effort`, `uaek_workflow_create/add_task/execute`, `uaek_memory_add/query/delete/compress`); `python -m pytest tests/unit/test_mcp_stdio.py -q` → 23 passed.
- The local TRAE Agent has hot-loaded all 9 `uaek` tools and actually called `uaek_effort` with six explicit parameters, returning `low`, confidence `0.825`, score `0.025`. The same acceptance read all three repository guides. This validates that call and guide access; it does not establish that every UAEK tool has passed host acceptance.

## Project notes

<!-- Add project-specific commands, gotchas, dependency relationships, and architecture below. -->
