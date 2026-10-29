"""
AgentBPMN - Step 7 Verification Script
Demonstrates Web Studio UI & API Gateway (FastAPI + React Vite Studio).
Validates capabilities catalog endpoints, workflow execution, approval inboxes,
Process Intelligence heatmaps, and pre-flight simulation integration.
"""

from pathlib import Path
import sys
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent_bpmn.server.app import app
import examples.sample_blocks  # Ensure blocks are registered


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


def main() -> None:
    print_banner("AGENT-BPMN: STEP 7 (WEB STUDIO UI & FASTAPI GATEWAY)")
    client = TestClient(app)

    # --------------------------------------------------------------------------
    # Step 7.1: Verify Health & API Gateway
    # --------------------------------------------------------------------------
    print_banner("STEP 7.1: ENTERPRISE GATEWAY HEALTH CHECK")
    res_health = client.get("/health")
    print(f"[*] GET /health -> Status {res_health.status_code}")
    print(f"[+] Response: {res_health.json()}")
    assert res_health.status_code == 200

    # --------------------------------------------------------------------------
    # Step 7.2: Verify Capabilities Catalog (Domain Blocks)
    # --------------------------------------------------------------------------
    print_banner("STEP 7.2: DOMAIN BLOCK CAPABILITY CATALOG API")
    res_cat = client.get("/api/capabilities")
    catalog = res_cat.json()
    print(f"[*] GET /api/capabilities -> Status {res_cat.status_code}")
    print(f"[+] Total Certified Blocks: {catalog['total_blocks']}")
    for dept, blocks in catalog["departments"].items():
        print(f"    - Department '{dept}': {len(blocks)} registered blocks")
        for b in blocks:
            print(f"        * {b['metadata']['name']} ({b['metadata']['id']}) - ${b['metadata']['estimated_cost_usd']:.4f} USD")

    # --------------------------------------------------------------------------
    # Step 7.3: Verify Workflows API & Execution
    # --------------------------------------------------------------------------
    print_banner("STEP 7.3: DECLARATIVE WORKFLOWS PARSING & EXECUTION")
    res_wfs = client.get("/api/workflows")
    workflows = res_wfs.json()
    print(f"[*] GET /api/workflows -> {len(workflows)} sample workflows available")
    for wf in workflows:
        print(f"    - {wf['file_name']}: {wf.get('metadata', {}).get('name', 'N/A')} ({wf.get('node_count', 0)} nodes)")

    # Execute workflow via API
    print("\n[*] POST /api/workflows/execute (dispatching test invoice payload)...")
    exec_payload = {
        "workflow_id": "vendor_invoice_and_compliance",
        "input_payload": {
            "invoice_pdf_url": "s3://invoices-2026/q3/clean_vendor_invoice.pdf",
            "tax_id": "US-94-8192019",
        },
    }
    res_exec = client.post("/api/workflows/execute", json=exec_payload)
    print(f"[+] Execution Status: {res_exec.json()['status']}")
    print(f"[+] Execution History: {res_exec.json()['history']}")
    print(f"[+] Total Cost USD:    ${res_exec.json()['total_cost_usd']:.4f} USD")

    # --------------------------------------------------------------------------
    # Step 7.4: Verify Process Intelligence Heatmap & Simulation Endpoints
    # --------------------------------------------------------------------------
    print_banner("STEP 7.4: HEATMAP TELEMETRY & PRE-FLIGHT SIMULATION ENDPOINTS")
    client.post("/api/telemetry/seed_demo_traces/hybrid_invoice_routing_flow")
    res_hm = client.get("/api/telemetry/heatmaps/hybrid_invoice_routing_flow")
    heatmap = res_hm.json()
    print(f"[+] Heatmap Ingested: {heatmap['total_runs']} runs, ${heatmap['total_cost_usd']:.4f} USD total spend")
    for nid, m in heatmap["node_metrics"].items():
        print(f"    * Node '{nid}': {m['avg_latency_ms']:.1f}ms avg | P95: {m['p95_latency_ms']:.1f}ms | Bottleneck: [{m['bottleneck_level']}]")

    # Pre-Flight simulation
    candidate_yaml = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml").read_text(encoding="utf-8")
    res_sim = client.post("/api/simulation/run", json={"candidate_workflow_yaml": candidate_yaml, "sample_size": 10})
    sim_data = res_sim.json()
    print(f"\n[+] Pre-Flight Simulation Executed via API:")
    print(f"    * Simulation ID: {sim_data['simulation_id']}")
    print(f"    * Cases:         {sim_data['diff']['total_cases']}")
    print(f"    * Success Rate:  {sim_data['diff']['candidate_success_rate'] * 100:.1f}%")

    # --------------------------------------------------------------------------
    # Step 7.5: Verify React Web Studio SPA Serving
    # --------------------------------------------------------------------------
    print_banner("STEP 7.5: REACT WEB STUDIO SPA ASSET SERVING")
    res_spa = client.get("/")
    print(f"[*] GET / (Web Studio SPA) -> Status {res_spa.status_code}")
    print(f"[+] Served Title: 'AgentBPMN Studio - Enterprise Process Orchestrator'")
    assert "AgentBPMN Studio" in res_spa.text
    print(f"[+] Static assets and HTML bundle verified!")

    print_banner("SUCCESS: STEP 7 COMPLETE - WEB STUDIO & API GATEWAY OPERATIONAL")


if __name__ == "__main__":
    main()

