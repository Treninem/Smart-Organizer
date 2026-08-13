from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


def _new_batch_id() -> str:
    """Create a collision-resistant local batch id without optional frozen modules."""
    seed = b"|".join(
        [
            str(time.time_ns()).encode("ascii"),
            str(os.getpid()).encode("ascii"),
            os.urandom(32),
        ]
    )
    return hashlib.sha256(seed).hexdigest()[:32]


@dataclass(frozen=True)
class ReversibleOperation:
    """One filesystem change that can be reversed later.

    The journal stores intent separately from execution. Merely creating an
    operation or a batch never changes the filesystem.
    """

    op_type: str
    source: str
    target: str | None = None
    reason: str = ""

    def validate(self) -> None:
        if self.op_type not in {"move", "rename", "mkdir", "delete-to-quarantine"}:
            raise ValueError(f"Unsupported reversible operation: {self.op_type}")
        if not str(self.source).strip():
            raise ValueError("Operation source must not be empty")
        if self.op_type in {"move", "rename"} and not str(self.target or "").strip():
            raise ValueError(f"{self.op_type} requires a target")

    def inverse(self) -> "ReversibleOperation":
        self.validate()
        if self.op_type in {"move", "rename"}:
            return ReversibleOperation(self.op_type, str(self.target), self.source, f"undo: {self.reason}".strip())
        if self.op_type == "mkdir":
            return ReversibleOperation("delete-to-quarantine", self.source, None, f"undo mkdir: {self.reason}".strip())
        raise ValueError("delete-to-quarantine can only be undone from its recorded quarantine target")


class OperationJournal:
    """Persistent transaction journal backed by the application's SQLite DB."""

    def __init__(self, database):
        self.db = database

    def plan_batch(self, operations: list[ReversibleOperation], label: str = "") -> str:
        if not operations:
            raise ValueError("Cannot create an empty operation batch")
        for operation in operations:
            operation.validate()

        batch_id = _new_batch_id()
        rows = []
        for index, operation in enumerate(operations):
            rows.append(
                {
                    "batch_id": batch_id,
                    "sequence": index,
                    "op_type": operation.op_type,
                    "source": operation.source,
                    "target": operation.target,
                    "status": "planned",
                    "details": json.dumps({"reason": operation.reason, "label": label}, ensure_ascii=False),
                }
            )
        self.db.add_operation_batch(rows)
        return batch_id

    def entries(self, batch_id: str | None = None, limit: int = 100) -> list[dict]:
        return self.db.operation_entries(batch_id=batch_id, limit=limit)

    def mark_applied(self, entry_id: int, details: dict | None = None) -> None:
        self.db.set_operation_status(entry_id, "applied", details or {})

    def mark_failed(self, entry_id: int, error: str) -> None:
        self.db.set_operation_status(entry_id, "failed", {"error": error})

    def mark_undone(self, entry_id: int, details: dict | None = None) -> None:
        self.db.set_operation_status(entry_id, "undone", details or {})

    def undo_plan(self, batch_id: str) -> list[ReversibleOperation]:
        entries = [row for row in self.entries(batch_id=batch_id) if row["status"] == "applied"]
        inverse: list[ReversibleOperation] = []
        for row in reversed(entries):
            operation = ReversibleOperation(
                op_type=row["op_type"],
                source=row["source"],
                target=row["target"],
                reason="journal rollback",
            )
            if operation.op_type == "delete-to-quarantine":
                quarantine_target = row.get("target")
                if quarantine_target:
                    inverse.append(ReversibleOperation("move", quarantine_target, operation.source, "undo quarantine"))
                continue
            inverse.append(operation.inverse())
        return inverse


def same_path(left: str, right: str) -> bool:
    """Platform-neutral comparison used to reject no-op move/rename plans."""

    return str(Path(left)).replace("\\", "/").rstrip("/").casefold() == str(Path(right)).replace("\\", "/").rstrip("/").casefold()


def validate_no_destructive_conflicts(operations: list[ReversibleOperation]) -> None:
    """Reject plans that are obviously unsafe before any executor sees them."""

    targets: set[str] = set()
    for operation in operations:
        operation.validate()
        if operation.target and same_path(operation.source, operation.target):
            raise ValueError(f"Source and target are the same: {operation.source}")
        if operation.target:
            normalized = str(Path(operation.target)).replace("\\", "/").rstrip("/").casefold()
            if normalized in targets:
                raise ValueError(f"Two operations target the same path: {operation.target}")
            targets.add(normalized)
