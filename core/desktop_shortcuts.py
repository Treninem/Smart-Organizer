"""Reversible shortcut sorting on a user-selected Desktop.

Only direct .lnk/.url shortcut files are considered, never installed program
directories, executables, system settings, other desktop files, or project trees.
"""
from __future__ import annotations

from pathlib import Path
import re

from core.operation_journal import ReversibleOperation, validate_no_destructive_conflicts

GROUPS = ("Игры", "Программы", "Работа", "Документы")
FOLDER = "Группы Smart Organizer"
SHORTCUT_EXTENSIONS = frozenset({".lnk", ".url", ".website"})
MAX_SHORTCUTS = 1000


def parse_shortcut_rules(text: str) -> list[tuple[str, str]]:
    """Manual 'substring=category' rules; reject duplicates/unsafe folder names."""
    rules: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for part in re.split(r"[;\n]+", str(text)):
        part = part.strip()
        if not part:
            continue
        if part.count("=") != 1:
            raise ValueError(f"Неверное правило: {part!r}. Используйте Имя=Игры")
        phrase, category = (s.strip() for s in part.split("=", 1))
        if category not in GROUPS:
            raise ValueError(f"Недопустимая категория {category!r}. Допустимо: {', '.join(GROUPS)}")
        if not 2 <= len(phrase) <= 90 or phrase in {".", ".."}:
            raise ValueError(f"Слишком короткий или длинный признак ярлыка: {phrase!r}")
        if any(x in phrase for x in ("/", "\\", "*", "?", "<", ">", "|", '"', ":")):
            raise ValueError(f"Нельзя использовать спецсимволы путей: {phrase!r}")
        key = (phrase.casefold(), category)
        if key in seen:
            continue
        seen.add(key)
        rules.append((phrase.casefold(), category))
    return rules


def plan_shortcut_sort(desktop: Path, rules: list[tuple[str, str]]) -> dict:
    """Preview only; changes must go via journal + confirmed execute_batch."""
    desktop = Path(desktop)
    if not desktop.is_dir():
        raise ValueError(f"Рабочий стол не найден: {desktop}")
    if not rules:
        return {"operations": [], "matches": [], "ambiguous": [], "untouched": 0}
    container = desktop / FOLDER
    if container.exists() and (not container.is_dir() or container.is_symlink()):
        raise ValueError(f"Небезопасная папка групп: {container}")
    shortcuts = sorted(
        (p for p in desktop.iterdir()
         if p.is_file() and not p.is_symlink() and p.suffix.casefold() in SHORTCUT_EXTENSIONS),
        key=lambda p: p.name.casefold(),
    )
    if len(shortcuts) > MAX_SHORTCUTS:
        raise ValueError("Слишком много ярлыков; разделите набор правил на несколько проходов.")
    matches: list[dict] = []
    ambiguous: list[str] = []
    untouched = 0
    used_groups = set()
    for shortcut in shortcuts:
        categories = {
            group for phrase, group in rules if phrase in shortcut.stem.casefold()
        }
        if len(categories) != 1:
            if categories:
                ambiguous.append(shortcut.name)
            else:
                untouched += 1
            continue
        category = next(iter(categories))
        destination = container / category / shortcut.name
        if destination.exists():
            ambiguous.append(shortcut.name + " (имя занято)")
            continue
        matches.append({
            "name": shortcut.name, "category": category,
            "source": str(shortcut), "target": str(destination),
        })
        used_groups.add(category)
    operations: list[ReversibleOperation] = []
    if matches:
        if not container.exists():
            operations.append(ReversibleOperation("mkdir", str(container), None, "shortcut group container"))
        for category in GROUPS:
            if category in used_groups and not (container / category).exists():
                operations.append(ReversibleOperation(
                    "mkdir", str(container / category), None, "confirmed shortcut category"
                ))
        for match in matches:
            operations.append(ReversibleOperation(
                "move", match["source"], match["target"], "confirmed desktop shortcut grouping"
            ))
    validate_no_destructive_conflicts(operations)
    return {"operations": operations, "matches": matches,
            "ambiguous": ambiguous, "untouched": untouched}
