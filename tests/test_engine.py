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
        
if __name__=='__main__':
    test_nonexistent_item(); test_existing_purchase(); test_stat_upgrade(); print('ALL TESTS PASS')