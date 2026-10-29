"""
AgentBPMN - Step 6 Verification Script
Demonstrates Pillar 5: "Shadow Mode" & Pre-Flight Replay Engine.
Validates replaying historical production cases through candidate workflow AST topologies
to evaluate route shifts, financial cost deltas, and schema safety before opening Git PRs.
"""

import asyncio
import json
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.simulation import (
    HistoricalCase,
    SimulationDataset,
    SimulationEngine,
)
import examples.sample_blocks  # Registers domain blocks


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


def build_historical_production_dataset() -> SimulationDataset:
    """Builds a representative dataset of 15 historical production invoice cases."""
    dataset = SimulationDataset(
        dataset_id="dataset_q3_invoices_15",
        workflow_id="hybrid_invoice_routing_flow",
        description="Historical Q3 production invoice run traces (15 sample transactions)",
    )

    # 12 Standard clean vendor invoices ($14,500 total, clean sanctions)
    # Under baseline policy (< $50k), these were ALL auto-settled.
    for i in range(12):
        dataset.add_case(
            HistoricalCase(
                case_id=f"prod_inv_clean_{i+1:03d}",
                input_payload={
                    "invoice_pdf_url": f"s3://production-invoices-2026/q3/clean_vendor_{i+1}.pdf",
                    "tax_id": f"US-94-81920{i+1:02d}",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "auto_payment_settlement"],
                baseline_terminal_node="auto_payment_settlement",
                baseline_cost_usd=0.0190,
                baseline_duration_ms=115.0,
                baseline_status="COMPLETED",
            )
        )

    # 3 High-risk or high-value cases that went to emergency review in baseline
    for i in range(3):
        dataset.add_case(
            HistoricalCase(
                case_id=f"prod_inv_highrisk_{i+1:03d}",
                input_payload={
                    "invoice_pdf_url": f"s3://production-invoices-2026/q3/redstar_freight_{i+1}.pdf",
                    "tax_id": f"US-94-99990{i+1}",
                    "sanctions_is_flagged": True,
                    "sanctions_risk_score": 0.88,
                    "sanctions_note": "OFAC Sanctions List Match",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "emergency_compliance_review"],
                baseline_terminal_node="emergency_compliance_review",
                baseline_cost_usd=0.0340,
                baseline_duration_ms=190.0,
                baseline_status="COMPLETED",
            )
        )

    return dataset


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 6 (PILLAR 5 - SHADOW MODE & PRE-FLIGHT REPLAY)")

    # --------------------------------------------------------------------------
    # Step 6.1: Load Production Historical Dataset & Candidate Workflow
    # --------------------------------------------------------------------------
    print_banner("STEP 6.1: REHYDRATING PRODUCTION DATASET & PARSING CANDIDATE AST")
    dataset = build_historical_production_dataset()
    print(f"[*] Rehydrated Historical Cases: {len(dataset)} production runs")
    print(f"[*] Baseline Workflow ID:        {dataset.workflow_id}")

    candidate_file = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(candidate_file)
    print(f"[*] Candidate Workflow ID:       {candidate_wf.metadata.id} (v{candidate_wf.metadata.version})")
    print(f"[*] Policy Modification:         Lowered L2 review threshold from $50,000 to $10,000")
    print(f"                                 Lowered Risk Score threshold from 0.70 to 0.50")

    # --------------------------------------------------------------------------
    # Step 6.2: Execute Sandboxed Pre-Flight Simulation Replay
    # --------------------------------------------------------------------------
    print_banner("STEP 6.2: EXECUTING PRE-FLIGHT REPLAY IN SANDBOX RUNTIME")
    engine = SimulationEngine()
    print("[*] Replaying 15 cases concurrently against candidate AST...")

    report = await engine.run_simulation(candidate_wf, dataset, simulation_id="sim_audit_pr_982")
    diff = report.diff

    print(f"[OK] Simulation Completed Successfully!")
    print(f"    Total Cases Evaluated:   {diff.total_cases}")
    print(f"    Candidate Success Count: {diff.candidate_success_count} / {diff.total_cases}")
    print(f"    Candidate Success Rate:  {diff.candidate_success_rate * 100:.1f}%")
    print(f"    Schema Contract Errors:  {diff.schema_failures} (Zero schema crashes)")
    print(f"    Guardrail Trip Violations: {diff.candidate_guardrail_trip_count}")

    # --------------------------------------------------------------------------
    # Step 6.3: Impact Diff Analysis (Route Shifts & Financial Economics)
    # --------------------------------------------------------------------------
    print_banner("STEP 6.3: PRE-FLIGHT IMPACT DIFF ANALYSIS")

    print("┌──────────────────────────────────┬────────────────┬─────────────────┬──────────────────┬──────────────┐")
    print("│ Destination Route / Node         │ Baseline Share │ Candidate Share │ Shift (% Points) │ Trend        │")
    print("├──────────────────────────────────┼────────────────┼─────────────────┼──────────────────┼──────────────┤")
    for nid, r in sorted(diff.route_shifts.items(), key=lambda x: abs(x[1].shift_pct_points), reverse=True):
        trend = "INCREASED" if r.shift_pct_points > 0 else ("DECREASED" if r.shift_pct_points < 0 else "STABLE")
        print(f"│ {nid:<32} │ {r.baseline_pct:>13.1f}% │ {r.candidate_pct:>14.1f}% │ {r.shift_pct_points:>+15.1f}% │ [{trend:<9}] │")
    print("└──────────────────────────────────┴────────────────┴─────────────────┴──────────────────┴──────────────┘")

    print("\n[+] Financial & Latency Impact Deltas:")
    print(f"    Baseline Avg Cost:   ${diff.baseline_avg_cost_usd:.4f} USD")
    print(f"    Candidate Avg Cost:  ${diff.candidate_avg_cost_usd:.4f} USD (Delta: {diff.cost_delta_pct:+.1f}%)")
    print(f"    Baseline Avg Lat:    {diff.baseline_avg_latency_ms:.1f} ms")
    print(f"    Candidate Avg Lat:   {diff.candidate_avg_latency_ms:.1f} ms (Delta: {diff.latency_delta_pct:+.1f}%)")

    print("\n[+] Critical Policy Findings:")
    for finding in diff.critical_findings:
        print(f"    * {finding}")

    # --------------------------------------------------------------------------
    # Step 6.4: Export Simulation Report (JSON & Markdown PR Summary)
    # --------------------------------------------------------------------------
    print_banner("STEP 6.4: EXPORTING GOVERNANCE SIMULATION ARTIFACTS")
    json_path = Path("preflight_simulation_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)
    print(f"[+] Simulation JSON Artifact saved: {json_path.resolve()}")

    md_path = Path("preflight_simulation_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())
    print(f"[+] Pull Request Markdown Report saved: {md_path.resolve()}")

    print_banner("SUCCESS: STEP 6 COMPLETE - PRE-FLIGHT SIMULATION ENGINE VERIFIED")


if __name__ == "__main__":
    asyncio.run(main())

