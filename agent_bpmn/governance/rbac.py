from typing import Dict, List, Optional
from agent_bpmn.governance.models import ChangeProposal, UserPrincipal
from agent_bpmn.runtime.hitl_inbox import ApprovalTask


class SecurityAuthorizationError(Exception):
    """Raised when an authenticated principal attempts an unauthorized action."""
    pass


class EnterpriseSecurityService:
    """
    Enterprise RBAC & Identity Service.
    Enforces Okta / OIDC role claims, least-privilege task access,
    and separation of duties for workflow governance.
    """

    def __init__(self) -> None:
        self._directory: Dict[str, UserPrincipal] = {}
        self._seed_default_principals()

    def _seed_default_principals(self) -> None:
        """Seeds standard enterprise test personas."""
        self.register_principal(
            UserPrincipal(
                user_id="usr_cfo_001",
                email="sarah.chen@enterprise.com",
                name="Sarah Chen (VP Finance)",
                department="Finance Operations",
                roles=["role:finance_executive", "role:business_analyst"],
                permissions=["workflow:propose", "task:approve", "task:edit"],
            )
        )
        self.register_principal(
            UserPrincipal(
                user_id="usr_comp_002",
                email="marcus.vance@enterprise.com",
                name="Marcus Vance (Chief Compliance Officer)",
                department="Regulatory Compliance",
                roles=["role:compliance_officer", "role:approver"],
                permissions=["workflow:propose", "task:approve", "proposal:approve"],
            )
        )
        self.register_principal(
            UserPrincipal(
                user_id="usr_dev_003",
                email="alex.kumar@enterprise.com",
                name="Alex Kumar (Principal AI Engineer)",
                department="Core Platform Engineering",
                roles=["role:developer"],
                permissions=["block:author", "workflow:compile", "simulation:run"],
            )
        )
        self.register_principal(
            UserPrincipal(
                user_id="usr_admin_000",
                email="secops.admin@enterprise.com",
                name="Global SecOps Admin",
                department="Information Security",
                roles=["role:admin"],
                permissions=["*"],
            )
        )

    def register_principal(self, principal: UserPrincipal) -> None:
        self._directory[principal.email.lower()] = principal
        self._directory[principal.user_id] = principal

    def get_principal(self, identifier: str) -> Optional[UserPrincipal]:
        return self._directory.get(identifier.lower())

    def can_resolve_task(self, user: UserPrincipal, task: ApprovalTask) -> bool:
        """
        Enforces Role-Based Access Control for Approval Inbox tasks.
        User must possess the exact `task.assigned_role` or have `role:admin`.
        """
        if user.has_role("role:admin"):
            return True
        return user.has_role(task.assigned_role)

    def can_propose_change(self, user: UserPrincipal, workflow_id: str) -> bool:
        """Verifies if the user is authorized to submit a workflow change proposal."""
        if user.has_role("role:admin"):
            return True
        return user.has_permission("workflow:propose")

    def can_approve_change(self, user: UserPrincipal, proposal: ChangeProposal) -> bool:
        """
        Separation of duties: The author cannot approve their own change proposal.
        Approver must possess `proposal:approve` or `role:admin`.
        """
        if user.email.lower() == proposal.author_email.lower():
            return False  # Self-approval strictly forbidden
        return user.has_permission("proposal:approve") or user.has_role("role:admin")


# Default global instance
security_service = EnterpriseSecurityService()
