from __future__ import annotations

from pathlib import Path

from .operation_journal import ReversibleOperation, validate_no_destructive_conflicts


def operations_from_sort_plan(plan: dict, existing_only: bool = True) -> list[ReversibleOperation]:
    """Convert a read-only sort plan into journalable move intents.

    This function never touches the filesystem. By default it accepts only
    destinations that already exist according to the planner, so proposals that
    would require creating a new folder cannot silently become executable work.
    """
    operations: list[ReversibleOperation] = []
    for item in plan.get("items", []):
        if existing_only and (item.get("mode") != "existing" or item.get("requires_confirmation")):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target_path") or "").strip()
        if not source or not target:
            continue
        operations.append(
            ReversibleOperation(
                op_type="move",
                source=source,
                target=target,
                reason=str(item.get("reason") or "safe sort plan"),
            )
        )

    validate_no_destructive_conflicts(operations)
    return operations


def operations_from_confirmed_sort_plan(plan: dict) -> list[ReversibleOperation]:
    """Build a complete reviewed organization batch, including new folders.

    Folder creation is explicit in the journal and therefore reversible. The
    caller must obtain user confirmation before using this function's result.
    """
    operations: list[ReversibleOperation] = []
    planned_dirs: set[str] = set()

    for item in plan.get("items", []):
        source = str(item.get("source") or "").strip()
        target_dir = str(item.get("target_dir") or "").strip()
        target = str(item.get("target_path") or "").strip()
        if not source or not target_dir or not target:
            continue

        if item.get("mode") != "existing":
            key = str(Path(target_dir)).replace("\\", "/").rstrip("/").casefold()
            if key not in planned_dirs and not Path(target_dir).exists():
                operations.append(
                    ReversibleOperation(
                        op_type="mkdir",
                        source=target_dir,
                        target=None,
                        reason="confirmed Smart Organizer destination folder",
                    )
                )
                planned_dirs.add(key)

        operations.append(
            ReversibleOperation(
                op_type="move",
                source=source,
                target=target,
                reason=str(item.get("reason") or "confirmed sort plan"),
            )
        )

    validate_no_destructive_conflicts(operations)
    return operations
