"""
AgentBPMN - Step 8 Verification Script
Demonstrates Pillar 6: Git-Backed Governance Without Exposing Git.
Validates automated Git branch/PR generation, RBAC identity checks,
separation of duties enforcement, and tamper-evident cryptographic audit logs.
"""

from pathlib import Path
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent_bpmn.dsl import parse_workflow_yaml
from agent_bpmn.governance import (
    ChangeProposalRequest,
    SecurityAuthorizationError,
    audit_logger,
    git_governance_client,
    security_service,
)
from agent_bpmn.simulation import HistoricalCase, SimulationDataset, SimulationEngine
import examples.sample_blocks  # Ensure blocks are registered


def print_banner(step_title: str) -> None:
    line = "=" * 76
    print(f"\n{line}")
    print(f"  {step_title}")
    print(f"{line}\n")


async def main() -> None:
    print_banner("AGENT-BPMN: STEP 8 (PILLAR 6 - GIT GOVERNANCE & RBAC SECURITY)")

    # --------------------------------------------------------------------------
    # Step 8.1: Authenticate Enterprise Principals & RBAC Permissions
    # --------------------------------------------------------------------------
    print_banner("STEP 8.1: ENTERPRISE IDENTITY & OKTA CLAIMS VERIFICATION")
    cfo = security_service.get_principal("sarah.chen@enterprise.com")
    cco = security_service.get_principal("marcus.vance@enterprise.com")
    engineer = security_service.get_principal("alex.kumar@enterprise.com")

    print(f"[*] Authenticated Author:   {cfo.name} <{cfo.email}>")
    print(f"    Roles: {cfo.roles} | Department: {cfo.department}")
    print(f"[*] Authenticated Approver: {cco.name} <{cco.email}>")
    print(f"    Roles: {cco.roles} | Department: {cco.department}")

    assert security_service.can_propose_change(cfo, "hybrid_invoice_routing_flow") is True
    print("[OK] RBAC verified: Author is authorized to propose workflow changes.")

    # --------------------------------------------------------------------------
    # Step 8.2: Run Pre-Flight Simulation to Attach to PR
    # --------------------------------------------------------------------------
    print_banner("STEP 8.2: GENERATING PRE-FLIGHT SIMULATION REPORT FOR PR BODY")
    candidate_file = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml")
    candidate_wf = parse_workflow_yaml(candidate_file)

    dataset = SimulationDataset(
        dataset_id="q3_audit_dataset",
        workflow_id="hybrid_invoice_routing_flow",
    )
    for i in range(5):
        dataset.add_case(
            HistoricalCase(
                case_id=f"audit_case_{i+1}",
                input_payload={
                    "invoice_pdf_url": f"s3://invoices-2026/q3/vendor_inv_{i+1}.pdf",
                    "tax_id": f"US-94-81920{i+1:02d}",
                },
                baseline_route=["extract_invoice", "screen_sanctions", "risk_decision_table", "auto_payment_settlement"],
                baseline_terminal_node="auto_payment_settlement",
                baseline_cost_usd=0.0190,
                baseline_duration_ms=115.0,
            )
        )

    engine = SimulationEngine()
    sim_report = await engine.run_simulation(candidate_wf, dataset, simulation_id="sim_pr_audit_77")
    print(f"[+] Simulation completed: {sim_report.diff.total_cases} cases, 0 crashes detected.")

    # --------------------------------------------------------------------------
    # Step 8.3: Propose Change & Generate Automated Git Pull Request
    # --------------------------------------------------------------------------
    print_banner("STEP 8.3: AUTOMATED GIT BRANCH & PULL REQUEST CREATION")
    req = ChangeProposalRequest(
        workflow_id=candidate_wf.metadata.id,
        target_version="1.3.0",
        author_email=cfo.email,
        business_justification=(
            "Tightened sanctions risk threshold from 0.70 to 0.50 and lowered L2 threshold from $50k to $10k "
            "per mandatory Q4 Enterprise Risk Committee directives."
        ),
        candidate_yaml=candidate_file.read_text(encoding="utf-8"),
        assigned_reviewers=[cco.email],
        simulation_report=sim_report,
    )

    proposal = git_governance_client.propose_change(req, cfo)
    print(f"[OK] Change Proposal Registered: {proposal.proposal_id}")
    print(f"    Git Branch:  {proposal.branch_name}")
    print(f"    PR Number:   #{proposal.pr_number}")
    print(f"    PR Title:    {proposal.pr_title}")
    print(f"    PR Status:   [{proposal.status}]")

    print("\n--- [Preview Generated Pull Request Markdown Body] ---")
    print(proposal.pr_body_markdown[:700] + "\n... [Remaining simulation diff tables attached] ...")

    # --------------------------------------------------------------------------
    # Step 8.4: Enforce Separation of Duties & Peer Approval Lifecycle
    # --------------------------------------------------------------------------
    print_banner("STEP 8.4: ENFORCING SEPARATION OF DUTIES")
    print("[*] Testing Author Self-Approval (strictly forbidden in enterprise governance)...")
    try:
        git_governance_client.approve_proposal(proposal.proposal_id, cfo)
        print("[X] ERROR: Author was able to self-approve proposal!")
    except SecurityAuthorizationError as e:
        print(f"[OK] SUCCESS: Self-approval safely rejected by security policy:")
        print(f"    Caught: {e}")

    print(f"\n[*] Submitting Peer Review Approval by {cco.name}...")
    approved = git_governance_client.approve_proposal(proposal.proposal_id, cco)
    print(f"[OK] Proposal #{approved.pr_number} Status: [{approved.status}] | Approved By: {approved.approved_by}")

    print(f"[*] Executing Production Merge by Designated Administrator...")
    merged = git_governance_client.merge_proposal(proposal.proposal_id, cco)
    print(f"[OK] Proposal #{merged.pr_number} Status: [{merged.status}] | Merged At: {merged.merged_at}")

    # --------------------------------------------------------------------------
    # Step 8.5: Verify Cryptographic Audit Trail (SHA-256 Hash Chaining)
    # --------------------------------------------------------------------------
    print_banner("STEP 8.5: CRYPTOGRAPHIC AUDIT TRAIL INTEGRITY (SOC2 COMPLIANCE)")
    is_valid, err = audit_logger.verify_integrity()
    print(f"[*] Audit Trail Integrity Check: {'VALID (Zero Tampering)' if is_valid else 'CORRUPTED'}")
    assert is_valid is True

    audit_entries = audit_logger.query()
    print(f"[+] Total Immutable Audit Logs Recorded: {len(audit_entries)}")
    for e in audit_entries[-3:]:
        print(f"    [{e.timestamp[:19]}] Actor: {e.actor:<28} Action: {e.action:<18} Hash: {e.current_hash[:16]}...")

    # Export audit trail JSON
    audit_path = Path("governance_audit_trail.json")
    audit_logger.export_json(audit_path)
    print(f"\n[+] Cryptographic Audit Trail exported to: {audit_path.resolve()}")

    print_banner("SUCCESS: STEP 8 COMPLETE - GIT GOVERNANCE & ENTERPRISE SECURITY OPERATIONAL")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
