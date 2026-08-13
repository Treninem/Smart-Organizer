from __future__ import annotations

from collections import Counter

from core.duplicate_insights import duplicate_candidate_groups
from core.project_templates import summarize_template_matches
from core.version_manager import version_groups


def analyze_local_snapshot(
    records: list[dict],
    templates: list[dict] | None = None,
    scan_root: str | None = None,
) -> dict:
    """Explain the latest snapshot using deterministic local rules only.

    No network or paid API is used. The function never mutates files and never
    labels a file for deletion without an exact SHA-256 confirmation elsewhere.
    Duplicate hints are also isolated by project scope, so identical/common
    files belonging to different projects are not treated as copies.
    """
    rows = [dict(item) for item in records]
    categories = Counter((item.get("category") or "не определено") for item in rows)
    projects = Counter((item.get("project_hint") or "не определён") for item in rows)
    versions = version_groups(rows)
    duplicate_candidates = duplicate_candidate_groups(rows, scan_root=scan_root)
    template_matches = summarize_template_matches(rows, templates or [])

    old_paths: set[str] = set()
    newest_paths: set[str] = set()
    for group in versions:
        newest = group.get("newest_path")
        if newest:
            newest_paths.add(str(newest))
        for old in group.get("older", []):
            path = old.get("path")
            if path:
                old_paths.add(str(path))

    copy_candidate_paths: set[str] = set()
    for group in duplicate_candidates["name_groups"]:
        copy_candidate_paths.update(str(path) for path in group.get("paths", []))

    known_project_paths = {str(item.get("path")) for item in rows if item.get("project_hint")}
    reviewed_paths = old_paths | copy_candidate_paths
    keep_paths = {str(item.get("path")) for item in rows} - reviewed_paths

    return {
        "summary": {
            "files": len(rows),
            "keep": len(keep_paths),
            "newest_versions": len(newest_paths),
            "old_version_candidates": len(old_paths),
            "copy_name_candidates": len(copy_candidate_paths),
            "known_project_files": len(known_project_paths),
            "unknown_project_files": len(rows) - len(known_project_paths),
            "delete_without_sha256": 0,
        },
        "categories": categories.most_common(),
        "projects": projects.most_common(),
        "template_matches": template_matches,
        "version_groups": versions,
        "duplicate_candidates": duplicate_candidates,
    }
