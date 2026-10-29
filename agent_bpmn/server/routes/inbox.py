from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_bpmn.runtime.hitl_inbox import ApprovalTask, TaskStatus, inbox_service

router = APIRouter(prefix="/api/inbox", tags=["Approval Inbox"])


class ResolveTaskPayload(BaseModel):
    action: str  # "APPROVE", "REJECT", "EDIT_AND_APPROVE"
    reviewer: str = "web_reviewer@enterprise.com"
    comments: Optional[str] = None
    updated_fields: Optional[Dict[str, Any]] = None


@router.get("/tasks")
def list_tasks(
    role: Optional[str] = None,
    status: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lists approval tasks, optionally filtered by assigned role, status, or workflow ID."""
    tasks = inbox_service.get_pending_tasks(role=role, workflow_id=workflow_id)
    if status:
        tasks = [t for t in tasks if t.status.value.upper() == status.upper()]
    return [t.model_dump() for t in tasks]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    """Retrieves full details and state snapshot for a single approval task."""
    task = inbox_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Approval task '{task_id}' not found.")
    return task.model_dump()


@router.post("/tasks/{task_id}/resolve")
def resolve_task(task_id: str, payload: ResolveTaskPayload) -> Dict[str, Any]:
    """
    Submits a human review decision (APPROVE, REJECT, EDIT_AND_APPROVE).
    Resolves the inbox task and returns resumption instructions.
    """
    try:
        task = inbox_service.resolve_task(
            task_id=task_id,
            action=payload.action,
            reviewer=payload.reviewer,
            comments=payload.comments,
            updated_fields=payload.updated_fields,
        )
        return {
            "success": True,
            "task_id": task_id,
            "status": task.status.value,
            "action": payload.action,
            "reviewer": payload.reviewer,
            "thread_id": task.thread_id,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

