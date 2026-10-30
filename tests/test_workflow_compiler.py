from pathlib import Path
import pytest

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import (
    NodeType,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowLinter,
    WorkflowMetadata,
    WorkflowNode,
    dump_workflow_yaml,
    parse_workflow_yaml,
)
from agent_bpmn.sdk import registry
import agent_bpmn.blocks.builtin  # Ensures sample blocks are in the registry


def test_step2_1_yaml_parser_loads_valid_ast():
    """Verify parse_workflow_yaml correctly parses declarative YAML into a strongly-typed AST."""
    yaml_path = Path("examples/sample_workflows/invoice_processing_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_path)

    assert workflow.metadata.id == "vendor_invoice_and_compliance"
    assert workflow.metadata.owner_department == "Finance Operations"
    assert len(workflow.nodes) == 2
    assert len(workflow.edges) == 3
    assert workflow.nodes[0].block == "finance.invoice_extractor"
    assert workflow.nodes[1].block == "compliance.sanctions_screener"


def test_step2_2_linter_detects_unknown_domain_block():
    """Verify WorkflowLinter raises errors when a node references an unregistered block."""
    linter = WorkflowLinter()
    bad_wf = WorkflowDefinition(
        metadata=WorkflowMetadata(id="test_bad", name="Bad Block Test"),
        nodes=[
            WorkflowNode(id="n1", type=NodeType.BLOCK, block="ghost.unknown_capability"),
        ],
        edges=[
            WorkflowEdge(source="START", target="n1"),
            WorkflowEdge(source="n1", target="END"),
        ],
    )
    res = linter.lint(bad_wf)
    assert not res.is_valid
    assert any("references unknown domain block" in err for err in res.errors)


def test_step2_3_linter_detects_broken_edge_endpoints():
    """Verify WorkflowLinter catches edges that point to non-existent node IDs."""
    linter = WorkflowLinter()
    broken_edge_wf = WorkflowDefinition(
        metadata=WorkflowMetadata(id="test_broken_edge", name="Broken Edge"),
        nodes=[
            WorkflowNode(id="n1", type=NodeType.BLOCK, block="finance.invoice_extractor"),
        ],
        edges=[
            WorkflowEdge(source="START", target="n1"),
            WorkflowEdge(source="n1", target="ghost_node_target"),
        ],
    )
    res = linter.lint(broken_edge_wf)
    assert not res.is_valid
    assert any("invalid target 'ghost_node_target'" in err for err in res.errors)


def test_step2_4_compiler_builds_langgraph_instance():
    """Verify GraphCompiler compiles a valid WorkflowDefinition AST into a LangGraph CompiledWorkflow."""
    yaml_path = Path("examples/sample_workflows/invoice_processing_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_path)

    compiler = GraphCompiler()
    compiled = compiler.compile(workflow)

    assert compiled is not None
    assert compiled.workflow.metadata.id == "vendor_invoice_and_compliance"
    assert compiled.compiled_graph is not None


@pytest.mark.asyncio
async def test_step2_5_end_to_end_workflow_execution():
    """Verify end-to-end execution where Node 2 consumes Node 1's outputs via state mappings."""
    yaml_path = Path("examples/sample_workflows/invoice_processing_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_path)

    compiler = GraphCompiler()
    compiled = compiler.compile(workflow)

    initial_payload = {
        "invoice_pdf_url": "s3://invoices-2026/q3/apex_cloud_inv9812.pdf",
        "tax_id": "US-94-8192019",
    }

    final_state = await compiled.ainvoke(initial_payload)

    # 1. Check Node 1 outputs were mapped into graph state
    assert final_state["extracted_invoice_num"] == "INV-2026-9812"
    assert final_state["extracted_vendor_name"] == "Apex Cloud Infrastructure Ltd"
    assert final_state["invoice_total_usd"] == 14500.00
    assert len(final_state["extracted_line_items"]) == 2

    # 2. Check Node 2 received mapped values from Node 1 and produced output
    assert "sanctions_is_flagged" in final_state
    assert final_state["sanctions_is_flagged"] is False  # Clean vendor
    assert final_state["sanctions_risk_score"] == 0.05
    assert "compliance_audit_summary" in final_state

    # 3. Check execution history & telemetry
    assert final_state["__history__"] == ["extract_invoice", "check_sanctions"]
    assert "extract_invoice" in final_state["__telemetry__"]
    assert "check_sanctions" in final_state["__telemetry__"]


def test_step2_6_ast_yaml_roundtrip_serialization():
    """Verify AST serializes to YAML and can be cleanly re-parsed with zero data loss."""
    yaml_path = Path("examples/sample_workflows/invoice_processing_workflow.yaml")
    original_wf = parse_workflow_yaml(yaml_path)

    dumped_yaml = dump_workflow_yaml(original_wf)
    reloaded_wf = parse_workflow_yaml(dumped_yaml)

    assert reloaded_wf.metadata.id == original_wf.metadata.id
    assert len(reloaded_wf.nodes) == len(original_wf.nodes)
    assert len(reloaded_wf.edges) == len(original_wf.edges)


def test_step2_7_autonomous_scf_workflow_compilation_and_execution():
    """Verify autonomous SCF treasury workflow passes linting and compiles to LangGraph."""
    yaml_path = Path("examples/sample_workflows/autonomous_scf_governance_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    linter = WorkflowLinter(registry=registry)
    lint_result = linter.lint(wf)
    assert lint_result.is_valid, f"Linting failed: {lint_result.errors}"

    compiler = GraphCompiler(registry=registry)
    compiled = compiler.compile(wf)
    assert compiled is not None
    assert compiled.workflow.metadata.id == "autonomous_scf_treasury_governance"

    # Execute with clean low-risk payload that routes automatically to structure_capital -> validate -> dispatch
    input_payload = {
        "supplier_id": "SUP-8821-ACME",
        "supplier_name": "Acme Clean Industrial Tech",
        "invoice_amount_usd": 24000.0,
        "buyer_id": "BUYER-CORP-001",
        "target_dpo_days": 60,
        "horizon_days": 60,
        "days_to_maturity": 45,
        "bank_facility_id": "FACILITY-CITI-REV-909",
        "invoice_number": "INV-2026-SCF-101",
    }
    result = compiled.invoke(input_payload)
    assert result["__history__"] == [
        "screen_supplier_risk",
        "forecast_liquidity",
        "scf_routing_decision",
        "structure_capital",
        "validate_bank_facility",
        "dispatch_drawdown",
    ]
    assert result["is_facility_approved"] is True
    assert result["execution_status"] == "FUNDS_DISBURSED_TO_SUPPLIER_ACCOUNT"


