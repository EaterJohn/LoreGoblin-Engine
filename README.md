# LoreGoblin-Engine
Feed it world,
Let it live

Local-first engine for persistent LLM-driven worlds.

## Requirements

- Python 3.12+ (проект разрабатывается на 3.14)
- Ollama
- Gemma 4 e4b

## Run

Выбери world pack из `data/worlds/`:

```powershell
python main.py --world allizium
python main.py --world station_demo
```

Если `--world` не указан, запускается `allizium`.

Каждый world pack содержит `world.json` со стартовым состоянием и
необязательный `system_prompt.txt` с контекстом конкретного сеттинга.
SQLite runtime state хранится рядом как `world.db` и не коммитится.

## Tests

```powershell
pip install -e ".[dev]"
pytest
```
