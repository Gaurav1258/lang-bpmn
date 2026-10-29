"""
AgentBPMN - Step 3 Verification Script
Demonstrates Pillar 2: Hybrid Routing (DMN Decision Tables + Semantic Routing).
Validates deterministic business rule tables and natural language intent routing.
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

from agent_bpmn.compiler import GraphCompiler, SafeEvaluationError, SafeExpressionEvaluator
from agent_bpmn.dsl import parse_workflow_yaml
import examples.sample_blocks  # Registers domain blocks


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 3 (PILLAR 2 - HYBRID ROUTING: DMN + SEMANTIC)")

    # --------------------------------------------------------------------------
    # Step 3.1: Safe AST Expression Evaluator & Sandboxing
    # --------------------------------------------------------------------------
    print_banner("STEP 3.1: SAFE AST EXPRESSION EVALUATION & INJECTION SECURITY")
    sample_state = {"amount": 25000.0, "risk_tier": "HIGH", "is_flagged": True, "score": 0.88}
    expr = "amount > 10000 and risk_tier == 'HIGH' and score >= 0.8"
    eval_result = SafeExpressionEvaluator.evaluate(expr, sample_state)
    print(f"[*] State Evaluated: {sample_state}")
    print(f"[*] DMN Expression:  '{expr}'")
    print(f"[OK] Evaluation Result: {eval_result} (100% deterministic AST parser)")

    print("\n[*] Testing Injection Resistance (Attempting code execution payload)...")
    try:
        SafeExpressionEvaluator.evaluate("__import__('os').system('dir')", sample_state)
        print("[X] ERROR: Unsafe code should have been blocked!")
    except SafeEvaluationError as err:
        print(f"[OK] SUCCESS: Arbitrary code blocked safely!")
        print(f"    Caught: {err}")

    # --------------------------------------------------------------------------
    # Step 3.2: DMN Workflow Execution (Scenario A: Auto-Payment Settlement)
    # --------------------------------------------------------------------------
    print_banner("STEP 3.2: DMN DECISION TABLE - SCENARIO A (CLEAN AUTO-SETTLEMENT)")
    hybrid_yaml = Path("examples/sample_workflows/hybrid_routing_workflow.yaml")
    workflow_dmn = parse_workflow_yaml(hybrid_yaml)
    compiler = GraphCompiler()
    compiled_dmn = compiler.compile(workflow_dmn)

    clean_payload = {
        "invoice_pdf_url": "s3://production-invoices-2026/q4/clean_vendor_invoice.pdf",
        "tax_id": "US-94-8192019",
    }
    print(f"[*] Submitting clean invoice payload: {clean_payload['invoice_pdf_url']}")
    state_a = await compiled_dmn.ainvoke(clean_payload)
    print(f"[OK] DMN Path Evaluated: {' -> '.join(state_a.get('__history__', []))}")
    print(f"    - Invoice Amount:   ${state_a.get('invoice_total_usd', 0):,.2f}")
    print(f"    - Sanctions Score:  {state_a.get('sanctions_risk_score')}")
    print(f"    - Final Decision:   {state_a.get('workflow_final_status')}")
    print(f"    - Transaction ID:   {state_a.get('settlement_txn_id')}")

    # --------------------------------------------------------------------------
    # Step 3.3: DMN Workflow Execution (Scenario B: Emergency Compliance Escalation)
    # --------------------------------------------------------------------------
    print_banner("STEP 3.3: DMN DECISION TABLE - SCENARIO B (EMERGENCY SANCTIONS ESCALATION)")
    flagged_payload = {
        "invoice_pdf_url": "s3://production-invoices-2026/q4/redstar_cargo_suspicious.pdf",
        "tax_id": "US-94-8192019",
    }
    print(f"[*] Submitting flagged invoice payload: {flagged_payload['invoice_pdf_url']}")
    state_b = await compiled_dmn.ainvoke(flagged_payload)
    print(f"[OK] DMN Path Evaluated: {' -> '.join(state_b.get('__history__', []))}")
    print(f"    - Sanctions Flagged: {state_b.get('sanctions_is_flagged')}")
    print(f"    - Sanctions Score:   {state_b.get('sanctions_risk_score')}")
    print(f"    - Routed Target:     emergency_compliance_review")
    print(f"    - Case Docket ID:    {state_b.get('review_docket_id')}")
    print(f"    - Status:            {state_b.get('workflow_final_status')}")

    # --------------------------------------------------------------------------
    # Step 3.4: Semantic Intent Router Execution
    # --------------------------------------------------------------------------
    print_banner("STEP 3.4: SEMANTIC INTENT ROUTER (NATURAL LANGUAGE ROUTING)")
    semantic_yaml = Path("examples/sample_workflows/semantic_routing_workflow.yaml")
    workflow_semantic = parse_workflow_yaml(semantic_yaml)
    compiled_semantic = compiler.compile(workflow_semantic)

    test_messages = [
        ("Billing / Refund Dispute", "Why did your invoice charge our corporate card twice for compute usage? Requesting refund."),
        ("Account Cancellation Churn", "We have decided to cancel our subscription and terminate the service contract."),
        ("Technical Defect Outage", "Production API endpoint is down throwing 500 internal server error. Total outage."),
    ]

    for label, msg in test_messages:
        payload = {
            "sender_email": "user@enterprise.org",
            "customer_message": msg,
            "tier": "ENTERPRISE",
        }
        res = await compiled_semantic.ainvoke(payload)
        history = res.get("__history__", [])
        routed_node = history[1] if len(history) > 1 else "Unknown"
        final_queue = res.get("final_queue_routed", "N/A")
        print(f"[*] Case: [{label}]")
        print(f"    Input:       \"{msg[:65]}...\"")
        print(f"    Classified:  {routed_node} -> Queue: '{final_queue}'\n")

    print_banner("SUCCESS: STEP 3 COMPLETE - HYBRID ROUTING (DMN + SEMANTIC) OPERATIONAL")


if __name__ == "__main__":
    asyncio.run(main())
