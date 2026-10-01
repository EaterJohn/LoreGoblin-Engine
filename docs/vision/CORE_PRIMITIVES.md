---
type: vision
status: vision
last_reviewed: 2026-10-01
related: [PRINCIPLES, RESOLUTION_ON_DEMAND, ../ideas/WORLD_MODEL_IDEA]
read_when: обсуждаешь словарь ядра, свойства и компоненты объектов, как домен уточняет грубое представление
---

# Словарь примитивов ядра

Ядро должно быть независимо от LLM, подачи нарратива и 2D/3D-клиентов.

## Список

Entity, State, Property, Component, Tag, Relation, Resource, Action, Effect, Event,
Rule, Capability, Time, Randomness.

В исходных заметках списки расходились: одни добавляли Spatial representation и
Resolution/materialization, другие Time и Randomness. Здесь объединены Time и
Randomness (примитивы), а пространство и материализация считаются подсистемами,
построенными на примитивах (`SPATIAL_AND_CHUNKS.md`, `RESOLUTION_ON_DEMAND.md`).
Аффордансы в список не входят: это идея (`../ideas/AFFORDANCES_AND_PERSISTENCE_IDEA.md`).

## Идея в одной формуле

```text
properties + constraints + generators + rules  →  instance
```

Не задавать каждый итоговый объект заранее: большое комбинаторное пространство
свойств, ограничений и правил, из которого получаются экземпляры. Пространство
огромно, но его не вычисляют целиком (`RESOLUTION_ON_DEMAND.md`).

## Сущность, компоненты, теги, связи

- **Entity**: идентифицируемая вещь (человек, стул, меч, здание, река, регион,
  вещество, организация). Не обязана иметь максимум деталей сразу.
- **Component / Property**: данные, которые сущность получает без смены идентичности.
- **Tag**: семантическая сокращёнка (`wooden`, `flammable`, `seatable`), не
  обязательно источник истины. Где можно, широкие теги выводятся из точного состояния.
- **Relation**: `owns`, `contains`, `supports`, `attached_to`, `knows`, `hates`,
  `belongs_to`, `located_in`, `connected_to`.
- **Action**: `актёр + действие + цель/контекст → правила → исход/события`.
- **Event**: `EntityMoved`, `ItemConsumed`, `DamageApplied`, `RelationshipChanged`
  и т.д.; основа причинности, истории, памяти, слухов, отладки и воспроизведения.

## Пример: стул, от грубого к детальному

```text
грубо:        materials {wood 0.45, metal 0.30, cotton 0.25}, mass 8 кг, tags {furniture, seatable}
по запросу:   leg_1 metal, leg_2 metal, leg_3 wood, leg_4 metal, seat wood+foam+cotton, back metal+cotton
дальше:       структура → геометрия → производственная геометрия (если стала нужна)
```

Для обычного нарратива хватает грубого. Детальное раскрытие идёт, когда игрок или
система спрашивает («какая нога деревянная?»); механика в `RESOLUTION_ON_DEMAND.md`.

## Производные свойства

Свойство может подразумевать другие: `material = steel → metal, conductive, dense,
rigid, magnetic (зависит от сплава), поведение при коррозии`. Точный вывод
принадлежит соответствующему домену.

## Пример: яд

Ядро: `object { tags: toxic }`. Токсикология добавляет `composition, substance,
concentration, dose, exposure, metabolism, resistance, effects`. Детальный модуль
**уточняет** грубое представление и не отменяет его (см. `refines` в `MODULES_AND_LAYERS.md`).

## Что модуль может регистрировать

Схемы компонентов, типы свойств, правила, эффекты, действия, аффордансы, типы
событий, генераторы, валидаторы, стратегии материализации. Точный API сознательно
не решён.

**Ограничение сегодня:** моды не добавляют tools и механики, `provides.tools`
зарезервировано пустым (`../MODDING.md`, #ENG-011). Мод пользуется только тем, что
ядро предоставляет; всё перечисленное в этом разделе станет возможным только после
отдельного решения.
