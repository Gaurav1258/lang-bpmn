from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import (
    WorkflowDefinition,
    WorkflowLinter,
    dump_workflow_yaml,
    parse_workflow_yaml,
)
from agent_bpmn.sdk.registry import registry
import examples.sample_blocks  # Ensure blocks are registered

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

SAMPLE_WORKFLOWS_DIR = Path("examples/sample_workflows")


class WorkflowYamlPayload(BaseModel):
    yaml_content: str


class WorkflowExecutePayload(BaseModel):
    workflow_yaml: Optional[str] = None
    workflow_id: Optional[str] = None
    input_payload: Dict[str, Any]


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


@router.get("/{file_name}")
def get_workflow_by_file(file_name: str) -> Dict[str, Any]:
    """Retrieves a workflow by file name in YAML and parsed AST format."""
    path = SAMPLE_WORKFLOWS_DIR / file_name
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
        # Search in samples
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

