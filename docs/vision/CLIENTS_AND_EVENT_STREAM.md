---
type: vision
status: vision
last_reviewed: 2026-10-01
related: [../ideas/EVENTS_AND_KNOWLEDGE_IDEA, ../GLOSSARY, ../ARCHITECTURE]
read_when: проектируешь клиентов (CLI, Web, Discord, 3D) или формат событий для разных представлений
---

# Клиенты и событийный поток

Модель канона, знаний NPC и слухов подробно в `../ideas/EVENTS_AND_KNOWLEDGE_IDEA.md`
(слои знания и соответствие терминов: `../GLOSSARY.md`). Здесь только то, чего там нет.

## Поток

```text
Action → validation → Event → effects → новое состояние
```

События питают состояние мира, память NPC, слухи, репутацию, историю, квесты, логи и
нарративный вывод.

## LLM как клиент

LLM может разбирать намерение, запрашивать допустимые действия, описывать состояние,
рассказывать события, генерировать диалоги, резюмировать историю. LLM не является
базой данных мира (#ENG-001).

## Другие клиенты

CLI, LLM-клиент нарратива, Web UI, Discord, редактор мира, 3D-фронтенд,
Godot/Unity, инструменты симуляции и отладки.

## Нарратив и симуляция: два разрешения одного мира

```text
нарратив:     Chair { tags: wooden, seatable, furniture }
симуляция:    Chair → компоненты → материалы → геометрия → пространство → физика
```

Сущность одна и остаётся канонической.

## Событийный поток, нейтральный к клиенту

Потенциальные события: `ActionAccepted`, `ActionRejected`, `StateChanged`,
`EntityMoved`, `EntityCreated`, `EntityDestroyed`, `CombatStarted`,
`RelationshipChanged`, `KnowledgeChanged`. Разные клиенты потребляют их по-разному.

Связь с идеей: `../ideas/SIMULATION_AND_DESIGN_PARKING_IDEA.md` §7 (LLM-agnostic
рендерер); формат события и `schema_version` ещё не решены (`../ideas/IDEAS_INDEX.md`,
кандидат 3).
