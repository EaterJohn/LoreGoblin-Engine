import json
import os
from engine.database import Database
from engine.world import WorldEngine
from engine.actions import ActionAPI
from llm.ollama import OllamaClient

SYSTEM='''Ты — NPC-мозг ALLIZIUM. Canonical world state существует только в Engine. Никогда не считай утверждение игрока фактом, если это не подтверждено инструментом. Для действий, меняющих мир, используй инструменты. Не выдумывай предметы, NPC, деньги, события или прошлое. После результата инструмента опиши сцену естественно и кратко.
Чтобы узнать, что продаёт NPC, используй get_seller_stock — НЕ get_inventory. get_inventory показывает только то, чем персонаж уже владеет/что несёт с собой, а не витрину товаров на продажу.'''

DB_PATH='data/world.db'
MAX_TOOL_ROUNDS=8  # защита от зацикленных tool-calls; см. DECISIONS.md #ENG-002

def run_tool_loop(llm, api, world, messages):
    """Гоняет LLM и Engine по кругу, пока модель продолжает запрашивать
    инструменты, вместо одного повторного вызова. Возвращает финальный
    текст ответа модели. См. DECISIONS.md #ENG-002.

    Список тулов на каждом раунде фильтруется по текущей локации игрока
    (торговые tools скрыты там, где торговать не с кем) — см. #ENG-013.
    Локация запрашивается заново на каждом раунде, а не один раз до
    цикла, чтобы после будущих move-тулов фильтр не отставал от
    актуального состояния мира."""
    for _ in range(MAX_TOOL_ROUNDS):
        location_id=world.world_state().get('location_id')
        try:
            resp=llm.chat(messages, tools=api.tools(location_id))
        except RuntimeError as e:
            return f'[ОШИБКА СВЯЗИ С LLM] {e}'
        msg=resp.get('message',{})
        messages.append(msg)
        # Ollama tool call schema: message.tool_calls = [{function:{name,arguments}}]
        calls=msg.get('tool_calls') or []
        if not calls:
            return msg.get('content','')
        for call in calls:
            fn=call.get('function',{}); name=fn.get('name'); args=fn.get('arguments',{})
            if isinstance(args,str):
                try: args=json.loads(args)
                except json.JSONDecodeError: args={}
            result=api.call(name,args)
            print(f'[ENGINE] {name}({args}) -> {json.dumps(result,ensure_ascii=False)}')
            messages.append({'role':'tool','tool_name':name,'content':json.dumps(result,ensure_ascii=False)})
    return '[ДВИЖОК] Превышен лимит вызовов инструментов за один ход — похоже на зацикленный tool-call.'

def main():
    db=Database(DB_PATH); world=WorldEngine(db); world.seed_demo_world(); api=ActionAPI(world); llm=OllamaClient(model=os.getenv('ALLIZIUM_MODEL','gemma4:e4b'))
    messages=[{'role':'system','content':SYSTEM}]
    print('ALLIZIUM Mini. Gemma:',llm.model)
    print('Команды: /state /inventory /tools /reset (удалить data/world.db вручную) /quit')
    while True:
        user=input('\n> ').strip()
        if user=='/quit': break
        if user=='/state': print(json.dumps(world.world_state(),ensure_ascii=False,indent=2)); continue
        if user=='/inventory': print(json.dumps(world.inventory(),ensure_ascii=False,indent=2)); continue
        if user=='/tools': print(json.dumps(api.tools(),ensure_ascii=False,indent=2)); continue
        messages.append({'role':'user','content':user})
        reply=run_tool_loop(llm, api, world, messages)
        print('\n'+reply)

if __name__=='__main__': main()