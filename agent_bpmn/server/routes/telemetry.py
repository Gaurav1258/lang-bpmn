from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from agent_bpmn.runtime.telemetry import (
    NodeTelemetryRecord,
    RunTelemetryRecord,
    WorkflowHeatmap,
    telemetry_aggregator,
)

router = APIRouter(prefix="/api/telemetry", tags=["Process Heatmap & Telemetry"])


@router.get("/heatmaps/{workflow_id}")
def get_heatmap(workflow_id: str) -> Dict[str, Any]:
    """Returns the Process Intelligence Heatmap (P95 latency, average spend, bottleneck levels)."""
    heatmap = telemetry_aggregator.get_heatmap(workflow_id)
    return heatmap.model_dump()


@router.post("/seed_demo_traces/{workflow_id}")
def seed_demo_traces(workflow_id: str) -> Dict[str, Any]:
    """Populates synthetic production traces for demonstration of the canvas heatmap overlay."""
    latencies_extract = [90.0, 110.0, 140.0, 200.0, 2200.0]
    latencies_screen = [45.0, 50.0, 55.0, 65.0, 80.0]

    for i in range(len(latencies_extract)):
        telemetry_aggregator.record_run(
            RunTelemetryRecord(
                run_id=f"demo_run_{i+1}",
                workflow_id=workflow_id,
                total_cost_usd=0.019,
                total_duration_ms=latencies_extract[i] + latencies_screen[i],
                node_records=[
                    NodeTelemetryRecord(node_id="extract_invoice", latency_ms=latencies_extract[i], cost_usd=0.015),
                    NodeTelemetryRecord(node_id="check_sanctions", latency_ms=latencies_screen[i], cost_usd=0.004),
                    NodeTelemetryRecord(
                        node_id="compliance_human_review",
                        latency_ms=1800.0,
                        cost_usd=0.0,
                        human_action="EDIT_AND_APPROVE" if i % 2 == 0 else "APPROVE",
                    ),
                ],
            )
        )

    heatmap = telemetry_aggregator.get_heatmap(workflow_id)
    return {
        "success": True,
        "message": f"Seeded demo traces for '{workflow_id}'",
        "heatmap": heatmap.model_dump(),
    }

