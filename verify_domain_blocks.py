"""
AgentBPMN - Domain Block SDK Verification Script
Demonstrates Pillar 1: Foundation & Business Domain Block SDK.
Validates capability discovery, JSON Schema introspection, and runtime contract safety.
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent_bpmn.sdk import registry, BlockValidationError
import examples.sample_blocks  # Triggers registration of sample domain blocks


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 1 (PILLAR 1 - FOUNDATION & DOMAIN BLOCK SDK)")

    # --------------------------------------------------------------------------
    # Step 1.1: Introspection & Capability Discovery
    # --------------------------------------------------------------------------
    print_banner("STEP 1.1: CAPABILITY REGISTRATION & DEPARTMENT PALETTE DISCOVERY")
    catalog = registry.to_catalog()
    print(f"[*] Total Certified Domain Blocks Registered: {catalog.total_blocks}")
    print(f"[*] Departments Discovered: {', '.join(catalog.departments.keys())}\n")

    print("----------------------------------------------------------------------------")
    print("[PALETTE] MANAGEMENT CANVAS PALETTE PREVIEW (Zero Prompt/Model Leakage)")
    print("----------------------------------------------------------------------------")
    for dept, blocks in catalog.departments.items():
        print(f"\n[DEPT: {dept.upper()}]")
        for b in blocks:
            m = b.metadata
            print(f"   * [{m.icon.upper()}] {m.name} (id: '{m.id}')")
            print(f"     Desc:     {m.description}")
            print(f"     Metrics:  Est. Cost: ${m.estimated_cost_usd:.4f} | P95 Latency: {m.p95_latency_ms}ms")
            print(f"     Input:    {b.input_model_name} -> {list(b.input_schema.get('properties', {}).keys())}")
            print(f"     Output:   {b.output_model_name} -> {list(b.output_schema.get('properties', {}).keys())}")

    # --------------------------------------------------------------------------
    # Step 1.2: JSON Schema Catalog Export
    # --------------------------------------------------------------------------
    print_banner("STEP 1.2: SERIALIZE CATALOG CONTRACT (JSON SCHEMA EXPORT)")
    catalog_path = Path("capabilities_catalog.json")
    registry.export_catalog_json(catalog_path)
    print(f"[+] Exported Canvas Capability Catalog to: {catalog_path.resolve()}")
    print(f"    Total Blocks Serialized: {catalog.total_blocks}")

    # --------------------------------------------------------------------------
    # Step 1.3: Clean Sanctions Screen Execution
    # --------------------------------------------------------------------------
    print_banner("STEP 1.3: RUNTIME EXECUTION - COMPLIANCE CLEAN SANCTIONS SCREEN")
    clean_input = {
        "entity_name": "Global Logistics Partners AG",
        "country_code": "CH",
        "transaction_amount_usd": 42000.0,
    }
    print(f"[*] Invoking 'compliance.sanctions_screener' with input:\n    {clean_input}")
    res1 = await registry.execute("compliance.sanctions_screener", clean_input)
    print(f"\n[OK] Validated Return ({res1.__class__.__name__}):")
    print(f"    - Flagged:         {res1.is_flagged}")
    print(f"    - Risk Score:      {res1.risk_score}")
    print(f"    - Compliance Note: {res1.compliance_note}")

    # --------------------------------------------------------------------------
    # Step 1.4: Sanctions Watchlist Flagged Match Execution
    # --------------------------------------------------------------------------
    print_banner("STEP 1.4: RUNTIME EXECUTION - COMPLIANCE WATCHLIST HIT DETECTION")
    flagged_input = {
        "entity_name": "Acme Contraband Corp / Logistics Division",
        "country_code": "IR",
        "transaction_amount_usd": 150000.0,
    }
    print(f"[*] Invoking 'compliance.sanctions_screener' with input:\n    {flagged_input}")
    res2 = await registry.execute("compliance.sanctions_screener", flagged_input)
    print(f"\n[FLAGGED] Warning Return ({res2.__class__.__name__}):")
    print(f"    - Flagged:         {res2.is_flagged}")
    print(f"    - Risk Score:      {res2.risk_score}")
    print(f"    - Matches:         {res2.matched_entries}")
    print(f"    - Compliance Note: {res2.compliance_note}")

    # --------------------------------------------------------------------------
    # Step 1.5: Complex Finance Invoice Extraction Execution
    # --------------------------------------------------------------------------
    print_banner("STEP 1.5: RUNTIME EXECUTION - FINANCE INVOICE LINE ITEMS EXTRACTION")
    invoice_input = {
        "document_url": "s3://enterprise-invoices-2026/q3/apex_cloud_inv9812.pdf",
        "vendor_tax_id": "US-94-8192019",
    }
    print(f"[*] Invoking 'finance.invoice_extractor' with input:\n    {invoice_input}")
    res3 = await registry.execute("finance.invoice_extractor", invoice_input)
    print(f"\n[OK] Extracted Invoice ({res3.__class__.__name__}):")
    print(f"    - Invoice Number:  {res3.invoice_number}")
    print(f"    - Vendor:          {res3.vendor_name}")
    print(f"    - Total Amount:    ${res3.total_amount_usd:,.2f} {res3.currency}")
    print(f"    - Line Items:      {len(res3.line_items)} items extracted")
    for idx, item in enumerate(res3.line_items, 1):
        print(f"      [{idx}] {item.description} (Qty: {item.quantity}) - ${item.total_usd:,.2f}")

    # --------------------------------------------------------------------------
    # Step 1.6: Runtime Schema Guardrail & Contract Enforcement
    # --------------------------------------------------------------------------
    print_banner("STEP 1.6: RUNTIME CONTRACT GUARDRAIL - REJECT INVALID SCHEMA PAYLOAD")
    invalid_input = {
        "entity_name": "Invalid Entity",
        "country_code": "USA_TOO_LONG",  # Violates max_length=2 constraint
        "transaction_amount_usd": -500.0,  # Violates ge=0.0 constraint
    }
    print(f"[*] Sending invalid payload violating Pydantic schema constraints:\n    {invalid_input}")
    try:
        await registry.execute("compliance.sanctions_screener", invalid_input)
        print("[X] ERROR: Execution should have been rejected!")
    except BlockValidationError as err:
        print(f"\n[OK] SUCCESS: Contract Guardrail intercepted invalid payload before execution!")
        print(f"    Caught: {err.__class__.__name__}")
        print(f"    Details: {len(err.details)} schema violations detected:")
        for issue in err.details:
            loc = " -> ".join(str(p) for p in issue.get("loc", []))
            print(f"      * Field '{loc}': {issue.get('msg')} (type: {issue.get('type')})")

    print_banner("SUCCESS: STEP 1 COMPLETE - ALL PILLAR 1 CAPABILITIES VERIFIED")


if __name__ == "__main__":
    asyncio.run(main())
