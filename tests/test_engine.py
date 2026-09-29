import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine.database import Database
from engine.world import WorldEngine

def make():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    db = Database(f.name)
    w = WorldEngine(db)
    w.seed_demo_world()
    return f.name, w

def test_nonexistent_item():
    p, w = make()
    try:
        r = w.buy_item('player', 'legendary_sword', 'boris')
        assert r['error'] == 'ITEM_NOT_FOUND'
        assert w.inventory()['items'] == []
    finally:
        w.db.close()
        os.unlink(p)

def test_existing_purchase():
    p, w = make()
    try:
        r = w.buy_item('player', 'iron_dagger', 'boris')
        assert r['ok']
        assert w.inventory()['money'] == 88
        assert w.inventory()['items'][0]['item_id'] == 'iron_dagger'
    finally:
        w.db.close()
        os.unlink(p)


def test_stat_upgrade():
    p, w = make()
    try:
        r = w.upgrade_stat('player', 'STR')
        assert r['ok']
        assert w.get_entity('player')['data']['stats']['STR'] == 11
    finally:
        w.db.close()
        os.unlink(p)

def test_seller_stock_matches_buy_item():
    # #ENG-012: get_seller_stock должен возвращать ровно то, что реально
    # покупаемо по правилам buy_item (co-location), а не пусто, как раньше
    # отдавал get_inventory для продавца.
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
        w.db.close()
        os.unlink(p)

def test_seller_stock_unknown_seller():
    p, w = make()
    try:
        r = w.get_seller_stock('nobody')
        assert r == {'ok': False, 'error': 'SELLER_NOT_FOUND'}
    finally:
        w.db.close()
        os.unlink(p)

def test_tools_filtered_by_location():
    # #ENG-013: торговые tools показываются только там, где реально есть
    # кому и что продавать; без location_id (например /tools для отладки)
    # список полный.
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
        w.db.close()
        os.unlink(p)

if __name__=='__main__':
    test_nonexistent_item(); test_existing_purchase(); test_stat_upgrade()
    test_seller_stock_matches_buy_item(); test_seller_stock_unknown_seller(); test_tools_filtered_by_location()
    print('ALL TESTS PASS')