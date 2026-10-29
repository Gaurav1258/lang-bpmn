from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.runtime import ApprovalInboxService, TaskStatus
import examples.sample_blocks  # Registers domain blocks


def test_step4_1_human_review_schema_validation():
    """Verify human_review_config parses correctly from declarative YAML."""
    yaml_path = Path("examples/sample_workflows/enterprise_hitl_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    human_node = next(n for n in wf.nodes if n.id == "l2_compliance_review")
    assert human_node.type == "human_review"
    assert human_node.human_review_config is not None
    cfg = human_node.human_review_config
    assert cfg.title == "Review Suspicious Vendor Invoice"
    assert cfg.assigned_role == "role:L2_Compliance_Analyst"
    assert "APPROVE" in cfg.allowed_actions
    assert "EDIT_AND_APPROVE" in cfg.allowed_actions
    assert cfg.sla_timeout_seconds == 14400
    assert "vendor_name" in cfg.form_fields


def test_step4_2_approval_inbox_task_lifecycle():
    """Verify task registration and role-based filtering in ApprovalInboxService."""
    inbox = ApprovalInboxService()

    task1 = inbox.create_task(
        thread_id="th_1",
        workflow_id="wf_invoice",
        node_id="review_1",
        title="Sanctions Review",
        assigned_role="role:L2_Compliance_Analyst",
        state_snapshot={"vendor": "Acme", "amount": 10000},
    )

    task2 = inbox.create_task(
        thread_id="th_2",
        workflow_id="wf_invoice",
        node_id="cfo_step",
        title="CFO Wire Sign-off",
        assigned_role="role:CFO",
        state_snapshot={"vendor": "Apex", "amount": 100000},
    )

    # Filter by role
    l2_tasks = inbox.list_tasks(role="role:L2_Compliance_Analyst")
    assert len(l2_tasks) == 1
    assert l2_tasks[0].task_id == task1.task_id

    cfo_tasks = inbox.list_tasks(role="role:CFO")
    assert len(cfo_tasks) == 1
    assert cfo_tasks[0].task_id == task2.task_id


@pytest.mark.asyncio
async def test_step4_3_workflow_interrupts_at_human_review_node():
    """Verify graph execution pauses at human_review node and registers a pending task."""
    yaml_path = Path("examples/sample_workflows/enterprise_hitl_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    local_inbox = ApprovalInboxService()
    compiler = GraphCompiler(inbox_service=local_inbox)
    compiled = compiler.compile(wf)

    initial_payload = {
        "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
        "tax_id": "US-94-8192019",
    }
    cfg = {"configurable": {"thread_id": "th_test_interrupt_01"}}

    state = await compiled.ainvoke(initial_payload, config=cfg)

    # Execution paused at human_review
    assert "__interrupt__" in state
    assert len(state["__interrupt__"]) > 0

    # Task was auto-registered in the Approval Inbox
    pending_tasks = local_inbox.list_tasks(role="role:L2_Compliance_Analyst", status=TaskStatus.PENDING)
    assert len(pending_tasks) == 1
    task = pending_tasks[0]
    assert task.thread_id == "th_test_interrupt_01"
    assert task.title == "Review Suspicious Vendor Invoice"
    assert task.state_snapshot["vendor_name"] == "Apex Cloud Infrastructure Ltd"


@pytest.mark.asyncio
async def test_step4_4_workflow_resumes_via_approval_submission():
    """Verify approving a pending task resumes the graph through DMN routing to auto-settlement."""
    yaml_path = Path("examples/sample_workflows/enterprise_hitl_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    local_inbox = ApprovalInboxService()
    compiler = GraphCompiler(inbox_service=local_inbox)
    compiled = compiler.compile(wf)

    initial_payload = {
        "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
        "tax_id": "US-94-8192019",
    }
    cfg = {"configurable": {"thread_id": "th_test_resume_02"}}

    # Run until interrupt
    await compiled.ainvoke(initial_payload, config=cfg)

    # Fetch pending task
    task = local_inbox.list_tasks(role="role:L2_Compliance_Analyst", status=TaskStatus.PENDING)[0]

    # Reviewer clicks "Approve" in the inbox
    resumed_state = await local_inbox.submit_decision(
        task_id=task.task_id,
        action="APPROVE",
        reviewer="sarah.compliance@bank.com",
        comments="KYC identity verified, vendor clean.",
        compiled_workflow=compiled,
    )

    # Verification: Task in inbox marked APPROVED
    assert task.status == TaskStatus.APPROVED
    assert task.decided_by == "sarah.compliance@bank.com"

    # Verification: Graph resumed and completed payment settlement
    assert resumed_state["last_review_decision"] == "APPROVE"
    assert resumed_state["last_reviewer"] == "sarah.compliance@bank.com"
    assert resumed_state["workflow_final_status"] == "SETTLED_AUTOMATICALLY"
    assert "settlement_txn_id" in resumed_state
    assert "auto_payment_settlement" in resumed_state["__history__"]


@pytest.mark.asyncio
async def test_step4_5_workflow_edit_and_approve_modifies_state():
    """Verify EDIT_AND_APPROVE applies human corrections to state and passes them downstream."""
    yaml_path = Path("examples/sample_workflows/enterprise_hitl_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    local_inbox = ApprovalInboxService()
    compiler = GraphCompiler(inbox_service=local_inbox)
    compiled = compiler.compile(wf)

    initial_payload = {
        "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
        "tax_id": "US-94-8192019",
    }
    cfg = {"configurable": {"thread_id": "th_test_edit_03"}}

    await compiled.ainvoke(initial_payload, config=cfg)
    task = local_inbox.list_tasks(role="role:L2_Compliance_Analyst", status=TaskStatus.PENDING)[0]

    # Human reviewer adjusts the invoice total from $14,500 down to $11,000 (disputed discount)
    resumed_state = await local_inbox.submit_decision(
        task_id=task.task_id,
        action="EDIT_AND_APPROVE",
        reviewer="marcus.analyst@bank.com",
        comments="Applied 15% negotiated vendor credit.",
        updated_fields={"invoice_total_usd": 11000.00},
        compiled_workflow=compiled,
    )

    assert task.status == TaskStatus.EDITED_AND_APPROVED
    assert resumed_state["invoice_total_usd"] == 11000.00
    assert resumed_state["workflow_final_status"] == "SETTLED_AUTOMATICALLY"


@pytest.mark.asyncio
async def test_step4_6_workflow_reject_routes_to_end_without_settlement():
    """Verify REJECT routes down default DMN branch to END without settlement."""
    yaml_path = Path("examples/sample_workflows/enterprise_hitl_workflow.yaml")
    wf = parse_workflow_yaml(yaml_path)

    local_inbox = ApprovalInboxService()
    compiler = GraphCompiler(inbox_service=local_inbox)
    compiled = compiler.compile(wf)

    cfg = {"configurable": {"thread_id": "th_test_reject_04"}}
    await compiled.ainvoke({
        "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
        "tax_id": "US-94-8192019",
    }, config=cfg)

    task = local_inbox.list_tasks(role="role:L2_Compliance_Analyst", status=TaskStatus.PENDING)[0]

    resumed_state = await local_inbox.submit_decision(
        task_id=task.task_id,
        action="REJECT",
        reviewer="sarah.compliance@bank.com",
        comments="Suspicious invoicing pattern detected.",
        compiled_workflow=compiled,
    )

    assert task.status == TaskStatus.REJECTED
    assert resumed_state["last_review_decision"] == "REJECT"
    # Did NOT reach auto_payment_settlement
    assert "auto_payment_settlement" not in resumed_state.get("__history__", [])


def test_step4_7_sla_watchdog_detects_breached_deadlines():
    """Verify SLA watchdog identifies and escalates overdue tasks."""
    inbox = ApprovalInboxService()

    # Create task with expired SLA (-60 seconds)
    task = inbox.create_task(
        thread_id="th_expired",
        workflow_id="wf_1",
        node_id="review_1",
        title="Urgent Review",
        assigned_role="role:L2_Compliance_Analyst",
        state_snapshot={},
        sla_timeout_seconds=-60,
    )

    assert task.status == TaskStatus.PENDING
    escalated = inbox.check_slas()
    assert len(escalated) == 1
    assert escalated[0].task_id == task.task_id
    assert task.status == TaskStatus.ESCALATED

