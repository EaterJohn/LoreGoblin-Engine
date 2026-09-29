from engine.actions import ActionAPI

from conftest import WORLD_ROOT


def test_nonexistent_item(world):
    r = world.buy_item('player', 'legendary_sword', 'boris')
    assert r['error'] == 'ITEM_NOT_FOUND'
    assert world.inventory()['items'] == []


def test_existing_purchase(world):
    r = world.buy_item('player', 'iron_dagger', 'boris')
    assert r['ok']
    assert world.inventory()['money'] == 88
    assert world.inventory()['items'][0]['item_id'] == 'iron_dagger'


def test_stat_upgrade(world):
    r = world.upgrade_stat('player', 'STR')
    assert r['ok']
    assert world.get_entity('player')['data']['stats']['STR'] == 11


def test_seller_stock_matches_buy_item(world):
    r = world.get_seller_stock('boris')
    assert r['ok']
    ids = {i['item_id'] for i in r['items']}
    assert ids == {'iron_dagger', 'beer_mug'}
    for i in r['items']:
        buy = world.buy_item('player', i['item_id'], 'boris')
        assert buy['ok'], f"{i['item_id']} listed by get_seller_stock but buy_item failed: {buy}"


def test_seller_stock_unknown_seller(world):
    r = world.get_seller_stock('nobody')
    assert r == {'ok': False, 'error': 'SELLER_NOT_FOUND'}


def test_allow_to_is_reusable_capability(world):
    assert world.allow_to('boris', 'trade')
    assert not world.allow_to('boris', 'repair')
    assert world.find_allowed_entities('trade', 'tavern_red_flask')[0]['id'] == 'boris'


def test_contextual_trade_tools(world):
    api = ActionAPI(world)
    world_names = {t['function']['name'] for t in api.tools('tavern_red_flask')}
    assert 'start_trade' in world_names
    assert 'buy_item' not in world_names
    result = api.call('start_trade', {})
    assert result['ok']
    assert result['interaction'] == 'trade'
    trade_names = {t['function']['name'] for t in api.tools('tavern_red_flask')}
    assert trade_names == {'get', 'buy', 'end'}
    stock = api.call('get', {})
    assert stock['ok']
    assert {i['name'] for i in stock['items']} == {'Кружка пива', 'Железный кинжал'}
    dagger_choice = next(
        i for i, item in enumerate(stock['items'], 1)
        if item['name'] == 'Железный кинжал'
    )
    bought = api.call('buy', {'choice': dagger_choice})
    assert bought['ok']
    assert world.inventory()['items'][0]['item_id'] == 'iron_dagger'

    # A repeated buy with the same old choice must not silently buy another item.
    repeated = api.call('buy', {'choice': dagger_choice})
    assert not repeated['ok']
    assert repeated['error'] == 'ITEM_NO_LONGER_AVAILABLE'
    ended = api.call('end', {})
    assert ended['ok']


def test_tools_filtered_by_location(world):
    api = ActionAPI(world)
    names_at_tavern = {t['function']['name'] for t in api.tools('tavern_red_flask')}
    assert 'start_trade' in names_at_tavern
    names_empty_location = {t['function']['name'] for t in api.tools('ashport')}
    assert 'start_trade' not in names_empty_location
    names_default = {t['function']['name'] for t in api.tools()}
    assert 'start_trade' in names_default


def test_load_world_is_world_agnostic(station):
    assert station.world_state()['location_id'] == 'station_hub'
    player = station.get_entity('player')
    assert player['name'] == 'Mara'
    assert player['data']['stats'] == {
        'TECH': 10,
        'REFLEX': 10,
        'WILL': 10,
        'SCIENCE': 10,
    }
    assert station.get_entity('quartermaster_lee')['name'] == 'Ли'
    assert station.get_entity('boris') is None
    stock = station.get_seller_stock('quartermaster_lee')
    assert {item['item_id'] for item in stock['items']} == {'power_cell', 'med_kit'}
    assert station.inventory()['money'] == 100


def test_advance_time_same_day(station):
    r = station.advance_time(30)
    assert r['ok']
    assert r['world_time'] == 'Day 1 08:30'


def test_advance_time_crosses_midnight(station):
    station.advance_time(16 * 60 + 30)
    assert station.world_state()['world_time'] == 'Day 2 00:30'


def test_advance_time_uses_rules_preset(station):
    station.rules['time']['hours_per_day'] = 30
    r = station.advance_time(22 * 60 + 30)
    assert r['ok']
    assert r['world_time'] == 'Day 2 00:30'


def test_load_world_does_not_overwrite_existing_state(station):
    station.advance_time(30)
    station.load_world(WORLD_ROOT / 'allizium' / 'world.json')
    assert station.world_state()['world_time'] == 'Day 1 08:30'
    assert station.get_entity('boris') is None
