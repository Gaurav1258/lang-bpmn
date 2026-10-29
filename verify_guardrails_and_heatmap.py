"""
AgentBPMN - Step 5 Verification Script
Demonstrates Pillar 4: Cost, Latency & Loop Guardrails as Visual Knobs + Process Intelligence Heatmap.
Validates cyclic loop limits, hard USD budget circuit breakers, and Camunda Optimize-style telemetry overlays.
"""

import asyncio
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent_bpmn.compiler import (
    BudgetExceededError,
    GraphCompiler,
    LoopIterationLimitExceeded,
)
from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.runtime import NodeTelemetryRecord, RunTelemetryRecord, TelemetryAggregator
import examples.sample_blocks  # Registers domain blocks


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 5 (PILLAR 4 - LOOP & BUDGET GUARDRAILS + HEATMAP)")

    # --------------------------------------------------------------------------
    # Step 5.1: Unit Economic Budget Cap Circuit Breaker
    # --------------------------------------------------------------------------
    print_banner("STEP 5.1: HARD BUDGET CAP CIRCUIT BREAKER ($ USD SPEND LIMIT)")
    yaml_file = Path("examples/sample_workflows/guardrailed_loop_workflow.yaml")
    wf_budget = parse_workflow_yaml(yaml_file)

    # Tighten budget cap to $0.010 USD. invoice_extractor costs $0.0150 USD.
    wf_budget.guardrails.max_total_budget_usd = 0.010
    compiler = GraphCompiler()
    compiled_budget = compiler.compile(wf_budget)

    print(f"[*] Configured Budget Cap Guardrail: ${wf_budget.guardrails.max_total_budget_usd:.4f} USD")
    print(f"[*] Block 'finance.invoice_extractor' estimated spend: $0.0150 USD")
    print("[*] Dispatching workflow execution...")

    try:
        await compiled_budget.ainvoke({
            "invoice_pdf_url": "s3://production-invoices-2026/q4/invoice.pdf",
            "tax_id": "US-94-8192019",
        })
        print("[X] ERROR: Execution should have tripped budget circuit breaker!")
    except BudgetExceededError as err:
        print(f"\n[OK] SUCCESS: Hard-Stop Budget Circuit Breaker Tripped!")
        print(f"    Caught: {err.__class__.__name__}")
        print(f"    Spend:  ${err.current_cost:.4f} USD > Limit: ${err.max_budget:.4f} USD")
        print(f"    Node:   '{err.node_id}'")

    # --------------------------------------------------------------------------
    # Step 5.2: Cyclic Loop Iteration Guardrail
    # --------------------------------------------------------------------------
    print_banner("STEP 5.2: CYCLIC LOOP ITERATION GUARDRAIL (MAX 3 RETRIES)")
    wf_loop = parse_workflow_yaml(yaml_file)
    wf_loop.guardrails.max_total_budget_usd = 5.0  # Allow sufficient budget
    wf_loop.guardrails.max_loop_iterations = 3
    for n in wf_loop.nodes:
        if n.id == "extract_invoice":
            n.max_retries = 3

    compiled_loop = compiler.compile(wf_loop)
    print(f"[*] Configured Max Loop Iterations: {wf_loop.guardrails.max_loop_iterations} retries")
    print("[*] Triggering cyclic refinement loop (Confidence 0.98 < Threshold 0.99)...")

    try:
        await compiled_loop.ainvoke({
            "invoice_pdf_url": "s3://production-invoices-2026/q4/invoice.pdf",
            "tax_id": "US-94-8192019",
        })
        print("[X] ERROR: Loop limit should have terminated the cycle!")
    except LoopIterationLimitExceeded as err:
        print(f"\n[OK] SUCCESS: Cyclic Loop Guardrail Tripped Safely!")
        print(f"    Caught:     {err.__class__.__name__}")
        print(f"    Iterations: {err.current_iterations} attempts > Max Allowed: {err.max_iterations}")
        print(f"    Node:       '{err.node_id}'")

    # --------------------------------------------------------------------------
    # Step 5.3: Process Intelligence Heatmap Telemetry
    # --------------------------------------------------------------------------
    print_banner("STEP 5.3: PROCESS INTELLIGENCE HEATMAP (CAMUNDA OPTIMIZE STYLE)")
    telemetry = TelemetryAggregator()
    wf_id = "vendor_invoice_and_compliance"

    # Simulate production telemetry records
    print(f"[*] Ingesting production run traces for workflow '{wf_id}'...")
    latencies_node1 = [80.0, 95.0, 110.0, 150.0, 180.0, 2200.0]  # Extraction
    latencies_node2 = [40.0, 45.0, 50.0, 60.0, 55.0, 70.0]        # Screening

    for idx in range(len(latencies_node1)):
        telemetry.record_run(
            RunTelemetryRecord(
                run_id=f"run_prod_{idx}",
                workflow_id=wf_id,
                total_cost_usd=0.019,
                total_duration_ms=latencies_node1[idx] + latencies_node2[idx],
                node_records=[
                    NodeTelemetryRecord(node_id="extract_invoice", latency_ms=latencies_node1[idx], cost_usd=0.015),
                    NodeTelemetryRecord(node_id="check_sanctions", latency_ms=latencies_node2[idx], cost_usd=0.004),
                    NodeTelemetryRecord(node_id="l2_human_review", latency_ms=1800.0, cost_usd=0.0, human_action="EDIT_AND_APPROVE" if idx % 2 == 0 else "APPROVE"),
                ],
            )
        )

    heatmap = telemetry.get_heatmap(wf_id)
    print(f"[+] Total Historical Runs:   {heatmap.total_runs}")
    print(f"[+] Total Aggregate Spend:   ${heatmap.total_cost_usd:.4f} USD")
    print(f"[+] Average Spend per Run:   ${heatmap.avg_run_cost_usd:.4f} USD\n")

    print("┌────────────────────────┬───────┬────────────┬────────────┬─────────────┬──────────────┬────────────┐")
    print("│ Canvas Node ID         │ Calls │ Avg Lat ms │ P95 Lat ms │ Avg Cost ($)│ Override Rate│ Bottleneck │")
    print("├────────────────────────┼───────┼────────────┼────────────┼─────────────┼──────────────┼────────────┤")
    for nid, m in heatmap.node_metrics.items():
        severity_tag = f"[{m.bottleneck_level}]"
        print(f"│ {nid:<22} │ {m.call_count:<5} │ {m.avg_latency_ms:<10.1f} │ {m.p95_latency_ms:<10.1f} │ ${m.avg_cost_usd:<10.4f} │ {m.human_override_rate * 100:<11.0f}% │ {severity_tag:<10} │")
    print("└────────────────────────┴───────┴────────────┴────────────┴─────────────┴──────────────┴────────────┘")

    # --------------------------------------------------------------------------
    # Step 5.4: Export Heatmap Artifact
    # --------------------------------------------------------------------------
    print_banner("STEP 5.4: EXPORT PROCESS INTELLIGENCE HEATMAP JSON")
    heatmap_path = Path("workflow_heatmap.json")
    telemetry.export_heatmap_json(wf_id, filepath=heatmap_path)
    print(f"[+] Heatmap JSON overlay exported to: {heatmap_path.resolve()}")

    print_banner("SUCCESS: STEP 5 COMPLETE - LOOP/BUDGET GUARDRAILS & HEATMAP OPERATIONAL")


if __name__ == "__main__":
    asyncio.run(main())

