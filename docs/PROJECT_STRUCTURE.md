# PROJECT_STRUCTURE.md

Живой документ — при добавлении/удалении/переносе файла обнови эту карту
в той же сессии, где менялась структура. Не обновлённая карта хуже
отсутствующей: следующая ИИ будет ей доверять.

## Дерево на 28.09.2026

```text
allizium_engine/
├── main.py                  # REPL-цикл, system prompt, сборка messages, tool-loop
├── README.md                # человеко-читаемое описание проекта (не для ИИ-контекста)
│
├── docs/                    # этот набор файлов — читать перед началом работы
│   ├── AI_CONTEXT.md
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md ← ты здесь
│   ├── DECISIONS.md
│   ├── MODDING.md
│   └── DEPENDENCY_GRAPH.md  # генерация диаграмм модов по запросу, не хранимый артефакт
│
├── data/
│   └── world.db             # SQLite БД текущего запуска (демо-мир Allizium)
│                             # ПЛАНИРУЕТСЯ: переезд под data/worlds/<name>/world.db
│
├── engine/                  # world-agnostic ядро — см. правило в ARCHITECTURE.md
│   ├── __init__.py
│   ├── database.py          # SQL-схема (world_state, entities, inventory, money, events) + connection
│   ├── world.py             # игровая механика: buy_item, upgrade_stat, advance_time, search_entities...
│   │                         # содержит seed_demo_world() — ЗНАЕТ про Бориса/таверну, техдолг #ENG-004
│   └── actions.py           # JSON-schema тулов для LLM + роутинг call(name, args) → WorldEngine
│
├── llm/
│   ├── __init__.py
│   └── ollama.py            # тонкий HTTP-клиент к Ollama /api/chat, без бизнес-логики
│
└── tests/
    └── test_engine.py       # запускать напрямую: python tests/test_engine.py
                              # (unittest discover НЕ находит эти тесты — стиль pytest-функций)
```

## Что где искать (быстрый указатель для ИИ)

| Нужно... | Смотри в |
|---|---|
| Добавить новый tool для LLM | `engine/actions.py` (schema) + `engine/world.py` (реализация) |
| Поменять SQL-схему | `engine/database.py` |
| Изменить system prompt / правила поведения LLM | `main.py` (`SYSTEM`) — после рефакторинга: `data/worlds/<name>/system_prompt.txt` |
| Добавить/поменять сущность демо-мира | `engine/world.py::seed_demo_world()` — после рефакторинга: `data/worlds/allizium/world.json` |
| Понять, как LLM вызывает тулы | `main.py`, цикл после `resp=llm.chat(...)` |
| Проверить, что уже решено и почему | `docs/DECISIONS.md` |
| Понять принципы, которые нельзя ломать | `docs/ARCHITECTURE.md` |
| Собрать новый мир/мод (когда рефакторинг будет готов) | `docs/MODDING.md` |

## Известные открытые задачи (дублируются в DECISIONS.md, статус актуальнее там)

- `#ENG-002` — tool-call loop однократный, нет цикла для последовательных вызовов.
- `#ENG-003` — нет персистентности диалога, нет суммаризации истории.
- `#ENG-004` — `seed_demo_world()` и дефолт `seller_id='boris'` — лор в коде движка.
- `#ENG-011` — манифест/lock-файл модов и генератор диаграмм зависимостей спроектированы, генератор не написан.
