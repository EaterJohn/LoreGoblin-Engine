# PROJECT_STRUCTURE.md

Живой документ — при добавлении/удалении/переносе файла обнови эту карту
в той же сессии, где менялась структура.

## Дерево на 29.09.2026

```text
LoreGoblin-Engine/
├── main.py                  # CLI, world selection, system prompt, messages, tool-loop
├── README.md
├── docs/
│   ├── AI_CONTEXT.md
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── DECISIONS.md
│   ├── MODDING.md
│   └── DEPENDENCY_GRAPH.md
├── data/
│   ├── rules/
│   │   └── presets/
│   │       └── standard.json     # внешний пресет базовой календарной механики
│   └── worlds/
│       ├── allizium/
│       │   ├── world.json          # стартовые данные ALLIZIUM
│       │   ├── system_prompt.txt   # world-specific prompt
│       │   └── world.db            # runtime state, в .gitignore
│       └── station_demo/
│           ├── world.json
│           ├── system_prompt.txt
│           └── world.db            # создаётся при запуске, в .gitignore
├── engine/
│   ├── __init__.py
│   ├── database.py
│   ├── world.py             # механика + generic load_world()
│   └── actions.py
├── llm/
│   ├── __init__.py
│   └── ollama.py
└── tests/
    └── test_engine.py
```

## Что где искать

| Нужно... | Смотри в |
|---|---|
| Добавить новый tool для LLM | `engine/actions.py` + `engine/world.py` |
| Поменять SQL-схему | `engine/database.py` |
| Изменить общие правила LLM | `main.py::ENGINE_SYSTEM` |
| Изменить лор мира | `data/worlds/<name>/world.json` |
| Изменить world-specific prompt | `data/worlds/<name>/system_prompt.txt` |
| Выбрать world при запуске | `python main.py --world <name>` |
| Понять загрузку стартового состояния | `engine/world.py::load_world()` |
| Изменить параметры календаря | `data/rules/presets/<id>.json` |
| Проверить архитектурные решения | `docs/DECISIONS.md` |

## Известные открытые задачи

- `#ENG-003` — персистентность диалога и суммаризация истории.
- `#ENG-011` — манифест/lock-файл модов и генератор диаграмм зависимостей.
- Техдолг: `money.silver` всё ещё зашит в SQLite-схему.
