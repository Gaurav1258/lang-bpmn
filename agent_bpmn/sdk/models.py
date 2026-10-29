from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DomainBlockMetadata(BaseModel):
    """Business and operational metadata for a domain block."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique dotted identifier, e.g. 'compliance.sanctions_screener'")
    name: str = Field(..., description="Human-readable display name, e.g. 'Screen Against Sanctions List'")
    department: str = Field(..., description="Department category, e.g. 'Compliance', 'Finance', 'Support'")
    description: str = Field(..., description="Clear explanation of the business capability")
    icon: str = Field(default="cpu", description="Lucide or BPMN icon identifier for canvas rendering")
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, description="Estimated average cost per execution in USD")
    p95_latency_ms: int = Field(default=0, ge=0, description="Estimated P95 latency in milliseconds")
    tags: List[str] = Field(default_factory=list, description="Searchable tags for palette filtering")
    version: str = Field(default="1.0.0", description="Semantic version of this domain block")


class DomainBlockContract(BaseModel):
    """
    The full public contract for a domain block.
    This is what the visual canvas consumes. Prompts, LLM models, and internal code
    are completely omitted to guarantee separation of concerns.
    """
    metadata: DomainBlockMetadata
    input_model_name: str = Field(..., description="Name of the input Pydantic model class")
    output_model_name: str = Field(..., description="Name of the output Pydantic model class")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema definition of the input parameters")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema definition of the output parameters")


class CapabilityCatalog(BaseModel):
    """The enterprise capability catalog grouped by department for the visual canvas sidebar."""
    version: str = "1.0.0"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_blocks: int = 0
    departments: Dict[str, List[DomainBlockContract]] = Field(default_factory=dict)

