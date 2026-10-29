import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import (
    HitPolicy,
    NodeType,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowGuardrails,
    WorkflowLinter,
    WorkflowMetadata,
    WorkflowNode,
    dump_workflow_yaml,
    parse_workflow_yaml,
)
from agent_bpmn.sdk.registry import registry
import examples.sample_blocks  # Ensure blocks are registered

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

SAMPLE_WORKFLOWS_DIR = Path("examples/sample_workflows")


def _safe_workflow_path(file_name: str) -> Path:
    safe_name = Path(file_name).name
    if not safe_name.endswith(".yaml"):
        safe_name = f"{safe_name}.yaml"
    return SAMPLE_WORKFLOWS_DIR / safe_name


class WorkflowYamlPayload(BaseModel):
    yaml_content: str


class WorkflowExecutePayload(BaseModel):
    workflow_yaml: Optional[str] = None
    workflow_id: Optional[str] = None
    input_payload: Dict[str, Any]


class CreateWorkflowPayload(BaseModel):
    workflow_id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    department: Optional[str] = "Finance Operations"
    template: Optional[str] = "blank"  # blank, linear, dmn, hitl, semantic
    yaml_content: Optional[str] = None
    max_budget_usd: Optional[float] = 0.50
    max_loop_iterations: Optional[int] = 3
    workflow_timeout_seconds: Optional[int] = 600


class UpdateWorkflowPayload(BaseModel):
    yaml_content: Optional[str] = None
    ast: Optional[Dict[str, Any]] = None


def _generate_template_workflow(payload: CreateWorkflowPayload) -> WorkflowDefinition:
    """Generates a certified WorkflowDefinition AST from a template preset."""
    raw_id = payload.workflow_id or re.sub(r"[^a-zA-Z0-9_]+", "_", payload.name.strip().lower()).strip("_")
    if not raw_id:
        raw_id = f"workflow_{int(Path(__file__).stat().st_mtime)}"

    metadata = WorkflowMetadata(
        id=raw_id,
        name=payload.name,
        version="1.0.0",
        department=payload.department or "Finance Operations",
        description=payload.description or f"Orchestrated process for {payload.name}",
        author="Enterprise Studio Architect",
    )

    guardrails = WorkflowGuardrails(
        max_total_budget_usd=payload.max_budget_usd or 0.50,
        max_loop_iterations=payload.max_loop_iterations or 3,
        workflow_timeout_seconds=payload.workflow_timeout_seconds or 600,
    )

    template = (payload.template or "blank").lower()

    if template == "linear":
        nodes = [
            WorkflowNode(
                id="extract_invoice",
                type=NodeType.BLOCK,
                name="Extract Invoice Line Items",
                block="finance.invoice_extractor",
                input_mapping={"document_url": "input.invoice_pdf_url", "vendor_tax_id": "input.tax_id"},
                output_mapping={"extracted_invoice_num": "invoice_number", "invoice_total_usd": "total_amount_usd", "entity_name": "vendor_name"},
                max_retries=3,
            ),
            WorkflowNode(
                id="screen_sanctions",
                type=NodeType.BLOCK,
                name="Screen Sanctions & Watchlists",
                block="compliance.sanctions_screener",
                input_mapping={"entity_name": "state.entity_name", "country_code": "input.country_code", "transaction_amount_usd": "state.invoice_total_usd"},
                output_mapping={"sanctions_is_flagged": "is_flagged", "sanctions_risk_score": "risk_score"},
                max_retries=2,
            ),
            WorkflowNode(
                id="auto_settlement",
                type=NodeType.BLOCK,
                name="Automated Payment Settlement",
                block="finance.auto_settlement",
                input_mapping={"invoice_number": "state.extracted_invoice_num", "amount_usd": "state.invoice_total_usd", "vendor_tax_id": "input.tax_id"},
                output_mapping={"settlement_tx_id": "transaction_id", "settlement_status": "status"},
                max_retries=3,
            ),
        ]
        edges = [
            WorkflowEdge(source="START", target="extract_invoice"),
            WorkflowEdge(source="extract_invoice", target="screen_sanctions"),
            WorkflowEdge(source="screen_sanctions", target="auto_settlement"),
            WorkflowEdge(source="auto_settlement", target="END"),
        ]
    elif template == "dmn":
        nodes = [
            WorkflowNode(
                id="extract_invoice",
                type=NodeType.BLOCK,
                name="Extract Invoice Line Items",
                block="finance.invoice_extractor",
                input_mapping={"document_url": "input.invoice_pdf_url", "vendor_tax_id": "input.tax_id"},
                output_mapping={"extracted_invoice_num": "invoice_number", "invoice_total_usd": "total_amount_usd", "entity_name": "vendor_name"},
                max_retries=3,
            ),
            WorkflowNode(
                id="screen_sanctions",
                type=NodeType.BLOCK,
                name="Screen Sanctions Watchlist",
                block="compliance.sanctions_screener",
                input_mapping={"entity_name": "state.entity_name", "country_code": "input.country_code", "transaction_amount_usd": "state.invoice_total_usd"},
                output_mapping={"sanctions_is_flagged": "is_flagged", "sanctions_risk_score": "risk_score"},
                max_retries=2,
            ),
            WorkflowNode(
                id="decision_matrix",
                type=NodeType.DMN_TABLE,
                name="Risk & Amount Routing Matrix",
                dmn_config={
                    "hit_policy": "FIRST_MATCH",
                    "rules": [
                        {"condition": "sanctions_is_flagged == True", "target": "emergency_review"},
                        {"condition": "invoice_total_usd > 10000", "target": "emergency_review"},
                        {"condition": "invoice_total_usd <= 10000", "target": "auto_settlement"},
                    ],
                    "default_target": "emergency_review",
                },
            ),
            WorkflowNode(
                id="auto_settlement",
                type=NodeType.BLOCK,
                name="Automated Payment Settlement",
                block="finance.auto_settlement",
                input_mapping={"invoice_number": "state.extracted_invoice_num", "amount_usd": "state.invoice_total_usd", "vendor_tax_id": "input.tax_id"},
                output_mapping={"settlement_tx_id": "transaction_id", "settlement_status": "status"},
                max_retries=3,
            ),
            WorkflowNode(
                id="emergency_review",
                type=NodeType.BLOCK,
                name="Compliance Investigation",
                block="compliance.emergency_review",
                input_mapping={"entity_name": "state.entity_name", "risk_score": "state.sanctions_risk_score"},
                output_mapping={"docket_id": "case_docket_id"},
                max_retries=2,
            ),
        ]
        edges = [
            WorkflowEdge(source="START", target="extract_invoice"),
            WorkflowEdge(source="extract_invoice", target="screen_sanctions"),
            WorkflowEdge(source="screen_sanctions", target="decision_matrix"),
            WorkflowEdge(source="auto_settlement", target="END"),
            WorkflowEdge(source="emergency_review", target="END"),
        ]
    elif template == "hitl":
        nodes = [
            WorkflowNode(
                id="extract_invoice",
                type=NodeType.BLOCK,
                name="Extract Invoice Line Items",
                block="finance.invoice_extractor",
                input_mapping={"document_url": "input.invoice_pdf_url", "vendor_tax_id": "input.tax_id"},
                output_mapping={"extracted_invoice_num": "invoice_number", "invoice_total_usd": "total_amount_usd", "entity_name": "vendor_name"},
                max_retries=3,
            ),
            WorkflowNode(
                id="screen_sanctions",
                type=NodeType.BLOCK,
                name="Screen Sanctions Watchlist",
                block="compliance.sanctions_screener",
                input_mapping={"entity_name": "state.entity_name", "country_code": "input.country_code", "transaction_amount_usd": "state.invoice_total_usd"},
                output_mapping={"sanctions_is_flagged": "is_flagged", "sanctions_risk_score": "risk_score"},
                max_retries=2,
            ),
            WorkflowNode(
                id="cfo_approval_node",
                type=NodeType.HUMAN_REVIEW,
                name="Executive Review Checkpoint",
                human_review_config={
                    "assigned_role": "role:finance_executive",
                    "sla_hours": 4,
                    "allowed_actions": ["APPROVE", "REJECT", "EDIT_AND_APPROVE"],
                    "timeout_action": "REJECT",
                },
            ),
            WorkflowNode(
                id="auto_settlement",
                type=NodeType.BLOCK,
                name="Automated Payment Settlement",
                block="finance.auto_settlement",
                input_mapping={"invoice_number": "state.extracted_invoice_num", "amount_usd": "state.invoice_total_usd", "vendor_tax_id": "input.tax_id"},
                output_mapping={"settlement_tx_id": "transaction_id", "settlement_status": "status"},
                max_retries=3,
            ),
        ]
        edges = [
            WorkflowEdge(source="START", target="extract_invoice"),
            WorkflowEdge(source="extract_invoice", target="screen_sanctions"),
            WorkflowEdge(source="screen_sanctions", target="cfo_approval_node"),
            WorkflowEdge(source="cfo_approval_node", target="auto_settlement"),
            WorkflowEdge(source="auto_settlement", target="END"),
        ]
    else:  # Blank starter
        nodes = [
            WorkflowNode(
                id="extract_invoice",
                type=NodeType.BLOCK,
                name="Extract Invoice Line Items",
                block="finance.invoice_extractor",
                input_mapping={"document_url": "input.invoice_pdf_url", "vendor_tax_id": "input.tax_id"},
                output_mapping={"extracted_invoice_num": "invoice_number", "invoice_total_usd": "total_amount_usd"},
                max_retries=3,
            )
        ]
        edges = [
            WorkflowEdge(source="START", target="extract_invoice"),
            WorkflowEdge(source="extract_invoice", target="END"),
        ]

    return WorkflowDefinition(
        version="1.0",
        metadata=metadata,
        guardrails=guardrails,
        nodes=nodes,
        edges=edges,
    )


@router.get("")
def list_sample_workflows() -> List[Dict[str, Any]]:
    """Lists available sample workflows with their metadata."""
    results = []
    if SAMPLE_WORKFLOWS_DIR.exists():
        for yaml_file in sorted(SAMPLE_WORKFLOWS_DIR.glob("*.yaml")):
            try:
                wf = parse_workflow_yaml(yaml_file)
                results.append({
                    "file_name": yaml_file.name,
                    "metadata": wf.metadata.model_dump(),
                    "node_count": len(wf.nodes),
                    "edge_count": len(wf.edges),
                    "guardrails": wf.guardrails.model_dump(),
                })
            except Exception as e:
                results.append({
                    "file_name": yaml_file.name,
                    "error": str(e),
                })
    return results


@router.post("")
def create_workflow(payload: CreateWorkflowPayload) -> Dict[str, Any]:
    """Creates a new workflow definition and persists it to disk."""
    if payload.yaml_content:
        try:
            wf = parse_workflow_yaml(payload.yaml_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML payload: {str(e)}")
    else:
        wf = _generate_template_workflow(payload)

    # Static linting check
    linter = WorkflowLinter(registry=registry)
    lint_res = linter.lint(wf)
    if not lint_res.is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Workflow failed static linting validation", "errors": lint_res.errors},
        )

    file_name = f"{wf.metadata.id}.yaml"
    path = _safe_workflow_path(file_name)
    yaml_str = dump_workflow_yaml(wf)

    SAMPLE_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    return {
        "file_name": file_name,
        "workflow_id": wf.metadata.id,
        "yaml_content": yaml_str,
        "ast": wf.model_dump(),
        "message": f"Workflow '{wf.metadata.name}' created successfully.",
    }


@router.get("/{file_name}")
def get_workflow_by_file(file_name: str) -> Dict[str, Any]:
    """Retrieves a workflow by file name in YAML and parsed AST format."""
    path = _safe_workflow_path(file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow file '{file_name}' not found.")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    wf = parse_workflow_yaml(content)
    return {
        "file_name": file_name,
        "yaml_content": content,
        "ast": wf.model_dump(),
    }


@router.put("/{file_name}")
def update_workflow(file_name: str, payload: UpdateWorkflowPayload) -> Dict[str, Any]:
    """Updates an existing workflow's YAML content or AST on disk."""
    path = _safe_workflow_path(file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow file '{file_name}' not found.")

    if payload.yaml_content:
        try:
            wf = parse_workflow_yaml(payload.yaml_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML content: {str(e)}")
    elif payload.ast:
        try:
            wf = WorkflowDefinition.model_validate(payload.ast)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid AST structure: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Must provide either yaml_content or ast.")

    linter = WorkflowLinter(registry=registry)
    lint_res = linter.lint(wf)
    if not lint_res.is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Workflow failed static linting validation", "errors": lint_res.errors},
        )

    yaml_str = dump_workflow_yaml(wf)
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    return {
        "file_name": file_name,
        "workflow_id": wf.metadata.id,
        "yaml_content": yaml_str,
        "ast": wf.model_dump(),
        "message": f"Workflow '{wf.metadata.name}' updated successfully.",
    }


@router.delete("/{file_name}")
def delete_workflow(file_name: str) -> Dict[str, Any]:
    """Deletes a workflow file from disk."""
    path = _safe_workflow_path(file_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow file '{file_name}' not found.")

    path.unlink()
    return {
        "file_name": file_name,
        "message": f"Workflow '{file_name}' deleted successfully.",
    }


@router.post("/lint")
def lint_workflow(payload: WorkflowYamlPayload) -> Dict[str, Any]:
    """Validates workflow syntax, topology, and Pydantic block connections."""
    try:
        wf = parse_workflow_yaml(payload.yaml_content)
    except Exception as e:
        return {
            "is_valid": False,
            "errors": [f"YAML Parse Error: {str(e)}"],
            "warnings": [],
        }

    linter = WorkflowLinter(registry=registry)
    res = linter.lint(wf)
    return {
        "is_valid": res.is_valid,
        "errors": res.errors,
        "warnings": res.warnings,
        "workflow_id": wf.metadata.id,
    }


@router.post("/execute")
async def execute_workflow(payload: WorkflowExecutePayload) -> Dict[str, Any]:
    """Compiles and executes a workflow with runtime guardrails and state tracking."""
    if payload.workflow_yaml:
        wf = parse_workflow_yaml(payload.workflow_yaml)
    elif payload.workflow_id:
        target_path = None
        for p in SAMPLE_WORKFLOWS_DIR.glob("*.yaml"):
            try:
                candidate = parse_workflow_yaml(p)
                if candidate.metadata.id == payload.workflow_id:
                    target_path = p
                    wf = candidate
                    break
            except Exception:
                pass
        if not target_path:
            raise HTTPException(status_code=404, detail=f"Workflow '{payload.workflow_id}' not found.")
    else:
        raise HTTPException(status_code=400, detail="Must provide either workflow_yaml or workflow_id.")

    compiler = GraphCompiler(registry=registry)
    try:
        compiled = compiler.compile(wf)
        result = await compiled.ainvoke(payload.input_payload)
        return {
            "status": "COMPLETED" if "__interrupt__" not in result or not result["__interrupt__"] else "INTERRUPTED",
            "final_state": result,
            "history": result.get("__history__", []),
            "total_cost_usd": result.get("__sys_total_cost_usd", 0.0),
            "telemetry": result.get("__telemetry__", {}),
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "error_type": e.__class__.__name__,
            "error_message": str(e),
        }


