from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agent_bpmn.runtime.hitl_inbox import inbox_service
from agent_bpmn.runtime.telemetry import (
    NodeTelemetryRecord,
    RunTelemetryRecord,
    telemetry_aggregator,
)
from agent_bpmn.server.routes.catalog import router as catalog_router
from agent_bpmn.server.routes.workflows import router as workflows_router
from agent_bpmn.server.routes.inbox import router as inbox_router
from agent_bpmn.server.routes.telemetry import router as telemetry_router
from agent_bpmn.server.routes.simulation import router as simulation_router
import examples.sample_blocks  # Ensure blocks are registered


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-populate demo traces for immediate visualization of Process Intelligence Heatmap
    for wf_id in ["hybrid_invoice_routing_flow", "vendor_invoice_and_compliance"]:
        latencies_ext = [80.0, 95.0, 120.0, 160.0, 2200.0]
        latencies_scr = [40.0, 45.0, 50.0, 60.0, 75.0]
        for idx in range(len(latencies_ext)):
            telemetry_aggregator.record_run(
                RunTelemetryRecord(
                    run_id=f"demo_trace_{wf_id}_{idx+1}",
                    workflow_id=wf_id,
                    total_cost_usd=0.019,
                    total_duration_ms=latencies_ext[idx] + latencies_scr[idx],
                    node_records=[
                        NodeTelemetryRecord(node_id="extract_invoice", latency_ms=latencies_ext[idx], cost_usd=0.015),
                        NodeTelemetryRecord(node_id="screen_sanctions", latency_ms=latencies_scr[idx], cost_usd=0.004),
                        NodeTelemetryRecord(
                            node_id="emergency_compliance_review",
                            latency_ms=1800.0,
                            cost_usd=0.002,
                            human_action="EDIT_AND_APPROVE" if idx % 2 == 0 else "APPROVE",
                        ),
                    ],
                )
            )

    # Pre-populate pending approval tasks for the Enterprise Task Inbox
    if not inbox_service.get_pending_tasks():
        inbox_service.create_task(
            thread_id="thread_exec_001",
            workflow_id="hybrid_invoice_routing_flow",
            node_id="cfo_approval_node",
            title="High-Value Invoice Payment Approval ($14,500.00 USD)",
            assigned_role="role:finance_executive",
            state_snapshot={
                "invoice_number": "INV-2026-9812",
                "vendor_name": "Apex Cloud Infrastructure Ltd",
                "invoice_total_usd": 14500.0,
                "sanctions_is_flagged": False,
                "sanctions_risk_score": 0.05,
                "confidence_score": 0.98,
            },
            description="Invoice exceeds automated payment limit ($10,000.00). Executive sign-off required.",
            allowed_actions=["APPROVE", "REJECT", "EDIT_AND_APPROVE"],
            sla_timeout_seconds=14400,
        )
        inbox_service.create_task(
            thread_id="thread_exec_002",
            workflow_id="hybrid_invoice_routing_flow",
            node_id="l2_compliance_review",
            title="Sanctions Watchlist Match Alert: RedStar Maritime Ltd",
            assigned_role="role:compliance_officer",
            state_snapshot={
                "invoice_number": "INV-2026-8840",
                "vendor_name": "RedStar Maritime Ltd",
                "invoice_total_usd": 68000.0,
                "sanctions_is_flagged": True,
                "sanctions_risk_score": 0.92,
                "sanctions_note": "OFAC SDN List (EU Sanctions Annex I)",
            },
            description="Counterparty flagged on international trade embargo watchlist. Immediate compliance review required.",
            allowed_actions=["APPROVE", "REJECT"],
            sla_timeout_seconds=7200,
        )

    yield


app = FastAPI(
    title="AgentBPMN Enterprise Studio API",
    description="Backend API Gateway for AgentBPMN Visual Canvas, DMN Decision Tables, Approval Inbox, and Pre-Flight Simulation.",
    version="0.7.0",
    lifespan=lifespan,
)

# Enable permissive CORS for frontend dev server & studio UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Endpoints
app.include_router(catalog_router)
app.include_router(workflows_router)
app.include_router(inbox_router)
app.include_router(telemetry_router)
app.include_router(simulation_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "HEALTHY", "service": "AgentBPMN Enterprise Gateway", "version": "0.7.0"}


# Serve built frontend Studio if available
STUDIO_DIST_DIR = Path("studio/dist")
if STUDIO_DIST_DIR.exists() and (STUDIO_DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STUDIO_DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        file_target = STUDIO_DIST_DIR / full_path
        if file_target.is_file():
            return FileResponse(file_target)
        return FileResponse(STUDIO_DIST_DIR / "index.html")

