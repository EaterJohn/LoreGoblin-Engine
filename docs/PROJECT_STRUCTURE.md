---
type: map
status: living
last_reviewed: 2026-10-01
related: [STATUS, README]
read_when: нужна карта файлов репозитория или «что где искать»; обновляй при любом добавлении, переносе, удалении файла
---

# PROJECT_STRUCTURE.md

Живой документ — при добавлении/удалении/переносе файла обнови эту карту
в той же сессии, где менялась структура.

## Дерево (сверка: см. `last_reviewed` в шапке)

```text
LoreGoblin-Engine/
├── main.py                  # CLI, world selection, system prompt, messages, tool-loop
├── pyproject.toml           # метаданные, dev-зависимость pytest, настройки pytest
├── README.md                # справка: что это, запуск, карта документации
├── AGENTS.md                # вход для ИИ-агентов: отсылка на docs/AI_CONTEXT.md
├── docs/
│   ├── README.md            # навигация по документации, статусы, правила
│   ├── AI_CONTEXT.md        # точка входа для ИИ
│   ├── STATUS.md            # что реализовано, техдолг, открытые задачи
│   ├── GLOSSARY.md          # термины и оси детализации
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── DECISIONS.md         # реестр + журнал решений
│   ├── MODDING.md
│   ├── DEPENDENCY_GRAPH.md
│   ├── ideas/               # идеи (не решения); IDEAS_INDEX.md, 6 файлов
│   └── vision/              # долгосрочное видение; VISION_INDEX.md
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
    ├── conftest.py          # фикстуры: world/station, make_pack, fail_on
    ├── test_engine.py       # механики на bundled-мирах (allizium, station_demo)
    ├── test_loader.py       # load_world: пресеты, валидация, откат при сбое
    ├── test_transactions.py # атомарность Database и мутаций Engine
    ├── test_actions.py      # ActionAPI: аргументы от LLM, ошибки
    └── test_main.py         # tool-loop с FakeLLM, resolve_world
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
| Узнать, что реализовано и что в долге | `docs/STATUS.md` |
| Найти значение термина | `docs/GLOSSARY.md` |
| Посмотреть идею или долгосрочное направление | `docs/ideas/IDEAS_INDEX.md`, `docs/vision/VISION_INDEX.md` |
| Запустить тесты | `pip install -e ".[dev]"` и `pytest` |

## Открытые задачи

Перенесены в `STATUS.md` (единый источник).
