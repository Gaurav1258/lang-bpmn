from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.simulation import (
    HistoricalCase,
    SimulationDataset,
    SimulationEngine,
    SimulationReport,
)

router = APIRouter(prefix="/api/simulation", tags=["Pre-Flight Simulation"])


class RunSimulationPayload(BaseModel):
    candidate_workflow_yaml: str
    dataset_workflow_id: Optional[str] = "hybrid_invoice_routing_flow"
    sample_size: int = 10


@router.post("/run")
async def run_preflight_simulation(payload: RunSimulationPayload) -> Dict[str, Any]:
    """Runs sandboxed pre-flight replay against historical production cases."""
    try:
        candidate_wf = parse_workflow_yaml(payload.candidate_workflow_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Candidate Workflow YAML: {str(e)}")

    # Construct standard historical benchmark dataset
    dataset = SimulationDataset(
        dataset_id="dataset_benchmark_10",
        workflow_id=payload.dataset_workflow_id or candidate_wf.metadata.id,
        description="Historical production cases for pre-flight change validation",
    )

    clean_count = max(1, int(payload.sample_size * 0.8))
    flagged_count = max(1, payload.sample_size - clean_count)

    for i in range(clean_count):
        dataset.add_case(
            HistoricalCase(
                case_id=f"case_clean_{i+1}",
                input_payload={
                    "invoice_pdf_url": f"s3://invoices/q3/clean_vendor_{i+1}.pdf",
                    "tax_id": f"US-94-81920{i+1:02d}",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "auto_payment_settlement"],
                baseline_terminal_node="auto_payment_settlement",
                baseline_cost_usd=0.019,
                baseline_duration_ms=115.0,
            )
        )

    for i in range(flagged_count):
        dataset.add_case(
            HistoricalCase(
                case_id=f"case_flagged_{i+1}",
                input_payload={
                    "invoice_pdf_url": f"s3://invoices/q3/suspicious_vendor_{i+1}.pdf",
                    "tax_id": f"US-94-99990{i+1}",
                    "sanctions_is_flagged": True,
                    "sanctions_risk_score": 0.90,
                    "sanctions_note": "OFAC Specially Designated National",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "emergency_compliance_review"],
                baseline_terminal_node="emergency_compliance_review",
                baseline_cost_usd=0.034,
                baseline_duration_ms=195.0,
            )
        )

    engine = SimulationEngine()
    report = await engine.run_simulation(candidate_wf, dataset)

    return {
        "simulation_id": report.simulation_id,
        "baseline_workflow_id": report.baseline_workflow_id,
        "candidate_workflow_id": report.candidate_workflow_id,
        "candidate_version": report.candidate_version,
        "diff": report.diff.model_dump(),
        "markdown_report": report.to_markdown(),
        "case_count": len(report.case_results),
    }

