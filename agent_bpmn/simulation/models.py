from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HistoricalCase(BaseModel):
    """
    A single historical production execution case used for sandbox simulation.
    Contains initial inputs and baseline metrics from production runs.
    """
    case_id: str
    input_payload: Dict[str, Any]
    baseline_route: List[str] = Field(default_factory=list)
    baseline_terminal_node: Optional[str] = None
    baseline_cost_usd: float = 0.0
    baseline_duration_ms: float = 0.0
    baseline_status: str = "COMPLETED"


class SimulationDataset(BaseModel):
    """
    A collection of historical production cases used for pre-flight testing.
    """
    dataset_id: str
    workflow_id: str
    description: Optional[str] = None
    cases: List[HistoricalCase] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_case(self, case: HistoricalCase) -> None:
        self.cases.append(case)

    def __len__(self) -> int:
        return len(self.cases)


class CandidateCaseResult(BaseModel):
    """
    The outcome of replaying a single historical case through the candidate workflow AST.
    """
    case_id: str
    status: str  # "SUCCESS", "FAILED", "GUARDRAIL_TRIPPED", "INTERRUPTED"
    route_taken: List[str] = Field(default_factory=list)
    terminal_node: Optional[str] = None
    final_state: Dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error_message: Optional[str] = None


class RouteShiftMetric(BaseModel):
    """
    Quantifies the distribution shift for a specific node or destination route.
    """
    node_id: str
    baseline_count: int = 0
    candidate_count: int = 0
    baseline_pct: float = 0.0
    candidate_pct: float = 0.0
    shift_pct_points: float = 0.0  # e.g., -15.0% or +25.0%


class SimulationImpactDiff(BaseModel):
    """
    Comprehensive pre-flight impact diff comparing production baseline vs candidate workflow.
    """
    total_cases: int
    candidate_success_count: int
    candidate_failure_count: int
    candidate_guardrail_trip_count: int
    candidate_success_rate: float

    route_shifts: Dict[str, RouteShiftMetric] = Field(default_factory=dict)

    baseline_avg_cost_usd: float = 0.0
    candidate_avg_cost_usd: float = 0.0
    cost_delta_usd: float = 0.0
    cost_delta_pct: float = 0.0

    baseline_avg_latency_ms: float = 0.0
    candidate_avg_latency_ms: float = 0.0
    latency_delta_ms: float = 0.0
    latency_delta_pct: float = 0.0

    schema_failures: int = 0
    critical_findings: List[str] = Field(default_factory=list)


class SimulationReport(BaseModel):
    """
    Complete Pre-Flight Simulation Report for Enterprise Change Governance.
    """
    simulation_id: str
    baseline_workflow_id: str
    candidate_workflow_id: str
    candidate_version: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    diff: SimulationImpactDiff
    case_results: List[CandidateCaseResult] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """Renders an executive Markdown summary table for Git PR descriptions."""
        lines = [
            f"# 🧪 Pre-Flight Simulation Report: `{self.candidate_workflow_id}` (v{self.candidate_version})",
            f"**Simulation ID:** `{self.simulation_id}` | **Generated:** {self.generated_at}",
            f"**Cases Evaluated:** {self.diff.total_cases} Historical Production Runs",
            "",
            "## 📊 Executive Summary Diff",
            "| Metric | Production Baseline | Candidate Version | Delta | Status |",
            "| :--- | :--- | :--- | :--- | :--- |",
            f"| **Success Rate** | 100.0% | {self.diff.candidate_success_rate * 100:.1f}% | {(self.diff.candidate_success_rate - 1.0) * 100:+.1f}% | {'✅ PASS' if self.diff.candidate_success_rate >= 0.95 else '⚠️ WARNING'} |",
            f"| **Average Cost** | ${self.diff.baseline_avg_cost_usd:.4f} USD | ${self.diff.candidate_avg_cost_usd:.4f} USD | {self.diff.cost_delta_pct:+.1f}% | {'✅ DECREASED' if self.diff.cost_delta_pct <= 0 else 'ℹ️ INCREASED'} |",
            f"| **Average Latency** | {self.diff.baseline_avg_latency_ms:.1f} ms | {self.diff.candidate_avg_latency_ms:.1f} ms | {self.diff.latency_delta_pct:+.1f}% | {'✅ FASTER' if self.diff.latency_delta_pct <= 0 else 'ℹ️ SLOWER'} |",
            f"| **Schema Violations** | 0 | {self.diff.schema_failures} | 0 | {'✅ ZERO CRASHES' if self.diff.schema_failures == 0 else '❌ CRITICAL'} |",
            "",
            "## 🔀 Route Distribution Shifts",
            "| Destination Route / Node | Baseline Share | Candidate Share | Shift (% Points) | Direction |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for nid, r in sorted(self.diff.route_shifts.items(), key=lambda x: abs(x[1].shift_pct_points), reverse=True):
            direction = "➖ Neutral"
            if r.shift_pct_points > 0:
                direction = "📈 Increased (+)"
            elif r.shift_pct_points < 0:
                direction = "📉 Decreased (-)"
            lines.append(f"| `{nid}` | {r.baseline_pct:.1f}% | {r.candidate_pct:.1f}% | {r.shift_pct_points:+.1f}% | {direction} |")

        if self.diff.critical_findings:
            lines.extend([
                "",
                "## ⚠️ Critical Findings & Guardrails",
            ])
            for finding in self.diff.critical_findings:
                lines.append(f"- {finding}")

        return "\n".join(lines)

