from __future__ import annotations

from pathlib import Path


def render_folder_tree(folders: list[dict], root: str | None = None, limit: int = 3000) -> str:
    """Render the latest scanned folder snapshot as a compact text tree."""
    if not folders:
        return "Папки ещё не просканированы."

    root_path = Path(root) if root else None
    ordered = sorted(
        folders,
        key=lambda item: (int(item.get("depth", 0)), str(item.get("path", "")).casefold()),
    )
    lines: list[str] = []
    for index, item in enumerate(ordered):
        if index >= limit:
            lines.append(f"… ещё {len(ordered) - limit} папок")
            break
        path = Path(str(item.get("path", "")))
        depth = max(0, int(item.get("depth", 0)))
        label = item.get("name") or path.name or str(path)
        if root_path is not None:
            try:
                relative = path.relative_to(root_path)
                if str(relative) == ".":
                    depth = 0
                    label = str(root_path)
                else:
                    depth = max(0, len(relative.parts) - 1)
                    label = relative.name
            except (ValueError, OSError):
                pass
        branch = "└─ " if depth else ""
        lines.append(f"{'   ' * depth}{branch}{label}")
    return "\n".join(lines)
