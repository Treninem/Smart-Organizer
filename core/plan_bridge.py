from __future__ import annotations

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
