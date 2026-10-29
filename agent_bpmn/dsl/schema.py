from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    START = "start"
    BLOCK = "block"
    ROUTER = "router"
    HUMAN_REVIEW = "human_review"
    END = "end"


class WorkflowMetadata(BaseModel):
    """Business and regulatory metadata for the workflow."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique workflow identifier, e.g. 'vendor_invoice_approval'")
    name: str = Field(..., description="Human-readable workflow name")
    version: str = Field(default="1.0.0", description="Semantic version of the workflow definition")
    description: Optional[str] = Field(default=None, description="Detailed business description of the process")
    owner_department: str = Field(default="General", description="Department responsible for this workflow")


class WorkflowGuardrails(BaseModel):
    """Operational guardrails and budget caps configured by management."""
    model_config = ConfigDict(extra="ignore")

    max_total_budget_usd: Optional[float] = Field(default=None, ge=0.0, description="Hard cap on total USD API spend per execution")
    workflow_timeout_seconds: Optional[int] = Field(default=3600, ge=1, description="Timeout in seconds before halting")
    max_loop_iterations: int = Field(default=10, ge=1, description="Maximum loop iterations across cyclic paths")


class WorkflowNode(BaseModel):
    """
    A single node in the declarative workflow topology.
    Can represent a Domain Block, Router, Human Review, or Gateway.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique identifier for the node instance within the workflow")
    type: NodeType = Field(default=NodeType.BLOCK, description="Node category")
    name: Optional[str] = Field(default=None, description="Display name on the canvas")
    block: Optional[str] = Field(default=None, description="Referenced domain block ID (required for type='block')")
    input_mapping: Dict[str, Any] = Field(
        default_factory=dict,
        description="Maps graph state keys or constant values to the block's input parameters",
    )
    output_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps the block's output attributes back into the graph state keys",
    )
    config: Dict[str, Any] = Field(default_factory=dict, description="Node-specific configuration parameters")


class WorkflowEdge(BaseModel):
    """Directed connection between two workflow nodes."""
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, description="Optional edge identifier")
    source: str = Field(..., description="Source node id, or 'START'")
    target: str = Field(..., description="Target node id, or 'END'")
    condition: Optional[str] = Field(default=None, description="Optional condition rule expression for branching")


class WorkflowDefinition(BaseModel):
    """
    Top-level Abstract Syntax Tree (AST) for an AgentBPMN workflow.
    This corresponds 1:1 to the declarative 'agent-bpmn.yaml' file.
    """
    model_config = ConfigDict(extra="ignore")

    version: str = Field(default="1.0", description="Specification format version")
    metadata: WorkflowMetadata
    guardrails: WorkflowGuardrails = Field(default_factory=WorkflowGuardrails)
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)

