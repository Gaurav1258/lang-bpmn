from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_bpmn.dsl import parse_workflow_yaml, dump_workflow_yaml
from agent_bpmn.sdk.registry import registry
from agent_bpmn.sdk.models import CapabilityCatalog

router = APIRouter(prefix="/api/capabilities", tags=["Capabilities"])


@router.get("", response_model=CapabilityCatalog)
def get_capabilities_catalog() -> CapabilityCatalog:
    """Returns the certified Domain Block capabilities catalog grouped by department."""
    return registry.to_catalog()


@router.get("/{block_id}")
def get_capability_detail(block_id: str) -> Dict[str, Any]:
    """Returns the full contract, schemas, and metadata for a specific domain block."""
    if not registry.has(block_id):
        raise HTTPException(status_code=404, detail=f"Domain block '{block_id}' not found in registry.")
    registered = registry.get(block_id)
    return {
        "metadata": registered.contract.metadata.model_dump(),
        "input_schema": registered.contract.input_schema,
        "output_schema": registered.contract.output_schema,
    }
