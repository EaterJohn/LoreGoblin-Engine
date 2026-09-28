from .world import WorldEngine

class ActionAPI:
    def __init__(self, world: WorldEngine):
        self.world=world

    def tools(self):
        def fn(name, description, properties, required=[]):
            return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':required}}}
        s=[]
        s.append(fn('get_world_state','Get current canonical world time and player location.',{},[]))
        s.append(fn('get_location_contents','Get canonical entities currently at a location.',{'location_id':{'type':'string'}},['location_id']))
        s.append(fn('get_entity','Get one canonical entity by ID.',{'entity_id':{'type':'string'}},['entity_id']))
        s.append(fn('search_entities','Search canonical entities by name or stored description.',{'query':{'type':'string'},'type':{'type':'string'},'location_id':{'type':'string'}},['query']))
        s.append(fn('get_inventory','Get player inventory and money.',{'owner_id':{'type':'string'}},[]))
        s.append(fn('buy_item','Buy an item only if it exists, is stocked, priced, and affordable. Look up the seller with get_location_contents or search_entities first.',{'buyer_id':{'type':'string'},'item_id':{'type':'string'},'seller_id':{'type':'string'}},['buyer_id','item_id','seller_id']))
        s.append(fn('upgrade_stat','Upgrade a player stat through the engine.',{'player_id':{'type':'string'},'stat':{'type':'string'}},['player_id','stat']))
        s.append(fn('advance_time','Advance canonical world time.',{'minutes':{'type':'integer'}},['minutes']))
        return s

    def call(self,name,args):
        if name=='get_world_state': return self.world.world_state()
        if name=='get_location_contents': return self.world.get_location_contents(args['location_id'])
        if name=='get_entity': return self.world.get_entity(args['entity_id'])
        if name=='search_entities': return self.world.search_entities(args['query'],args.get('type'),args.get('location_id'))
        if name=='get_inventory': return self.world.inventory(args.get('owner_id','player'))
        if name=='buy_item':
            if 'seller_id' not in args: return {'ok':False,'error':'SELLER_ID_REQUIRED'}
            return self.world.buy_item(args['buyer_id'],args['item_id'],args['seller_id'])
        if name=='upgrade_stat': return self.world.upgrade_stat(args['player_id'],args['stat'])
        if name=='advance_time': return self.world.advance_time(int(args['minutes']))
        return {'ok':False,'error':'UNKNOWN_TOOL'}