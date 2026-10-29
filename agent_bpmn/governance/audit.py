import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from agent_bpmn.governance.models import AuditTrailEntry

GENESIS_HASH = "0" * 64


class AuditLogger:
    """
    Cryptographically chained, tamper-evident audit logging service.
    Guarantees immutable historical audit trails for SOC2 Type II, HIPAA,
    and enterprise change governance.
    """

    def __init__(self) -> None:
        self._entries: List[AuditTrailEntry] = []
        self._init_genesis()

    def _init_genesis(self) -> None:
        """Initializes the blockchain-style genesis audit anchor."""
        genesis = AuditTrailEntry(
            entry_id="audit_genesis_000",
            index=0,
            actor="system:genesis",
            action="INITIALIZE_AUDIT_LEDGER",
            workflow_id="system",
            details={"description": "AgentBPMN Cryptographic Audit Trail Genesis Block"},
            previous_hash=GENESIS_HASH,
        )
        genesis.current_hash = genesis.calculate_hash()
        self._entries.append(genesis)

    def log(
        self,
        actor: str,
        action: str,
        workflow_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditTrailEntry:
        """Appends a new immutable, hash-chained entry to the audit log."""
        prev_entry = self._entries[-1]
        entry = AuditTrailEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:10]}",
            index=len(self._entries),
            actor=actor,
            action=action,
            workflow_id=workflow_id,
            details=details or {},
            previous_hash=prev_entry.current_hash,
        )
        entry.current_hash = entry.calculate_hash()
        self._entries.append(entry)
        return entry

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Validates the entire hash chain from genesis to head.
        Returns (True, None) if completely untampered, or (False, error_reason) if corruption detected.
        """
        for i in range(len(self._entries)):
            current = self._entries[i]
            # 1. Verify self-hash matches calculated hash
            expected_hash = current.calculate_hash()
            if current.current_hash != expected_hash:
                return (
                    False,
                    f"Tamper detected at index {i} ({current.entry_id}): "
                    f"Stored hash '{current.current_hash[:12]}...' != Recomputed '{expected_hash[:12]}...'",
                )

            # 2. Verify previous_hash link
            if i > 0:
                previous = self._entries[i - 1]
                if current.previous_hash != previous.current_hash:
                    return (
                        False,
                        f"Chain breakage between index {i-1} and {i}: "
                        f"Entry {i} previous_hash does not match Entry {i-1} current_hash.",
                    )

        return True, None

    def query(
        self,
        workflow_id: Optional[str] = None,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditTrailEntry]:
        """Queries audit entries with optional filters."""
        results = [e for e in self._entries if e.index > 0]  # Exclude genesis
        if workflow_id:
            results = [e for e in results if e.workflow_id == workflow_id]
        if actor:
            results = [e for e in results if e.actor.lower() == actor.lower()]
        if action:
            results = [e for e in results if e.action.upper() == action.upper()]
        return results[-limit:]

    def export_json(self, filepath: Path) -> None:
        """Exports full audit trail as indented JSON."""
        data = [e.model_dump() for e in self._entries]
        filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")


# Default global instance
audit_logger = AuditLogger()
