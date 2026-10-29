from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_bpmn.governance.audit import audit_logger
from agent_bpmn.governance.git_client import git_governance_client
from agent_bpmn.governance.models import ChangeProposalRequest
from agent_bpmn.governance.rbac import security_service, SecurityAuthorizationError

router = APIRouter(prefix="/api/governance", tags=["Git Governance & Security"])


class ProposeChangeApiPayload(BaseModel):
    workflow_id: str
    target_version: str
    business_justification: str
    candidate_yaml: str
    author_email: str = "sarah.chen@enterprise.com"
    assigned_reviewers: Optional[List[str]] = None


class ApproveProposalPayload(BaseModel):
    approver_email: str = "marcus.vance@enterprise.com"


@router.post("/propose")
def propose_change(payload: ProposeChangeApiPayload) -> Dict[str, Any]:
    """Submits a change proposal, creates an automated Git branch, and prepares a Pull Request."""
    author = security_service.get_principal(payload.author_email)
    if not author:
        raise HTTPException(status_code=401, detail=f"Author '{payload.author_email}' not found in directory.")

    req = ChangeProposalRequest(
        workflow_id=payload.workflow_id,
        target_version=payload.target_version,
        author_email=payload.author_email,
        business_justification=payload.business_justification,
        candidate_yaml=payload.candidate_yaml,
        assigned_reviewers=payload.assigned_reviewers or ["marcus.vance@enterprise.com"],
    )

    try:
        proposal = git_governance_client.propose_change(req, author)
        return proposal.model_dump()
    except SecurityAuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/proposals")
def list_proposals(workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists change proposals / Pull Requests."""
    return [p.model_dump() for p in git_governance_client.list_proposals(workflow_id=workflow_id)]


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str) -> Dict[str, Any]:
    """Retrieves full details and Markdown body of a specific change proposal."""
    proposal = git_governance_client.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal '{proposal_id}' not found.")
    return proposal.model_dump()


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, payload: ApproveProposalPayload) -> Dict[str, Any]:
    """Approves a change proposal enforcing separation of duties."""
    approver = security_service.get_principal(payload.approver_email)
    if not approver:
        raise HTTPException(status_code=401, detail=f"Approver '{payload.approver_email}' not found.")

    try:
        proposal = git_governance_client.approve_proposal(proposal_id, approver)
        return proposal.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Proposal '{proposal_id}' not found.")
    except SecurityAuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/merge")
def merge_proposal(proposal_id: str, payload: ApproveProposalPayload) -> Dict[str, Any]:
    """Simulates merging an approved change proposal into main."""
    merger = security_service.get_principal(payload.approver_email)
    if not merger:
        raise HTTPException(status_code=401, detail=f"Merger '{payload.approver_email}' not found.")

    try:
        proposal = git_governance_client.merge_proposal(proposal_id, merger)
        return proposal.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Proposal '{proposal_id}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/audit-trail")
def get_audit_trail(workflow_id: Optional[str] = None) -> Dict[str, Any]:
    """Returns the cryptographic audit trail along with head-to-genesis integrity status."""
    is_valid, error = audit_logger.verify_integrity()
    entries = audit_logger.query(workflow_id=workflow_id)
    return {
        "ledger_integrity": "VALID" if is_valid else "CORRUPTED",
        "error": error,
        "total_entries": len(entries),
        "entries": [e.model_dump() for e in entries],
    }
