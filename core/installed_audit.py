"""Evidence-led audit of software installed together.

InstallDate is registry metadata and can be missing/inaccurate. Coinciding
dates are **not** proof of bundling or adware. We only surface review candidates.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta


def parse_registry_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if len(raw) != 8 or not raw.isdigit():
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        return None


def installation_review(applications: list[dict], today: date | None = None,
                        days: int = 45) -> dict:
    today = today or date.today()
    since = today - timedelta(days=max(1, min(365, days)))
    by_day: dict[date, list[dict]] = defaultdict(list)
    unknown_dates = 0
    for app in applications:
        installed = parse_registry_date(app.get("installed"))
        if installed is None:
            unknown_dates += 1
        elif since <= installed <= today:
            by_day[installed].append(app)
    recent = []
    same_day = []
    for installed in sorted(by_day, reverse=True):
        items = sorted(by_day[installed], key=lambda row: str(row.get("name", "")).casefold())
        recent.append({"date": installed.isoformat(), "apps": items})
        if len(items) >= 2:
            same_day.append({"date": installed.isoformat(), "apps": items})
    return {"recent": recent, "same_day": same_day,
            "unknown_dates": unknown_dates, "days": days}


def installation_review_text(result: dict) -> str:
    lines = [
        f"История программ за последние {result['days']} дней (по реестру Windows)",
        f"Без даты установки: {result['unknown_dates']}. Эти программы не показаны ниже.",
        "",
        "Одинаковая дата НЕ доказывает установку рекламного ПО в комплекте.",
        "Если программа незнакома, сначала проверьте её издателя и Microsoft Defender.",
        "",
    ]
    for group in result["recent"]:
        lines.append(group["date"] + ("  ← установлено несколько программ"
                                      if len(group["apps"]) >= 2 else ""))
        for app in group["apps"]:
            lines.append("  • " + str(app.get("name") or "?") +
                         " — " + str(app.get("publisher") or "издатель не указан"))
    if not result["recent"]:
        lines.append("Недавние установки не найдены или InstallDate отсутствует.")
    return "\n".join(lines)
