import json
from datetime import datetime, timedelta

class WorldEngine:
    def __init__(self, db):
        self.db = db

    def seed_demo_world(self):
        if self.db.query('SELECT id FROM world_state WHERE id=1'):
            return
        self.db.execute("INSERT INTO world_state(id, world_time, location_id) VALUES(1, 'Day 1 12:00', 'tavern_red_flask')")
        entities = [
            ('player', 'player', 'Иван', 'tavern_red_flask', {'stats': {'STR':10,'CON':10,'DEX':10,'PER':10,'WIL':10,'INT':10,'CHA':10,'Luck':10,'Eth':10}}),
            ('boris', 'npc', 'Борис', 'tavern_red_flask', {'personality':['cautious','practical'], 'role':'innkeeper'}),
            ('tavern_red_flask', 'location', 'Таверна «Красный Факел»', 'ashport', {'contents':['table_1','chair_1','chair_2','chair_3','chair_4','iron_dagger','beer_mug']}),
            ('iron_dagger', 'item', 'Железный кинжал', 'tavern_red_flask', {'price':12,'damage':3}),
            ('beer_mug', 'item', 'Кружка пива', 'tavern_red_flask', {'price':2}),
            ('table_1', 'object', 'Стол', 'tavern_red_flask', {}),
            ('chair_1', 'object', 'Стул', 'tavern_red_flask', {}),
            ('chair_2', 'object', 'Стул', 'tavern_red_flask', {}),
            ('chair_3', 'object', 'Стул', 'tavern_red_flask', {}),
            ('chair_4', 'object', 'Стул', 'tavern_red_flask', {}),
        ]
        for eid, typ, name, loc, data in entities:
            self.db.execute('INSERT INTO entities(id,type,name,location_id,data_json) VALUES(?,?,?,?,?)', (eid,typ,name,loc,json.dumps(data,ensure_ascii=False)))
        self.db.execute('INSERT INTO money(owner_id,silver) VALUES(?,?)', ('player',100))
        self.db.execute("INSERT INTO events(world_time,event_type,actor_id,data_json) VALUES(?,?,?,?)", ('Day 1 12:00','world_created','player',json.dumps({'note':'demo world'},ensure_ascii=False)))

    def world_state(self):
        return dict(self.db.query('SELECT * FROM world_state WHERE id=1')[0])

    def get_entity(self, entity_id):
        rows = self.db.query('SELECT * FROM entities WHERE id=?', (entity_id,))
        if not rows: return None
        r = dict(rows[0]); r['data'] = json.loads(r.pop('data_json')); return r

    def search_entities(self, query, type_=None, location_id=None):
        sql = 'SELECT * FROM entities WHERE (name LIKE ? OR data_json LIKE ?)'
        params = [f'%{query}%', f'%{query}%']
        if type_:
            sql += ' AND type=?'; params.append(type_)
        if location_id:
            sql += ' AND location_id=?'; params.append(location_id)
        sql += ' ORDER BY name LIMIT 20'
        rows = self.db.query(sql, params)
        out=[]
        for r in rows:
            d=dict(r); d['data']=json.loads(d.pop('data_json')); out.append(d)
        return out

    def get_location_contents(self, location_id):
        rows=self.db.query('SELECT id,type,name FROM entities WHERE location_id=? ORDER BY type,name',(location_id,))
        return [dict(r) for r in rows]

    def inventory(self, owner_id='player'):
        rows=self.db.query('''SELECT i.item_id,i.quantity,e.name FROM inventory i JOIN entities e ON e.id=i.item_id WHERE i.owner_id=?''',(owner_id,))
        money=self.db.query('SELECT silver FROM money WHERE owner_id=?',(owner_id,))
        return {'money': money[0]['silver'] if money else 0, 'items':[dict(r) for r in rows]}

    def buy_item(self, buyer_id, item_id, seller_id):
        item=self.get_entity(item_id)
        if not item or item['type']!='item': return {'ok':False,'error':'ITEM_NOT_FOUND'}
        seller=self.get_entity(seller_id)
        if not seller: return {'ok':False,'error':'SELLER_NOT_FOUND'}
        price=item['data'].get('price')
        if price is None: return {'ok':False,'error':'PRICE_UNKNOWN'}
        # Demo shop rule: only items whose location is seller's location are stocked.
        if item['location_id'] != seller['location_id']:
            return {'ok':False,'error':'ITEM_NOT_IN_SHOP'}
        money=self.db.query('SELECT silver FROM money WHERE owner_id=?',(buyer_id,))
        if not money or money[0]['silver'] < price: return {'ok':False,'error':'INSUFFICIENT_FUNDS'}
        self.db.execute('UPDATE money SET silver=silver-? WHERE owner_id=?',(price,buyer_id))
        self.db.execute('''INSERT INTO inventory(owner_id,item_id,quantity) VALUES(?,?,1)
                           ON CONFLICT(owner_id,item_id) DO UPDATE SET quantity=quantity+1''',(buyer_id,item_id))
        self.db.execute('UPDATE entities SET location_id=NULL WHERE id=?',(item_id,))
        self.db.execute('INSERT INTO events(world_time,event_type,actor_id,target_id,data_json) VALUES(?,?,?,?,?)',(self.world_state()['world_time'],'purchase',buyer_id,item_id,json.dumps({'price':price},ensure_ascii=False)))
        return {'ok':True,'item':item['name'],'price':price,'inventory':self.inventory(buyer_id)}

    def get_seller_stock(self, seller_id):
        """Каноничный список товаров продавца. Использует то же правило
        co-location, что и buy_item, так что результат всегда совпадает с
        тем, что реально можно купить. См. DECISIONS.md #ENG-012 — раньше
        модель для вопроса "что продаёт X" ошибочно брала get_inventory
        (таблица купленных вещей), а не то, что реально выставлено на
        продажу по правилам buy_item."""
        seller=self.get_entity(seller_id)
        if not seller: return {'ok':False,'error':'SELLER_NOT_FOUND'}
        rows=self.db.query("SELECT id,name,data_json FROM entities WHERE type='item' AND location_id=?",(seller['location_id'],))
        items=[]
        for r in rows:
            data=json.loads(r['data_json'])
            if 'price' in data:
                items.append({'item_id':r['id'],'name':r['name'],'price':data['price']})
        return {'ok':True,'seller_id':seller_id,'items':items}

    def location_has_shop(self, location_id):
        """Есть ли в локации хоть один NPC и хоть один предмет с ценой —
        используется для контекстной фильтрации тулов в ActionAPI.tools(),
        чтобы не показывать модели торговые инструменты там, где торговать
        не с кем. См. DECISIONS.md #ENG-013."""
        if not location_id: return False
        npcs=self.db.query("SELECT id FROM entities WHERE type='npc' AND location_id=?",(location_id,))
        if not npcs: return False
        items=self.db.query("SELECT data_json FROM entities WHERE type='item' AND location_id=?",(location_id,))
        return any('price' in json.loads(r['data_json']) for r in items)

    def upgrade_stat(self, player_id, stat):
        ent=self.get_entity(player_id)
        if not ent or ent['type']!='player': return {'ok':False,'error':'PLAYER_NOT_FOUND'}
        stats=ent['data'].get('stats',{})
        if stat not in stats: return {'ok':False,'error':'UNKNOWN_STAT'}
        cost=stats[stat] - 9
        if cost < 1: cost=1
        # Demo progression pool: use silver as temporary resource for now.
        money=self.inventory(player_id)['money']
        if money < cost: return {'ok':False,'error':'INSUFFICIENT_FUNDS','cost':cost,'silver':money}
        stats[stat]+=1
        ent['data']['stats']=stats
        self.db.execute('UPDATE entities SET data_json=? WHERE id=?',(json.dumps(ent['data'],ensure_ascii=False),player_id))
        self.db.execute('UPDATE money SET silver=silver-? WHERE owner_id=?',(cost,player_id))
        self.db.execute('INSERT INTO events(world_time,event_type,actor_id,data_json) VALUES(?,?,?,?)',(self.world_state()['world_time'],'stat_upgrade',player_id,json.dumps({'stat':stat,'cost':cost},ensure_ascii=False)))
        return {'ok':True,'stat':stat,'value':stats[stat],'cost':cost,'silver':self.inventory(player_id)['money']}

    def advance_time(self, minutes):
        # Demo parser for "Day N HH:MM".
        state=self.world_state(); prefix,time=state['world_time'].split(' '); day=int(prefix.replace('Day','')); h,m=map(int,time.split(':'))
        total=h*60+m+minutes; day += total//1440; total%=1440
        new=f'Day {day} {total//60:02d}:{total%60:02d}'
        self.db.execute('UPDATE world_state SET world_time=? WHERE id=1',(new,))
        self.db.execute('INSERT INTO events(world_time,event_type,data_json) VALUES(?,?,?)',(new,'time_advanced',json.dumps({'minutes':minutes})))
        return {'ok':True,'world_time':new}