import json
from datetime import datetime, timedelta
from pathlib import Path


class WorldEngine:
    def __init__(self, db):
        self.db = db

    def load_world(self, path):
        """Load a world definition from JSON into an empty database.

        The JSON file contains only world data: initial time/location, player
        data, entities, and starting money. The engine mechanics stay here;
        world-specific lore does not.
        """
        if self.db.query('SELECT id FROM world_state WHERE id=1'):
            return

        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'World definition not found: {path}')

        with path.open('r', encoding='utf-8') as f:
            world = json.load(f)

        self._validate_world_definition(world, path)

        world_time = world['world_time']
        start_location_id = world['start_location_id']
        player = world['player']

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

    @staticmethod
    def _validate_world_definition(world, path):
        if not isinstance(world, dict):
            raise ValueError(f'World definition must be an object: {path}')

        required = {'world_time', 'start_location_id', 'player', 'entities'}
        missing = required - world.keys()
        if missing:
            raise ValueError(
                f'World definition missing required fields {sorted(missing)}: {path}'
            )

        player = world['player']
        if not isinstance(player, dict):
            raise ValueError('World player must be an object')
        for field in ('id', 'name', 'location_id', 'stats', 'starting_money'):
            if field not in player:
                raise ValueError(f'World player missing required field: {field}')

        if not isinstance(world['entities'], list):
            raise ValueError('World entities must be a list')

        ids = [player['id']]
        for entity in world['entities']:
            if not isinstance(entity, dict):
                raise ValueError('Every world entity must be an object')
            for field in ('id', 'type', 'name'):
                if field not in entity:
                    raise ValueError(f'World entity missing required field: {field}')
            ids.append(entity['id'])

        if len(ids) != len(set(ids)):
            raise ValueError('World entity IDs must be unique')

        if world['start_location_id'] != player['location_id']:
            raise ValueError(
                'World start_location_id must match the player location_id'
            )

        if not isinstance(player['starting_money'], int) or player['starting_money'] < 0:
            raise ValueError('World player starting_money must be a non-negative integer')

    def seed_demo_world(self):
        """Compatibility wrapper for the bundled ALLIZIUM world."""
        world_path = (
            Path(__file__).resolve().parents[1]
            / 'data'
            / 'worlds'
            / 'allizium'
            / 'world.json'
        )
        self.load_world(world_path)

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
        npcs = self.db.query(
            "SELECT id FROM entities WHERE type='npc' AND location_id=?",
            (location_id,),
        )
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
        # Demo parser for "Day N HH:MM".
        state = self.world_state()
        prefix, time = state['world_time'].split(' ')
        day = int(prefix.replace('Day', ''))
        h, m = map(int, time.split(':'))
        total = h * 60 + m + minutes
        day += total // 1440
        total %= 1440
        new = f'Day {day} {total // 60:02d}:{total % 60:02d}'
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
