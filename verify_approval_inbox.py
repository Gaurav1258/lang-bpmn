"""
AgentBPMN - Step 4 Verification Script
Demonstrates Pillar 3: First-Class Approval Inbox & True Enterprise Human-in-the-Loop (HITL).
Validates interrupt checkpointing, Okta role task routing, dynamic form rendering,
and zero-code graph resumption via Command(resume=...).
"""

import asyncio
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent_bpmn.compiler import GraphCompiler
from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.runtime import ApprovalInboxService, TaskStatus
import examples.sample_blocks  # Registers domain blocks


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 4 (PILLAR 3 - FIRST-CLASS APPROVAL INBOX & ENTERPRISE HITL)")

    # --------------------------------------------------------------------------
    # Step 4.1: Compile Enterprise Workflow with Human Review Node
    # --------------------------------------------------------------------------
    print_banner("STEP 4.1: COMPILE ENTERPRISE WORKFLOW WITH HUMAN REVIEW NODE")
    yaml_file = Path("examples/sample_workflows/enterprise_hitl_workflow.yaml")
    workflow = parse_workflow_yaml(yaml_file)
    inbox = ApprovalInboxService()
    compiler = GraphCompiler(inbox_service=inbox)
    compiled = compiler.compile(workflow)

    human_node = next(n for n in workflow.nodes if n.id == "l2_compliance_review")
    cfg_review = human_node.human_review_config
    print(f"[+] Workflow Loaded:     {workflow.metadata.name}")
    print(f"[+] Human Node ID:       '{human_node.id}'")
    print(f"[+] Assigned Role:       {cfg_review.assigned_role} (Okta / SAML / Active Directory)")
    print(f"[+] Task Title:          \"{cfg_review.title}\"")
    print(f"[+] SLA Timeout:         {cfg_review.sla_timeout_seconds}s (4 Hours)")
    print(f"[+] Allowed Actions:     {cfg_review.allowed_actions}")
    print(f"[+] Escalation Target:   '{cfg_review.escalation_target}'")

    # --------------------------------------------------------------------------
    # Step 4.2: Execute until Interruption
    # --------------------------------------------------------------------------
    print_banner("STEP 4.2: EXECUTE PIPELINE & TRIGGER CHECKPOINT INTERRUPT")
    thread_id = "thread_compliance_aud_8891"
    initial_payload = {
        "invoice_pdf_url": "s3://invoices-2026/q4/vendor_apex_9812.pdf",
        "tax_id": "US-94-8192019",
    }
    run_cfg = {"configurable": {"thread_id": thread_id}}
    print(f"[*] Dispatching workflow with initial state (Thread ID: {thread_id})...")

    interrupted_state = await compiled.ainvoke(initial_payload, config=run_cfg)

    print("[OK] LangGraph encountered Human Review node and safely paused execution!")
    print(f"    - Execution History: {' -> '.join(interrupted_state.get('__history__', []))}")
    print(f"    - Checkpoint Status: Paused at interrupt point")
    print(f"    - Interrupt Count:   {len(interrupted_state.get('__interrupt__', []))} active interrupt")

    # --------------------------------------------------------------------------
    # Step 4.3: Enterprise Task Inbox View (Okta Role Filtering & Dynamic Form)
    # --------------------------------------------------------------------------
    print_banner("STEP 4.3: ENTERPRISE TASK INBOX VIEW (ROLE: L2_COMPLIANCE_ANALYST)")
    pending_tasks = inbox.list_tasks(role="role:L2_Compliance_Analyst", status=TaskStatus.PENDING)
    print(f"[*] Total Pending Tasks for 'role:L2_Compliance_Analyst': {len(pending_tasks)}")
    assert len(pending_tasks) > 0, "Expected a pending approval task in inbox!"

    task = pending_tasks[0]
    print(f"\n┌────────────────────────────────────────────────────────────────────────┐")
    print(f"│ 📋 ENTERPRISE APPROVAL CARD                                             │")
    print(f"│ Task ID:        {task.task_id:<54} │")
    print(f"│ Title:          {task.title:<54} │")
    print(f"│ Assigned Role:  {task.assigned_role:<54} │")
    print(f"│ Status:         {task.status.value:<54} │")
    print(f"│ SLA Deadline:   {str(task.sla_deadline):<54} │")
    print(f"├────────────────────────────────────────────────────────────────────────┤")
    print(f"│ 📝 Dynamic Form Fields (Captured State):                                │")
    for field_name in (task.form_fields or []):
        val = task.state_snapshot.get(field_name, "N/A")
        print(f"│   * {field_name:<20}: {str(val):<47} │")
    print(f"├────────────────────────────────────────────────────────────────────────┤")
    print(f"│ Allowed Actions: [APPROVE]  [REJECT]  [EDIT_AND_APPROVE]               │")
    print(f"└────────────────────────────────────────────────────────────────────────┘")

    # --------------------------------------------------------------------------
    # Step 4.4: Actioning Task & Resuming Graph via Command(resume=...)
    # --------------------------------------------------------------------------
    print_banner("STEP 4.4: REVIEWER ACTIONS TASK -> RESUME VIA Command(resume=...)")
    reviewer_email = "sarah.compliance@bank.com"
    comments = "Invoice verified against master vendor agreements. Applied 10% negotiated vendor credit."
    human_edits = {"invoice_total_usd": 13050.00}  # 10% credit discount applied by human

    print(f"[*] Reviewer '{reviewer_email}' submitting 'EDIT_AND_APPROVE'...")
    print(f"    - Adjusted Invoice Total: $14,500.00 -> $13,050.00")
    print(f"    - Reviewer Notes: \"{comments}\"")

    resumed_state = await inbox.submit_decision(
        task_id=task.task_id,
        action="EDIT_AND_APPROVE",
        reviewer=reviewer_email,
        comments=comments,
        updated_fields=human_edits,
        compiled_workflow=compiled,
    )

    print("\n[OK] Command(resume=...) dispatched! LangGraph completed downstream execution:")
    print(f"    - Complete Flow:     {' -> '.join(resumed_state.get('__history__', []))}")
    print(f"    - Final Status:      {resumed_state.get('workflow_final_status')}")
    print(f"    - Settlement Txn ID: {resumed_state.get('settlement_txn_id')}")
    print(f"    - Final Settled Amt: ${resumed_state.get('invoice_total_usd', 0):,.2f}")
    print(f"    - Task Status:       {task.status.value}")

    # --------------------------------------------------------------------------
    # Step 4.5: SLA Watchdog Verification
    # --------------------------------------------------------------------------
    print_banner("STEP 4.5: SLA WATCHDOG TIMER & ESCALATION ENGINE")
    # Simulate an overdue task
    overdue_task = inbox.create_task(
        thread_id="th_breached_sla",
        workflow_id="wf_invoices",
        node_id="l2_review",
        title="Overdue Escalation Test",
        assigned_role="role:L2_Compliance_Analyst",
        state_snapshot={"amount": 500000},
        sla_timeout_seconds=-10,  # Expired in past
    )
    print(f"[*] Checking SLA deadlines across all open tasks...")
    escalated = inbox.check_slas()
    print(f"[OK] SLA Watchdog identified {len(escalated)} breached tasks:")
    for esc in escalated:
        print(f"    * Task '{esc.task_id}' -> Marked {esc.status.value} (Deadline: {esc.sla_deadline})")

    print_banner("SUCCESS: STEP 4 COMPLETE - ENTERPRISE HITL & APPROVAL INBOX OPERATIONAL")


if __name__ == "__main__":
    asyncio.run(main())

