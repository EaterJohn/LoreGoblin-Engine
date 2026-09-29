from pathlib import Path

import pytest

from engine.database import Database
from engine.world import WorldEngine

ROOT = Path(__file__).resolve().parents[1]
WORLD_ROOT = ROOT / 'data' / 'worlds'


@pytest.fixture
def open_world(tmp_path):
    """Фабрика: грузит bundled world pack в свежую временную БД.

    Все открытые соединения закрываются в teardown (актуально для Windows,
    см. DECISIONS #ENG-008).
    """
    opened = []

    def _open(world_id='allizium'):
        db = Database(str(tmp_path / f'{world_id}-{len(opened)}.db'))
        opened.append(db)
        engine = WorldEngine(db)
        engine.load_world(WORLD_ROOT / world_id / 'world.json')
        return engine

    yield _open
    for db in opened:
        db.close()


@pytest.fixture
def world(open_world):
    return open_world('allizium')


@pytest.fixture
def station(open_world):
    return open_world('station_demo')


BASE_WORLD = {
    'world_time': 'Day 1 08:00',
    'start_location_id': 'hub',
    'player': {
        'id': 'player',
        'name': 'Tester',
        'location_id': 'hub',
        'stats': {'A': 10, 'B': 10},
        'starting_money': 100,
    },
    'entities': [
        {'id': 'hub', 'type': 'location', 'name': 'Hub', 'location_id': None, 'data': {}},
        {
            'id': 'shopkeeper', 'type': 'npc', 'name': 'Shopkeeper',
            'location_id': 'hub', 'data': {'role': 'trader', 'allow_to': ['trade']},
        },
        {
            'id': 'potion', 'type': 'item', 'name': 'Potion',
            'location_id': 'hub', 'data': {'price': 5},
        },
    ],
}


@pytest.fixture
def make_pack(tmp_path):
    """Собирает минимальный world pack в tmp_path и возвращает путь к world.json.

    Структура повторяет реальную (data/worlds/<id>/world.json +
    data/rules/presets/<id>.json), потому что загрузчик ищет пресеты
    относительно world.json. Тесты загрузчика не зависят от лора bundled-миров.
    """
    import copy
    import json

    def _make(hours_per_day=30, **overrides):
        data = tmp_path / 'data'
        (data / 'rules' / 'presets').mkdir(parents=True, exist_ok=True)
        (data / 'worlds' / 'test_world').mkdir(parents=True, exist_ok=True)
        preset = {
            'id': 'custom',
            'version': 1,
            'time': {
                'minutes_per_hour': 60,
                'hours_per_day': hours_per_day,
                'days_per_month': 30,
                'months_per_year': 12,
            },
        }
        (data / 'rules' / 'presets' / 'custom.json').write_text(
            json.dumps(preset), encoding='utf-8'
        )
        world = copy.deepcopy(BASE_WORLD)
        world['rules_preset'] = 'custom'
        world.update(overrides)
        path = data / 'worlds' / 'test_world' / 'world.json'
        path.write_text(json.dumps(world, ensure_ascii=False), encoding='utf-8')
        return path

    return _make


@pytest.fixture
def fail_on(monkeypatch):
    """Заставляет engine.db.execute падать на SQL, содержащем fragment.

    Так проверяем, что мутации не оставляют полузаписанное состояние.
    """

    def _install(engine, fragment):
        original = engine.db.execute

        def wrapper(sql, params=()):
            if fragment in sql:
                raise RuntimeError(f'injected failure on: {fragment}')
            return original(sql, params)

        monkeypatch.setattr(engine.db, 'execute', wrapper)
        return monkeypatch.undo  # вызвать, чтобы снять инъекцию

    return _install
