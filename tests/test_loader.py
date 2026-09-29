import pytest

from engine.database import Database
from engine.world import WorldEngine


def count(engine, table):
    return engine.db.query(f'SELECT COUNT(*) AS n FROM {table}')[0]['n']


def test_load_world_reports_whether_it_created_state(tmp_path, make_pack):
    path = make_pack()
    db = Database(str(tmp_path / 'w.db'))
    try:
        engine = WorldEngine(db)
        assert engine.load_world(path) is True
        assert engine.load_world(path) is False
    finally:
        db.close()


def test_rules_preset_applies_on_first_load(tmp_path, make_pack):
    db = Database(str(tmp_path / 'w.db'))
    try:
        engine = WorldEngine(db)
        engine.load_world(make_pack(hours_per_day=30))
        assert engine.rules['time']['hours_per_day'] == 30
    finally:
        db.close()


def test_rules_preset_survives_restart(tmp_path, make_pack):
    """Регрессия: при существующей БД load_world выходил до загрузки пресета,
    и сохранённый мир после перезапуска жил по дефолтным правилам."""
    path = make_pack(hours_per_day=30)
    db_path = str(tmp_path / 'w.db')

    first = Database(db_path)
    WorldEngine(first).load_world(path)
    first.close()

    second = Database(db_path)
    try:
        engine = WorldEngine(second)
        assert engine.load_world(path) is False
        assert engine.rules['time']['hours_per_day'] == 30
        # 08:00 + 22h: при 30-часовых сутках это ровно полночь Day 2,
        # при дефолтных 24 часах было бы 06:00.
        engine.advance_time(22 * 60)
        assert engine.world_state()['world_time'] == 'Day 2 00:00'
    finally:
        second.close()


def test_failed_load_rolls_back_everything(tmp_path, make_pack, fail_on):
    """Регрессия: каждый execute коммитился сам, и падение посреди загрузки
    оставляло world_state + часть сущностей; повторная загрузка считала
    мир уже созданным и не догружала остальное."""
    path = make_pack()
    db = Database(str(tmp_path / 'w.db'))
    try:
        engine = WorldEngine(db)
        restore = fail_on(engine, 'INSERT INTO money')
        with pytest.raises(RuntimeError):
            engine.load_world(path)
        assert count(engine, 'world_state') == 0
        assert count(engine, 'entities') == 0
        assert count(engine, 'events') == 0

        restore()
        assert engine.load_world(path) is True
        assert count(engine, 'entities') == 4  # player + hub + shopkeeper + potion
    finally:
        db.close()


@pytest.mark.parametrize(
    'override',
    [
        {'rules_preset': '../../evil'},
        {'rules_preset': 'a/b'},
        {'rules_preset': 42},
        {'rules_preset': ''},
        {'entities': [{'id': '', 'type': 'npc', 'name': 'x'}]},
        {'entities': [{'id': 'a', 'type': 'npc', 'name': None}]},
        {'entities': [{'id': 'a', 'type': 'npc', 'name': 'x', 'data': []}]},
        {'player': {'id': 'player', 'name': 'T', 'location_id': 'hub',
                    'stats': [], 'starting_money': 1}},
        {'player': {'id': 'player', 'name': 'T', 'location_id': 'hub',
                    'stats': {'A': 1}, 'starting_money': True}},
    ],
    ids=[
        'preset-traversal', 'preset-slash', 'preset-not-str', 'preset-empty',
        'entity-empty-id', 'entity-name-none', 'entity-data-not-dict',
        'stats-not-dict', 'money-is-bool',
    ],
)
def test_invalid_world_definitions_are_rejected_before_any_write(tmp_path, make_pack, override):
    path = make_pack(**override)
    db = Database(str(tmp_path / 'w.db'))
    try:
        engine = WorldEngine(db)
        with pytest.raises(ValueError):
            engine.load_world(path)
        assert count(engine, 'world_state') == 0
        assert count(engine, 'entities') == 0
    finally:
        db.close()


def test_missing_preset_file_is_reported(tmp_path, make_pack):
    path = make_pack(rules_preset='does_not_exist')
    db = Database(str(tmp_path / 'w.db'))
    try:
        with pytest.raises(FileNotFoundError):
            WorldEngine(db).load_world(path)
    finally:
        db.close()
