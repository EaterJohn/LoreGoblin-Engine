# LoreGoblin-Engine

Feed it world,
Let it live

Детерминированная модульная основа для симуляций, которые строит и запускает ИИ.

Ядро проверяет и фиксирует, модули считают, LLM предлагает и объясняет. Мир
собирается из примитивов, контрактов и ограничений, а не вшивается в движок.
Первый эталонный мир: long-form текстовая RPG ALLIZIUM с локальной LLM в роли
NPC-мозга и рассказчика, рассчитанная на тысячи ходов без дрейфа канона.

> Статус: ранний вертикальный срез (RPG). Модульная основа это принятое
> направление (#ENG-024), а не готовая реализация. Что реально работает:
> [docs/STATUS.md](docs/STATUS.md). Правила, которые нельзя нарушать:
> [docs/GOLDEN_RULES.md](docs/GOLDEN_RULES.md).

## Главная идея

**Engine знает, что существует. LLM решает, что делать и как это описать.**
Источник истины это SQLite. LLM меняет мир только через tool calls, которые
проверяет движок, а слова игрока не становятся фактом, пока их не подтвердил
канон (`PLAYER CLAIM ≠ CANON`).

```text
Игрок  →  LLM (llm/)  →  tool calls  →  Engine (engine/)  →  SQLite (world.db)
```

## Требования

- Python 3.14+
- [Ollama](https://ollama.com)
- Модель Gemma 4 e4b (сейчас `gemma4:e4b`)

## Запуск

```bash
ollama pull gemma4:e4b
python main.py                      # мир по умолчанию (allizium)
python main.py --world station_demo # другой мир из data/worlds/
```

Служебные команды в диалоге: `/state`, `/inventory`, `/tools`.

## Тесты

```bash
pip install -e ".[dev]"
pytest
```

## Структура репозитория

```text
engine/   ядро: база, механика мира, ActionAPI (мир-независимое)
llm/      клиент к Ollama
data/     миры (data/worlds/<имя>/) и пресеты механик (data/rules/)
tests/    тесты на pytest
docs/     документация
main.py   диалог и tool-calling loop
```

Подробная карта файлов: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md).

## Свой мир

Мир это папка `data/worlds/<имя>/` с `world.json` и (по желанию)
`system_prompt.txt`. Код движка трогать не нужно. Формат и ограничения:
[docs/MODDING.md](docs/MODDING.md).

## Документация

Начни с [docs/README.md](docs/README.md): карта, статусы, «задача → какие файлы читать».

| Что нужно | Файл |
|---|---|
| что работает и что открыто | [docs/STATUS.md](docs/STATUS.md) |
| как устроено | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| что решено и почему | [docs/DECISIONS.md](docs/DECISIONS.md) |
| как собрать мир или мод | [docs/MODDING.md](docs/MODDING.md) |
| термины | [docs/GLOSSARY.md](docs/GLOSSARY.md) |
| правила, которые нельзя нарушать | [docs/GOLDEN_RULES.md](docs/GOLDEN_RULES.md) |
| идеи и видение | [docs/ideas/](docs/ideas/IDEAS_INDEX.md), [docs/vision/](docs/vision/VISION_INDEX.md) |

Если работаешь с ИИ-ассистентом: [AGENTS.md](AGENTS.md) читается первым,
затем [docs/AI_CONTEXT.md](docs/AI_CONTEXT.md). Документация написана по-русски.
