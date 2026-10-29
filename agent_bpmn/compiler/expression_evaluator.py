import ast
import operator
from typing import Any, Dict


class SafeEvaluationError(Exception):
    """Raised when an expression cannot be safely evaluated."""
    pass


class SafeExpressionEvaluator:
    """
    Evaluates business rule condition expressions safely using Python's AST parser.
    Strictly forbids builtins, arbitrary function calls, attribute access, and imports
    to guarantee 100% deterministic, sandboxed execution without arbitrary code execution.
    """

    OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.Not: operator.not_,
    }

    @classmethod
    def evaluate(cls, expression: str, state: Dict[str, Any]) -> bool:
        """
        Parses and evaluates a boolean expression string against the provided state dictionary.
        Example: "invoice_total_usd > 10000 and sanctions_risk_score >= 0.7"
        """
        expr_clean = expression.strip()
        if not expr_clean:
            return True

        # Convert common natural/SQL boolean syntax to Python syntax
        expr_normalized = expr_clean.replace("&&", " and ").replace("||", " or ")

        try:
            tree = ast.parse(expr_normalized, mode="eval")
            result = cls._eval_node(tree.body, state)
            return bool(result)
        except SafeEvaluationError:
            raise
        except Exception as e:
            raise SafeEvaluationError(f"Failed to evaluate expression '{expression}': {str(e)}") from e

    @classmethod
    def _eval_node(cls, node: ast.AST, state: Dict[str, Any]) -> Any:
        # Constant literals: int, float, str, bool, None
        if isinstance(node, ast.Constant):
            return node.value

        # Variable lookups from graph state
        if isinstance(node, ast.Name):
            var_name = node.id
            if var_name in ("True", "true"):
                return True
            if var_name in ("False", "false"):
                return False
            if var_name in ("None", "null"):
                return None
            if var_name in state:
                return state[var_name]
            # If not in state, treat as None or 0 to avoid crashes on missing keys
            return None

        # Comparisons: a > b, x == y, item in list
        if isinstance(node, ast.Compare):
            left = cls._eval_node(node.left, state)
            for op_type, comparator in zip(node.ops, node.comparators):
                right = cls._eval_node(comparator, state)
                op_func = cls.OPERATORS.get(type(op_type))
                if op_func is None:
                    raise SafeEvaluationError(f"Unsupported comparison operator: {type(op_type).__name__}")
                
                # Handle None comparison gracefully
                if left is None and right is not None and type(op_type) in (ast.Lt, ast.LtE, ast.Gt, ast.GtE):
                    return False
                if right is None and left is not None and type(op_type) in (ast.Lt, ast.LtE, ast.Gt, ast.GtE):
                    return False

                if not op_func(left, right):
                    return False
                left = right
            return True

        # Boolean operations: and, or
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value_node in node.values:
                    if not bool(cls._eval_node(value_node, state)):
                        return False
                return True
            elif isinstance(node.op, ast.Or):
                for value_node in node.values:
                    if bool(cls._eval_node(value_node, state)):
                        return True
                return False
            else:
                raise SafeEvaluationError(f"Unsupported boolean operator: {type(node.op).__name__}")

        # Unary operations: not x
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return not bool(cls._eval_node(node.operand, state))
            raise SafeEvaluationError(f"Unsupported unary operator: {type(node.op).__name__}")

        # Lists/Tuples for 'in' comparisons: e.g. "country in ['US', 'CA', 'GB']"
        if isinstance(node, (ast.List, ast.Tuple)):
            return [cls._eval_node(elt, state) for elt in node.elts]

        # Forbid all other node types (Call, Attribute, Import, Lambda, etc.)
        raise SafeEvaluationError(
            f"Security Violation: Node type '{type(node).__name__}' is forbidden in safe business expressions."
        )

