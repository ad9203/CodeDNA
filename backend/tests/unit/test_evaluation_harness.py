"""Unit tests for the Memory Evaluation Harness."""

from pathlib import Path

import pytest

from app.evaluation.runner import MemoryEvaluationRunner


@pytest.mark.asyncio
async def test_scenario_a_stateless():
    runner = MemoryEvaluationRunner()
    res = await runner.run_scenario_a_stateless()

    assert res["memories_recalled"] == 0
    assert res["findings_count"] >= 1
    assert res["critical_violations_caught"] is False
    assert "FAILED" in res["assessment"]


@pytest.mark.asyncio
async def test_scenario_b_with_memory():
    runner = MemoryEvaluationRunner()
    res = await runner.run_scenario_b_with_memory()

    assert res["memories_recalled"] >= 1
    assert res["critical_violations_caught"] is True
    assert "PASSED" in res["assessment"]
    findings = res["findings"]
    assert any(f["severity"] == "critical" for f in findings)
    assert any("repository" in f["title"].lower() for f in findings)


@pytest.mark.asyncio
async def test_scenario_c_learning_loop():
    runner = MemoryEvaluationRunner()
    res = await runner.run_scenario_c_learning_loop()

    assert res["memories_recalled"] >= 1
    assert res["false_positive_suppressed"] is True
    assert res["findings_count"] == 0
    assert "PASSED" in res["assessment"]


@pytest.mark.asyncio
async def test_full_evaluation_generates_report(tmp_path: Path):
    runner = MemoryEvaluationRunner()
    out_file = tmp_path / "eval_report.md"

    res = await runner.run_full_evaluation(output_path=out_file)

    assert "scenario_a" in res
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# CodeDNA Memory Evaluation Report" in content
    assert "Scenario A" in content
    assert "Scenario B" in content
    assert "Scenario C" in content
    assert "Hindsight Persistent Memory" in content
