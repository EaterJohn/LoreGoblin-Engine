---
type: index
status: living
last_reviewed: 2026-10-01
related: [AI_CONTEXT, STATUS, GLOSSARY, DECISIONS, GOLDEN_RULES, INDEX]
read_when: ищешь нужный документ, не знаешь, с чего начать, или добавляешь новый файл в docs/
---

# docs/ — карта документации

Единственная точка навигации. Ты ИИ: начни с `../AGENTS.md` или `AI_CONTEXT.md`,
затем `GOLDEN_RULES.md` и `STATUS.md`, затем **один пакет** из таблицы ниже.
Полный список документов с условиями чтения генерируется в `INDEX.md`.

## Из чего состоит

| Слой | Файлы | О чём |
|---|---|---|
| **Вход** | `AI_CONTEXT.md`, `GOLDEN_RULES.md`, `STATUS.md`, `GLOSSARY.md` | что это, правила, что работает, термины |
| **Текущее (код)** | `ARCHITECTURE.md`, `PROJECT_STRUCTURE.md`, `MODDING.md`, `DEPENDENCY_GRAPH.md` | как устроено сейчас; в `MODDING` и `DEPENDENCY_GRAPH` есть спроектированные, но не реализованные части (помечены) |
| **Решения** | `DECISIONS.md` | реестр + журнал `#ENG-0XX`: что решено и почему |
| **Идеи** | `ideas/` (вход: `IDEAS_INDEX.md`) | предложения RPG-эталона, прошедшие обсуждение, но не принятые |
| **Видение** | `vision/` (вход: `VISION_INDEX.md`) | стратегия и модульная основа, ориентир без обязательств |

Жизненный цикл: `vision / идея → обсуждение → запись в DECISIONS.md → код → STATUS.md`.
Архитектурное изменение сначала запись в `DECISIONS.md`, потом код.

## Задача → пакет файлов

Читай **только** пакет своей задачи. Если не хватает, `INDEX.md` подскажет, какой
документ нужен по условию `read_when`.

| Задача | Пакет |
|---|---|
| Начало любой сессии | `AI_CONTEXT.md`, `GOLDEN_RULES.md`, `STATUS.md` |
| Правка кода `engine/`, `llm/`, `main.py` | `ARCHITECTURE.md`, `PROJECT_STRUCTURE.md`, нужные записи `DECISIONS.md` |
| Новый tool для LLM | `ARCHITECTURE.md` (ActionAPI), #ENG-013, #ENG-019, #ENG-022 |
| Моду или модулю «не хватает ядра» | `GOLDEN_RULES.md` (правило 7), `vision/KERNEL_AND_SUBSYSTEMS.md` |
| Новый модуль (код) | `GOLDEN_RULES.md`, `vision/MODULE_CONTRACT.md`, `vision/TRUST_AND_ROLLBACK.md`, `vision/CONSTRAINTS.md` |
| Собрать свой мир / мод (данные) | `MODDING.md`, образец `data/worlds/allizium/` |
| Менеджер модов, зависимости, манифест | `MODDING.md`, `vision/MODULES_AND_LAYERS.md`, `vision/MODULE_CONTRACT.md`, #ENG-011 |
| Ограничения, валидация, формат отказа | `vision/CONSTRAINTS.md` |
| Откат, детерминизм, воспроизведение | `vision/TRUST_AND_ROLLBACK.md`, `vision/RELIABILITY_AND_PERFORMANCE.md` |
| Зачем проект, стратегия, вехи, аналоги | `vision/STRATEGY.md`, при необходимости `vision/PRECEDENTS.md` |
| Память диалога, суммаризация | #ENG-003, `ideas/EVENTS_AND_KNOWLEDGE_IDEA.md` |
| Разбор ввода игрока, автомат состояний | `ideas/INTENT_PARSER_IDEA.md` |
| Поведение и решения NPC | `ideas/NPC_MECHANICS_IDEA.md`, `vision/AGENTS_AND_COGNITION.md` |
| Свойства объектов, материалы, воздействия | `ideas/WORLD_MODEL_IDEA.md`, `vision/CORE_PRIMITIVES.md` |
| Генерация мира, чанки, пространство | `vision/GENERATION_AND_MATERIALIZATION.md`, `vision/SPATIAL_AND_CHUNKS.md` |
| Документация | этот файл, `GLOSSARY.md` |
| Непонятный термин | `GLOSSARY.md` |
| Что открыто, что в долге | `STATUS.md` |

**Стоп-условия.** Ты знаешь, какой файл править, и правило, которое применяется:
хватит читать, приступай. Находишь противоречие между документами: прав код,
затем `DECISIONS.md`; зафиксируй расхождение в `STATUS.md`, а не додумывай.

## Один факт — одно место

| Факт | Единственный источник |
|---|---|
| что работает, закрыто, открыто, техдолг | `STATUS.md` |
| что и почему решено | `DECISIONS.md` (реестр сверху) |
| правила, которые нельзя нарушать | `GOLDEN_RULES.md` |
| дерево файлов кода | `PROJECT_STRUCTURE.md` |
| список документов и условия чтения | `INDEX.md` (генерируется) |
| определение термина | `GLOSSARY.md` |
| формат world pack, правила для модов | `MODDING.md` |
| формат модуля и паспорта | `vision/MODULE_CONTRACT.md` |
| принципы и слои кода | `ARCHITECTURE.md` |

Нашёл факт в двух местах: оставь один и поставь ссылку на него.

## Соглашения

**Шапка (frontmatter) у каждого файла:**

```yaml
---
type: entry | status | reference | map | spec | log | index | idea | vision
status: см. таблицу ниже
last_reviewed: ГГГГ-ММ-ДД      # когда последний раз сверяли с реальностью
related: [ENG-011, MODDING]     # номера решений и файлы
read_when: одна фраза, когда этот файл нужен
---
```

Шапку читает `tools/docs_index.py` и строит из неё `INDEX.md`. Без шапки или с
неизвестным статусом `--check` падает.

**Статусы:**

| Статус | Значение |
|---|---|
| `implemented` | описывает то, что есть в коде |
| `partial` | часть описана и реализована, часть только спроектирована (разделы помечены) |
| `living` | живой документ (карта, реестр), обновляется вместе с кодом |
| `accepted` | решено, ещё не реализовано |
| `proposed` | кандидат в решение, ждёт подтверждения |
| `idea` | идея, не решение |
| `vision` | долгосрочный ориентир |
| `in-progress` | в работе |
| `rejected` / `superseded` | отклонено / отменено другой записью (запись остаётся) |

**Прочее:** проза по-русски, машинные метки (ключи, статусы, ID, имена файлов,
названия терминов) по-английски. Даты ISO. Один файл = одна идея, ориентир до
~300 строк. Утверждение «реализовано» требует ссылки на код или тест. Диаграммы не
хранятся как факт (`DEPENDENCY_GRAPH.md`).

## Когда что обновлять

| Событие | Обнови |
|---|---|
| принято архитектурное решение | запись и строку реестра в `DECISIONS.md`, `STATUS.md` |
| реализована или закрыта задача | `STATUS.md`, статус в реестре `DECISIONS.md` |
| добавлен, перенесён или удалён файл | `PROJECT_STRUCTURE.md`, затем `python tools/docs_index.py` |
| идея выросла в решение | запись в `DECISIONS.md`, статус идеи, `IDEAS_INDEX.md` |
| правишь файл | `last_reviewed` в его шапке |
