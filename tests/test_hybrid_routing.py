from pathlib import Path
import pytest

from agent_bpmn.compiler import (
    GraphCompiler,
    SafeEvaluationError,
    SafeExpressionEvaluator,
    SemanticIntentClassifier,
    compile_dmn_table_router,
)
from agent_bpmn.dsl import (
    DMNRule,
    DMNTableConfig,
    SemanticRoute,
    SemanticRouterConfig,
    parse_workflow_yaml,
)
import agent_bpmn.blocks.builtin  # Registers domain blocks


# ------------------------------------------------------------------------------
# 1. Safe AST Evaluator Unit Tests
# ------------------------------------------------------------------------------

def test_step3_1_safe_expression_evaluator_operators():
    """Verify safe AST evaluator correctly evaluates numeric, string, and boolean expressions."""
    state = {
        "amount": 25000.0,
        "risk_tier": "HIGH",
        "is_flagged": True,
        "country": "US",
        "score": 0.85,
    }

    assert SafeExpressionEvaluator.evaluate("amount > 10000 and risk_tier == 'HIGH'", state) is True
    assert SafeExpressionEvaluator.evaluate("amount < 5000", state) is False
    assert SafeExpressionEvaluator.evaluate("is_flagged == True and score >= 0.8", state) is True
    assert SafeExpressionEvaluator.evaluate("country in ['US', 'CA', 'GB']", state) is True
    assert SafeExpressionEvaluator.evaluate("country not in ['IR', 'KP', 'SY']", state) is True
    assert SafeExpressionEvaluator.evaluate("not is_flagged", state) is False


def test_step3_2_safe_expression_evaluator_security_rejections():
    """Verify safe evaluator strictly forbids code injections and arbitrary function calls."""
    state = {"x": 10}

    # Calls like __import__ or eval must raise SafeEvaluationError
    with pytest.raises(SafeEvaluationError, match="Security Violation"):
        SafeExpressionEvaluator.evaluate("__import__('os').system('echo pwned')", state)

    with pytest.raises(SafeEvaluationError, match="Security Violation"):
        SafeExpressionEvaluator.evaluate("open('secrets.txt').read()", state)


# ------------------------------------------------------------------------------
# 2. DMN Decision Table Compiler Unit Tests
# ------------------------------------------------------------------------------

def test_step3_3_dmn_decision_table_first_match_routing():
    """Verify DMN table routes deterministically using FIRST_MATCH policy."""
    dmn_config = DMNTableConfig(
        rules=[
            DMNRule(condition="amount > 100000", target="board_approval"),
            DMNRule(condition="amount > 10000 and is_flagged == true", target="senior_compliance"),
            DMNRule(condition="amount > 10000", target="manager_approval"),
            DMNRule(target="auto_approve"),  # Default fallback
        ],
        default_target="auto_approve",
    )

    router_fn, path_map = compile_dmn_table_router(dmn_config)
    assert "board_approval" in path_map
    assert "senior_compliance" in path_map
    assert "manager_approval" in path_map
    assert "auto_approve" in path_map

    # Case A: Board approval threshold
    assert router_fn({"amount": 150000, "is_flagged": False}) == "board_approval"

    # Case B: High amount + flagged
    assert router_fn({"amount": 25000, "is_flagged": True}) == "senior_compliance"

    # Case C: High amount + clean
    assert router_fn({"amount": 25000, "is_flagged": False}) == "manager_approval"

    # Case D: Low amount -> auto_approve fallback
    assert router_fn({"amount": 500, "is_flagged": False}) == "auto_approve"


# ------------------------------------------------------------------------------
# 3. Semantic Router Unit Tests
# ------------------------------------------------------------------------------

def test_step3_4_semantic_router_intent_classification():
    """Verify semantic router scores and routes text based on natural language descriptions."""
    routes = [
        SemanticRoute(
            id="billing",
            description="Customer disputes payment, invoices, credit card charges, or refunds",
            target="billing_support",
        ),
        SemanticRoute(
            id="churn",
            description="Customer wishes to cancel subscription, close account, or terminate service",
            target="retention_team",
        ),
        SemanticRoute(
            id="technical",
            description="System outage, 500 server error, bug report, or API connection issues",
            target="engineering_triage",
        ),
    ]

    classifier = SemanticIntentClassifier(routes=routes, default_target="general_support")

    # Match billing intent
    res1 = classifier.classify("Why was my credit card charged twice for this invoice?")
    assert res1 == "billing_support"

    # Match cancellation intent
    res2 = classifier.classify("I want to cancel my subscription and close my account immediately.")
    assert res2 == "retention_team"

    # Match technical outage intent
    res3 = classifier.classify("Our production server received a 500 internal error and API is broken.")
    assert res3 == "engineering_triage"


# ------------------------------------------------------------------------------
# 4. End-to-End Workflow Execution with Hybrid Routing
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_step3_5_end_to_end_dmn_workflow_auto_settle_branch():
    """Verify the hybrid workflow routes a clean invoice (<$50k) to automated payment settlement."""
    yaml_path = Path("examples/sample_workflows/hybrid_routing_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_path)

    compiler = GraphCompiler()
    compiled = compiler.compile(workflow)

    # Standard clean vendor invoice ($14,500, clean sanctions)
    payload = {
        "invoice_pdf_url": "s3://invoices-2026/q4/clean_vendor_invoice.pdf",
        "tax_id": "US-94-8192019",
    }

    final_state = await compiled.ainvoke(payload)

    # Should take auto_payment_settlement branch
    assert final_state["workflow_final_status"] == "SETTLED_AUTOMATICALLY"
    assert "settlement_txn_id" in final_state
    assert "risk_decision_table" in final_state["__history__"]
    assert "auto_payment_settlement" in final_state["__history__"]
    assert "emergency_compliance_review" not in final_state["__history__"]


@pytest.mark.asyncio
async def test_step3_6_end_to_end_dmn_workflow_emergency_branch():
    """Verify the hybrid workflow routes a high-risk or high-value invoice to emergency review."""
    yaml_path = Path("examples/sample_workflows/hybrid_routing_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_path)

    compiler = GraphCompiler()
    compiled = compiler.compile(workflow)

    # Pre-inject high risk score to trigger DMN emergency rule
    payload = {
        "invoice_pdf_url": "s3://invoices-2026/q4/suspicious_vendor.pdf",
        "tax_id": "US-94-8192019",
        "sanctions_is_flagged": True,
        "sanctions_risk_score": 0.95,
        "sanctions_note": "OFAC Specially Designated National Hit",
    }

    final_state = await compiled.ainvoke(payload)

    # Should take emergency_compliance_review branch
    assert final_state["workflow_final_status"] == "PENDING_SENIOR_OFFICER_SIGN_OFF"
    assert "review_docket_id" in final_state
    assert "emergency_compliance_review" in final_state["__history__"]
    assert "auto_payment_settlement" not in final_state["__history__"]


@pytest.mark.asyncio
async def test_step3_7_end_to_end_semantic_workflow_execution():
    """Verify semantic router workflow routes an inbound customer message to the correct queue."""
    yaml_path = Path("examples/sample_workflows/semantic_routing_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_path)

    compiler = GraphCompiler()
    compiled = compiler.compile(workflow)

    # Test Billing message
    billing_payload = {
        "sender_email": "finance@clientcorp.com",
        "customer_message": "Can you check invoice INV-9812? We noticed an extra payment charge on our card.",
        "tier": "ENTERPRISE",
    }
    state_billing = await compiled.ainvoke(billing_payload)
    assert "billing_queue" in state_billing["__history__"]
    assert state_billing["final_queue_routed"] == "billing_support_queue"

    # Test Churn cancellation message
    churn_payload = {
        "sender_email": "ops@leavingcompany.com",
        "customer_message": "We would like to cancel our account and discontinue subscription services.",
        "tier": "ENTERPRISE",
    }
    state_churn = await compiled.ainvoke(churn_payload)
    assert "retention_queue" in state_churn["__history__"]
    assert state_churn["final_queue_routed"] == "retention_specialist_queue"

