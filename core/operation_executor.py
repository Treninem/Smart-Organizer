from __future__ import annotations

import os
import shutil
from pathlib import Path

from core.operation_journal import ReversibleOperation, same_path, validate_no_destructive_conflicts


class OperationExecutionError(RuntimeError):
    pass


def _ensure_safe_source(path: Path) -> None:
    if not path.exists():
        raise OperationExecutionError(f"Source does not exist: {path}")


def _ensure_free_target(source: Path, target: Path) -> None:
    if same_path(str(source), str(target)):
        raise OperationExecutionError(f"Source and target are the same: {source}")
    if target.exists():
        raise OperationExecutionError(f"Target already exists: {target}")
    if not target.parent.exists():
        raise OperationExecutionError(f"Target parent does not exist: {target.parent}")


def execute_operation(operation: ReversibleOperation) -> dict:
    """Execute one previously reviewed reversible operation.

    The executor is intentionally conservative: it never overwrites an existing
    target and never creates missing parent directories implicitly.
    """

    operation.validate()
    source = Path(operation.source)

    if operation.op_type in {"move", "rename"}:
        assert operation.target is not None
        target = Path(operation.target)
        _ensure_safe_source(source)
        _ensure_free_target(source, target)
        shutil.move(str(source), str(target))
        return {"source": str(source), "target": str(target), "op_type": operation.op_type}

    if operation.op_type == "mkdir":
        if source.exists():
            raise OperationExecutionError(f"Directory target already exists: {source}")
        if not source.parent.exists():
            raise OperationExecutionError(f"Directory parent does not exist: {source.parent}")
        source.mkdir()
        return {"source": str(source), "target": None, "op_type": operation.op_type}

    if operation.op_type == "delete-to-quarantine":
        if not operation.target:
            raise OperationExecutionError("Quarantine operation requires an explicit target")
        target = Path(operation.target)
        _ensure_safe_source(source)
        _ensure_free_target(source, target)
        shutil.move(str(source), str(target))
        return {"source": str(source), "target": str(target), "op_type": operation.op_type}

    raise OperationExecutionError(f"Unsupported operation: {operation.op_type}")


def execute_batch(journal, batch_id: str) -> dict:
    """Apply only planned entries from a persisted journal batch.

    On the first error the executor stops. Already applied entries stay marked
    as applied so the batch can be rolled back deterministically with
    ``undo_batch``.
    """

    rows = journal.entries(batch_id=batch_id, limit=5000)
    planned = [row for row in rows if row["status"] == "planned"]
    if not planned:
        raise OperationExecutionError(f"No planned operations in batch: {batch_id}")

    operations = [
        ReversibleOperation(
            op_type=row["op_type"],
            source=row["source"],
            target=row["target"],
            reason=(row.get("details") or {}).get("reason", ""),
        )
        for row in planned
    ]
    validate_no_destructive_conflicts(operations)

    applied = 0
    for row, operation in zip(planned, operations):
        try:
            details = execute_operation(operation)
            journal.mark_applied(int(row["id"]), details)
            applied += 1
        except Exception as exc:
            journal.mark_failed(int(row["id"]), str(exc))
            raise OperationExecutionError(
                f"Batch {batch_id} stopped after {applied} applied operation(s): {exc}"
            ) from exc

    return {"batch_id": batch_id, "applied": applied, "failed": 0}


def undo_batch(journal, batch_id: str) -> dict:
    """Undo all currently applied entries in reverse sequence order."""

    rows = journal.entries(batch_id=batch_id, limit=5000)
    applied = [row for row in rows if row["status"] == "applied"]
    if not applied:
        raise OperationExecutionError(f"No applied operations to undo in batch: {batch_id}")

    undone = 0
    for row in reversed(applied):
        op_type = row["op_type"]
        source = row["source"]
        target = row["target"]

        if op_type in {"move", "rename"}:
            inverse = ReversibleOperation(op_type, str(target), source, "journal rollback")
        elif op_type == "delete-to-quarantine":
            if not target:
                raise OperationExecutionError(f"Missing quarantine target for entry {row['id']}")
            inverse = ReversibleOperation("move", target, source, "undo quarantine")
        elif op_type == "mkdir":
            path = Path(source)
            if not path.exists():
                raise OperationExecutionError(f"Created directory disappeared before undo: {path}")
            try:
                path.rmdir()
            except OSError as exc:
                raise OperationExecutionError(
                    f"Refusing to remove non-empty directory during undo: {path}"
                ) from exc
            journal.mark_undone(int(row["id"]), {"removed_empty_directory": str(path)})
            undone += 1
            continue
        else:
            raise OperationExecutionError(f"Unsupported journal operation during undo: {op_type}")

        details = execute_operation(inverse)
        journal.mark_undone(int(row["id"]), {"inverse": details})
        undone += 1

    return {"batch_id": batch_id, "undone": undone}
