from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    START = "start"
    BLOCK = "block"
    DMN_TABLE = "dmn_table"
    SEMANTIC_ROUTER = "semantic_router"
    HUMAN_REVIEW = "human_review"
    END = "end"


class HitPolicy(str, Enum):
    FIRST_MATCH = "FIRST_MATCH"
    PRIORITY = "PRIORITY"


class DMNRule(BaseModel):
    """A single decision rule in a DMN table."""
    model_config = ConfigDict(extra="ignore")

    condition: Optional[str] = Field(
        default=None,
        description="Boolean condition expression, e.g. 'amount > 10000 and risk == \"HIGH\"'. If None, acts as fallback.",
    )
    target: str = Field(..., description="Target node ID or 'END' to route to when condition is met")
    description: Optional[str] = Field(default=None, description="Human-readable business explanation for the rule")


class DMNTableConfig(BaseModel):
    """Configuration for a Deterministic DMN Decision Table node."""
    model_config = ConfigDict(extra="ignore")

    hit_policy: HitPolicy = Field(default=HitPolicy.FIRST_MATCH, description="Evaluation strategy")
    rules: List[DMNRule] = Field(default_factory=list, description="Ordered list of decision rules")
    default_target: Optional[str] = Field(default=None, description="Fallback target if no rules match")


class SemanticRoute(BaseModel):
    """A single natural language classification bucket."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Route identifier, e.g. 'billing_inquiry'")
    description: str = Field(..., description="Natural language description of customer/user intent")
    target: str = Field(..., description="Target node ID or 'END'")


class SemanticRouterConfig(BaseModel):
    """Configuration for an LLM-powered Semantic Intent Router node."""
    model_config = ConfigDict(extra="ignore")

    input_field: str = Field(..., description="Graph state key holding the text content to classify")
    routes: List[SemanticRoute] = Field(default_factory=list, description="List of semantic routes")
    default_target: Optional[str] = Field(default=None, description="Fallback target if intent is ambiguous")


class HumanReviewConfig(BaseModel):
    """Configuration for an Enterprise Human-in-the-Loop review & approval node."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Task title displayed in the Enterprise Approval Inbox")
    description: Optional[str] = Field(default=None, description="Detailed instructions for the human reviewer")
    assigned_role: str = Field(default="role:general_operator", description="Okta/AD role authorized to approve (e.g. 'role:L2_Compliance_Analyst')")
    allowed_actions: List[str] = Field(
        default_factory=lambda: ["APPROVE", "REJECT", "EDIT_AND_APPROVE"],
        description="Allowed decision actions",
    )
    sla_timeout_seconds: Optional[int] = Field(default=14400, ge=1, description="SLA duration in seconds before escalation")
    escalation_target: Optional[str] = Field(default=None, description="Fallback target node if SLA is breached")
    form_fields: Optional[List[str]] = Field(default=None, description="Subset of graph state fields to display in review form")


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
    Can represent a Domain Block, DMN Table, Semantic Router, Human Review, or Gateway.
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
    dmn_config: Optional[DMNTableConfig] = Field(default=None, description="Decision rules if type='dmn_table'")
    semantic_config: Optional[SemanticRouterConfig] = Field(default=None, description="Semantic routes if type='semantic_router'")
    human_review_config: Optional[HumanReviewConfig] = Field(default=None, description="HITL approval settings if type='human_review'")
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
