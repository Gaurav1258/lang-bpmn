from typing import Any, Callable, Dict, Tuple
from langgraph.graph import END

from agent_bpmn.compiler.expression_evaluator import SafeExpressionEvaluator
from agent_bpmn.dsl.schema import DMNTableConfig, HitPolicy


class DMNCompilationError(Exception):
    """Raised when compiling a DMN Decision Table fails."""
    pass


def compile_dmn_table_router(
    dmn_config: DMNTableConfig,
    table_id: str = "dmn_table",
) -> Tuple[Callable[[Dict[str, Any]], str], Dict[str, Any]]:
    """
    Compiles a DMN Decision Table into a deterministic routing function and path map
    compatible with LangGraph's add_conditional_edges().

    Returns:
        (routing_function, path_map)
    """
    if not dmn_config.rules and not dmn_config.default_target:
        raise DMNCompilationError(f"DMN table '{table_id}' has no decision rules and no default target.")

    # Build path map for LangGraph
    path_map: Dict[str, Any] = {}
    for rule in dmn_config.rules:
        target_name = rule.target
        target_dest = END if target_name == "END" else target_name
        path_map[target_name] = target_dest

    if dmn_config.default_target:
        def_name = dmn_config.default_target
        path_map[def_name] = END if def_name == "END" else def_name

    def dmn_router(state: Dict[str, Any]) -> str:
        """Evaluates rules in order (FIRST_MATCH) against runtime graph state."""
        for rule in dmn_config.rules:
            # Fallback or default rule without condition
            if rule.condition is None or rule.condition.strip().lower() in ("default", "true", "*"):
                return rule.target

            try:
                matched = SafeExpressionEvaluator.evaluate(rule.condition, state)
                if matched:
                    return rule.target
            except Exception as e:
                # Log or handle expression evaluation error
                continue

        # If no rule matches, return default target
        if dmn_config.default_target:
            return dmn_config.default_target

        # If no default, route to END
        return "END"

    return dmn_router, path_map

