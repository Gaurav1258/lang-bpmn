from pathlib import Path
import pytest

from agent_bpmn.compiler import (
    BudgetExceededError,
    GraphCompiler,
    LoopIterationLimitExceeded,
)
from agent_bpmn.dsl import (
    NodeType,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowGuardrails,
    WorkflowMetadata,
    WorkflowNode,
    parse_workflow_yaml,
)
from agent_bpmn.runtime import NodeTelemetryRecord, RunTelemetryRecord, TelemetryAggregator
import agent_bpmn.blocks.builtin  # Registers domain blocks


def test_step5_1_budget_cap_guardrail_trips_on_overspend():
    """Verify workflow execution halts immediately when accumulated spend exceeds budget cap."""
    yaml_path = Path("examples/sample_workflows/guardrailed_loop_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    # Set very tight budget cap ($0.010 USD). invoice_extractor costs $0.0150 USD.
    wf.guardrails.max_total_budget_usd = 0.010

    compiler = GraphCompiler()
    compiled = compiler.compile(wf)

    with pytest.raises(BudgetExceededError) as exc_info:
        compiled.invoke({
            "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
            "tax_id": "US-94-8192019",
        })

    err = exc_info.value
    assert err.node_id == "extract_invoice"
    assert err.current_cost >= 0.015
    assert err.max_budget == 0.010


def test_step5_2_cyclic_loop_iteration_guardrail_trips():
    """Verify cyclic loop circuit breaker trips when loop iteration count exceeds max_loop_iterations."""
    yaml_path = Path("examples/sample_workflows/guardrailed_loop_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    # Set budget high enough so loop limit trips first
    wf.guardrails.max_total_budget_usd = 5.0
    wf.guardrails.max_loop_iterations = 3
    for n in wf.nodes:
        if n.id == "extract_invoice":
            n.max_retries = 3

    compiler = GraphCompiler()
    compiled = compiler.compile(wf)

    # invoice_extractor returns confidence 0.98 which is < 0.99, triggering the loop
    with pytest.raises(LoopIterationLimitExceeded) as exc_info:
        compiled.invoke({
            "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
            "tax_id": "US-94-8192019",
        })

    err = exc_info.value
    assert err.node_id == "extract_invoice"
    assert err.current_iterations == 4
    assert err.max_iterations == 3


@pytest.mark.asyncio
async def test_step5_3_telemetry_captures_run_records():
    """Verify telemetry aggregator automatically records run records upon completion."""
    yaml_path = Path("examples/sample_workflows/hybrid_routing_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    local_telemetry = TelemetryAggregator()
    compiler = GraphCompiler(telemetry_aggregator=local_telemetry)
    compiled = compiler.compile(wf)

    payload = {
        "invoice_pdf_url": "s3://production-invoices-2026/q4/clean_vendor_invoice.pdf",
        "tax_id": "US-94-8192019",
    }
    await compiled.ainvoke(payload)

    runs = local_telemetry._runs.get("hybrid_invoice_routing_flow", [])
    assert len(runs) == 1
    run = runs[0]
    assert run.status == "COMPLETED"
    assert run.total_cost_usd > 0
    assert len(run.node_records) >= 2


def test_step5_4_heatmap_computes_p95_and_averages():
    """Verify Process Intelligence Heatmap aggregates latency, P95, and cost per node."""
    aggregator = TelemetryAggregator()
    wf_id = "test_heatmap_wf"

    # Simulate 10 runs with varying latencies
    latencies = [100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 3200.0]  # P95 outlier
    for idx, lat in enumerate(latencies):
        rec = RunTelemetryRecord(
            run_id=f"run_{idx}",
            workflow_id=wf_id,
            total_cost_usd=0.015,
            total_duration_ms=lat,
            node_records=[
                NodeTelemetryRecord(node_id="heavy_node", latency_ms=lat, cost_usd=0.015)
            ],
        )
        aggregator.record_run(rec)

    heatmap = aggregator.get_heatmap(wf_id)
    assert heatmap.total_runs == 10
    metric = heatmap.node_metrics["heavy_node"]

    assert metric.call_count == 10
    assert metric.avg_latency_ms == 590.0  # Sum / 10
    assert metric.p95_latency_ms >= 500.0  # P95 captures high percentile
    assert metric.avg_cost_usd == 0.015
    assert metric.bottleneck_level == "CRITICAL"  # High P95 > 2500ms triggers CRITICAL


def test_step5_5_heatmap_computes_human_override_rate():
    """Verify Process Intelligence Heatmap accurately calculates Human Override Rate (%)."""
    aggregator = TelemetryAggregator()
    wf_id = "test_hitl_heatmap"

    actions = ["APPROVE", "APPROVE", "EDIT_AND_APPROVE", "REJECT"]  # 2 overrides out of 4 = 50%
    for idx, act in enumerate(actions):
        rec = RunTelemetryRecord(
            run_id=f"run_h_{idx}",
            workflow_id=wf_id,
            node_records=[
                NodeTelemetryRecord(node_id="compliance_review_node", latency_ms=1200.0, cost_usd=0.0, human_action=act)
            ],
        )
        aggregator.record_run(rec)

    heatmap = aggregator.get_heatmap(wf_id)
    metric = heatmap.node_metrics["compliance_review_node"]
    assert metric.call_count == 4
    assert metric.human_override_rate == 0.50

