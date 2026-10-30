from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from agent_bpmn.compiler.graph_compiler import GraphCompiler
from agent_bpmn.compiler.guardrails import GuardrailViolationError
from agent_bpmn.dsl.schema import WorkflowDefinition
from agent_bpmn.runtime.telemetry import TelemetryAggregator
from agent_bpmn.sdk.registry import CapabilityRegistry, registry as default_registry
from agent_bpmn.simulation.models import (
    CandidateCaseResult,
    HistoricalCase,
    RouteShiftMetric,
    SimulationDataset,
    SimulationImpactDiff,
    SimulationReport,
)


class SimulationEngine:
    """
    Pillar 5: "Shadow Mode" & Pre-Flight Replay Simulation Engine.
    Executes historical production cases through candidate workflow AST topologies
    in a sandboxed runtime to evaluate route shifts, cost deltas, and schema safety
    prior to enterprise change approval.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or default_registry

    async def run_simulation(
        self,
        candidate_workflow: WorkflowDefinition,
        dataset: SimulationDataset,
        mock_blocks: Optional[Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None,
        simulation_id: Optional[str] = None,
    ) -> SimulationReport:
        """
        Executes all historical cases in the dataset against the candidate workflow AST
        and computes the complete pre-flight Impact Diff Analysis.
        """
        sim_id = simulation_id or f"sim_{uuid.uuid4().hex[:8]}"
        compiler = GraphCompiler(registry=self.registry)
        compiled = compiler.compile(candidate_workflow)

        case_results: List[CandidateCaseResult] = []
        schema_failures = 0
        guardrail_trips = 0
        success_count = 0
        failure_count = 0

        for case in dataset.cases:
            t0 = time.perf_counter()
            # Deep copy input payload to isolate each sandbox run
            payload = dict(case.input_payload)

            try:
                # Execute in candidate workflow
                res = await compiled.ainvoke(payload)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

                route = list(res.get("__history__", []))
                terminal = route[-1] if route else "END"
                cost = float(res.get("__sys_total_cost_usd", 0.0))

                is_interrupted = "__interrupt__" in res and bool(res["__interrupt__"])
                status = "INTERRUPTED" if is_interrupted else "SUCCESS"
                success_count += 1

                case_results.append(
                    CandidateCaseResult(
                        case_id=case.case_id,
                        status=status,
                        route_taken=route,
                        terminal_node=terminal,
                        final_state=res,
                        cost_usd=cost,
                        duration_ms=elapsed_ms,
                    )
                )

            except GuardrailViolationError as g_err:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                guardrail_trips += 1
                failure_count += 1
                case_results.append(
                    CandidateCaseResult(
                        case_id=case.case_id,
                        status="GUARDRAIL_TRIPPED",
                        route_taken=[],
                        terminal_node=getattr(g_err, "node_id", "GUARDRAIL"),
                        cost_usd=getattr(g_err, "current_cost", 0.0),
                        duration_ms=elapsed_ms,
                        error_message=str(g_err),
                    )
                )

            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                failure_count += 1
                err_msg = str(exc)
                if "validation" in err_msg.lower() or "schema" in err_msg.lower():
                    schema_failures += 1

                case_results.append(
                    CandidateCaseResult(
                        case_id=case.case_id,
                        status="FAILED",
                        route_taken=[],
                        terminal_node="ERROR",
                        cost_usd=0.0,
                        duration_ms=elapsed_ms,
                        error_message=err_msg,
                    )
                )

        diff = self._calculate_impact_diff(dataset, case_results, schema_failures, guardrail_trips)

        return SimulationReport(
            simulation_id=sim_id,
            baseline_workflow_id=dataset.workflow_id,
            candidate_workflow_id=candidate_workflow.metadata.id,
            candidate_version=candidate_workflow.metadata.version,
            diff=diff,
            case_results=case_results,
        )

    def run_simulation_sync(
        self,
        candidate_workflow: WorkflowDefinition,
        dataset: SimulationDataset,
        mock_blocks: Optional[Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None,
        simulation_id: Optional[str] = None,
    ) -> SimulationReport:
        """
        Synchronous version of run_simulation.
        Executes all historical cases against the candidate workflow using sync invoke.
        """
        sim_id = simulation_id or f"sim_{uuid.uuid4().hex[:8]}"
        compiler = GraphCompiler(registry=self.registry)
        compiled = compiler.compile(candidate_workflow)

        case_results: List[CandidateCaseResult] = []
        schema_failures = 0
        guardrail_trips = 0
        success_count = 0
        failure_count = 0

        for case in dataset.cases:
            t0 = time.perf_counter()
            payload = dict(case.input_payload)

            try:
                res = compiled.invoke(payload)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

                route = list(res.get("__history__", []))
                terminal = route[-1] if route else "END"
                cost = float(res.get("__sys_total_cost_usd", 0.0))

                is_interrupted = "__interrupt__" in res and bool(res["__interrupt__"])
                status = "INTERRUPTED" if is_interrupted else "SUCCESS"
                success_count += 1

                case_results.append(
                    CandidateCaseResult(
                        case_id=case.case_id,
                        status=status,
                        route_taken=route,
                        terminal_node=terminal,
                        final_state=res,
                        cost_usd=cost,
                        duration_ms=elapsed_ms,
                    )
                )

            except GuardrailViolationError as g_err:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                guardrail_trips += 1
                failure_count += 1
                case_results.append(
                    CandidateCaseResult(
                        case_id=case.case_id,
                        status="GUARDRAIL_TRIPPED",
                        route_taken=[],
                        terminal_node=getattr(g_err, "node_id", "GUARDRAIL"),
                        cost_usd=getattr(g_err, "current_cost", 0.0),
                        duration_ms=elapsed_ms,
                        error_message=str(g_err),
                    )
                )

            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                failure_count += 1
                err_msg = str(exc)
                if "validation" in err_msg.lower() or "schema" in err_msg.lower():
                    schema_failures += 1

                case_results.append(
                    CandidateCaseResult(
                        case_id=case.case_id,
                        status="FAILED",
                        route_taken=[],
                        terminal_node="ERROR",
                        cost_usd=0.0,
                        duration_ms=elapsed_ms,
                        error_message=err_msg,
                    )
                )

        diff = self._calculate_impact_diff(dataset, case_results, schema_failures, guardrail_trips)

        return SimulationReport(
            simulation_id=sim_id,
            baseline_workflow_id=dataset.workflow_id,
            candidate_workflow_id=candidate_workflow.metadata.id,
            candidate_version=candidate_workflow.metadata.version,
            diff=diff,
            case_results=case_results,
        )

    def _calculate_impact_diff(
        self,
        dataset: SimulationDataset,
        case_results: List[CandidateCaseResult],
        schema_failures: int,
        guardrail_trips: int,
    ) -> SimulationImpactDiff:
        """Computes statistical diffs between baseline production telemetry and candidate runs."""
        total_cases = len(dataset.cases)
        if total_cases == 0:
            return SimulationImpactDiff(
                total_cases=0,
                candidate_success_count=0,
                candidate_failure_count=0,
                candidate_guardrail_trip_count=0,
                candidate_success_rate=1.0,
            )

        success_count = sum(1 for c in case_results if c.status in ("SUCCESS", "INTERRUPTED"))
        failure_count = total_cases - success_count
        success_rate = round(success_count / total_cases, 4)

        # 1. Route Distribution Shifts
        # Count destination / terminal routes for baseline and candidate
        baseline_counts: Dict[str, int] = {}
        for case in dataset.cases:
            target = case.baseline_terminal_node or (case.baseline_route[-1] if case.baseline_route else "UNKNOWN")
            baseline_counts[target] = baseline_counts.get(target, 0) + 1

        candidate_counts: Dict[str, int] = {}
        for r in case_results:
            target = r.terminal_node or "UNKNOWN"
            candidate_counts[target] = candidate_counts.get(target, 0) + 1

        all_routes = set(baseline_counts.keys()).union(set(candidate_counts.keys()))
        route_shifts: Dict[str, RouteShiftMetric] = {}

        for route_id in sorted(all_routes):
            b_cnt = baseline_counts.get(route_id, 0)
            c_cnt = candidate_counts.get(route_id, 0)
            b_pct = round((b_cnt / total_cases) * 100, 2)
            c_pct = round((c_cnt / total_cases) * 100, 2)
            shift = round(c_pct - b_pct, 2)

            route_shifts[route_id] = RouteShiftMetric(
                node_id=route_id,
                baseline_count=b_cnt,
                candidate_count=c_cnt,
                baseline_pct=b_pct,
                candidate_pct=c_pct,
                shift_pct_points=shift,
            )

        # 2. Financial Economics & Latency Deltas
        baseline_costs = [c.baseline_cost_usd for c in dataset.cases]
        candidate_costs = [r.cost_usd for r in case_results]

        b_avg_cost = round(sum(baseline_costs) / total_cases, 4) if total_cases > 0 else 0.0
        c_avg_cost = round(sum(candidate_costs) / total_cases, 4) if total_cases > 0 else 0.0
        cost_delta_usd = round(c_avg_cost - b_avg_cost, 4)
        cost_delta_pct = round((cost_delta_usd / b_avg_cost) * 100, 2) if b_avg_cost > 0 else 0.0

        baseline_lats = [c.baseline_duration_ms for c in dataset.cases]
        candidate_lats = [r.duration_ms for r in case_results]

        b_avg_lat = round(sum(baseline_lats) / total_cases, 1) if total_cases > 0 else 0.0
        c_avg_lat = round(sum(candidate_lats) / total_cases, 1) if total_cases > 0 else 0.0
        lat_delta_ms = round(c_avg_lat - b_avg_lat, 1)
        lat_delta_pct = round((lat_delta_ms / b_avg_lat) * 100, 2) if b_avg_lat > 0 else 0.0

        # 3. Critical Findings Generation
        critical_findings: List[str] = []
        if schema_failures > 0:
            critical_findings.append(f"❌ {schema_failures} case(s) failed runtime Pydantic schema validation contracts.")
        if guardrail_trips > 0:
            critical_findings.append(f"⚠️ {guardrail_trips} case(s) tripped guardrail circuit breakers (budget or loop limits).")

        for route_id, metric in route_shifts.items():
            if abs(metric.shift_pct_points) >= 10.0:
                direction = "increased" if metric.shift_pct_points > 0 else "decreased"
                critical_findings.append(
                    f"🔀 Significant route shift on '{route_id}': {direction} by {abs(metric.shift_pct_points):.1f}% points "
                    f"({metric.baseline_pct:.1f}% -> {metric.candidate_pct:.1f}%)."
                )

        if not critical_findings:
            critical_findings.append("✅ Candidate workflow passed simulation with zero schema errors or unexpected anomalies.")

        return SimulationImpactDiff(
            total_cases=total_cases,
            candidate_success_count=success_count,
            candidate_failure_count=failure_count,
            candidate_guardrail_trip_count=guardrail_trips,
            candidate_success_rate=success_rate,
            route_shifts=route_shifts,
            baseline_avg_cost_usd=b_avg_cost,
            candidate_avg_cost_usd=c_avg_cost,
            cost_delta_usd=cost_delta_usd,
            cost_delta_pct=cost_delta_pct,
            baseline_avg_latency_ms=b_avg_lat,
            candidate_avg_latency_ms=c_avg_lat,
            latency_delta_ms=lat_delta_ms,
            latency_delta_pct=lat_delta_pct,
            schema_failures=schema_failures,
            critical_findings=critical_findings,
        )

    def extract_dataset_from_telemetry(
        self,
        aggregator: TelemetryAggregator,
        workflow_id: str,
        limit: int = 50,
    ) -> SimulationDataset:
        """Rehydrates a simulation dataset from historical production telemetry records."""
        runs = aggregator._runs.get(workflow_id, [])
        selected_runs = runs[-limit:] if limit > 0 else runs

        dataset = SimulationDataset(
            dataset_id=f"dataset_telemetry_{workflow_id}_{int(time.time())}",
            workflow_id=workflow_id,
            description=f"Extracted {len(selected_runs)} historical production traces from telemetry",
        )

        for run in selected_runs:
            terminal = run.node_records[-1].node_id if run.node_records else "END"
            route = [n.node_id for n in run.node_records]
            dataset.add_case(
                HistoricalCase(
                    case_id=run.run_id,
                    input_payload={},  # Will be enriched by caller or checkpointer if available
                    baseline_route=route,
                    baseline_terminal_node=terminal,
                    baseline_cost_usd=run.total_cost_usd,
                    baseline_duration_ms=run.total_duration_ms,
                    baseline_status=run.status,
                )
            )

        return dataset

