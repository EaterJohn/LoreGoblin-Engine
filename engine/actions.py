"""Tool surface для LLM: реестр тулов и политика взаимодействий.

Принципы (DECISIONS #ENG-027, #ENG-028):

* Имя тула: одно короткое слово. Аргументов не больше одного. Внутренние id
  (свой персонаж, продавец) модель не передаёт: движок знает их сам.
* Взаимодействие (торговля, в будущем бой) прерывает другие взаимодействия.
  Что разрешено внутри него, описывает `MODE_POLICY`, а не `if` в коде.
* `call()` не бросает исключений (#ENG-022).
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from .world import WorldEngine

log = logging.getLogger(__name__)

# Политика взаимодействий: что делать с обычными тулами, пока идёт взаимодействие.
#   read  — тулы, которые только смотрят (look, inspect, find, inventory);
#   act   — тулы, которые меняют мир (upgrade, wait).
# Значения:
#   'allow' — разрешено, взаимодействие продолжается;
#   'end'   — разрешено, но успешный вызов завершает взаимодействие
#             («занялся другим» значит «ушёл от торговца»);
#   'block' — запрещено: тул скрыт из списка, вызов даёт BLOCKED_BY_INTERACTION.
# Режим без записи в таблице закрыт целиком (fail closed). В режиме 'world'
# разрешено всё. Пример на будущее: 'combat': {'read': 'allow', 'act': 'block'}.
MODE_POLICY = {
    'trade': {'read': 'allow', 'act': 'end'},
}

KINDS = ('read', 'act', 'enter', 'inside')

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


def _error(code, **extra):
    return {'ok': False, 'error': code, **extra}


@dataclass(frozen=True, eq=False)
class Tool:
    """Один тул: схема для LLM, вид, обработчик.

    kind:
      read   — смотрит, состояние мира не меняет;
      act    — меняет мир;
      enter  — начинает взаимодействие `interaction` (доступно только в мире);
      inside — существует только внутри взаимодействия `interaction`.
    """

    name: str
    kind: str
    description: str
    handler: Callable
    params: dict = field(default_factory=dict)
    required: tuple = ()
    interaction: Optional[str] = None
    available: Optional[Callable] = None  # (location_id) -> bool, для kind='enter'

    def schema(self):
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': {
                    'type': 'object',
                    'properties': self.params,
                    'required': list(self.required),
                },
            },
        }


class ActionAPI:
    def __init__(self, world: WorldEngine):
        self.world = world
        self.session = {
            'mode': 'world',
            'trade_seller_id': None,
            'trade_choices': {},
        }
        text, number = {'type': 'string'}, {'type': 'integer'}
        self.registry = (
            Tool('look', 'read',
                 'Look around: the current time, the place, and who or what is here.',
                 self._look),
            Tool('inspect', 'read',
                 'Examine one thing or person by its id from look(). '
                 'Without an id: yourself, including your stats.',
                 self._inspect, {'id': text}),
            Tool('find', 'read',
                 'Find things or people anywhere in the world by name.',
                 self._find, {'query': text}, ('query',)),
            Tool('inventory', 'read',
                 'What you carry and how much money you have. '
                 "This is not a merchant's goods.",
                 self._inventory),
            Tool('upgrade', 'act',
                 'Raise one of your stats by 1 for silver. Pass the stat name.',
                 self._upgrade, {'stat': text}, ('stat',)),
            Tool('wait', 'act',
                 'Let time pass.',
                 self._wait, {'minutes': number}, ('minutes',)),
            Tool('trade', 'enter',
                 'Start trading with a merchant here. If several merchants are here, '
                 'the result is a numbered list: call trade again with that number.',
                 self._trade, {'choice': number}, interaction='trade',
                 available=self._shop_here),
            Tool('stock', 'inside',
                 'Show what the merchant sells: numbered goods with prices.',
                 self._stock, interaction='trade'),
            Tool('buy', 'inside',
                 'Buy one item by its number from the latest stock().',
                 self._buy, {'choice': number}, ('choice',), interaction='trade'),
            Tool('end', 'inside',
                 'Stop trading.',
                 self._end, interaction='trade'),
        )
        self._by_name = {t.name: t for t in self.registry}

    # ---------- какие тулы видит модель ----------

    @staticmethod
    def _policy(mode, kind):
        if mode == 'world':
            return 'allow'
        return MODE_POLICY.get(mode, {}).get(kind, 'block')

    def _visible(self, tool, mode, location_id):
        if tool.kind == 'enter':
            return mode == 'world' and (
                tool.available is None or tool.available(location_id)
            )
        if tool.kind == 'inside':
            return mode == tool.interaction
        return self._policy(mode, tool.kind) != 'block'

    def tools(self, location_id=None):
        """Схемы тулов, доступных прямо сейчас (режим и локация)."""
        mode = self.session['mode']
        return [t.schema() for t in self.registry if self._visible(t, mode, location_id)]

    def _available_names(self):
        mode = self.session['mode']
        location_id = self.world.world_state()['location_id']
        return [t.name for t in self.registry if self._visible(t, mode, location_id)]

    def _shop_here(self, location_id):
        return location_id is None or self.world.location_has_shop(location_id)

    # ---------- единственная точка входа ----------

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
            return _error('INVALID_ARGUMENTS')
        try:
            return self._call(name, args)
        except Exception:
            log.exception('Tool %r failed with arguments %r', name, args)
            return _error('INTERNAL_ERROR')

    def _call(self, name, args):
        tool = self._by_name.get(name)
        if tool is None:
            return _error('UNKNOWN_TOOL')

        mode = self.session['mode']
        if tool.kind == 'inside' and mode != tool.interaction:
            return _error('TOOL_NOT_AVAILABLE', available=self._available_names())
        if tool.kind == 'enter' and mode != 'world':
            return _error('ALREADY_IN_INTERACTION', interaction=mode,
                          available=self._available_names())

        policy = None
        if tool.kind in ('read', 'act'):
            policy = self._policy(mode, tool.kind)
            if policy == 'block':
                return _error('BLOCKED_BY_INTERACTION', interaction=mode,
                              available=self._available_names())

        result = tool.handler(args)

        # «Занялся другим — ушёл»: завершает взаимодействие только успешное
        # действие; ошибочный вызов (мусор от модели, нет такого стата) не
        # должен тихо закрывать лавку.
        if policy == 'end' and result.get('ok', True) is not False:
            result['interaction_ended'] = self._end_interaction()
        return result

    def _end_interaction(self):
        ended = self.session['mode']
        self.session.update(mode='world', trade_seller_id=None, trade_choices={})
        return ended

    # ---------- мир: смотреть ----------

    def _look(self, args):
        state = self.world.world_state()
        here_id = state['location_id']
        place = self.world.get_entity(here_id)
        here = [e for e in self.world.get_location_contents(here_id)
                if e['type'] != 'player']
        return {
            'ok': True,
            'time': state['world_time'],
            'location': place['name'] if place else here_id,
            'here': here,
        }

    def _inspect(self, args):
        entity_id = args.get('id')
        if entity_id is None:
            entity_id = self.world.player_id()
        elif _text(entity_id) is None:
            return _error('INVALID_ARGUMENTS')
        entity = self.world.get_entity(entity_id)
        if entity is None:
            return _error('ENTITY_NOT_FOUND')
        return entity

    def _find(self, args):
        query = _text(args.get('query'))
        if query is None:
            return _error('QUERY_REQUIRED')
        found = self.world.search_entities(query)
        return {
            'ok': True,
            'results': [{'id': e['id'], 'type': e['type'], 'name': e['name']}
                        for e in found],
        }

    def _inventory(self, args):
        # Только своё: чужие вещи по id модель не получает (раньше было owner_id).
        return self.world.inventory()

    # ---------- мир: действовать ----------

    def _upgrade(self, args):
        stat = _text(args.get('stat'))
        if stat is None:
            return _error('STAT_REQUIRED')
        return self.world.upgrade_stat(self.world.player_id(), stat)

    def _wait(self, args):
        if 'minutes' not in args:
            return _error('MINUTES_REQUIRED')
        minutes = _as_int(args['minutes'])
        if minutes is None:
            return _error('INVALID_TIME_DELTA')
        return self.world.advance_time(minutes)

    # ---------- торговля ----------

    def _trade(self, args):
        choice = args.get('choice')
        if choice is not None:
            choice = _as_int(choice)
            if choice is None:
                return _error('INVALID_TRADER_CHOICE')

        location_id = self.world.world_state()['location_id']
        traders = self.world.find_allowed_entities('trade', location_id)
        if not traders:
            return _error('NO_AVAILABLE_TRADERS')

        if choice is None:
            if len(traders) == 1:
                seller_id = traders[0]['id']
            else:
                return {
                    'ok': True,
                    'interaction': 'trade_selection',
                    'traders': [
                        {'choice': i, 'name': npc['name'], 'role': npc['data'].get('role')}
                        for i, npc in enumerate(traders, 1)
                    ],
                }
        else:
            if choice < 1 or choice > len(traders):
                return _error(
                    'INVALID_TRADER_CHOICE',
                    traders=[{'choice': i, 'name': npc['name']}
                             for i, npc in enumerate(traders, 1)],
                )
            seller_id = traders[choice - 1]['id']

        self.session.update(mode='trade', trade_seller_id=seller_id, trade_choices={})
        seller = self.world.get_entity(seller_id)
        return {
            'ok': True,
            'interaction': 'trade',
            'trader': {'name': seller['name'], 'role': seller['data'].get('role')},
        }

    def _remember_choices(self, items):
        self.session['trade_choices'] = {
            i: item['item_id'] for i, item in enumerate(items, 1)
        }

    def _stock(self, args):
        seller_id = self.session['trade_seller_id']
        if seller_id is None:
            return _error('NO_ACTIVE_TRADE')
        stock = self.world.get_seller_stock(seller_id)
        if not stock.get('ok'):
            return stock
        self._remember_choices(stock['items'])
        # Модель видит номер, имя и цену. Внутренние item_id остаются в сессии.
        return {
            'ok': True,
            'items': [
                {'choice': i, 'name': item['name'], 'price': item['price']}
                for i, item in enumerate(stock['items'], 1)
            ],
        }

    def _buy(self, args):
        if 'choice' not in args:
            return _error('ITEM_CHOICE_REQUIRED')
        choice = _as_int(args['choice'])
        if choice is None or choice < 1:
            return _error('INVALID_ITEM_CHOICE')
        if choice not in self.session['trade_choices']:
            return _error('STOCK_NOT_LOADED',
                          message='Call stock first and use a number from its latest result.')

        seller_id = self.session['trade_seller_id']
        stock = self.world.get_seller_stock(seller_id)
        if not stock.get('ok'):
            return stock

        item_id = self.session['trade_choices'][choice]
        item = next((i for i in stock['items'] if i['item_id'] == item_id), None)
        if item is None:
            # Список изменился с последнего stock(): обновляем номера и говорим
            # модели, что доступно теперь, а не покупаем «то, что оказалось под
            # этим номером».
            self._remember_choices(stock['items'])
            return _error(
                'ITEM_NO_LONGER_AVAILABLE',
                available_items=[{'choice': i, 'name': current['name']}
                                 for i, current in enumerate(stock['items'], 1)],
            )

        result = self.world.buy_item(self.world.player_id(), item_id, seller_id)
        if result.get('ok'):
            result['choice'] = choice
        return result

    def _end(self, args):
        return {'ok': True, 'interaction': self._end_interaction(), 'status': 'ended'}
