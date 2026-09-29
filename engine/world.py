import json
import re
from pathlib import Path

# id пресета — это имя файла, а не путь: только безопасные символы.
PRESET_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')


class WorldEngine:
    def __init__(self, db, rules=None):
        self.db = db
        self.rules = rules or {
            'time': {
                'minutes_per_hour': 60,
                'hours_per_day': 24,
                'days_per_month': 30,
                'months_per_year': 12,
            }
        }

    def load_rules(self, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'Rules preset not found: {path}')
        with path.open('r', encoding='utf-8') as f:
            rules = json.load(f)
        self._validate_rules(rules, path)
        self.rules = rules
        return rules

    @staticmethod
    def _validate_rules(rules, path):
        if not isinstance(rules, dict):
            raise ValueError(f'Rules preset must be an object: {path}')
        time = rules.get('time')
        if not isinstance(time, dict):
            raise ValueError(f'Rules preset missing time object: {path}')
        for field in ('minutes_per_hour', 'hours_per_day', 'days_per_month', 'months_per_year'):
            value = time.get(field)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f'Rules preset time.{field} must be a positive integer: {path}')

    def load_world(self, path):
        """Load a world definition from JSON.

        Возвращает True, если состояние мира создано в пустой БД, и False,
        если БД уже содержит мир (существующее состояние не перезаписывается).

        Файл читается и валидируется всегда, а `rules_preset` применяется при
        каждой загрузке, в том числе для уже существующей БД: правила механик
        это конфигурация, а не сохранённое состояние (DECISIONS #ENG-021).
        Создание состояния идёт одной транзакцией: при любой ошибке в БД не
        остаётся ни world_state, ни части сущностей.

        The JSON file contains only world data: initial time/location, player
        data, entities, and starting money. The engine mechanics stay here;
        world-specific lore does not.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'World definition not found: {path}')

        with path.open('r', encoding='utf-8') as f:
            world = json.load(f)

        self._validate_world_definition(world, path)

        if world.get('rules_preset') is not None:
            self.load_rules(self._preset_path(world['rules_preset'], path))

        if self.db.query('SELECT id FROM world_state WHERE id=1'):
            return False

        world_time = world['world_time']
        start_location_id = world['start_location_id']
        player = world['player']

        with self.db.transaction():
            self.db.execute(
                'INSERT INTO world_state(id, world_time, location_id) VALUES(1, ?, ?)',
                (world_time, start_location_id),
            )

            player_data = {
                'stats': player['stats'],
            }
            self.db.execute(
                'INSERT INTO entities(id,type,name,location_id,data_json) VALUES(?,?,?,?,?)',
                (
                    player['id'],
                    'player',
                    player['name'],
                    player['location_id'],
                    json.dumps(player_data, ensure_ascii=False),
                ),
            )

            for entity in world['entities']:
                self.db.execute(
                    'INSERT INTO entities(id,type,name,location_id,data_json) VALUES(?,?,?,?,?)',
                    (
                        entity['id'],
                        entity['type'],
                        entity['name'],
                        entity.get('location_id'),
                        json.dumps(entity.get('data', {}), ensure_ascii=False),
                    ),
                )

            self.db.execute(
                'INSERT INTO money(owner_id,silver) VALUES(?,?)',
                (player['id'], player['starting_money']),
            )
            self.db.execute(
                'INSERT INTO events(world_time,event_type,actor_id,data_json) VALUES(?,?,?,?)',
                (
                    world_time,
                    'world_created',
                    player['id'],
                    json.dumps(
                        {'world_definition': str(path.as_posix())},
                        ensure_ascii=False,
                    ),
                ),
            )
        return True

    @staticmethod
    def _preset_path(preset_id, world_path):
        """Путь к пресету: <data>/rules/presets/<id>.json рядом с <data>/worlds/<w>/world.json."""
        parents = Path(world_path).resolve().parents
        if len(parents) < 3:
            raise FileNotFoundError(
                f'Cannot locate rules presets directory for world: {world_path}'
            )
        return parents[2] / 'rules' / 'presets' / f'{preset_id}.json'

    @staticmethod
    def _validate_world_definition(world, path):
        def non_empty_str(value):
            return isinstance(value, str) and bool(value.strip())

        if not isinstance(world, dict):
            raise ValueError(f'World definition must be an object: {path}')

        required = {'world_time', 'start_location_id', 'player', 'entities'}
        missing = required - world.keys()
        if missing:
            raise ValueError(
                f'World definition missing required fields {sorted(missing)}: {path}'
            )

        preset_id = world.get('rules_preset')
        if preset_id is not None and not (
            isinstance(preset_id, str) and PRESET_ID_RE.fullmatch(preset_id)
        ):
            raise ValueError(
                f'World rules_preset must be a simple id (letters, digits, _ or -): {path}'
            )

        player = world['player']
        if not isinstance(player, dict):
            raise ValueError('World player must be an object')
        for field in ('id', 'name', 'location_id', 'stats', 'starting_money'):
            if field not in player:
                raise ValueError(f'World player missing required field: {field}')
        for field in ('id', 'name', 'location_id'):
            if not non_empty_str(player[field]):
                raise ValueError(f'World player {field} must be a non-empty string')
        if not isinstance(player['stats'], dict):
            raise ValueError('World player stats must be an object')

        if not isinstance(world['entities'], list):
            raise ValueError('World entities must be a list')

        ids = [player['id']]
        for entity in world['entities']:
            if not isinstance(entity, dict):
                raise ValueError('Every world entity must be an object')
            for field in ('id', 'type', 'name'):
                if field not in entity:
                    raise ValueError(f'World entity missing required field: {field}')
                if not non_empty_str(entity[field]):
                    raise ValueError(f'World entity {field} must be a non-empty string')
            if not isinstance(entity.get('data', {}), dict):
                raise ValueError(f"World entity {entity['id']!r} data must be an object")
            ids.append(entity['id'])

        if len(ids) != len(set(ids)):
            raise ValueError('World entity IDs must be unique')

        if world['start_location_id'] != player['location_id']:
            raise ValueError(
                'World start_location_id must match the player location_id'
            )

        money = player['starting_money']
        if isinstance(money, bool) or not isinstance(money, int) or money < 0:
            raise ValueError('World player starting_money must be a non-negative integer')

    def world_state(self):
        return dict(self.db.query('SELECT * FROM world_state WHERE id=1')[0])

    def get_entity(self, entity_id):
        rows = self.db.query('SELECT * FROM entities WHERE id=?', (entity_id,))
        if not rows:
            return None
        r = dict(rows[0])
        r['data'] = json.loads(r.pop('data_json'))
        return r

    def search_entities(self, query, type_=None, location_id=None):
        sql = 'SELECT * FROM entities WHERE (name LIKE ? OR data_json LIKE ?)'
        params = [f'%{query}%', f'%{query}%']
        if type_:
            sql += ' AND type=?'
            params.append(type_)
        if location_id:
            sql += ' AND location_id=?'
            params.append(location_id)
        sql += ' ORDER BY name LIMIT 20'
        rows = self.db.query(sql, params)
        out = []
        for r in rows:
            d = dict(r)
            d['data'] = json.loads(d.pop('data_json'))
            out.append(d)
        return out

    def allow_to(self, entity_id, action):
        """Return whether an entity is canonically allowed to perform an action."""
        entity = self.get_entity(entity_id)
        if not entity:
            return False
        allowed = entity['data'].get('allow_to', [])
        return isinstance(allowed, list) and action in allowed

    def find_allowed_entities(self, action, location_id, entity_type='npc'):
        """Find entities at a location that are allowed to perform action."""
        rows = self.db.query(
            'SELECT id,type,name,data_json FROM entities WHERE type=? AND location_id=? ORDER BY name',
            (entity_type, location_id),
        )
        out = []
        for r in rows:
            data = json.loads(r['data_json'])
            allowed = data.get('allow_to', [])
            if isinstance(allowed, list) and action in allowed:
                out.append({
                    'id': r['id'],
                    'type': r['type'],
                    'name': r['name'],
                    'data': data,
                })
        return out

    def get_location_contents(self, location_id):
        rows = self.db.query(
            'SELECT id,type,name FROM entities WHERE location_id=? ORDER BY type,name',
            (location_id,),
        )
        return [dict(r) for r in rows]

    def inventory(self, owner_id='player'):
        rows = self.db.query(
            '''SELECT i.item_id,i.quantity,e.name FROM inventory i
               JOIN entities e ON e.id=i.item_id WHERE i.owner_id=?''',
            (owner_id,),
        )
        money = self.db.query(
            'SELECT silver FROM money WHERE owner_id=?',
            (owner_id,),
        )
        return {
            'money': money[0]['silver'] if money else 0,
            'items': [dict(r) for r in rows],
        }

    def buy_item(self, buyer_id, item_id, seller_id):
        item = self.get_entity(item_id)
        if not item or item['type'] != 'item':
            return {'ok': False, 'error': 'ITEM_NOT_FOUND'}
        seller = self.get_entity(seller_id)
        if not seller:
            return {'ok': False, 'error': 'SELLER_NOT_FOUND'}
        if not self.allow_to(seller_id, 'trade'):
            return {'ok': False, 'error': 'SELLER_NOT_AVAILABLE_FOR_TRADE'}
        buyer = self.get_entity(buyer_id)
        if not buyer:
            return {'ok': False, 'error': 'BUYER_NOT_FOUND'}
        if buyer['location_id'] != seller['location_id']:
            return {'ok': False, 'error': 'BUYER_AND_SELLER_NOT_TOGETHER'}
        price = item['data'].get('price')
        if price is None:
            return {'ok': False, 'error': 'PRICE_UNKNOWN'}
        # Demo shop rule: only items whose location is seller's location are stocked.
        if item['location_id'] != seller['location_id']:
            return {'ok': False, 'error': 'ITEM_NOT_IN_SHOP'}
        money = self.db.query(
            'SELECT silver FROM money WHERE owner_id=?',
            (buyer_id,),
        )
        if not money or money[0]['silver'] < price:
            return {'ok': False, 'error': 'INSUFFICIENT_FUNDS'}
        with self.db.transaction():
            self.db.execute(
                'UPDATE money SET silver=silver-? WHERE owner_id=?',
                (price, buyer_id),
            )
            self.db.execute(
                '''INSERT INTO inventory(owner_id,item_id,quantity) VALUES(?,?,1)
                   ON CONFLICT(owner_id,item_id) DO UPDATE SET quantity=quantity+1''',
                (buyer_id, item_id),
            )
            self.db.execute(
                'UPDATE entities SET location_id=NULL WHERE id=?',
                (item_id,),
            )
            self.db.execute(
                '''INSERT INTO events(world_time,event_type,actor_id,target_id,data_json)
                   VALUES(?,?,?,?,?)''',
                (
                    self.world_state()['world_time'],
                    'purchase',
                    buyer_id,
                    item_id,
                    json.dumps({'price': price}, ensure_ascii=False),
                ),
            )
        return {
            'ok': True,
            'item': item['name'],
            'price': price,
            'inventory': self.inventory(buyer_id),
        }

    def get_seller_stock(self, seller_id):
        """Return the canonical set of items currently purchasable from a seller."""
        seller = self.get_entity(seller_id)
        if not seller:
            return {'ok': False, 'error': 'SELLER_NOT_FOUND'}
        if not self.allow_to(seller_id, 'trade'):
            return {'ok': False, 'error': 'SELLER_NOT_AVAILABLE_FOR_TRADE'}
        rows = self.db.query(
            "SELECT id,name,data_json FROM entities WHERE type='item' AND location_id=?",
            (seller['location_id'],),
        )
        items = []
        for r in rows:
            data = json.loads(r['data_json'])
            if 'price' in data:
                items.append({
                    'item_id': r['id'],
                    'name': r['name'],
                    'price': data['price'],
                })
        return {'ok': True, 'seller_id': seller_id, 'items': items}

    def location_has_shop(self, location_id):
        """Return whether a location has an NPC and at least one priced item."""
        if not location_id:
            return False
        npcs = self.find_allowed_entities('trade', location_id)
        if not npcs:
            return False
        items = self.db.query(
            "SELECT data_json FROM entities WHERE type='item' AND location_id=?",
            (location_id,),
        )
        return any('price' in json.loads(r['data_json']) for r in items)

    def upgrade_stat(self, player_id, stat):
        ent = self.get_entity(player_id)
        if not ent or ent['type'] != 'player':
            return {'ok': False, 'error': 'PLAYER_NOT_FOUND'}
        stats = ent['data'].get('stats', {})
        if stat not in stats:
            return {'ok': False, 'error': 'UNKNOWN_STAT'}
        cost = stats[stat] - 9
        if cost < 1:
            cost = 1
        money = self.inventory(player_id)['money']
        if money < cost:
            return {'ok': False, 'error': 'INSUFFICIENT_FUNDS', 'cost': cost, 'silver': money}
        with self.db.transaction():
            stats[stat] += 1
            ent['data']['stats'] = stats
            self.db.execute(
                'UPDATE entities SET data_json=? WHERE id=?',
                (json.dumps(ent['data'], ensure_ascii=False), player_id),
            )
            self.db.execute(
                'UPDATE money SET silver=silver-? WHERE owner_id=?',
                (cost, player_id),
            )
            self.db.execute(
                'INSERT INTO events(world_time,event_type,actor_id,data_json) VALUES(?,?,?,?)',
                (
                    self.world_state()['world_time'],
                    'stat_upgrade',
                    player_id,
                    json.dumps({'stat': stat, 'cost': cost}, ensure_ascii=False),
                ),
            )
        return {
            'ok': True,
            'stat': stat,
            'value': stats[stat],
            'cost': cost,
            'silver': self.inventory(player_id)['money'],
        }

    def advance_time(self, minutes):
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
            return {'ok': False, 'error': 'INVALID_TIME_DELTA'}
        state = self.world_state()
        parts = state['world_time'].split(' ', 2)
        if len(parts) != 3 or parts[0] != 'Day':
            raise ValueError(
                f"Invalid world_time format: {state['world_time']!r}; "
                'expected "Day N HH:MM"'
            )
        day = int(parts[1])
        h, m = map(int, parts[2].split(':'))
        time_rules = self.rules['time']
        minutes_per_hour = time_rules['minutes_per_hour']
        hours_per_day = time_rules['hours_per_day']
        total = h * minutes_per_hour + m + minutes
        day += total // (minutes_per_hour * hours_per_day)
        total %= minutes_per_hour * hours_per_day
        new = f'Day {day} {total // minutes_per_hour:02d}:{total % minutes_per_hour:02d}'
        with self.db.transaction():
            self.db.execute(
                'UPDATE world_state SET world_time=? WHERE id=1',
                (new,),
            )
            self.db.execute(
                'INSERT INTO events(world_time,event_type,data_json) VALUES(?,?,?)',
                (
                    new,
                    'time_advanced',
                    json.dumps({'minutes': minutes}),
                ),
            )
        return {'ok': True, 'world_time': new}
