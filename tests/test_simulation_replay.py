from pathlib import Path
import pytest

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.runtime import NodeTelemetryRecord, RunTelemetryRecord, TelemetryAggregator
from agent_bpmn.simulation import (
    CandidateCaseResult,
    HistoricalCase,
    RouteShiftMetric,
    SimulationDataset,
    SimulationEngine,
    SimulationImpactDiff,
    SimulationReport,
)
import agent_bpmn.blocks.builtin  # Registers domain blocks


def _create_mock_production_dataset() -> SimulationDataset:
    """Creates a representative dataset of 10 historical production invoice cases."""
    dataset = SimulationDataset(
        dataset_id="dataset_q3_invoices",
        workflow_id="hybrid_invoice_routing_flow",
        description="Historical Q3 production invoice run traces",
    )

    # 8 standard clean invoices (<$50k) that were auto-settled in baseline production
    for i in range(8):
        dataset.add_case(
            HistoricalCase(
                case_id=f"case_clean_{i}",
                input_payload={
                    "invoice_pdf_url": f"s3://invoices-2026/q3/clean_vendor_{i}.pdf",
                    "tax_id": f"US-94-819201{i}",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "auto_payment_settlement"],
                baseline_terminal_node="auto_payment_settlement",
                baseline_cost_usd=0.019,
                baseline_duration_ms=120.0,
                baseline_status="COMPLETED",
            )
        )

    # 2 high-risk invoices that were routed to emergency compliance review in baseline
    for i in range(2):
        dataset.add_case(
            HistoricalCase(
                case_id=f"case_flagged_{i}",
                input_payload={
                    "invoice_pdf_url": f"s3://invoices-2026/q3/suspicious_vendor_{i}.pdf",
                    "tax_id": f"US-94-999900{i}",
                    "sanctions_is_flagged": True,
                    "sanctions_risk_score": 0.95,
                    "sanctions_note": "OFAC Watchlist Match",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "emergency_compliance_review"],
                baseline_terminal_node="emergency_compliance_review",
                baseline_cost_usd=0.034,
                baseline_duration_ms=185.0,
                baseline_status="COMPLETED",
            )
        )

    return dataset


def test_step6_1_dataset_creation_and_telemetry_extraction():
    """Verify SimulationDataset instantiation and extraction from TelemetryAggregator."""
    telemetry = TelemetryAggregator()
    wf_id = "test_wf"

    telemetry.record_run(
        RunTelemetryRecord(
            run_id="run_001",
            workflow_id=wf_id,
            total_cost_usd=0.02,
            total_duration_ms=150.0,
            node_records=[
                NodeTelemetryRecord(node_id="extract_invoice", latency_ms=100.0, cost_usd=0.015),
                NodeTelemetryRecord(node_id="auto_payment_settlement", latency_ms=50.0, cost_usd=0.005),
            ],
        )
    )

    engine = SimulationEngine()
    dataset = engine.extract_dataset_from_telemetry(telemetry, wf_id)

    assert len(dataset) == 1
    assert dataset.cases[0].case_id == "run_001"
    assert dataset.cases[0].baseline_terminal_node == "auto_payment_settlement"
    assert dataset.cases[0].baseline_cost_usd == 0.02


@pytest.mark.asyncio
async def test_step6_2_sandboxed_candidate_replay_execution():
    """Verify candidate workflow executes all historical cases in sandbox mode without crashing."""
    yaml_path = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(yaml_path)

    dataset = _create_mock_production_dataset()
    engine = SimulationEngine()

    report = await engine.run_simulation(candidate_wf, dataset)

    assert report.diff.total_cases == 10
    assert report.diff.candidate_success_count == 10
    assert report.diff.candidate_failure_count == 0
    assert report.diff.candidate_success_rate == 1.0
    assert report.diff.schema_failures == 0
    assert len(report.case_results) == 10


@pytest.mark.asyncio
async def test_step6_3_impact_diff_detects_route_distribution_shifts():
    """
    Verify impact diff accurately captures route shifts when management tightens compliance policy.
    In baseline: 80% auto-settled, 20% emergency review.
    In candidate: invoice total ($14,500) > lowered threshold ($10,000), so clean invoices now route to emergency review!
    """
    yaml_path = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(yaml_path)

    dataset = _create_mock_production_dataset()
    engine = SimulationEngine()

    report = await engine.run_simulation(candidate_wf, dataset)
    diff = report.diff

    # Baseline was 80% auto-settlement (8/10), 20% emergency review (2/10)
    assert diff.route_shifts["auto_payment_settlement"].baseline_pct == 80.0
    assert diff.route_shifts["emergency_compliance_review"].baseline_pct == 20.0

    # Under tightened policy ($14.5k > $10k), all 10 cases route to emergency review (100%)
    assert diff.route_shifts["emergency_compliance_review"].candidate_pct == 100.0
    assert diff.route_shifts["emergency_compliance_review"].shift_pct_points == +80.0

    assert diff.route_shifts["auto_payment_settlement"].candidate_pct == 0.0
    assert diff.route_shifts["auto_payment_settlement"].shift_pct_points == -80.0

    # Ensure critical findings identified the massive shift
    assert any("Significant route shift on 'emergency_compliance_review'" in f for f in diff.critical_findings)


@pytest.mark.asyncio
async def test_step6_4_financial_cost_and_latency_deltas():
    """Verify simulation computes accurate cost and latency delta calculations."""
    yaml_path = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(yaml_path)

    dataset = _create_mock_production_dataset()
    engine = SimulationEngine()

    report = await engine.run_simulation(candidate_wf, dataset)
    diff = report.diff

    # Baseline cost: (8 * 0.019 + 2 * 0.034) / 10 = 0.0220 USD
    assert diff.baseline_avg_cost_usd == 0.0220
    assert diff.candidate_avg_cost_usd > 0
    assert diff.cost_delta_usd != 0.0

    # Baseline latency: (8 * 120 + 2 * 185) / 10 = 133.0 ms
    assert diff.baseline_avg_latency_ms == 133.0
    assert diff.candidate_avg_latency_ms > 0


@pytest.mark.asyncio
async def test_step6_5_guardrail_trip_detection_during_replay():
    """Verify that if candidate workflow trips budget caps on historical cases, simulation records guardrail trips."""
    yaml_path = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(yaml_path)

    # Artificially strangle budget to $0.010 USD (lower than invoice_extractor's $0.0150)
    candidate_wf.guardrails.max_total_budget_usd = 0.010

    dataset = _create_mock_production_dataset()
    engine = SimulationEngine()

    report = await engine.run_simulation(candidate_wf, dataset)
    diff = report.diff

    assert diff.candidate_guardrail_trip_count == 10
    assert diff.candidate_success_count == 0
    assert diff.candidate_success_rate == 0.0
    assert any("tripped guardrail circuit breakers" in f for f in diff.critical_findings)


@pytest.mark.asyncio
async def test_step6_6_report_markdown_and_summary_generation():
    """Verify simulation report produces a clean Markdown executive summary suitable for Git PRs."""
    yaml_path = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(yaml_path)

    dataset = _create_mock_production_dataset()
    engine = SimulationEngine()

    report = await engine.run_simulation(candidate_wf, dataset)
    md = report.to_markdown()

    assert "# 🧪 Pre-Flight Simulation Report" in md
    assert "Executive Summary Diff" in md
    assert "Route Distribution Shifts" in md
    assert "emergency_compliance_review" in md
    assert "auto_payment_settlement" in md

