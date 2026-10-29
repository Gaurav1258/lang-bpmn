"""
AgentBPMN - Step 2 Verification Script
Demonstrates Phase 2: Declarative Specification (DSL) & LangGraph StateGraph Compiler.
Parses agent-bpmn.yaml, lints topology, compiles to LangGraph, and executes end-to-end.
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

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import WorkflowLinter, dump_workflow_yaml, parse_workflow_yaml
import examples.sample_blocks  # Registers domain blocks in registry


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 2 (PHASE 2 - DECLARATIVE DSL & LANGGRAPH COMPILER)")

    # --------------------------------------------------------------------------
    # Step 2.1: Parse Declarative Specification AST
    # --------------------------------------------------------------------------
    print_banner("STEP 2.1: PARSE DECLARATIVE WORKFLOW SPECIFICATION (YAML AST)")
    yaml_file = Path("examples/sample_workflows/invoice_processing_workflow.yaml")
    print(f"[*] Reading workflow definition from: {yaml_file.resolve()}")
    workflow = parse_workflow_yaml(yaml_file)

    meta = workflow.metadata
    print(f"[+] Workflow ID:         {meta.id}")
    print(f"[+] Name:                {meta.name}")
    print(f"[+] Version:             {meta.version}")
    print(f"[+] Owner Department:    {meta.owner_department}")
    print(f"[+] Budget Cap Guardrail: ${workflow.guardrails.max_total_budget_usd:.2f} USD")
    print(f"[+] Total Nodes:         {len(workflow.nodes)}")
    print(f"[+] Total Edges:         {len(workflow.edges)}")

    for idx, node in enumerate(workflow.nodes, 1):
        print(f"    Node #{idx}: [{node.type.upper()}] '{node.id}' -> Block: '{node.block}'")
        print(f"      Inputs:  {node.input_mapping}")
        print(f"      Outputs: {node.output_mapping}")

    # --------------------------------------------------------------------------
    # Step 2.2: Static Linting & Semantic Validation
    # --------------------------------------------------------------------------
    print_banner("STEP 2.2: STATIC GRAPH LINTING & CONTRACT INTEGRITY CHECK")
    linter = WorkflowLinter()
    lint_res = linter.lint(workflow)
    print(f"[*] Linter Result: Valid = {lint_res.is_valid}")
    if lint_res.warnings:
        for w in lint_res.warnings:
            print(f"    [WARN] {w}")
    if lint_res.errors:
        for e in lint_res.errors:
            print(f"    [ERR] {e}")
    assert lint_res.is_valid, "Linter validation failed!"
    print("[OK] Graph topology, block contracts, and edge endpoints verified cleanly.")

    # --------------------------------------------------------------------------
    # Step 2.3: LangGraph StateGraph Compilation
    # --------------------------------------------------------------------------
    print_banner("STEP 2.3: LANGGRAPH STATEGRAPH COMPILATION")
    print("[*] Translating WorkflowDefinition AST -> LangGraph StateGraph runtime...")
    compiler = GraphCompiler()
    compiled = compiler.compile(workflow)
    print("[OK] Successfully compiled to LangGraph StateGraph!")
    print(f"[+] Runtime Engine: LangGraph CompiledGraph (with dynamic state merging)")

    # --------------------------------------------------------------------------
    # Step 2.4: End-to-End Workflow Execution
    # --------------------------------------------------------------------------
    print_banner("STEP 2.4: END-TO-END EXECUTION THROUGH COMPILED LANGGRAPH")
    initial_input = {
        "invoice_pdf_url": "s3://production-invoices-2026/q4/vendor_apex_9812.pdf",
        "tax_id": "US-94-8192019",
    }
    print(f"[*] Initial Graph State Injected:\n    {initial_input}\n")
    print("[*] Invoking compiled graph via compiled.ainvoke()...\n")

    final_state = await compiled.ainvoke(initial_input)

    print("[OK] Workflow Execution Succeeded! Final State Captured:")
    print("----------------------------------------------------------------------------")
    print(f"  * Node 1 Extracted Invoice:   {final_state.get('extracted_invoice_num')}")
    print(f"  * Extracted Vendor:           {final_state.get('extracted_vendor_name')}")
    print(f"  * Invoice Total (USD):        ${final_state.get('invoice_total_usd', 0):,.2f}")
    print(f"  * Line Items Found:           {len(final_state.get('extracted_line_items', []))} items")
    print("----------------------------------------------------------------------------")
    print(f"  * Node 2 Screened Vendor:     '{final_state.get('extracted_vendor_name')}'")
    print(f"  * Sanctions Flagged:          {final_state.get('sanctions_is_flagged')}")
    print(f"  * Compliance Risk Score:      {final_state.get('sanctions_risk_score')}")
    print(f"  * Audit Note:                 {final_state.get('compliance_audit_summary')}")
    print("----------------------------------------------------------------------------")

    # --------------------------------------------------------------------------
    # Step 2.5: Execution History & Telemetry Verification
    # --------------------------------------------------------------------------
    print_banner("STEP 2.5: TELEMETRY & EXECUTION HISTORY AUDIT TRAIL")
    print(f"[+] Execution Trail: {' -> '.join(final_state.get('__history__', []))}")
    telemetry = final_state.get("__telemetry__", {})
    for node_id, data in telemetry.items():
        print(f"    * [{node_id}] Block '{data['block']}' completed in {data['latency_ms']}ms at {data['completed_at']}")

    # --------------------------------------------------------------------------
    # Step 2.6: Round-Trip Declarative Serialization
    # --------------------------------------------------------------------------
    print_banner("STEP 2.6: DECLARATIVE SPECIFICATION (YAML ROUND-TRIP SERIALIZATION)")
    serialized_yaml = dump_workflow_yaml(workflow)
    preview_lines = serialized_yaml.splitlines()[:18]
    print("[*] Serialized YAML Preview (Ready for Git PR / Governance):")
    for line in preview_lines:
        print(f"    {line}")
    print("    [... remaining YAML omitted for brevity ...]")

    print_banner("SUCCESS: STEP 2 COMPLETE - DECLARATIVE COMPILER OPERATIONAL")


if __name__ == "__main__":
    asyncio.run(main())

