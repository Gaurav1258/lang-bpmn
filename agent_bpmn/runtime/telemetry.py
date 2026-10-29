from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class NodeTelemetryRecord(BaseModel):
    """Telemetry captured for a single node execution in a workflow run."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    block_id: Optional[str] = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    human_action: Optional[str] = None


class RunTelemetryRecord(BaseModel):
    """Execution telemetry captured for an entire workflow run."""
    model_config = ConfigDict(extra="ignore")

    run_id: str
    workflow_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "COMPLETED"
    total_cost_usd: float = 0.0
    total_duration_ms: float = 0.0
    node_visits: Dict[str, int] = Field(default_factory=dict)
    node_records: List[NodeTelemetryRecord] = Field(default_factory=list)


class NodeHeatmapMetric(BaseModel):
    """Aggregated process intelligence metrics for a single canvas node."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    call_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    human_override_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Percentage of human tasks modified or rejected")
    bottleneck_level: str = Field(default="NORMAL", description="'NORMAL', 'WARNING', or 'CRITICAL' bottleneck indicator")


class WorkflowHeatmap(BaseModel):
    """
    Process Intelligence Heatmap for a workflow topology.
    Maps 1:1 to canvas node overlays for visual unit economics and latency bottlenecks.
    """
    model_config = ConfigDict(extra="ignore")

    workflow_id: str
    total_runs: int = 0
    total_cost_usd: float = 0.0
    avg_run_cost_usd: float = 0.0
    node_metrics: Dict[str, NodeHeatmapMetric] = Field(default_factory=dict)


class TelemetryAggregator:
    """
    Collects, indexes, and computes Process Intelligence Heatmap metrics
    across historical production runs.
    """

    def __init__(self) -> None:
        self._runs: Dict[str, List[RunTelemetryRecord]] = {}

    def record_run(self, run: RunTelemetryRecord) -> None:
        wf_id = run.workflow_id
        if wf_id not in self._runs:
            self._runs[wf_id] = []
        self._runs[wf_id].append(run)

    def record_from_state(
        self,
        workflow_id: str,
        state: Dict[str, Any],
        status: str = "COMPLETED",
        total_duration_ms: float = 0.0,
    ) -> RunTelemetryRecord:
        """Extracts telemetry from the LangGraph execution state updates and indexes it."""
        run_id = state.get("__thread_id__", f"run_{datetime.now(timezone.utc).timestamp()}")
        node_visits = dict(state.get("__sys_node_visits", {}))
        total_cost = float(state.get("__sys_total_cost_usd", 0.0))
        telemetry_map = state.get("__telemetry__", {})

        records: List[NodeTelemetryRecord] = []
        for nid, data in telemetry_map.items():
            if isinstance(data, dict):
                # Detect human action if present
                h_action = state.get(f"{nid}_decision")
                records.append(
                    NodeTelemetryRecord(
                        node_id=nid,
                        block_id=data.get("block"),
                        latency_ms=float(data.get("latency_ms", 0.0)),
                        cost_usd=float(data.get("cost_usd", 0.0)),
                        human_action=h_action,
                    )
                )

        run = RunTelemetryRecord(
            run_id=run_id,
            workflow_id=workflow_id,
            status=status,
            total_cost_usd=total_cost,
            total_duration_ms=total_duration_ms,
            node_visits=node_visits,
            node_records=records,
        )
        self.record_run(run)
        return run

    def get_heatmap(self, workflow_id: str) -> WorkflowHeatmap:
        runs = self._runs.get(workflow_id, [])
        if not runs:
            return WorkflowHeatmap(workflow_id=workflow_id)

        total_runs = len(runs)
        total_wf_cost = sum(r.total_cost_usd for r in runs)
        avg_wf_cost = total_wf_cost / total_runs

        # Group metrics per node
        node_latencies: Dict[str, List[float]] = {}
        node_costs: Dict[str, List[float]] = {}
        node_human_actions: Dict[str, List[str]] = {}

        for r in runs:
            for rec in r.node_records:
                nid = rec.node_id
                if nid not in node_latencies:
                    node_latencies[nid] = []
                    node_costs[nid] = []
                    node_human_actions[nid] = []

                node_latencies[nid].append(rec.latency_ms)
                node_costs[nid].append(rec.cost_usd)
                if rec.human_action:
                    node_human_actions[nid].append(rec.human_action)

        node_metrics: Dict[str, NodeHeatmapMetric] = {}
        for nid, latencies in node_latencies.items():
            call_count = len(latencies)
            avg_lat = sum(latencies) / call_count if call_count > 0 else 0.0

            # Calculate P95 latency
            sorted_lat = sorted(latencies)
            p95_idx = min(math.ceil(0.95 * call_count) - 1, call_count - 1)
            p95_lat = sorted_lat[p95_idx] if sorted_lat else 0.0

            costs = node_costs.get(nid, [])
            tot_cost = sum(costs)
            avg_cost = tot_cost / call_count if call_count > 0 else 0.0

            # Calculate Human Override / Rejection Rate
            actions = node_human_actions.get(nid, [])
            override_count = sum(1 for a in actions if a in ("EDIT_AND_APPROVE", "REJECT"))
            override_rate = (override_count / len(actions)) if actions else 0.0

            # Determine bottleneck severity level
            severity = "NORMAL"
            if p95_lat > 2500 or avg_cost > 0.05 or override_rate > 0.35:
                severity = "CRITICAL"
            elif p95_lat > 1000 or avg_cost > 0.02 or override_rate > 0.15:
                severity = "WARNING"

            node_metrics[nid] = NodeHeatmapMetric(
                node_id=nid,
                call_count=call_count,
                avg_latency_ms=round(avg_lat, 2),
                p95_latency_ms=round(p95_lat, 2),
                avg_cost_usd=round(avg_cost, 4),
                total_cost_usd=round(tot_cost, 4),
                human_override_rate=round(override_rate, 2),
                bottleneck_level=severity,
            )

        return WorkflowHeatmap(
            workflow_id=workflow_id,
            total_runs=total_runs,
            total_cost_usd=round(total_wf_cost, 4),
            avg_run_cost_usd=round(avg_wf_cost, 4),
            node_metrics=node_metrics,
        )

    def export_heatmap_json(self, workflow_id: str, filepath: Optional[Union[str, Path]] = None, indent: int = 2) -> str:
        heatmap = self.get_heatmap(workflow_id)
        json_str = heatmap.model_dump_json(indent=indent)
        if filepath:
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
        return json_str

    def clear(self) -> None:
        self._runs.clear()


# Default singleton telemetry aggregator
telemetry_aggregator = TelemetryAggregator()

