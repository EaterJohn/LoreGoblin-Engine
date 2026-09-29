from .world import WorldEngine


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
                choice = args['choice']
                if not isinstance(choice, int) or choice < 1:
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
            if choice is not None and not isinstance(choice, int):
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
            if 'location_id' not in args:
                return {'ok': False, 'error': 'LOCATION_ID_REQUIRED'}
            return self.world.get_location_contents(args['location_id'])
        if name == 'get_entity':
            if 'entity_id' not in args:
                return {'ok': False, 'error': 'ENTITY_ID_REQUIRED'}
            return self.world.get_entity(args['entity_id'])
        if name == 'search_entities':
            if 'query' not in args:
                return {'ok': False, 'error': 'QUERY_REQUIRED'}
            return self.world.search_entities(
                args['query'], args.get('type'), args.get('location_id')
            )
        if name == 'get_inventory':
            return self.world.inventory(args.get('owner_id', 'player'))
        if name == 'upgrade_stat':
            if 'player_id' not in args or 'stat' not in args:
                return {'ok': False, 'error': 'PLAYER_ID_AND_STAT_REQUIRED'}
            return self.world.upgrade_stat(args['player_id'], args['stat'])
        if name == 'advance_time':
            if 'minutes' not in args:
                return {'ok': False, 'error': 'MINUTES_REQUIRED'}
            return self.world.advance_time(int(args['minutes']))
        return {'ok': False, 'error': 'UNKNOWN_TOOL'}
