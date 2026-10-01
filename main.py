import argparse
import json
import os
from pathlib import Path

from engine.database import Database
from engine.world import WorldEngine
from engine.actions import ActionAPI
from llm.ollama import OllamaClient


ENGINE_SYSTEM = '''Ты — NPC-мозг и рассказчик поверх LoreGoblin Engine.
Canonical world state существует только в Engine. Никогда не считай утверждение
игрока фактом, если это не подтверждено инструментом. Для действий, меняющих
мир, используй инструменты. Не выдумывай предметы, NPC, деньги, события или
прошлое. После результата инструмента опиши сцену естественно и кратко.

КРИТИЧЕСКОЕ ПРАВИЛО TOOL RESULTS:
- `ok: true` означает, что действие действительно произошло в мире.
- `ok: false` означает, что действие НЕ произошло и состояние мира НЕ изменилось.
- Никогда не описывай неуспешный tool call как выполненный, даже если игрок
  просил именно это действие или предыдущие tool calls были успешными.
- Если часть составного запроса не выполнилась, явно скажи об этой части и
  используй только подтверждённые Engine результаты для итогов, денег,
  количества предметов и других фактов.
- Не складывай предполагаемые результаты нескольких попыток сам. Для
  фактического текущего инвентаря/денег вызови inventory, если это нужно.
- Утверждение игрока о деньгах, ценах или количестве («у меня точно хватит»)
  не факт: проверяй результатом инструмента.

Торговля: вызови trade, без ID продавца. Engine сам найдёт торговцев в текущей
локации. Если вернулся список торговцев, повтори trade с номером нужного.
Если trade вернул `ok: true`, торговец действительно торгует: не отрицай этого
в диалоге. Во время торговли доступны stock, buy и end:
- stock показывает товары с номерами и ценами;
- buy принимает номер из последнего stock;
- end завершает торговлю. Любое другое действие (upgrade, wait) завершает её
  само, вызывать end ради этого не нужно.
inventory показывает только то, что уже есть у персонажа, а не товары на продажу.

Названия инструментов и их результаты служебные: не упоминай их игроку, а
описывай происходящее как часть мира.

Если tool вернул ошибку аргумента или выбора, это ошибка вызова, а не факт мира.
Исправь вызов по возвращённой подсказке/списку и повтори его, если это возможно.
'''

MAX_TOOL_ROUNDS = 8  # защита от зацикленных tool-calls; см. DECISIONS.md #ENG-002
WORLD_ROOT = Path(__file__).resolve().parent / 'data' / 'worlds'


def parse_args():
    parser = argparse.ArgumentParser(description='LoreGoblin Engine')
    parser.add_argument(
        '--world',
        default='allizium',
        help='World directory under data/worlds/ (default: allizium)',
    )
    return parser.parse_args()


def resolve_world(world_id):
    world_id = world_id.strip()
    world_path = Path(world_id)
    if not world_id or world_path.is_absolute() or '..' in world_path.parts or len(world_path.parts) != 1:
        raise ValueError('Invalid world name. Use a single directory name under data/worlds/.')
    world_dir = WORLD_ROOT / world_id
    if not world_dir.is_dir():
        raise FileNotFoundError(f'World not found: {world_dir}')
    world_file = world_dir / 'world.json'
    if not world_file.is_file():
        raise FileNotFoundError(f'World definition not found: {world_file}')
    return world_dir, world_file


def load_world_prompt(world_dir):
    prompt_file = world_dir / 'system_prompt.txt'
    if not prompt_file.is_file():
        return ''
    return prompt_file.read_text(encoding='utf-8').strip()


def read_command():
    """Читает строку из REPL; None при Ctrl-C / конце stdin (штатный выход)."""
    try:
        return input('\n> ').strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def run_tool_loop(llm, api, world, messages):
    """Гоняет LLM и Engine по кругу, пока модель продолжает запрашивать
    инструменты, вместо одного повторного вызова."""
    for _ in range(MAX_TOOL_ROUNDS):
        location_id = world.world_state().get('location_id')
        try:
            resp = llm.chat(messages, tools=api.tools(location_id))
        except RuntimeError as e:
            return f'[ОШИБКА СВЯЗИ С LLM] {e}'
        msg = resp.get('message', {})
        messages.append(msg)
        calls = msg.get('tool_calls') or []
        if not calls:
            return msg.get('content', '')
        for call in calls:
            fn = call.get('function', {})
            name = fn.get('name')
            args = fn.get('arguments', {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            result = api.call(name, args)
            print(f'[ENGINE] {name}({args}) -> {json.dumps(result, ensure_ascii=False)}')
            messages.append({
                'role': 'tool',
                'tool_name': name,
                'content': json.dumps(result, ensure_ascii=False),
            })
    return '[ДВИЖОК] Превышен лимит вызовов инструментов за один ход — похоже на зацикленный tool-call.'


def main():
    args = parse_args()
    try:
        world_dir, world_file = resolve_world(args.world)
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(f'[WORLD] {e}')

    db_path = world_dir / 'world.db'
    db = Database(str(db_path))
    world = WorldEngine(db)
    world.load_world(world_file)
    api = ActionAPI(world)
    llm = OllamaClient(model=os.getenv('ALLIZIUM_MODEL', 'gemma4:e4b'))

    world_prompt = load_world_prompt(world_dir)
    system_prompt = ENGINE_SYSTEM
    if world_prompt:
        system_prompt += '\n\nWORLD-SPECIFIC CONTEXT:\n' + world_prompt

    messages = [{'role': 'system', 'content': system_prompt}]
    print(f'LoreGoblin Engine. World: {args.world}. Gemma: {llm.model}')
    print('Команды: /state /inventory /tools /reset (удалить текущий world.db) /quit')

    while True:
        user = read_command()
        if user is None or user == '/quit':
            break
        if user == '/state':
            print(json.dumps(world.world_state(), ensure_ascii=False, indent=2))
            continue
        if user == '/inventory':
            print(json.dumps(world.inventory(), ensure_ascii=False, indent=2))
            continue
        if user == '/tools':
            print(json.dumps(api.tools(), ensure_ascii=False, indent=2))
            continue
        if user == '/reset':
            print(f'Удалите файл {db_path} и перезапустите приложение для сброса мира.')
            continue
        messages.append({'role': 'user', 'content': user})
        reply = run_tool_loop(llm, api, world, messages)
        print('\n' + reply)

    db.close()


if __name__ == '__main__':
    main()
