from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, Optional, Union
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from agent_bpmn.compiler.dmn_compiler import compile_dmn_table_router
from agent_bpmn.compiler.semantic_compiler import compile_semantic_router
from agent_bpmn.dsl.linter import WorkflowLinter
from agent_bpmn.dsl.schema import NodeType, WorkflowDefinition
from agent_bpmn.sdk.registry import CapabilityRegistry, registry as default_registry


class CompilationError(Exception):
    """Raised when compiling a declarative workflow definition into LangGraph fails."""
    pass


class CompiledWorkflow:
    """
    An executable AgentBPMN workflow compiled into a LangGraph StateGraph runtime.
    """

    def __init__(
        self,
        workflow: WorkflowDefinition,
        state_graph: StateGraph,
        compiled_graph: Any,
    ) -> None:
        self.workflow = workflow
        self.state_graph = state_graph
        self.compiled_graph = compiled_graph

    async def ainvoke(
        self,
        initial_state: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Asynchronously executes the compiled workflow with the given initial state."""
        state_payload = dict(initial_state)
        if "__telemetry__" not in state_payload:
            state_payload["__telemetry__"] = {}
        if "__history__" not in state_payload:
            state_payload["__history__"] = []

        return await self.compiled_graph.ainvoke(state_payload, config=config)

    def invoke(
        self,
        initial_state: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronously executes the compiled workflow."""
        state_payload = dict(initial_state)
        if "__telemetry__" not in state_payload:
            state_payload["__telemetry__"] = {}
        if "__history__" not in state_payload:
            state_payload["__history__"] = []

        return self.compiled_graph.invoke(state_payload, config=config)


class GraphCompiler:
    """
    Compiles an AgentBPMN declarative WorkflowDefinition AST directly
    into a LangGraph StateGraph execution graph supporting hybrid routing
    (DMN Decision Tables + Semantic Intent Classifiers).
    """

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ) -> None:
        self.registry = registry if registry is not None else default_registry
        self.checkpointer = checkpointer
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

        # Helper for router pass-through nodes
        def make_passthrough_node(node_id: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
            def passthrough(state: Dict[str, Any]) -> Dict[str, Any]:
                history = list(state.get("__history__", []))
                history.append(node_id)
                return {**state, "__history__": history}
            return passthrough

        # 1. Register Nodes & Conditional Routers
        for node in workflow.nodes:
            if node.type == NodeType.BLOCK:
                handler = self._create_block_node_handler(node)
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
        )

    def _create_block_node_handler(self, node: Any) -> Callable[[Dict[str, Any]], Any]:
        """Creates an async LangGraph node function that bridges graph state to a certified Domain Block."""
        block_id = node.block
        reg = self.registry

        async def block_node_handler(state: Dict[str, Any]) -> Dict[str, Any]:
            # 1. Extract and map inputs from graph state
            payload: Dict[str, Any] = {}

            # Apply explicit input mapping
            for block_param, mapping_spec in node.input_mapping.items():
                if isinstance(mapping_spec, str) and mapping_spec.startswith("$"):
                    state_key = mapping_spec.lstrip("$").replace("state.", "")
                    payload[block_param] = state.get(state_key)
                elif isinstance(mapping_spec, str) and mapping_spec in state:
                    payload[block_param] = state[mapping_spec]
                else:
                    payload[block_param] = mapping_spec

            # For unmapped required block properties, pull matching keys from state
            registered = reg.get(block_id)
            input_props = registered.contract.input_schema.get("properties", {}).keys()
            for prop in input_props:
                if prop not in payload and prop in state:
                    payload[prop] = state[prop]

            # 2. Execute block with strict runtime Pydantic validation
            t0 = time.perf_counter()
            output_model = await reg.execute(block_id, payload)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            output_dict = output_model.model_dump()

            # 3. Map output attributes back to graph state
            state_updates: Dict[str, Any] = {}
            if node.output_mapping:
                for block_attr, target_state_key in node.output_mapping.items():
                    if block_attr in output_dict:
                        state_updates[target_state_key] = output_dict[block_attr]
            else:
                state_updates[node.id] = output_dict
                for k, v in output_dict.items():
                    if k not in state_updates:
                        state_updates[k] = v

            # 4. Telemetry tracking
            telemetry = dict(state.get("__telemetry__", {}))
            telemetry[node.id] = {
                "block": block_id,
                "latency_ms": elapsed_ms,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            state_updates["__telemetry__"] = telemetry

            # Execution history trail
            history = list(state.get("__history__", []))
            history.append(node.id)
            state_updates["__history__"] = history

            # Return merged state to preserve full context across nodes in LangGraph
            return {**state, **state_updates}

        return block_node_handler
