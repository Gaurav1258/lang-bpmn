from typing import Any, Dict, Optional


class GuardrailViolationError(Exception):
    """Base exception for workflow operational guardrail violations."""
    pass


class BudgetExceededError(GuardrailViolationError):
    """Raised when workflow accumulated spend exceeds the management-configured budget cap."""
    def __init__(self, current_cost: float, max_budget: float, node_id: str):
        super().__init__(
            f"Budget Cap Exceeded at node '{node_id}': Accumulated spend ${current_cost:.4f} USD "
            f"exceeds hard limit of ${max_budget:.4f} USD."
        )
        self.current_cost = current_cost
        self.max_budget = max_budget
        self.node_id = node_id


class LoopIterationLimitExceeded(GuardrailViolationError):
    """Raised when a cyclic node or loop edge exceeds maximum allowable iterations."""
    def __init__(self, node_id: str, current_iterations: int, max_iterations: int):
        super().__init__(
            f"Loop Guardrail Tripped at node '{node_id}': Iteration count {current_iterations} "
            f"exceeds maximum allowed loop limit of {max_iterations} iterations."
        )
        self.node_id = node_id
        self.current_iterations = current_iterations
        self.max_iterations = max_iterations

