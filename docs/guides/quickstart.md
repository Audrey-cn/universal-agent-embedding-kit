# UAEK Quickstart

Install the local package:

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

Run a workflow config:

```bash
.venv/bin/uaek workflow --config tests/fixtures/workflow.yaml
```

Use memory:

```bash
.venv/bin/uaek memory add "Decision: keep workflow actions safe" --layer l3 --tag decision
.venv/bin/uaek memory query "workflow actions" --layer l3
```

Run a project skill:

```bash
.venv/bin/uaek skill list
.venv/bin/uaek skill run verification-framework
```

Run the local Agent Harness:

```bash
.venv/bin/uaek run "implement external adapter plan" --output /tmp/uaek-run.json
.venv/bin/uaek run "implement external adapter plan" --config config/default.yaml --log-file /tmp/uaek-run.jsonl --output /tmp/uaek-run.json
```

Generate local benchmark evidence:

```bash
.venv/bin/uaek benchmark --suite quick --iterations 2 --output benchmarks/results
.venv/bin/uaek benchmark --suite quick --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
.venv/bin/uaek benchmark --suite proxy --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
.venv/bin/uaek benchmark --suite adapter --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
.venv/bin/uaek platform discover --output benchmarks/results/platform-discovery.json
.venv/bin/uaek benchmark --suite platform --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
.venv/bin/uaek benchmark --suite excellence --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
.venv/bin/uaek benchmark --suite live_matrix --iterations 2 --baseline benchmarks/baselines/fable5.example.json --output benchmarks/results
```

Run a command-backed external Agent Adapter:

```bash
.venv/bin/uaek adapter run "adapter smoke task" \
  --command .venv/bin/python \
  --command -c \
  --command 'import json,sys; p=json.load(sys.stdin); print(json.dumps({"success": True, "output": p["task"]}))' \
  --output /tmp/uaek-adapter.json \
  --trace /tmp/uaek-adapter.jsonl
```

Run quality gates:

```bash
.venv/bin/python -m ruff check src api mcp tests
.venv/bin/python -m mypy src api mcp
.venv/bin/python -m pytest
```
