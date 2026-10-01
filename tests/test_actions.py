import pytest

from engine.actions import ActionAPI


@pytest.fixture
def api(world):
    return ActionAPI(world)


# ---------- look / inspect / find / inventory ----------

def test_look_shows_time_place_and_what_is_here(api):
    r = api.call('look', {})
    assert r['ok'] is True
    assert r['time'] == 'Day 1 12:00'
    assert r['location'] == 'Таверна «Красный Факел»'
    ids = {e['id'] for e in r['here']}
    assert {'boris', 'iron_dagger', 'beer_mug'} <= ids
    assert 'player' not in ids  # игрок не «находится рядом» с самим собой


def test_look_survives_a_location_without_entity(api, world):
    world.db.execute("UPDATE world_state SET location_id='void' WHERE id=1")
    r = api.call('look', {})
    assert r['ok'] is True
    assert r['location'] == 'void'
    assert r['here'] == []


def test_inspect_entity(api):
    assert api.call('inspect', {'id': 'boris'})['name'] == 'Борис'


def test_inspect_without_id_is_the_player(api):
    r = api.call('inspect', {})
    assert r['name'] == 'Иван'
    assert r['data']['stats']['STR'] == 10


def test_inspect_unknown_id(api):
    assert api.call('inspect', {'id': 'nope'}) == {'ok': False, 'error': 'ENTITY_NOT_FOUND'}


@pytest.mark.parametrize('bad', [5, '', '  ', ['boris']])
def test_inspect_rejects_mistyped_id(api, bad):
    assert api.call('inspect', {'id': bad}) == {'ok': False, 'error': 'INVALID_ARGUMENTS'}


def test_find_returns_compact_results(api):
    r = api.call('find', {'query': 'Борис'})
    assert r['ok'] is True
    assert [e['id'] for e in r['results']] == ['boris']
    assert set(r['results'][0]) == {'id', 'type', 'name'}


def test_find_without_matches_is_an_empty_list_not_an_error(api):
    assert api.call('find', {'query': 'zzzz'}) == {'ok': True, 'results': []}


@pytest.mark.parametrize('bad', [None, 7, '', ['x']])
def test_find_requires_a_text_query(api, bad):
    assert api.call('find', {'query': bad}) == {'ok': False, 'error': 'QUERY_REQUIRED'}
    assert api.call('find', {}) == {'ok': False, 'error': 'QUERY_REQUIRED'}


def test_inventory_is_always_the_players_own(api):
    assert api.call('inventory', {}) == {'money': 100, 'items': []}


def test_inventory_ignores_an_owner_the_model_may_still_try_to_pass(api):
    """Старая привычка модели: inventory(owner_id='boris'). Чужие вещи не отдаём."""
    assert api.call('inventory', {'owner_id': 'boris'}) == {'money': 100, 'items': []}


# ---------- upgrade / wait ----------

def test_upgrade_needs_only_the_stat_name(api, world):
    r = api.call('upgrade', {'stat': 'STR'})
    assert r['ok'] is True
    assert r['value'] == 11
    assert world.get_entity('player')['data']['stats']['STR'] == 11


@pytest.mark.parametrize('bad', [None, 3, '', ['STR']])
def test_upgrade_requires_a_text_stat(api, bad):
    assert api.call('upgrade', {'stat': bad}) == {'ok': False, 'error': 'STAT_REQUIRED'}
    assert api.call('upgrade', {}) == {'ok': False, 'error': 'STAT_REQUIRED'}


def test_upgrade_unknown_stat_tells_what_exists(api):
    r = api.call('upgrade', {'stat': 'SPEED'})
    assert r['error'] == 'UNKNOWN_STAT'
    assert 'STR' in r['stats']


@pytest.mark.parametrize('minutes', ['abc', None, True, [], {}, 1.5, ''])
def test_wait_rejects_garbage_without_crashing(api, world, minutes):
    before = world.world_state()['world_time']
    assert api.call('wait', {'minutes': minutes})['ok'] is False
    assert world.world_state()['world_time'] == before


def test_wait_rejects_negative_and_missing(api):
    assert api.call('wait', {'minutes': -5})['error'] == 'INVALID_TIME_DELTA'
    assert api.call('wait', {}) == {'ok': False, 'error': 'MINUTES_REQUIRED'}


@pytest.mark.parametrize('minutes', [30, '30', ' 30 ', 30.0])
def test_wait_accepts_numeric_lookalikes(api, minutes):
    """Слабые модели часто шлют число строкой; это не повод отказывать."""
    assert api.call('wait', {'minutes': minutes})['world_time'] == 'Day 1 12:30'


# ---------- общий контракт call() ----------

def test_none_arguments_are_treated_as_no_arguments(api):
    """Ollama может прислать arguments=None для тулов без параметров."""
    assert api.call('look', None)['ok'] is True


@pytest.mark.parametrize('args', [['x'], 'text', 5])
def test_non_object_arguments_are_rejected(api, args):
    assert api.call('look', args) == {'ok': False, 'error': 'INVALID_ARGUMENTS'}


def test_unknown_tool(api):
    assert api.call('fly_to_moon', {}) == {'ok': False, 'error': 'UNKNOWN_TOOL'}


@pytest.mark.parametrize('old_name', [
    'get_world_state', 'get_location_contents', 'get_entity', 'search_entities',
    'get_inventory', 'upgrade_stat', 'advance_time', 'start_trade', 'get',
])
def test_old_tool_names_are_gone(api, old_name):
    assert api.call(old_name, {}) == {'ok': False, 'error': 'UNKNOWN_TOOL'}


def test_unexpected_exception_becomes_a_tool_error(api, world, monkeypatch, caplog):
    """Баг в движке не должен ронять REPL: модель получает ok:false, детали в лог."""

    def boom(_entity_id):
        raise RuntimeError('kaboom')

    monkeypatch.setattr(world, 'get_entity', boom)
    with caplog.at_level('ERROR'):
        result = api.call('inspect', {'id': 'boris'})
    assert result == {'ok': False, 'error': 'INTERNAL_ERROR'}
    assert 'kaboom' in caplog.text


# ---------- торговля: валидация и форма ответов ----------

def test_stock_numbers_every_item_and_hides_internal_ids(api):
    api.call('trade', {})
    r = api.call('stock', {})
    assert r['ok'] is True
    assert [i['choice'] for i in r['items']] == [1, 2]
    assert all(set(i) == {'choice', 'name', 'price'} for i in r['items'])


@pytest.mark.parametrize('choice', [True, False, 'abc', 0, -1, 1.5, [], None])
def test_buy_rejects_bad_choice(api, choice):
    api.call('trade', {})
    api.call('stock', {})
    assert api.call('buy', {'choice': choice})['ok'] is False


def test_buy_accepts_numeric_string_choice(api, world):
    api.call('trade', {})
    stock = api.call('stock', {})
    dagger = next(i['choice'] for i in stock['items'] if i['name'] == 'Железный кинжал')
    assert api.call('buy', {'choice': str(dagger)})['ok'] is True
    assert world.inventory()['items'][0]['item_id'] == 'iron_dagger'


@pytest.mark.parametrize('choice', [True, 'abc', 1.5, []])
def test_trade_rejects_bad_choice(api, choice):
    assert api.call('trade', {'choice': choice})['error'] == 'INVALID_TRADER_CHOICE'
    assert api.session['mode'] == 'world'


def test_trade_session_is_left_consistent_after_internal_error(api, world, monkeypatch):
    api.call('trade', {})
    monkeypatch.setattr(world, 'get_seller_stock', lambda _sid: 1 / 0)
    assert api.call('stock', {})['error'] == 'INTERNAL_ERROR'
    assert api.session['mode'] == 'trade'  # состояние не сломано, торговлю можно завершить
    assert api.call('end', {})['ok'] is True
