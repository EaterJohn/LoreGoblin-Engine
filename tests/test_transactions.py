import sqlite3

import pytest

from engine.database import Database


def rows(db, table):
    return db.query(f'SELECT * FROM {table}')


def test_transaction_commits_on_success(tmp_path):
    path = str(tmp_path / 't.db')
    db = Database(path)
    try:
        with db.transaction():
            db.execute("INSERT INTO money(owner_id, silver) VALUES('a', 1)")
            db.execute("INSERT INTO money(owner_id, silver) VALUES('b', 2)")
        other = sqlite3.connect(path)
        try:
            assert other.execute('SELECT COUNT(*) FROM money').fetchone()[0] == 2
        finally:
            other.close()
    finally:
        db.close()


def test_transaction_rolls_back_on_error(tmp_path):
    db = Database(str(tmp_path / 't.db'))
    try:
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute("INSERT INTO money(owner_id, silver) VALUES('a', 1)")
                raise RuntimeError('boom')
        assert rows(db, 'money') == []
    finally:
        db.close()


def test_nested_transaction_joins_the_outer_one(tmp_path):
    db = Database(str(tmp_path / 't.db'))
    try:
        with pytest.raises(RuntimeError):
            with db.transaction():
                with db.transaction():
                    db.execute("INSERT INTO money(owner_id, silver) VALUES('a', 1)")
                # inner блок завершился штатно, но внешний ещё не закоммитил
                raise RuntimeError('outer fails')
        assert rows(db, 'money') == []
    finally:
        db.close()


def test_execute_outside_transaction_still_commits(tmp_path):
    path = str(tmp_path / 't.db')
    db = Database(path)
    try:
        db.execute("INSERT INTO money(owner_id, silver) VALUES('a', 1)")
        other = sqlite3.connect(path)
        try:
            assert other.execute('SELECT COUNT(*) FROM money').fetchone()[0] == 1
        finally:
            other.close()
    finally:
        db.close()


def test_buy_item_is_atomic(world, fail_on):
    fail_on(world, 'UPDATE entities SET location_id=NULL')
    with pytest.raises(RuntimeError):
        world.buy_item('player', 'iron_dagger', 'boris')
    assert world.inventory() == {'money': 100, 'items': []}
    assert world.get_entity('iron_dagger')['location_id'] == 'tavern_red_flask'
    assert rows(world.db, 'events')[-1]['event_type'] == 'world_created'


def test_upgrade_stat_is_atomic(world, fail_on):
    fail_on(world, 'UPDATE money SET silver')
    with pytest.raises(RuntimeError):
        world.upgrade_stat('player', 'STR')
    assert world.get_entity('player')['data']['stats']['STR'] == 10
    assert world.inventory()['money'] == 100
    assert all(e['event_type'] != 'stat_upgrade' for e in rows(world.db, 'events'))


def test_advance_time_is_atomic(station, fail_on):
    before = station.world_state()['world_time']
    fail_on(station, 'INSERT INTO events')
    with pytest.raises(RuntimeError):
        station.advance_time(30)
    assert station.world_state()['world_time'] == before
