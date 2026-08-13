from __future__ import annotations

from pathlib import Path

from .operation_journal import ReversibleOperation, validate_no_destructive_conflicts


def _norm(path: str | Path) -> str:
    return str(Path(path)).replace("\\", "/").rstrip("/").casefold()


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


def _missing_folder_chain(target_dir: Path) -> list[Path]:
    """Return missing folders from nearest existing parent to target."""
    missing: list[Path] = []
    cursor = target_dir
    while not cursor.exists():
        missing.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    return list(reversed(missing))


def operations_from_confirmed_sort_plan(plan: dict) -> list[ReversibleOperation]:
    """Build a complete reviewed organization batch, including new folders.

    Folder creation is explicit in the journal and therefore reversible. The
    caller must obtain user confirmation before using this function's result.
    Missing parent folders are added in parent-to-child order.
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
            for directory in _missing_folder_chain(Path(target_dir)):
                key = _norm(directory)
                if key in planned_dirs:
                    continue
                operations.append(
                    ReversibleOperation(
                        op_type="mkdir",
                        source=str(directory),
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
