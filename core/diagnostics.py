from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from core.paths import app_root
from core.windows_paths import desktop_path


def _check(name: str, ok: bool, detail: str, level: str | None = None) -> dict:
    return {
        "name": name,
        "ok": bool(ok),
        "level": level or ("ok" if ok else "error"),
        "detail": detail,
    }


def _directory_access(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"папка не найдена: {path}"
    if not path.is_dir():
        return False, f"ожидалась папка: {path}"
    ok = os.access(path, os.R_OK | os.W_OK)
    return ok, str(path)


def _runtime_layout(root: Path) -> tuple[bool, str]:
    if not getattr(sys, "frozen", False):
        return True, "режим исходного кода"
    runtime_dir = root / "_runtime"
    if runtime_dir.is_dir():
        return True, f"onedir runtime: {runtime_dir}"
    return False, f"не найдена папка runtime: {runtime_dir}"


def collect_diagnostics(root: Path | None = None) -> dict:
    """Collect local, non-destructive diagnostics without network access."""
    root = Path(root or app_root())
    data_dir = root / "data"
    logs_dir = root / "logs"

    checks: list[dict] = []
    checks.append(_check("Корень приложения", root.exists(), str(root)))

    data_ok, data_detail = _directory_access(data_dir)
    checks.append(_check("Доступ к data", data_ok, data_detail))

    logs_ok, logs_detail = _directory_access(logs_dir)
    checks.append(_check("Доступ к logs", logs_ok, logs_detail))

    runtime_ok, runtime_detail = _runtime_layout(root)
    checks.append(_check("Windows runtime", runtime_ok, runtime_detail))

    try:
        desktop = desktop_path()
        desktop_ok = desktop.exists()
        checks.append(_check("Рабочий стол Windows", desktop_ok, str(desktop), "ok" if desktop_ok else "warning"))
    except Exception as exc:
        checks.append(_check("Рабочий стол Windows", False, str(exc), "warning"))

    seven_zip = shutil.which("7z") or shutil.which("7zz") or shutil.which("7z.exe") or shutil.which("7zz.exe")
    checks.append(
        _check(
            "7-Zip для RAR/7Z",
            bool(seven_zip),
            seven_zip or "не найден; ZIP продолжит работать встроенными средствами",
            "ok" if seven_zip else "warning",
        )
    )

    version_file = root / "version.json"
    checks.append(_check("Файл версии", version_file.is_file(), str(version_file)))

    build_file = root / "runtime-build.txt"
    build_ok = build_file.is_file() or not getattr(sys, "frozen", False)
    checks.append(
        _check(
            "Маркер runtime-сборки",
            build_ok,
            str(build_file) if build_file.is_file() else "в исходном режиме необязателен",
            "ok" if build_ok else "warning",
        )
    )

    error_count = sum(1 for item in checks if item["level"] == "error")
    warning_count = sum(1 for item in checks if item["level"] == "warning")
    return {
        "checks": checks,
        "summary": {
            "ok": len(checks) - error_count - warning_count,
            "warnings": warning_count,
            "errors": error_count,
            "healthy": error_count == 0,
        },
    }
