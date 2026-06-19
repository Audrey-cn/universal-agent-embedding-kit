# Capability Batch Runs

`uaek capability batch` reruns multiple provider capability recipes from one JSON
manifest. It is intended for auditable local reruns where each provider may need
an isolated writable HOME plus explicit config seeds.

## Manifest

```json
{
  "artifact_dir": "benchmarks/results/capability-runs",
  "provider_home_root": "/tmp/uaek-provider-homes",
  "timeout": 120,
  "providers": [
    {
      "provider": "codex",
      "command": [
        "/Applications/Codex.app/Contents/Resources/codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only"
      ],
      "output_mode": "plain",
      "provider_home_seed_paths": [
        "~/.codex/auth.json",
        "~/.codex/config.toml"
      ]
    },
    {
      "provider": "mimo_code",
      "command": [
        "/Users/audrey/.mimocode/bin/mimo",
        "run",
        "--pure",
        "--dir",
        "/tmp",
        "--format",
        "json"
      ],
      "output_mode": "mimo_jsonl"
    }
  ]
}
```

Each provider writes `<artifact_dir>/<provider>-capability-run.json` unless
`artifact_name` is set on that provider recipe.

## Run

Validate a manifest in CI without touching provider CLIs or secrets:

```bash
uaek capability batch benchmarks/manifests/capability-batch.ci-example.json \
  --dry-run \
  --output /tmp/uaek-capability-manifest-validation.json
```

Run a real local batch:

```bash
uaek capability batch capability-manifest.json \
  --matrix-output benchmarks/results/capability-matrix.json \
  --output benchmarks/results/capability-batch.json
```

Use `provider_home_seed_paths` only for explicit config or auth files required by
that provider. File contents are copied into the isolated HOME and are not
printed by UAEK, but they should still be treated as local secrets.

`--dry-run` checks structure, output modes, duplicate providers, resolved
provider HOME paths, and expected-provider coverage. Missing seed files are
reported as warnings so a CI template can stay secret-free.
