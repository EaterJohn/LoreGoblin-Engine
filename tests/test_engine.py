import os, tempfile, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.database import Database
from engine.world import WorldEngine


WORLD_ROOT = Path(__file__).resolve().parents[1] / 'data' / 'worlds'


def make():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    db = Database(f.name)
    w = WorldEngine(db)
    w.seed_demo_world()
    return f.name, w


def make_world(world_id):
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    db = Database(f.name)
    w = WorldEngine(db)
    w.load_world(WORLD_ROOT / world_id / 'world.json')
    return f.name, w


def cleanup(path, world):
    world.db.close()
    os.unlink(path)


def test_nonexistent_item():
    p, w = make()
    try:
        r = w.buy_item('player', 'legendary_sword', 'boris')
        assert r['error'] == 'ITEM_NOT_FOUND'
        assert w.inventory()['items'] == []
    finally:
        cleanup(p, w)


def test_existing_purchase():
    p, w = make()
    try:
        r = w.buy_item('player', 'iron_dagger', 'boris')
        assert r['ok']
        assert w.inventory()['money'] == 88
        assert w.inventory()['items'][0]['item_id'] == 'iron_dagger'
    finally:
        cleanup(p, w)


def test_stat_upgrade():
    p, w = make()
    try:
        r = w.upgrade_stat('player', 'STR')
        assert r['ok']
        assert w.get_entity('player')['data']['stats']['STR'] == 11
    finally:
        cleanup(p, w)


def test_seller_stock_matches_buy_item():
    p, w = make()
    try:
        r = w.get_seller_stock('boris')
        assert r['ok']
        ids = {i['item_id'] for i in r['items']}
        assert ids == {'iron_dagger', 'beer_mug'}
        for i in r['items']:
            buy = w.buy_item('player', i['item_id'], 'boris')
            assert buy['ok'], f"{i['item_id']} listed by get_seller_stock but buy_item failed: {buy}"
    finally:
        cleanup(p, w)


def test_seller_stock_unknown_seller():
    p, w = make()
    try:
        r = w.get_seller_stock('nobody')
        assert r == {'ok': False, 'error': 'SELLER_NOT_FOUND'}
    finally:
        cleanup(p, w)


def test_tools_filtered_by_location():
    p, w = make()
    try:
        from engine.actions import ActionAPI
        api = ActionAPI(w)
        names_at_tavern = {t['function']['name'] for t in api.tools('tavern_red_flask')}
        assert {'get_seller_stock', 'buy_item'} <= names_at_tavern
        names_empty_location = {t['function']['name'] for t in api.tools('ashport')}
        assert 'buy_item' not in names_empty_location
        assert 'get_seller_stock' not in names_empty_location
        names_default = {t['function']['name'] for t in api.tools()}
        assert 'buy_item' in names_default
    finally:
        cleanup(p, w)


def test_load_world_is_world_agnostic():
    p, w = make_world('station_demo')
    try:
        assert w.world_state()['location_id'] == 'station_hub'
        player = w.get_entity('player')
        assert player['name'] == 'Mara'
        assert player['data']['stats'] == {
            'TECH': 10,
            'REFLEX': 10,
            'WILL': 10,
            'SCIENCE': 10,
        }
        assert w.get_entity('quartermaster_lee')['name'] == 'Ли'
        assert w.get_entity('boris') is None
        stock = w.get_seller_stock('quartermaster_lee')
        assert {item['item_id'] for item in stock['items']} == {'power_cell', 'med_kit'}
        assert w.inventory()['money'] == 100
    finally:
        cleanup(p, w)


def test_load_world_does_not_overwrite_existing_state():
    p, w = make_world('station_demo')
    try:
        w.advance_time(30)
        w.load_world(WORLD_ROOT / 'allizium' / 'world.json')
        assert w.world_state()['world_time'] == 'Day 1 08:30'
        assert w.get_entity('boris') is None
    finally:
        cleanup(p, w)


if __name__ == '__main__':
    test_nonexistent_item()
    test_existing_purchase()
    test_stat_upgrade()
    test_seller_stock_matches_buy_item()
    test_seller_stock_unknown_seller()
    test_tools_filtered_by_location()
    test_load_world_is_world_agnostic()
    test_load_world_does_not_overwrite_existing_state()
    print('ALL TESTS PASS')
