from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from agent_bpmn.governance import (
    AuditLogger,
    AuditTrailEntry,
    ChangeProposalRequest,
    EnterpriseSecurityService,
    GitGovernanceClient,
    SecurityAuthorizationError,
    UserPrincipal,
    audit_logger,
)
from agent_bpmn.runtime.hitl_inbox import ApprovalTask, TaskStatus
from agent_bpmn.server.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_step8_1_tamper_evident_audit_log_hash_chaining():
    """Verify cryptographic hash chaining detects any tampering or historical ledger mutation."""
    logger = AuditLogger()

    # Log 3 events
    e1 = logger.log(actor="user:cfo@enterprise.com", action="PROPOSE_CHANGE", workflow_id="wf_invoice", details={"v": "1.1"})
    e2 = logger.log(actor="user:cco@enterprise.com", action="APPROVE_PROPOSAL", workflow_id="wf_invoice", details={"pr": 101})
    e3 = logger.log(actor="user:admin@enterprise.com", action="MERGE_PROPOSAL", workflow_id="wf_invoice", details={"pr": 101})

    # 1. Unmodified chain must pass integrity verification
    is_valid, err = logger.verify_integrity()
    assert is_valid is True
    assert err is None

    # 2. Maliciously mutate entry 2's details in-memory
    e2.details["malicious_tamper"] = "unauthorized modification"

    # Integrity verification must immediately catch the forgery
    is_valid_after_tamper, tamper_err = logger.verify_integrity()
    assert is_valid_after_tamper is False
    assert "Tamper detected at index 2" in tamper_err


def test_step8_2_rbac_identity_and_role_permissions():
    """Verify Okta / RBAC claims enforce least-privilege task access and permission boundaries."""
    sec = EnterpriseSecurityService()

    cfo = sec.get_principal("sarah.chen@enterprise.com")
    compliance_officer = sec.get_principal("marcus.vance@enterprise.com")
    engineer = sec.get_principal("alex.kumar@enterprise.com")

    # Compliance review task
    comp_task = ApprovalTask(
        thread_id="t1",
        workflow_id="wf_sanctions",
        node_id="l2_review",
        title="Sanctions Review",
        assigned_role="role:compliance_officer",
        status=TaskStatus.PENDING,
        state_snapshot={"risk": 0.9},
    )

    # Compliance officer is authorized
    assert sec.can_resolve_task(compliance_officer, comp_task) is True
    # CFO is NOT authorized for sanctions review
    assert sec.can_resolve_task(cfo, comp_task) is False
    # Engineer is NOT authorized
    assert sec.can_resolve_task(engineer, comp_task) is False


def test_step8_3_git_governance_change_proposal_and_pr_body():
    """Verify Git client creates governance branches, PR metadata, and markdown descriptions."""
    git_client = GitGovernanceClient()
    sec = EnterpriseSecurityService()
    cfo = sec.get_principal("sarah.chen@enterprise.com")

    valid_yaml = Path("examples/sample_workflows/invoice_processing_workflow.yaml").read_text(encoding="utf-8")

    req = ChangeProposalRequest(
        workflow_id="vendor_invoice_and_compliance",
        target_version="2.0.0",
        author_email=cfo.email,
        business_justification="Updated extraction confidence threshold per Q4 compliance audit.",
        candidate_yaml=valid_yaml,
        assigned_reviewers=["marcus.vance@enterprise.com"],
    )

    proposal = git_client.propose_change(req, cfo)

    assert proposal.status == "PENDING_REVIEW"
    assert proposal.branch_name.startswith("governance/wf-vendor_invoice_and_compliance-v2.0.0-")
    assert proposal.pr_number >= 100
    assert "feat(vendor_invoice_and_compliance): Upgrade to v2.0.0" in proposal.pr_title
    assert "Business Justification (Audit Trail Required)" in proposal.pr_body_markdown
    assert "Updated extraction confidence threshold per Q4 compliance audit." in proposal.pr_body_markdown


def test_step8_4_separation_of_duties_approval_and_merge():
    """Verify separation of duties: authors cannot approve their own PRs."""
    git_client = GitGovernanceClient()
    sec = EnterpriseSecurityService()
    cfo = sec.get_principal("sarah.chen@enterprise.com")
    cco = sec.get_principal("marcus.vance@enterprise.com")

    valid_yaml = Path("examples/sample_workflows/invoice_processing_workflow.yaml").read_text(encoding="utf-8")
    req = ChangeProposalRequest(
        workflow_id="vendor_invoice_and_compliance",
        target_version="2.1.0",
        author_email=cfo.email,
        business_justification="Routine threshold bump.",
        candidate_yaml=valid_yaml,
    )
    proposal = git_client.propose_change(req, cfo)

    # Self-approval by the author (CFO) must raise SecurityAuthorizationError
    with pytest.raises(SecurityAuthorizationError, match="Separation of duties violation"):
        git_client.approve_proposal(proposal.proposal_id, cfo)

    # Peer review approval by CCO succeeds
    approved_proposal = git_client.approve_proposal(proposal.proposal_id, cco)
    assert approved_proposal.status == "APPROVED"
    assert approved_proposal.approved_by == cco.email

    # Merge proposal
    merged_proposal = git_client.merge_proposal(proposal.proposal_id, cco)
    assert merged_proposal.status == "MERGED"
    assert merged_proposal.merged_at is not None


def test_step8_5_server_governance_api_endpoints(client):
    """Verify backend API endpoints for change proposal submission, peer approval, and audit query."""
    valid_yaml = Path("examples/sample_workflows/invoice_processing_workflow.yaml").read_text(encoding="utf-8")

    # 1. Propose change via API
    propose_payload = {
        "workflow_id": "vendor_invoice_and_compliance",
        "target_version": "3.0.0",
        "business_justification": "API-triggered policy enhancement.",
        "candidate_yaml": valid_yaml,
        "author_email": "sarah.chen@enterprise.com",
    }
    res_prop = client.post("/api/governance/propose", json=propose_payload)
    assert res_prop.status_code == 200
    prop_data = res_prop.json()
    proposal_id = prop_data["proposal_id"]
    assert prop_data["status"] == "PENDING_REVIEW"

    # 2. List proposals
    res_list = client.get("/api/governance/proposals")
    assert res_list.status_code == 200
    assert any(p["proposal_id"] == proposal_id for p in res_list.json())

    # 3. Peer Approval via API
    res_appr = client.post(
        f"/api/governance/proposals/{proposal_id}/approve",
        json={"approver_email": "marcus.vance@enterprise.com"},
    )
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"

    # 4. Merge via API
    res_merge = client.post(
        f"/api/governance/proposals/{proposal_id}/merge",
        json={"approver_email": "marcus.vance@enterprise.com"},
    )
    assert res_merge.status_code == 200
    assert res_merge.json()["status"] == "MERGED"

    # 5. Query Audit Trail
    res_audit = client.get("/api/governance/audit-trail")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["ledger_integrity"] == "VALID"
    assert audit_data["total_entries"] > 0
