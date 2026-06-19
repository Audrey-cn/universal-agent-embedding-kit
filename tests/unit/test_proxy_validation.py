"""Tests for GitHub-derived proxy validation when direct baseline is unavailable."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.cli import main


def test_proxy_validation_matrix_documents_github_practices():
    """Proxy validation should cite public benchmark practices, not invented claims."""
    from src.proxy_validation import build_proxy_validation_matrix, run_proxy_validation

    matrix = build_proxy_validation_matrix()
    source_urls = {source["url"] for source in matrix["sources"]}

    assert "https://github.com/swe-bench/SWE-bench" in source_urls
    assert "https://github.com/princeton-pli/hal-harness" in source_urls
    assert "https://github.com/StonyBrookNLP/appworld" in source_urls
    assert "https://github.com/safety-research/impossiblebench" in source_urls
    assert len(matrix["dimensions"]) >= 6

    result = run_proxy_validation(iterations=1)

    assert result["status"] == "completed"
    assert result["direct_baseline"]["status"] == "retired_unavailable"
    assert result["recommended_score"] == 88
    assert result["score_delta"] == 6
    assert result["checks"]
    assert all(check["status"] == "pass" for check in result["checks"] if check["required"])


def test_benchmark_proxy_suite_writes_side_validation_evidence(tmp_path: Path):
    """Benchmark proxy suite should produce score evidence without claiming direct baseline."""
    from src.benchmark import run_benchmark, write_benchmark_result

    result = run_benchmark("proxy", iterations=1)

    assert result["suite"] == "proxy"
    assert result["scorecard"]["previous_score"] == 82
    assert result["scorecard"]["current_score"] == 88
    assert "F007_PROXY_VALIDATED" in result["scorecard"]["resolved_findings"]
    assert "DIRECT_RETIRED_MODEL_UNAVAILABLE" in result["scorecard"]["remaining_findings"]
    assert result["proxy_validation"]["direct_baseline"]["status"] == "retired_unavailable"
    assert result["external_baseline"]["status"] == "not_configured"

    output_path = write_benchmark_result(result, tmp_path / "benchmark-proxy.json")
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["scorecard"]["current_score"] == 88
    assert data["proxy_validation"]["matrix"]["sources"]


def test_cli_benchmark_proxy_suite(tmp_path: Path):
    """CLI should expose the proxy validation suite as a first-class benchmark."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["benchmark", "--suite", "proxy", "--iterations", "1", "--output", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Score" in result.output
    assert "Proxy validation" in result.output

    output_path = tmp_path / "benchmark-proxy.json"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["scorecard"]["current_score"] == 88
    assert data["proxy_validation"]["status"] == "completed"
