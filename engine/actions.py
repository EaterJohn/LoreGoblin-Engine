import logging
import re

from .world import WorldEngine

log = logging.getLogger(__name__)

_INT_RE = re.compile(r'[+-]?\d+')


def _as_int(value):
    """Целое из аргумента tool call или None.

    Слабые модели часто шлют число строкой ("30") или как 30.0, это принимаем.
    bool не считается числом (True не должно превращаться в 1).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str) and _INT_RE.fullmatch(value.strip()):
        return int(value.strip())
    return None


def _text(value):
    """Непустая строка из аргумента tool call или None."""
    return value if isinstance(value, str) and value.strip() else None


class ActionAPI:
    def __init__(self, world: WorldEngine):
        self.world = world
        self.session = {
            'mode': 'world',
            'trade_seller_id': None,
            'trade_choices': {},
        }

    def tools(self, location_id=None):
        """Return only tools relevant to the current interaction context."""
        def fn(name, description, properties, required=None):
            required = required or []
            return {
                'type': 'function',
                'function': {
                    'name': name,
                    'description': description,
                    'parameters': {
                        'type': 'object',
                        'properties': properties,
                        'required': required,
                    },
                },
            }

        if self.session['mode'] == 'trade':
            return [
                fn('get', 'Show the current seller stock and prices.', {}, []),
                fn(
                    'buy',
                    'Buy one item from the current seller by its number in the latest get() result.',
                    {'choice': {'type': 'integer'}},
                    ['choice'],
                ),
                fn('end', 'End the current interaction.', {}, []),
            ]

        core = [
            fn('get_world_state', 'Get current canonical world time and player location.', {}, []),
            fn('get_location_contents', 'Get canonical entities currently at a location.', {
                'location_id': {'type': 'string'},
            }, ['location_id']),
            fn('get_entity', 'Get one canonical entity by ID.', {
                'entity_id': {'type': 'string'},
            }, ['entity_id']),
            fn('search_entities', 'Search canonical entities by name or stored description.', {
                'query': {'type': 'string'},
                'type': {'type': 'string'},
                'location_id': {'type': 'string'},
            }, ['query']),
            fn('get_inventory', 'Get an owner\'s own possessions and money.', {
                'owner_id': {'type': 'string'},
            }, []),
            fn('upgrade_stat', 'Upgrade a player stat through the engine.', {
                'player_id': {'type': 'string'},
                'stat': {'type': 'string'},
            }, ['player_id', 'stat']),
            fn('advance_time', 'Advance canonical world time.', {
                'minutes': {'type': 'integer'},
            }, ['minutes']),
        ]

        if location_id is None or self.world.location_has_shop(location_id):
            core.append(
                fn(
                    'start_trade',
                    'Start trade. If one trader is available, it starts automatically. If several are available, returns a numbered list; call start_trade with that number.',
                    {'choice': {'type': 'integer'}},
                    [],
                )
            )
        return core

    def call(self, name, args):
        """Единственная точка входа для tool calls от LLM.

        Контракт: не бросает исключений. Некорректные аргументы и любой сбой
        внутри Engine возвращаются как `{'ok': False, 'error': ...}`, чтобы
        ошибка модели или движка не роняла REPL. Изменения состояния
        атомарны (см. `Database.transaction`), поэтому после сбоя мир
        остаётся согласованным.
        """
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return {'ok': False, 'error': 'INVALID_ARGUMENTS'}
        try:
            return self._dispatch(name, args)
        except Exception:
            log.exception('Tool %r failed with arguments %r', name, args)
            return {'ok': False, 'error': 'INTERNAL_ERROR'}

    def _dispatch(self, name, args):
        if self.session['mode'] == 'trade':
            if name == 'get':
                seller_id = self.session['trade_seller_id']
                if seller_id is None:
                    return {'ok': False, 'error': 'NO_ACTIVE_TRADE'}
                stock = self.world.get_seller_stock(seller_id)
                if stock.get('ok'):
                    self.session['trade_choices'] = {
                        i: item['item_id']
                        for i, item in enumerate(stock['items'], 1)
                    }
                return stock

            if name == 'buy':
                if 'choice' not in args:
                    return {'ok': False, 'error': 'ITEM_CHOICE_REQUIRED'}
                choice = _as_int(args['choice'])
                if choice is None or choice < 1:
                    return {'ok': False, 'error': 'INVALID_ITEM_CHOICE'}
                if choice not in self.session['trade_choices']:
                    return {
                        'ok': False,
                        'error': 'STOCK_NOT_LOADED',
                        'message': 'Call get first and use a choice from its latest result.',
                    }

                seller_id = self.session['trade_seller_id']
                stock = self.world.get_seller_stock(seller_id)
                if not stock.get('ok'):
                    return stock

                item_id = self.session['trade_choices'][choice]
                item = next(
                    (item for item in stock['items'] if item['item_id'] == item_id),
                    None,
                )
                if item is None:
                    self.session['trade_choices'] = {
                        i: current['item_id']
                        for i, current in enumerate(stock['items'], 1)
                    }
                    return {
                        'ok': False,
                        'error': 'ITEM_NO_LONGER_AVAILABLE',
                        'available_items': [
                            {'choice': i, 'name': current['name']}
                            for i, current in enumerate(stock['items'], 1)
                        ],
                    }

                result = self.world.buy_item('player', item_id, seller_id)
                if result.get('ok'):
                    result['choice'] = choice
                return result

            if name == 'end':
                self.session['mode'] = 'world'
                self.session['trade_seller_id'] = None
                self.session['trade_choices'] = {}
                return {'ok': True, 'interaction': 'trade', 'status': 'ended'}

            return {'ok': False, 'error': 'TOOL_NOT_AVAILABLE_IN_TRADE'}

        if name == 'start_trade':
            choice = args.get('choice')
            if choice is not None:
                choice = _as_int(choice)
                if choice is None:
                    return {'ok': False, 'error': 'INVALID_TRADER_CHOICE'}

            location_id = self.world.world_state()['location_id']
            traders = self.world.find_allowed_entities('trade', location_id)
            if not traders:
                return {'ok': False, 'error': 'NO_AVAILABLE_TRADERS'}

            if choice is None:
                if len(traders) == 1:
                    seller_id = traders[0]['id']
                else:
                    return {
                        'ok': True,
                        'interaction': 'trade_selection',
                        'traders': [
                            {
                                'choice': i,
                                'name': npc['name'],
                                'role': npc['data'].get('role'),
                            }
                            for i, npc in enumerate(traders, 1)
                        ],
                    }
            else:
                if choice < 1 or choice > len(traders):
                    return {
                        'ok': False,
                        'error': 'INVALID_TRADER_CHOICE',
                        'traders': [
                            {'choice': i, 'name': npc['name']}
                            for i, npc in enumerate(traders, 1)
                        ],
                    }
                seller_id = traders[choice - 1]['id']

            self.session['mode'] = 'trade'
            self.session['trade_seller_id'] = seller_id
            self.session['trade_choices'] = {}
            seller = self.world.get_entity(seller_id)
            return {
                'ok': True,
                'interaction': 'trade',
                'trader': {'name': seller['name'], 'role': seller['data'].get('role')},
                'message': 'Trade interaction started. Available commands: get, buy, end.',
            }

        if name == 'get_world_state':
            return self.world.world_state()
        if name == 'get_location_contents':
            location_id = _text(args.get('location_id'))
            if location_id is None:
                return {'ok': False, 'error': 'LOCATION_ID_REQUIRED'}
            return self.world.get_location_contents(location_id)
        if name == 'get_entity':
            entity_id = _text(args.get('entity_id'))
            if entity_id is None:
                return {'ok': False, 'error': 'ENTITY_ID_REQUIRED'}
            entity = self.world.get_entity(entity_id)
            if entity is None:
                return {'ok': False, 'error': 'ENTITY_NOT_FOUND'}
            return entity
        if name == 'search_entities':
            query = _text(args.get('query'))
            if query is None:
                return {'ok': False, 'error': 'QUERY_REQUIRED'}
            type_, location_id = args.get('type'), args.get('location_id')
            for optional in (type_, location_id):
                if optional is not None and not isinstance(optional, str):
                    return {'ok': False, 'error': 'INVALID_ARGUMENTS'}
            return self.world.search_entities(query, type_, location_id)
        if name == 'get_inventory':
            owner_id = args.get('owner_id')
            if owner_id is None:
                owner_id = 'player'
            elif _text(owner_id) is None:
                return {'ok': False, 'error': 'INVALID_OWNER_ID'}
            return self.world.inventory(owner_id)
        if name == 'upgrade_stat':
            player_id, stat = _text(args.get('player_id')), _text(args.get('stat'))
            if player_id is None or stat is None:
                return {'ok': False, 'error': 'PLAYER_ID_AND_STAT_REQUIRED'}
            return self.world.upgrade_stat(player_id, stat)
        if name == 'advance_time':
            if 'minutes' not in args:
                return {'ok': False, 'error': 'MINUTES_REQUIRED'}
            minutes = _as_int(args['minutes'])
            if minutes is None:
                return {'ok': False, 'error': 'INVALID_TIME_DELTA'}
            return self.world.advance_time(minutes)
        return {'ok': False, 'error': 'UNKNOWN_TOOL'}
