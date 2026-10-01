#!/usr/bin/env python3
"""Строит docs/INDEX.md из шапок (frontmatter) документов и проверяет их.

    python tools/docs_index.py           # пересобрать docs/INDEX.md
    python tools/docs_index.py --check   # CI: ошибка, если индекс устарел или есть нарушения

Проверки: у каждого .md в docs/ есть шапка с type, status, last_reviewed,
read_when; статус из допустимого списка; относительные ссылки на .md существуют.
Стандартная библиотека, без зависимостей.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
INDEX = DOCS / "INDEX.md"
STATUSES = {
    "implemented", "partial", "living", "accepted", "proposed",
    "idea", "vision", "in-progress", "rejected", "superseded",
}
REQUIRED = ("type", "status", "last_reviewed", "read_when")
LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")


def parse(path: Path) -> dict[str, str] | None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta


def collect() -> tuple[list[tuple[str, dict[str, str], int]], list[str]]:
    rows, errors = [], []
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(DOCS).as_posix()
        if rel == "INDEX.md":
            continue
        meta = parse(path)
        if meta is None:
            errors.append(f"{rel}: нет шапки (frontmatter)")
            continue
        for key in REQUIRED:
            if not meta.get(key):
                errors.append(f"{rel}: в шапке нет поля {key}")
        if meta.get("status") and meta["status"] not in STATUSES:
            errors.append(f"{rel}: неизвестный статус {meta['status']!r}")
        text = path.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://")):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{rel}: битая ссылка {target}")
        rows.append((rel, meta, text.count("\n") + 1))
    return rows, errors


def render(rows: list[tuple[str, dict[str, str], int]]) -> str:
    out = [
        "---",
        "type: index",
        "status: living",
        "last_reviewed: generated",
        "read_when: нужно выбрать документ по условию чтения; файл генерируется, не правь вручную",
        "---",
        "",
        "# INDEX.md — все документы",
        "",
        "Генерируется командой `python tools/docs_index.py` из шапок файлов.",
        "Не правь вручную. Колонка «строк» помогает оценить, сколько читать.",
        "",
        "| Файл | Тип | Статус | Строк | Читать, когда |",
        "|---|---|---|---|---|",
    ]
    for rel, meta, lines in rows:
        out.append(
            f"| `{rel}` | {meta.get('type', '')} | {meta.get('status', '')} | {lines} | {meta.get('read_when', '')} |"
        )
    return "\n".join(out) + "\n"


def main() -> int:
    rows, errors = collect()
    content = render(rows)
    if "--check" in sys.argv:
        current = INDEX.read_text(encoding="utf-8").replace("\r\n", "\n") if INDEX.exists() else ""
        if current != content:
            errors.append("docs/INDEX.md устарел: запусти python tools/docs_index.py")
        for err in errors:
            print(err)
        return 1 if errors else 0
    INDEX.write_text(content, encoding="utf-8", newline="\n")
    for err in errors:
        print("ВНИМАНИЕ:", err)
    print(f"INDEX.md: {len(rows)} документов")
    return 0


if __name__ == "__main__":
    sys.exit(main())
