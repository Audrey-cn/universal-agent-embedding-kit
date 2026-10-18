# BaiLongma reference primitives

Five JavaScript modules recovered as a small, independent reference package from
[BaiLongma](https://github.com/Audrey-cn/BaiLongma), commit
`cf452607d917a895b8428758cafcb172a1a5ce6c`. The listed source files, original budget
test, and [MIT license](LICENSE) are byte-for-byte copies. Original copyright:
**2026 xiaoyuanda666-ship-it**. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) records
the original repository paths and SHA-256 hashes, so provenance remains inspectable
without a running upstream repository.

| Module | Reusable idea | Host responsibilities |
| --- | --- | --- |
| `src/runtime/background-budget.js` | Select idle/active heartbeat and ordinary/durable recognition budgets from task and tool evidence. | Apply deadlines, token limits, round limits, cancellation, and accounting in the executor. Selection alone enforces nothing. |
| `src/runtime/tick-policy.js` | Build heartbeat context that distinguishes private working text, explicit delivery, and unanswered conversation. | Implement delivery semantics, permissions, recipient validation, and scheduling. Prompt text is not a security boundary. |
| `src/memory/threads.js` | Keep concurrent topics, a foreground pointer, explicit commitments, read-time cooling, and bounded in-memory views. | Persist state, arbitrate ambiguous attribution, summarize, and render context. |
| `src/memory/keywords.js` | Extract Chinese n-grams and English keywords without loading a database. | Assess retrieval quality on the host's languages and corpus. This is a heuristic, not a semantic classifier. |
| `src/privacy/write-policy.js` | Prepare supported conversation, thread, action-log, and audit fields before persistence; propagate private provenance through thread merges. | Validate policies and safe metadata, supply approved summaries, and route every write through the appropriate preparation function. |

The runtime modules and keyword/privacy modules have no imports. `threads.js`
imports only the recovered keyword and privacy modules. There are no external
runtime dependencies. This package is not wired into UAEK's Python core, CLI,
HTTP API, or MCP server.

## Run the local checks

Use Node.js with its built-in test runner; no install step is required:

```bash
cd examples/recovered/bailongma
node --test src/test-background-budget.js tests/*.test.js
```

The added tests check source hashes and dependency closure, budget selection,
heartbeat text construction, thread time boundaries and commitment transitions,
merge/eviction behavior, and supported privacy field transformations. The original
budget test is also executed unchanged. This is **static extraction plus local
unit validation**. It does not establish live host integration, model behavior,
privacy enforcement across an application, retrieval quality, or a performance
advantage. No Electron, SQLite, network, or model is invoked.

## Integration constraints

- Budget values are policy defaults from the source project, not calibrated
  limits for every agent. `maxRounds: null` requires an explicit host interpretation.
- Thread functions mutate caller-owned state and generate IDs using wall-clock
  time and randomness. Cooling can be evaluated with an explicit `now`; eviction
  only removes entries from memory. The host must persist before eviction if it
  needs durable recovery. Existing source comments mention other BaiLongma modules
  and design documents that are outside this extraction.
- Privacy preparation covers specific fields, not arbitrary object schemas.
  Unrecognized or missing policies often pass data through; `allowMemoryWrite`
  defaults to allowing writes. Select and validate the policy before calling it.
  Conversation metadata and some thread fields are retained, so callers must
  supply safe metadata and must not place raw content in extra fields.
- Private thread provenance uses non-enumerable in-memory properties. Mark private
  state before merging, then prepare the live objects before serialization; a
  JSON round trip or object spread can lose those markers. Approved summaries
  are trusted input, not automatically checked for sensitive content.
- The heartbeat builder only returns text. Its references to `send_message`,
  `find_tool`, and `set_tick_interval` require host implementations and permissions.

The desktop shell, full agent loop, database, model configuration, delivery stack,
SceneStore, and application integration tests are intentionally outside this
reference package. New tests and documentation in this directory are covered by
UAEK's [MIT license](../../../LICENSE); the recovered code retains its own original
MIT notice in [LICENSE](LICENSE).
