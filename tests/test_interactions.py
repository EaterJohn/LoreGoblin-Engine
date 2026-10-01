"""Политика взаимодействий (торговля, в будущем бой и т.д.).

Принцип: взаимодействие прерывает другие взаимодействия. Нельзя сидеть на
стуле за 100 метров от торговца и продолжать торговлю. Что именно разрешено
внутри взаимодействия, описывает данные (`MODE_POLICY`), а не if-ы в коде.
"""
import re

import pytest

from engine import actions
from engine.actions import ActionAPI

WORLD_TOOLS = {'look', 'inspect', 'find', 'inventory', 'upgrade', 'wait'}
TRADE_TOOLS = {'stock', 'buy', 'end'}
TAVERN = 'tavern_red_flask'


@pytest.fixture
def api(world):
    return ActionAPI(world)


def names(api, location=TAVERN):
    return {t['function']['name'] for t in api.tools(location)}


# ---------- поверхность тулов ----------

def test_world_surface(api):
    assert names(api) == WORLD_TOOLS | {'trade'}


def test_no_trade_where_nobody_sells(api):
    assert names(api, 'ashport') == WORLD_TOOLS


def test_trade_surface_keeps_world_tools_and_adds_trade_tools(api):
    api.call('trade', {})
    assert names(api) == WORLD_TOOLS | TRADE_TOOLS  # 'trade' скрыт: уже торгуем


def test_trade_tools_do_not_exist_outside_trade(api):
    for tool in ('stock', 'buy', 'end'):
        r = api.call(tool, {'choice': 1})
        assert r['error'] == 'TOOL_NOT_AVAILABLE'
        assert 'trade' in r['available']


def test_trade_cannot_be_started_twice(api):
    api.call('trade', {})
    r = api.call('trade', {})
    assert r['error'] == 'ALREADY_IN_INTERACTION'
    assert api.session['mode'] == 'trade'


# ---------- что прерывает торговлю ----------

@pytest.mark.parametrize('tool, args', [
    ('look', {}), ('inventory', {}), ('inspect', {'id': 'boris'}), ('find', {'query': 'Борис'}),
])
def test_reads_do_not_end_trade(api, tool, args):
    api.call('trade', {})
    r = api.call(tool, args)
    assert 'interaction_ended' not in r
    assert api.session['mode'] == 'trade'


@pytest.mark.parametrize('tool, args', [
    ('upgrade', {'stat': 'STR'}), ('wait', {'minutes': 10}),
])
def test_successful_act_ends_trade(api, tool, args):
    api.call('trade', {})
    r = api.call(tool, args)
    assert r['ok'] is True
    assert r['interaction_ended'] == 'trade'
    assert api.session['mode'] == 'world'
    assert names(api) == WORLD_TOOLS | {'trade'}
    assert api.call('stock', {})['error'] == 'TOOL_NOT_AVAILABLE'


@pytest.mark.parametrize('tool, args', [
    ('upgrade', {'stat': 'SPEED'}),   # нет такого стата
    ('upgrade', {}),                  # забыт аргумент
    ('wait', {'minutes': 'abc'}),     # мусор от модели
])
def test_failed_act_does_not_end_trade(api, tool, args):
    """Ошибочный вызов не должен тихо закрывать лавку."""
    api.call('trade', {})
    r = api.call(tool, args)
    assert r['ok'] is False
    assert 'interaction_ended' not in r
    assert api.session['mode'] == 'trade'


def test_explicit_end_still_works(api):
    api.call('trade', {})
    assert api.call('end', {}) == {'ok': True, 'interaction': 'trade', 'status': 'ended'}
    assert api.session['mode'] == 'world'


def test_live_log_scenario_leaving_the_shop_by_doing_something_else(api, world):
    """Регрессия по живому логу: торговля, покупка, прощание без end,
    затем «хочу повысить характеристики». Раньше upgrade_stat был недоступен
    (TOOL_NOT_AVAILABLE_IN_TRADE), и модель выдумала консоль с отказом."""
    api.call('trade', {})
    stock = api.call('stock', {})
    first = stock['items'][0]['choice']
    assert api.call('buy', {'choice': first})['ok'] is True
    stale = api.call('buy', {'choice': first})
    assert stale['error'] == 'ITEM_NO_LONGER_AVAILABLE'

    upgraded = api.call('upgrade', {'stat': 'STR'})
    assert upgraded['ok'] is True
    assert upgraded['interaction_ended'] == 'trade'
    assert world.get_entity('player')['data']['stats']['STR'] == 11


# ---------- политика как данные: «в бою так нельзя» ----------

def test_a_blocking_interaction_hides_and_rejects_acts(api, monkeypatch):
    monkeypatch.setitem(actions.MODE_POLICY, 'combat', {'read': 'allow', 'act': 'block'})
    api.session['mode'] = 'combat'

    assert names(api) == {'look', 'inspect', 'find', 'inventory'}

    r = api.call('upgrade', {'stat': 'STR'})
    assert r['error'] == 'BLOCKED_BY_INTERACTION'
    assert r['interaction'] == 'combat'
    assert 'look' in r['available'] and 'upgrade' not in r['available']

    assert api.call('look', {})['ok'] is True
    assert api.session['mode'] == 'combat'  # блокировка не сбрасывает режим


def test_unknown_interaction_fails_closed(api):
    """Режим без политики не должен молча разрешать действия."""
    api.session['mode'] = 'mystery'
    assert names(api) == set()
    assert api.call('upgrade', {'stat': 'STR'})['error'] == 'BLOCKED_BY_INTERACTION'


# ---------- сторожевые тесты: принципы простоты ----------

def test_registry_is_consistent(api):
    tools = api.registry
    assert len({t.name for t in tools}) == len(tools), 'имена тулов должны быть уникальны'
    for t in tools:
        assert t.kind in {'read', 'act', 'enter', 'inside'}
        assert t.description.strip()
        assert set(t.required) <= set(t.params)
        if t.kind in {'enter', 'inside'}:
            assert t.interaction in actions.MODE_POLICY, f'{t.name}: у взаимодействия нет политики'


def test_tool_names_are_short_plain_words(api):
    """Принцип проекта: имена тулов максимально простые — одно короткое слово."""
    for t in api.registry:
        assert re.fullmatch(r'[a-z]{2,10}', t.name), f'{t.name!r}: нужно одно короткое слово'


def test_tools_take_at_most_one_argument(api):
    """Принцип проекта: чем больше аргументов, тем больше точек отказа для модели."""
    for t in api.registry:
        assert len(t.params) <= 1, f'{t.name}: {sorted(t.params)}'
