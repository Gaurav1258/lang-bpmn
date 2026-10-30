from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from langgraph.types import Command


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED_AND_APPROVED = "EDITED_AND_APPROVED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


class ApprovalTask(BaseModel):
    """
    An enterprise review task awaiting human intervention in the Task Inbox.
    Auto-generated whenever a workflow encounters a 'human_review' node.
    """
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    thread_id: str = Field(..., description="LangGraph execution checkpoint thread ID")
    workflow_id: str = Field(..., description="Parent workflow definition identifier")
    node_id: str = Field(..., description="Human review canvas node ID")
    title: str = Field(..., description="Human-readable title displayed in the Inbox")
    description: Optional[str] = Field(default=None, description="Detailed instructions for the reviewer")
    assigned_role: str = Field(..., description="Okta/AD Role authorized to action this task (e.g. 'role:L2_Compliance_Analyst')")
    allowed_actions: List[str] = Field(default_factory=lambda: ["APPROVE", "REJECT", "EDIT_AND_APPROVE"])
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sla_timeout_seconds: Optional[int] = Field(default=14400)
    sla_deadline: Optional[datetime] = None
    escalation_target: Optional[str] = None
    state_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Captured graph state at the moment of interruption")
    form_fields: Optional[List[str]] = Field(default=None, description="Selective fields to present in the dynamic UI form")
    decision_action: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    reviewer_comments: Optional[str] = None
    updated_fields: Optional[Dict[str, Any]] = None


class ApprovalInboxService:
    """
    Enterprise Human-in-the-Loop Task Service.
    Indexes pending approval tasks by Okta/AD role, tracks SLA timers,
    and resumes paused LangGraph StateGraphs via Command(resume=...).
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, ApprovalTask] = {}
        self._active_workflows: Dict[str, Any] = {}

    def register_active_workflow(self, thread_id: str, compiled_workflow: Any) -> None:
        """Stores the compiled workflow instance so paused threads can be resumed via API."""
        self._active_workflows[thread_id] = compiled_workflow

    def get_active_workflow(self, thread_id: str) -> Optional[Any]:
        """Retrieves a previously registered compiled workflow for a paused thread."""
        return self._active_workflows.get(thread_id)

    def create_task(
        self,
        thread_id: str,
        workflow_id: str,
        node_id: str,
        title: str,
        assigned_role: str,
        state_snapshot: Dict[str, Any],
        description: Optional[str] = None,
        allowed_actions: Optional[List[str]] = None,
        sla_timeout_seconds: Optional[int] = 14400,
        escalation_target: Optional[str] = None,
        form_fields: Optional[List[str]] = None,
    ) -> ApprovalTask:
        """Registers a new pending approval task when a workflow hits a human_review node."""
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=sla_timeout_seconds) if sla_timeout_seconds else None

        task = ApprovalTask(
            thread_id=thread_id,
            workflow_id=workflow_id,
            node_id=node_id,
            title=title,
            description=description,
            assigned_role=assigned_role,
            allowed_actions=allowed_actions or ["APPROVE", "REJECT", "EDIT_AND_APPROVE"],
            status=TaskStatus.PENDING,
            created_at=now,
            sla_timeout_seconds=sla_timeout_seconds,
            sla_deadline=deadline,
            escalation_target=escalation_target,
            state_snapshot=state_snapshot,
            form_fields=form_fields,
        )
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> ApprovalTask:
        if task_id not in self._tasks:
            raise KeyError(f"Approval task '{task_id}' not found.")
        return self._tasks[task_id]

    def list_tasks(
        self,
        role: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[ApprovalTask]:
        """Lists tasks, optionally filtered by authorized role and task status."""
        results = list(self._tasks.values())
        if role:
            results = [t for t in results if t.assigned_role.lower() == role.lower()]
        if status:
            results = [t for t in results if t.status == status]
        return sorted(results, key=lambda t: t.created_at, reverse=True)

    def get_pending_tasks(
        self,
        role: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> List[ApprovalTask]:
        """Convenience method returning pending tasks filtered by role or workflow ID."""
        tasks = self.list_tasks(role=role, status=TaskStatus.PENDING)
        if workflow_id:
            tasks = [t for t in tasks if t.workflow_id == workflow_id]
        return tasks

    async def submit_decision(
        self,
        task_id: str,
        action: str,
        reviewer: str,
        comments: Optional[str] = None,
        updated_fields: Optional[Dict[str, Any]] = None,
        compiled_workflow: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Actions an approval task and dispatches Command(resume=...) to resume LangGraph.
        """
        task = self.get_task(task_id)
        if task.status != TaskStatus.PENDING:
            raise ValueError(f"Task '{task_id}' is already {task.status.value} and cannot be actioned.")

        action_upper = action.upper()
        if action_upper not in task.allowed_actions:
            raise ValueError(f"Action '{action}' is not in allowed actions: {task.allowed_actions}")

        # Update task record
        now = datetime.now(timezone.utc)
        if action_upper == "APPROVE":
            task.status = TaskStatus.APPROVED
        elif action_upper == "REJECT":
            task.status = TaskStatus.REJECTED
        elif action_upper == "EDIT_AND_APPROVE":
            task.status = TaskStatus.EDITED_AND_APPROVED
        else:
            task.status = TaskStatus.APPROVED

        task.decision_action = action_upper
        task.decided_by = reviewer
        task.decided_at = now
        task.reviewer_comments = comments
        task.updated_fields = updated_fields or {}

        # If a compiled LangGraph workflow instance is provided, resume execution
        resumed_state: Dict[str, Any] = {}
        if compiled_workflow is not None:
            resume_payload = {
                "action": action_upper,
                "reviewer": reviewer,
                "comments": comments,
                "updated_fields": task.updated_fields,
                "timestamp": now.isoformat(),
            }
            cfg = {"configurable": {"thread_id": task.thread_id}}
            resumed_state = await compiled_workflow.ainvoke(
                Command(resume=resume_payload),
                config=cfg,
            )

        return resumed_state

    def submit_decision_sync(
        self,
        task_id: str,
        action: str,
        reviewer: str,
        comments: Optional[str] = None,
        updated_fields: Optional[Dict[str, Any]] = None,
        compiled_workflow: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous version of submit_decision.
        Actions an approval task and dispatches Command(resume=...) to resume LangGraph.
        """
        task = self.get_task(task_id)
        if task.status != TaskStatus.PENDING:
            raise ValueError(f"Task '{task_id}' is already {task.status.value} and cannot be actioned.")

        action_upper = action.upper()
        if action_upper not in task.allowed_actions:
            raise ValueError(f"Action '{action}' is not in allowed actions: {task.allowed_actions}")

        # Update task record
        now = datetime.now(timezone.utc)
        if action_upper == "APPROVE":
            task.status = TaskStatus.APPROVED
        elif action_upper == "REJECT":
            task.status = TaskStatus.REJECTED
        elif action_upper == "EDIT_AND_APPROVE":
            task.status = TaskStatus.EDITED_AND_APPROVED
        else:
            task.status = TaskStatus.APPROVED

        task.decision_action = action_upper
        task.decided_by = reviewer
        task.decided_at = now
        task.reviewer_comments = comments
        task.updated_fields = updated_fields or {}

        # If a compiled LangGraph workflow instance is provided, resume execution
        resumed_state: Dict[str, Any] = {}
        if compiled_workflow is not None:
            resume_payload = {
                "action": action_upper,
                "reviewer": reviewer,
                "comments": comments,
                "updated_fields": task.updated_fields,
                "timestamp": now.isoformat(),
            }
            cfg = {"configurable": {"thread_id": task.thread_id}}
            resumed_state = compiled_workflow.invoke(
                Command(resume=resume_payload),
                config=cfg,
            )

        return resumed_state

    def check_slas(self) -> List[ApprovalTask]:
        """Scans pending tasks and escalates any that have exceeded their SLA deadline."""
        now = datetime.now(timezone.utc)
        escalated: List[ApprovalTask] = []
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING and task.sla_deadline and now > task.sla_deadline:
                task.status = TaskStatus.ESCALATED
                escalated.append(task)
        return escalated

    def clear(self) -> None:
        self._tasks.clear()


# Default singleton inbox service
inbox_service = ApprovalInboxService()

