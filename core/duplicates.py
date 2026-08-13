from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

COPY_MARKER_RE = re.compile(r"(?i)(?:\(\d+\)|\[\d+\]|(?:copy|копия)(?:\s*\(\d+\))?)")
QUICK_CHUNK_SIZE = 64 * 1024


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quick_signature(path: Path, size: int, chunk_size: int = QUICK_CHUNK_SIZE) -> str:
    """Cheap content filter before a full SHA-256 pass.

    The final duplicate decision still always uses a full-file SHA-256. This
    signature only prevents unnecessary full reads of unrelated files that
    happen to have the same size.
    """
    digest = hashlib.blake2b(digest_size=16)
    digest.update(str(size).encode("ascii"))
    with path.open("rb") as fh:
        first = fh.read(chunk_size)
        digest.update(first)
        if size > chunk_size:
            fh.seek(max(0, size - chunk_size))
            digest.update(fh.read(chunk_size))
    return digest.hexdigest()


def _normalize_scope_piece(value: str) -> str:
    return str(value).replace("\\", "/").rstrip("/").casefold()


def duplicate_scope(record: dict, scan_root: str | None = None) -> str:
    """Return a conservative duplicate scope for one scanned file.

    Identical bytes in different projects are intentionally NOT treated as
    removable duplicates. When a scan root is known, the first directory below
    that root acts as a structural project boundary. A recognized project hint
    is added as a second boundary. Without a scan root, the parent directory is
    used, preferring false negatives over deleting a legitimate project file.
    """
    path = Path(str(record.get("path", "")))
    project = str(record.get("project_hint") or "").strip().casefold()

    structural = ""
    if scan_root:
        root = Path(str(scan_root))
        try:
            relative = path.relative_to(root)
            if len(relative.parts) >= 2:
                structural = f"tree:{_normalize_scope_piece(relative.parts[0])}"
            else:
                structural = f"root:{_normalize_scope_piece(root)}"
        except (ValueError, OSError):
            structural = f"parent:{_normalize_scope_piece(path.parent)}"
    else:
        structural = f"parent:{_normalize_scope_piece(path.parent)}"

    if project:
        return f"{structural}|project:{project}"
    return structural


def _canonical_score(record: dict) -> tuple:
    name = record.get("name", "")
    has_copy_marker = bool(COPY_MARKER_RE.search(name))
    return (1 if has_copy_marker else 0, len(name), record.get("modified", 0))


def exact_duplicate_groups(records: Iterable[dict], scan_root: str | None = None) -> list[dict]:
    """Find exact duplicates only inside the same conservative project scope."""
    by_size: dict[int, list[dict]] = {}
    for record in records:
        size = int(record.get("size", -1))
        if size < 0:
            continue
        by_size.setdefault(size, []).append(record)

    results: list[dict] = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue

        by_quick: dict[str, list[dict]] = {}
        for record in candidates:
            path = Path(record["path"])
            try:
                if not path.is_file():
                    continue
                signature = quick_signature(path, size)
            except (OSError, PermissionError):
                continue
            by_quick.setdefault(signature, []).append(record)

        for quick_matches in by_quick.values():
            if len(quick_matches) < 2:
                continue
            by_hash: dict[str, list[dict]] = {}
            for record in quick_matches:
                path = Path(record["path"])
                try:
                    digest = sha256_file(path)
                except (OSError, PermissionError):
                    continue
                by_hash.setdefault(digest, []).append(record)

            for digest, matches in by_hash.items():
                if len(matches) < 2:
                    continue

                by_scope: dict[str, list[dict]] = {}
                for record in matches:
                    scope = duplicate_scope(record, scan_root)
                    by_scope.setdefault(scope, []).append(record)

                for scope, scoped_matches in by_scope.items():
                    if len(scoped_matches) < 2:
                        continue
                    ordered = sorted(scoped_matches, key=_canonical_score)
                    results.append(
                        {
                            "sha256": digest,
                            "size": size,
                            "scope": scope,
                            "canonical": ordered[0]["path"],
                            "duplicates": [item["path"] for item in ordered[1:]],
                            "count": len(ordered),
                        }
                    )
    return sorted(results, key=lambda x: (-x["size"], x["canonical"].lower()))
