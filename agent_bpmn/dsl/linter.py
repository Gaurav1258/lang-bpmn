from dataclasses import dataclass, field
from typing import List, Optional, Set
from pydantic import BaseModel

from agent_bpmn.dsl.schema import NodeType, WorkflowDefinition
from agent_bpmn.sdk.registry import CapabilityRegistry, registry as default_registry


@dataclass
class LintResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            error_msg = "\n".join(f" - {err}" for err in self.errors)
            raise ValueError(f"Workflow failed static linting validation:\n{error_msg}")


class WorkflowLinter:
    """
    Static analyzer for WorkflowDefinition ASTs.
    Catches disconnected nodes, broken edges, missing blocks, and contract mismatches
    before compiling to LangGraph runtime.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry if registry is not None else default_registry

    def lint(self, workflow: WorkflowDefinition) -> LintResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not workflow.nodes:
            errors.append("Workflow contains no nodes.")
            return LintResult(is_valid=False, errors=errors, warnings=warnings)

        # 1. Unique node IDs
        seen_ids: Set[str] = set()
        node_map = {}
        for node in workflow.nodes:
            if node.id in seen_ids:
                errors.append(f"Duplicate node ID detected: '{node.id}'")
            seen_ids.add(node.id)
            node_map[node.id] = node

        # 2. Block validation
        for node in workflow.nodes:
            if node.type == NodeType.BLOCK:
                if not node.block:
                    errors.append(f"Block node '{node.id}' has no 'block' capability reference specified.")
                elif not self.registry.has(node.block):
                    errors.append(
                        f"Node '{node.id}' references unknown domain block '{node.block}'. "
                        f"Ensure the capability is registered in the CapabilityRegistry."
                    )
                else:
                    # Validate input contract mapping
                    registered = self.registry.get(node.block)
                    contract = registered.contract
                    required_inputs = set(contract.input_schema.get("required", []))
                    mapped_inputs = set(node.input_mapping.keys())
                    missing_required = required_inputs - mapped_inputs
                    if missing_required:
                        warnings.append(
                            f"Node '{node.id}' does not explicitly map required block inputs: {list(missing_required)}. "
                            f"These must exist as matching keys in the graph state at runtime."
                        )

        # 3. Edge validation
        valid_endpoints = seen_ids.union({"START", "END"})
        for idx, edge in enumerate(workflow.edges):
            if edge.source not in valid_endpoints:
                errors.append(f"Edge #{idx} has invalid source '{edge.source}'. Must be 'START' or a known node ID.")
            if edge.target not in valid_endpoints:
                errors.append(f"Edge #{idx} has invalid target '{edge.target}'. Must be 'END' or a known node ID.")

        # 4. Topology & reachability
        incoming = {nid: 0 for nid in seen_ids}
        outgoing = {nid: 0 for nid in seen_ids}

        has_start_edge = False
        for edge in workflow.edges:
            if edge.source == "START":
                has_start_edge = True
                if edge.target in incoming:
                    incoming[edge.target] += 1
            elif edge.source in outgoing:
                outgoing[edge.source] += 1

            if edge.target != "END" and edge.target in incoming:
                incoming[edge.target] += 1

        # Check for disconnected or dead-end nodes
        for nid, count in incoming.items():
            if count == 0 and not has_start_edge:
                # If no explicit START edge, check if node is intended entrypoint
                pass
            elif count == 0 and has_start_edge:
                warnings.append(f"Node '{nid}' has no incoming edges and is unreachable from START.")

        for nid, count in outgoing.items():
            node = node_map.get(nid)
            if count == 0 and node and node.type != NodeType.END:
                warnings.append(f"Node '{nid}' has no outgoing edges and does not connect to 'END'.")

        is_valid = len(errors) == 0
        return LintResult(is_valid=is_valid, errors=errors, warnings=warnings)

