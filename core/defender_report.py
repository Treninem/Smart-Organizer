"""Read-only Microsoft Defender status / detection report.

Security results come from Windows Defender. The organizer does not invent
malware verdicts and does not delete, quarantine, or whitelist detected files.
"""
from __future__ import annotations

import json
import os
import subprocess


STATUS_SCRIPT = (
    "$ErrorActionPreference='Stop'; "
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
    "$s=Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,"
    "RealTimeProtectionEnabled,OnAccessProtectionEnabled,IoavProtectionEnabled,"
    "AntivirusSignatureLastUpdated,QuickScanEndTime,FullScanEndTime; "
    "$t=@(Get-MpThreatDetection -ErrorAction SilentlyContinue | "
    "Select-Object -First 25 ThreatID,ThreatName,InitialDetectionTime,"
    "ActionSuccess,Resources); "
    "@{status=$s;threats=$t} | ConvertTo-Json -Depth 5 -Compress"
)


def parse_defender_json(value: str) -> dict:
    """Normalize PowerShell's scalar/array JSON without making security claims."""
    data = json.loads(value.strip().lstrip("\ufeff"))
    if not isinstance(data, dict):
        raise ValueError("Неверный формат отчёта Defender")
    status = data.get("status") or {}
    threats = data.get("threats") or []
    if not isinstance(status, dict):
        status = {}
    if isinstance(threats, dict):
        threats = [threats]
    if not isinstance(threats, list):
        threats = []
    return {
        "source": "Microsoft Defender",
        "status": status,
        "threats": [x for x in threats if isinstance(x, dict)][:25],
    }


def defender_report(timeout: int = 15) -> dict:
    if os.name != "nt":
        raise RuntimeError("Отчёт Microsoft Defender доступен только в Windows.")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", STATUS_SCRIPT],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(
            "Microsoft Defender не предоставил отчёт: " +
            (result.stderr.strip() or "нет сведений (проверьте доступность Defender)")[:350]
        )
    return parse_defender_json(result.stdout)


def report_text(report: dict) -> str:
    status = report.get("status", {})
    enabled = {
        True: "ДА", False: "НЕТ", None: "нет данных",
    }
    lines = ["Источник: Microsoft Defender (отчёт только для чтения)",
             "Наличие записи НЕ означает, что угроза активна.",
             "",
             "Антивирус: " + enabled.get(status.get("AntivirusEnabled"), "нет данных"),
             "Защита в реальном времени: " + enabled.get(
                 status.get("RealTimeProtectionEnabled"), "нет данных"),
             "Сигнатуры обновлены: " + str(status.get("AntivirusSignatureLastUpdated") or "—"),
             "Последняя быстрая проверка: " + str(status.get("QuickScanEndTime") or "—"),
             "", "Последние обнаружения (максимум 25):"]
    threats = report.get("threats") or []
    if not threats:
        lines.append("Нет записей об обнаружениях, либо Defender не вернул сведения.")
    for item in threats:
        name = item.get("ThreatName") or item.get("ThreatID") or "Неизвестная запись"
        lines.append(f"• {name} | {item.get('InitialDetectionTime') or '—'} "
                     f"| действие отмечено как успешное: {item.get('ActionSuccess')}")
        resources = item.get("Resources") or []
        if isinstance(resources, str):
            resources = [resources]
        for resource in resources[:4]:
            lines.append("  " + str(resource)[:260])
    lines.append("\nДля карантина, истории и решений используйте «Безопасность Windows».")
    return "\n".join(lines)
