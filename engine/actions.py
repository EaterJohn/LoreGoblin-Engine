from .world import WorldEngine

class ActionAPI:
    def __init__(self, world: WorldEngine):
        self.world=world

    def tools(self, location_id=None):
        """location_id=None -> полный список (используется /tools для
        отладки и как безопасный дефолт). При передаче реальной локации
        торговые тулы показываются модели, только если в локации есть кому
        и что продавать — экономит контекст слабых моделей и убирает
        соблазн вызвать buy_item там, где торговать не с кем.
        См. DECISIONS.md #ENG-013."""
        def fn(name, description, properties, required=[]):
            return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':required}}}
        core=[]
        core.append(fn('get_world_state','Get current canonical world time and player location.',{},[]))
        core.append(fn('get_location_contents','Get canonical entities currently at a location.',{'location_id':{'type':'string'}},['location_id']))
        core.append(fn('get_entity','Get one canonical entity by ID.',{'entity_id':{'type':'string'}},['entity_id']))
        core.append(fn('search_entities','Search canonical entities by name or stored description.',{'query':{'type':'string'},'type':{'type':'string'},'location_id':{'type':'string'}},['query']))
        core.append(fn('get_inventory','Get an owner\'s OWN possessions and money (what they carry/own). Do NOT use this to find out what an NPC sells — use get_seller_stock for that.',{'owner_id':{'type':'string'}},[]))
        core.append(fn('upgrade_stat','Upgrade a player stat through the engine.',{'player_id':{'type':'string'},'stat':{'type':'string'}},['player_id','stat']))
        core.append(fn('advance_time','Advance canonical world time.',{'minutes':{'type':'integer'}},['minutes']))
        shop=[]
        shop.append(fn('get_seller_stock','Get what a specific NPC currently sells (canonical, with prices). Use this — not get_inventory — to answer "what does X sell/have for sale".',{'seller_id':{'type':'string'}},['seller_id']))
        shop.append(fn('buy_item','Buy an item only if it exists, is stocked, priced, and affordable. Check get_seller_stock first.',{'buyer_id':{'type':'string'},'item_id':{'type':'string'},'seller_id':{'type':'string'}},['buyer_id','item_id','seller_id']))
        if location_id is None or self.world.location_has_shop(location_id):
            return core+shop
        return core

    def call(self,name,args):
        if name=='get_world_state': return self.world.world_state()
        if name=='get_location_contents':
            if 'location_id' not in args: return {'ok':False,'error':'LOCATION_ID_REQUIRED'}
            return self.world.get_location_contents(args['location_id'])
        if name=='get_entity':
            if 'entity_id' not in args: return {'ok':False,'error':'ENTITY_ID_REQUIRED'}
            return self.world.get_entity(args['entity_id'])
        if name=='search_entities':
            if 'query' not in args: return {'ok':False,'error':'QUERY_REQUIRED'}
            return self.world.search_entities(args['query'],args.get('type'),args.get('location_id'))
        if name=='get_inventory': return self.world.inventory(args.get('owner_id','player'))
        if name=='get_seller_stock':
            if 'seller_id' not in args: return {'ok':False,'error':'SELLER_ID_REQUIRED'}
            return self.world.get_seller_stock(args['seller_id'])
        if name=='buy_item':
            if 'seller_id' not in args: return {'ok':False,'error':'SELLER_ID_REQUIRED'}
            return self.world.buy_item(args['buyer_id'],args['item_id'],args['seller_id'])
        if name=='upgrade_stat':
            if 'player_id' not in args or 'stat' not in args:
                return {'ok':False,'error':'PLAYER_ID_AND_STAT_REQUIRED'}
            return self.world.upgrade_stat(args['player_id'],args['stat'])
        if name=='advance_time': return self.world.advance_time(int(args['minutes']))
        return {'ok':False,'error':'UNKNOWN_TOOL'}