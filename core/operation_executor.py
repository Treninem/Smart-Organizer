from __future__ import annotations

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


def preflight_operation(operation: ReversibleOperation) -> None:
    """Validate the current filesystem state without changing it."""

    operation.validate()
    source = Path(operation.source)
    if operation.op_type in {"move", "rename"}:
        assert operation.target is not None
        _ensure_safe_source(source)
        _ensure_free_target(source, Path(operation.target))
        return
    if operation.op_type == "mkdir":
        if source.exists():
            raise OperationExecutionError(f"Directory target already exists: {source}")
        if not source.parent.exists():
            raise OperationExecutionError(f"Directory parent does not exist: {source.parent}")
        return
    if operation.op_type == "delete-to-quarantine":
        if not operation.target:
            raise OperationExecutionError("Quarantine operation requires an explicit target")
        _ensure_safe_source(source)
        _ensure_free_target(source, Path(operation.target))
        return
    raise OperationExecutionError(f"Unsupported operation: {operation.op_type}")


def execute_operation(operation: ReversibleOperation) -> dict:
    """Execute one reviewed reversible operation without overwriting targets."""

    preflight_operation(operation)
    source = Path(operation.source)

    if operation.op_type in {"move", "rename", "delete-to-quarantine"}:
        assert operation.target is not None
        target = Path(operation.target)
        shutil.move(str(source), str(target))
        return {"source": str(source), "target": str(target), "op_type": operation.op_type}

    if operation.op_type == "mkdir":
        source.mkdir()
        return {"source": str(source), "target": None, "op_type": operation.op_type}

    raise OperationExecutionError(f"Unsupported operation: {operation.op_type}")


def execute_batch(journal, batch_id: str) -> dict:
    """Apply a persisted batch only after the whole batch passes preflight.

    A batch containing a previous failed entry is not silently resumed. The user
    must generate a fresh plan after resolving the conflict, which keeps the
    journal deterministic and understandable.
    """

    rows = journal.entries(batch_id=batch_id, limit=5000)
    if any(row["status"] == "failed" for row in rows):
        raise OperationExecutionError(
            f"Batch {batch_id} contains a failed entry. Create a fresh plan after resolving the conflict."
        )
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

    # Preflight every operation before the first mutation. This catches missing
    # sources, occupied targets and missing parents without leaving a half-moved
    # batch in the common failure cases.
    for row, operation in zip(planned, operations):
        try:
            preflight_operation(operation)
        except Exception as exc:
            journal.mark_failed(int(row["id"]), str(exc))
            raise OperationExecutionError(f"Batch {batch_id} preflight failed: {exc}") from exc

    applied = 0
    for row, operation in zip(planned, operations):
        try:
            details = execute_operation(operation)
            journal.mark_applied(int(row["id"]), details)
            applied += 1
        except Exception as exc:
            # A race can still happen after preflight (for example another
            # process creates a target). Preserve exact progress for Undo.
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

    # Preflight inverse moves before changing anything where practical.
    inverse_rows: list[tuple[dict, ReversibleOperation | None]] = []
    for row in reversed(applied):
        op_type = row["op_type"]
        source = row["source"]
        target = row["target"]
        if op_type in {"move", "rename"}:
            inverse = ReversibleOperation(op_type, str(target), source, "journal rollback")
            preflight_operation(inverse)
            inverse_rows.append((row, inverse))
        elif op_type == "delete-to-quarantine":
            if not target:
                raise OperationExecutionError(f"Missing quarantine target for entry {row['id']}")
            inverse = ReversibleOperation("move", target, source, "undo quarantine")
            preflight_operation(inverse)
            inverse_rows.append((row, inverse))
        elif op_type == "mkdir":
            path = Path(source)
            if not path.exists():
                raise OperationExecutionError(f"Created directory disappeared before undo: {path}")
            if any(path.iterdir()):
                raise OperationExecutionError(f"Refusing to remove non-empty directory during undo: {path}")
            inverse_rows.append((row, None))
        else:
            raise OperationExecutionError(f"Unsupported journal operation during undo: {op_type}")

    undone = 0
    for row, inverse in inverse_rows:
        if inverse is None:
            path = Path(row["source"])
            path.rmdir()
            journal.mark_undone(int(row["id"]), {"removed_empty_directory": str(path)})
        else:
            details = execute_operation(inverse)
            journal.mark_undone(int(row["id"]), {"inverse": details})
        undone += 1

    return {"batch_id": batch_id, "undone": undone}
