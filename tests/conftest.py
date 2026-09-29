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
