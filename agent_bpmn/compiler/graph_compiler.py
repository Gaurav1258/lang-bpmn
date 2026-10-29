from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, Optional, Union
import uuid
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

from agent_bpmn.compiler.dmn_compiler import compile_dmn_table_router
from agent_bpmn.compiler.guardrails import (
    BudgetExceededError,
    GuardrailViolationError,
    LoopIterationLimitExceeded,
)
from agent_bpmn.compiler.semantic_compiler import compile_semantic_router
from agent_bpmn.dsl.linter import WorkflowLinter
from agent_bpmn.dsl.schema import NodeType, WorkflowDefinition
from agent_bpmn.runtime.hitl_inbox import ApprovalInboxService, inbox_service as default_inbox_service
from agent_bpmn.runtime.telemetry import (
    TelemetryAggregator,
    WorkflowHeatmap,
    telemetry_aggregator as default_telemetry_aggregator,
)
from agent_bpmn.sdk.registry import CapabilityRegistry, registry as default_registry


class CompilationError(Exception):
    """Raised when compiling a declarative workflow definition into LangGraph fails."""
    pass


class CompiledWorkflow:
    """
    An executable AgentBPMN workflow compiled into a LangGraph StateGraph runtime.
    Features automated state merging, checkpoint resumption, guardrail enforcement,
    and Process Intelligence Heatmap aggregation.
    """

    def __init__(
        self,
        workflow: WorkflowDefinition,
        state_graph: StateGraph,
        compiled_graph: Any,
        inbox_service: ApprovalInboxService,
        telemetry_aggregator: TelemetryAggregator,
    ) -> None:
        self.workflow = workflow
        self.state_graph = state_graph
        self.compiled_graph = compiled_graph
        self.inbox_service = inbox_service
        self.telemetry_aggregator = telemetry_aggregator

    async def ainvoke(
        self,
        initial_state: Union[Dict[str, Any], Command],
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Asynchronously executes the compiled workflow with the given initial state or Command(resume=...)."""
        run_config = dict(config or {})
        if "configurable" not in run_config:
            run_config["configurable"] = {}
        if "thread_id" not in run_config["configurable"]:
            run_config["configurable"]["thread_id"] = f"run_{uuid.uuid4().hex[:10]}"

        thread_id = run_config["configurable"]["thread_id"]
        t0 = time.perf_counter()

        if isinstance(initial_state, Command):
            res = await self.compiled_graph.ainvoke(initial_state, config=run_config)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            self.telemetry_aggregator.record_from_state(
                self.workflow.metadata.id, res, status="COMPLETED", total_duration_ms=elapsed_ms
            )
            return res

        state_payload = dict(initial_state)
        state_payload["__thread_id__"] = thread_id
        if "__telemetry__" not in state_payload:
            state_payload["__telemetry__"] = {}
        if "__history__" not in state_payload:
            state_payload["__history__"] = []
        if "__sys_node_visits" not in state_payload:
            state_payload["__sys_node_visits"] = {}
        if "__sys_total_cost_usd" not in state_payload:
            state_payload["__sys_total_cost_usd"] = 0.0

        res = await self.compiled_graph.ainvoke(state_payload, config=run_config)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        status = "INTERRUPTED" if "__interrupt__" in res and res["__interrupt__"] else "COMPLETED"
        self.telemetry_aggregator.record_from_state(
            self.workflow.metadata.id, res, status=status, total_duration_ms=elapsed_ms
        )
        return res

    def invoke(
        self,
        initial_state: Union[Dict[str, Any], Command],
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronously executes the compiled workflow, bridging to async execution."""
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self.ainvoke(initial_state, config=config))
                return future.result()
        else:
            return asyncio.run(self.ainvoke(initial_state, config=config))

    def get_heatmap(self) -> WorkflowHeatmap:
        """Computes and returns the visual Process Intelligence Heatmap for this workflow."""
        return self.telemetry_aggregator.get_heatmap(self.workflow.metadata.id)


class GraphCompiler:
    """
    Compiles an AgentBPMN declarative WorkflowDefinition AST directly
    into a LangGraph StateGraph execution graph supporting:
    - Domain Blocks with Pydantic contracts
    - Hybrid Routing (DMN Tables + Semantic Routers)
    - Enterprise Human-in-the-Loop Approval Inboxes with Command(resume=...)
    - Visual Loop & Budget Guardrails (Loop iteration caps & USD spend limits)
    - Process Intelligence Heatmap Telemetry
    """

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        inbox_service: Optional[ApprovalInboxService] = None,
        telemetry_aggregator: Optional[TelemetryAggregator] = None,
    ) -> None:
        self.registry = registry if registry is not None else default_registry
        self.checkpointer = checkpointer or MemorySaver()
        self.inbox_service = inbox_service or default_inbox_service
        self.telemetry_aggregator = telemetry_aggregator or default_telemetry_aggregator
        self.linter = WorkflowLinter(registry=self.registry)

    def compile(self, workflow: WorkflowDefinition, validate: bool = True) -> CompiledWorkflow:
        """
        Validates and translates a WorkflowDefinition AST into an executable LangGraph instance.
        """
        if validate:
            lint_res = self.linter.lint(workflow)
            lint_res.raise_if_invalid()

        builder = StateGraph(dict)
        connected_sources = set()
        connected_targets = set()

        def make_passthrough_node(node_id: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
            def passthrough(state: Dict[str, Any]) -> Dict[str, Any]:
                history = list(state.get("__history__", []))
                history.append(node_id)
                return {**state, "__history__": history}
            return passthrough

        # 1. Register Nodes
        for node in workflow.nodes:
            if node.type == NodeType.BLOCK:
                handler = self._create_block_node_handler(node, workflow)
                builder.add_node(node.id, handler)

            elif node.type == NodeType.DMN_TABLE:
                builder.add_node(node.id, make_passthrough_node(node.id))
                if node.dmn_config:
                    router_fn, path_map = compile_dmn_table_router(node.dmn_config, table_id=node.id)
                    builder.add_conditional_edges(node.id, router_fn, path_map)
                    connected_sources.add(node.id)

            elif node.type == NodeType.SEMANTIC_ROUTER:
                builder.add_node(node.id, make_passthrough_node(node.id))
                if node.semantic_config:
                    router_fn, path_map = compile_semantic_router(node.semantic_config, router_id=node.id)
                    builder.add_conditional_edges(node.id, router_fn, path_map)
                    connected_sources.add(node.id)

            elif node.type == NodeType.HUMAN_REVIEW:
                human_handler = self._create_human_review_node_handler(node, workflow.metadata.id)
                builder.add_node(node.id, human_handler)

            elif node.type in (NodeType.START, NodeType.END):
                builder.add_node(node.id, make_passthrough_node(node.id))

            else:
                builder.add_node(node.id, make_passthrough_node(node.id))

        # 2. Wire Standard Directed Edges
        for edge in workflow.edges:
            src = START if edge.source == "START" else edge.source
            tgt = END if edge.target == "END" else edge.target

            builder.add_edge(src, tgt)
            connected_sources.add(edge.source)
            connected_targets.add(edge.target)

        # 3. Auto-infer entrypoint if not explicitly defined
        if "START" not in connected_sources:
            candidate_starts = [n.id for n in workflow.nodes if n.id not in connected_targets]
            if candidate_starts:
                builder.add_edge(START, candidate_starts[0])
            elif workflow.nodes:
                builder.add_edge(START, workflow.nodes[0].id)

        # 4. Auto-infer exit edges for nodes without outgoing links
        for node in workflow.nodes:
            if node.id not in connected_sources and node.type != NodeType.END:
                builder.add_edge(node.id, END)

        compiled_graph = builder.compile(checkpointer=self.checkpointer)

        return CompiledWorkflow(
            workflow=workflow,
            state_graph=builder,
            compiled_graph=compiled_graph,
            inbox_service=self.inbox_service,
            telemetry_aggregator=self.telemetry_aggregator,
        )

    def _create_human_review_node_handler(
        self,
        node: Any,
        workflow_id: str,
    ) -> Callable[[Dict[str, Any]], Any]:
        """Creates an interrupt-driven Human Review node handler linked to the Approval Inbox."""
        inbox = self.inbox_service
        cfg = node.human_review_config

        def human_review_handler(state: Dict[str, Any]) -> Any:
            title = cfg.title if cfg else f"Human Review Required: {node.id}"
            assigned_role = cfg.assigned_role if cfg else "role:general_operator"
            description = cfg.description if cfg else None
            allowed_actions = cfg.allowed_actions if cfg else ["APPROVE", "REJECT", "EDIT_AND_APPROVE"]
            sla_timeout_seconds = cfg.sla_timeout_seconds if cfg else 14400
            escalation_target = cfg.escalation_target if cfg else None
            form_fields = cfg.form_fields if cfg else None

            thread_id = state.get("__thread_id__", f"thread_{uuid.uuid4().hex[:8]}")
            clean_state = {k: v for k, v in state.items() if not k.startswith("__")}

            task = inbox.create_task(
                thread_id=thread_id,
                workflow_id=workflow_id,
                node_id=node.id,
                title=title,
                assigned_role=assigned_role,
                state_snapshot=clean_state,
                description=description,
                allowed_actions=allowed_actions,
                sla_timeout_seconds=sla_timeout_seconds,
                escalation_target=escalation_target,
                form_fields=form_fields,
            )

            decision = interrupt({
                "task_id": task.task_id,
                "title": title,
                "assigned_role": assigned_role,
                "state_snapshot": clean_state,
                "allowed_actions": allowed_actions,
            })

            action = decision.get("action", "APPROVE")
            reviewer = decision.get("reviewer", "human_reviewer")
            comments = decision.get("comments")
            updated_fields = decision.get("updated_fields", {})

            state_updates: Dict[str, Any] = {
                f"{node.id}_decision": action,
                f"{node.id}_reviewer": reviewer,
                f"{node.id}_comments": comments,
                "last_review_decision": action,
                "last_reviewer": reviewer,
            }

            if updated_fields and isinstance(updated_fields, dict):
                state_updates.update(updated_fields)

            history = list(state.get("__history__", []))
            history.append(node.id)
            state_updates["__history__"] = history

            return {**state, **state_updates}

        return human_review_handler

    def _create_block_node_handler(
        self,
        node: Any,
        workflow: WorkflowDefinition,
    ) -> Callable[[Dict[str, Any]], Any]:
        """Creates an async LangGraph node function with strict loop & budget guardrails."""
        block_id = node.block
        reg = self.registry

        async def block_node_handler(state: Dict[str, Any]) -> Dict[str, Any]:
            state_updates: Dict[str, Any] = {}

            # 1. Loop Guardrail Check
            visits_map = dict(state.get("__sys_node_visits", {}))
            current_visits = visits_map.get(node.id, 0) + 1
            visits_map[node.id] = current_visits
            state_updates["__sys_node_visits"] = visits_map

            max_visits = node.max_retries if node.max_retries is not None else workflow.guardrails.max_loop_iterations
            if current_visits > max_visits:
                raise LoopIterationLimitExceeded(node.id, current_visits, max_visits)

            # 2. Budget Guardrail Check
            registered = reg.get(block_id)
            node_cost = registered.contract.metadata.estimated_cost_usd
            current_total_cost = float(state.get("__sys_total_cost_usd", 0.0)) + node_cost
            state_updates["__sys_total_cost_usd"] = round(current_total_cost, 6)

            max_budget = workflow.guardrails.max_total_budget_usd
            if max_budget is not None and current_total_cost > max_budget:
                raise BudgetExceededError(current_total_cost, max_budget, node.id)

            # 3. Extract and map inputs from graph state
            payload: Dict[str, Any] = {}
            for block_param, mapping_spec in node.input_mapping.items():
                if isinstance(mapping_spec, str) and mapping_spec.startswith("$"):
                    state_key = mapping_spec.lstrip("$").replace("state.", "")
                    payload[block_param] = state.get(state_key)
                elif isinstance(mapping_spec, str) and mapping_spec in state:
                    payload[block_param] = state[mapping_spec]
                else:
                    payload[block_param] = mapping_spec

            input_props = registered.contract.input_schema.get("properties", {}).keys()
            for prop in input_props:
                if prop not in payload and prop in state:
                    payload[prop] = state[prop]

            # 4. Execute block with strict runtime Pydantic validation
            t0 = time.perf_counter()
            output_model = await reg.execute(block_id, payload)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            output_dict = output_model.model_dump()

            # 5. Map output attributes back to graph state
            if node.output_mapping:
                for block_attr, target_state_key in node.output_mapping.items():
                    if block_attr in output_dict:
                        state_updates[target_state_key] = output_dict[block_attr]
            else:
                state_updates[node.id] = output_dict
                for k, v in output_dict.items():
                    if k not in state_updates:
                        state_updates[k] = v

            # 6. Telemetry tracking
            telemetry = dict(state.get("__telemetry__", {}))
            telemetry[node.id] = {
                "block": block_id,
                "latency_ms": elapsed_ms,
                "cost_usd": node_cost,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            state_updates["__telemetry__"] = telemetry

            # Execution history trail
            history = list(state.get("__history__", []))
            history.append(node.id)
            state_updates["__history__"] = history

            return {**state, **state_updates}

        return block_node_handler
