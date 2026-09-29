import pytest

from engine.actions import ActionAPI


@pytest.fixture
def api(world):
    return ActionAPI(world)


@pytest.mark.parametrize('minutes', ['abc', None, True, [], {}, 1.5, ''])
def test_advance_time_rejects_garbage_without_crashing(api, world, minutes):
    before = world.world_state()['world_time']
    result = api.call('advance_time', {'minutes': minutes})
    assert result['ok'] is False
    assert world.world_state()['world_time'] == before


def test_advance_time_rejects_negative(api):
    assert api.call('advance_time', {'minutes': -5})['error'] == 'INVALID_TIME_DELTA'


@pytest.mark.parametrize('minutes', [30, '30', ' 30 ', 30.0])
def test_advance_time_accepts_numeric_lookalikes(api, minutes):
    """Слабые модели часто шлют число строкой; это не повод отказывать."""
    assert api.call('advance_time', {'minutes': minutes})['world_time'] == 'Day 1 12:30'


@pytest.mark.parametrize(
    'tool, args, error',
    [
        ('get_location_contents', {}, 'LOCATION_ID_REQUIRED'),
        ('get_location_contents', {'location_id': 5}, 'LOCATION_ID_REQUIRED'),
        ('get_location_contents', {'location_id': ''}, 'LOCATION_ID_REQUIRED'),
        ('get_entity', {}, 'ENTITY_ID_REQUIRED'),
        ('get_entity', {'entity_id': None}, 'ENTITY_ID_REQUIRED'),
        ('search_entities', {}, 'QUERY_REQUIRED'),
        ('search_entities', {'query': 7}, 'QUERY_REQUIRED'),
        ('upgrade_stat', {'stat': 'STR'}, 'PLAYER_ID_AND_STAT_REQUIRED'),
        ('upgrade_stat', {'player_id': 'player', 'stat': 3}, 'PLAYER_ID_AND_STAT_REQUIRED'),
        ('advance_time', {}, 'MINUTES_REQUIRED'),
    ],
)
def test_missing_or_mistyped_required_args_return_structured_errors(api, tool, args, error):
    result = api.call(tool, args)
    assert result == {'ok': False, 'error': error}


def test_optional_args_with_wrong_type_are_rejected(api):
    assert api.call('get_inventory', {'owner_id': 5})['error'] == 'INVALID_OWNER_ID'
    r = api.call('search_entities', {'query': 'x', 'type': 5})
    assert r['error'] == 'INVALID_ARGUMENTS'
    r = api.call('search_entities', {'query': 'x', 'location_id': ['a']})
    assert r['error'] == 'INVALID_ARGUMENTS'


def test_none_arguments_are_treated_as_no_arguments(api):
    """Ollama может прислать arguments=None для тулов без параметров."""
    assert 'world_time' in api.call('get_world_state', None)


@pytest.mark.parametrize('args', [['x'], 'text', 5])
def test_non_object_arguments_are_rejected(api, args):
    assert api.call('get_world_state', args) == {'ok': False, 'error': 'INVALID_ARGUMENTS'}


def test_get_entity_unknown_id_is_an_error_not_null(api):
    """Раньше возвращался None (JSON null), и модель должна была гадать, что это значит."""
    assert api.call('get_entity', {'entity_id': 'nope'}) == {
        'ok': False,
        'error': 'ENTITY_NOT_FOUND',
    }


def test_get_entity_known_id_is_unchanged(api):
    assert api.call('get_entity', {'entity_id': 'boris'})['name'] == 'Борис'


def test_unknown_tool(api):
    assert api.call('fly_to_moon', {}) == {'ok': False, 'error': 'UNKNOWN_TOOL'}


@pytest.mark.parametrize('choice', [True, False, 'abc', 0, -1, 1.5, [], None])
def test_buy_rejects_bad_choice(api, choice):
    api.call('start_trade', {})
    api.call('get', {})
    result = api.call('buy', {'choice': choice})
    assert result['ok'] is False


def test_buy_accepts_numeric_string_choice(api, world):
    api.call('start_trade', {})
    stock = api.call('get', {})
    dagger = next(i for i, it in enumerate(stock['items'], 1) if it['item_id'] == 'iron_dagger')
    result = api.call('buy', {'choice': str(dagger)})
    assert result['ok'] is True
    assert world.inventory()['items'][0]['item_id'] == 'iron_dagger'


@pytest.mark.parametrize('choice', [True, 'abc', 1.5, []])
def test_start_trade_rejects_bad_choice(api, choice):
    assert api.call('start_trade', {'choice': choice})['error'] == 'INVALID_TRADER_CHOICE'
    assert api.session['mode'] == 'world'


def test_unexpected_exception_becomes_a_tool_error(api, world, monkeypatch, caplog):
    """Баг в движке не должен ронять REPL: модель получает ok:false, детали в лог."""

    def boom(_entity_id):
        raise RuntimeError('kaboom')

    monkeypatch.setattr(world, 'get_entity', boom)
    with caplog.at_level('ERROR'):
        result = api.call('get_entity', {'entity_id': 'boris'})
    assert result == {'ok': False, 'error': 'INTERNAL_ERROR'}
    assert 'kaboom' in caplog.text


def test_trade_session_is_left_consistent_after_internal_error(api, world, monkeypatch):
    api.call('start_trade', {})
    monkeypatch.setattr(world, 'get_seller_stock', lambda _sid: 1 / 0)
    assert api.call('get', {})['error'] == 'INTERNAL_ERROR'
    assert api.session['mode'] == 'trade'  # состояние не сломано, торговлю можно завершить
    assert api.call('end', {})['ok'] is True
