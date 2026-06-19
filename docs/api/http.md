# UAEK HTTP API

Start locally:

```bash
.venv/bin/python -m api.server localhost 8000
```

## Endpoints

### `GET /health`

Returns:

```json
{"status": "ok"}
```

### `POST /effort`

Request:

```json
{"task_description": "implement auth module"}
```

### `POST /workflow`

Request:

```json
{
  "id": "api-workflow",
  "type": "sequential",
  "tasks": [
    {"id": "echo", "name": "Echo", "action": "echo", "args": ["hello api"]}
  ]
}
```

The response includes `success`, task status lists, and `task_results`.

### `POST /memory`

Add:

```json
{"action": "add", "content": "Architecture decision", "layer": "l3", "tags": ["decision"]}
```

Query:

```json
{"action": "query", "query": "Architecture", "layer": "l3"}
```

Other actions: `compress`, `persist`, `restore`, `clear`, `stats`.
