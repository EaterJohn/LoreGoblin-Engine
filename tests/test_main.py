import json

import pytest

import main
from engine.actions import ActionAPI


class FakeLLM:
    """Подменяет OllamaClient: отдаёт заготовленные ответы по очереди,
    последний повторяется бесконечно (для проверки лимита раундов)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.tool_names_seen = []

    def chat(self, messages, tools=None):
        self.tool_names_seen.append({t['function']['name'] for t in tools or []})
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response


def say(text):
    return {'message': {'role': 'assistant', 'content': text}}


def call(name, arguments):
    return {
        'message': {
            'role': 'assistant',
            'content': '',
            'tool_calls': [{'function': {'name': name, 'arguments': arguments}}],
        }
    }


@pytest.fixture
def run(world):
    api = ActionAPI(world)

    def _run(llm):
        messages = [{'role': 'user', 'content': 'привет'}]
        return main.run_tool_loop(llm, api, world, messages), messages

    return _run


def test_plain_answer_needs_no_tools(run):
    reply, messages = run(FakeLLM(say('Добро пожаловать')))
    assert reply == 'Добро пожаловать'
    assert messages[-1]['content'] == 'Добро пожаловать'


def test_tool_result_is_fed_back_to_the_model(run):
    reply, messages = run(FakeLLM(call('get_world_state', {}), say('Полдень')))
    assert reply == 'Полдень'
    tool_msg = next(m for m in messages if m['role'] == 'tool')
    assert tool_msg['tool_name'] == 'get_world_state'
    assert json.loads(tool_msg['content'])['world_time'] == 'Day 1 12:00'


def test_arguments_may_arrive_as_json_string(run, world):
    run(FakeLLM(call('advance_time', '{"minutes": 30}'), say('ok')))
    assert world.world_state()['world_time'] == 'Day 1 12:30'


@pytest.mark.parametrize('arguments', ['{not json', ['x'], 42, None])
def test_garbage_arguments_do_not_crash_the_loop(run, world, arguments):
    reply, messages = run(FakeLLM(call('advance_time', arguments), say('ok')))
    assert reply == 'ok'
    tool_msg = next(m for m in messages if m['role'] == 'tool')
    assert json.loads(tool_msg['content'])['ok'] is False
    assert world.world_state()['world_time'] == 'Day 1 12:00'


def test_tool_surface_follows_engine_mode(run):
    llm = FakeLLM(call('start_trade', {}), say('Борис кивает'))
    run(llm)
    assert 'start_trade' in llm.tool_names_seen[0]
    assert llm.tool_names_seen[1] == {'get', 'buy', 'end'}


def test_round_limit_stops_runaway_tool_calls(run):
    llm = FakeLLM(call('get_world_state', {}))
    reply, _ = run(llm)
    assert 'лимит' in reply
    assert len(llm.tool_names_seen) == main.MAX_TOOL_ROUNDS


def test_llm_failure_is_reported_not_raised(run):
    reply, _ = run(FakeLLM(RuntimeError('нет связи')))
    assert reply.startswith('[ОШИБКА СВЯЗИ С LLM]')
    assert 'нет связи' in reply


@pytest.mark.parametrize('name', ['', '   ', '..', '../x', 'a/b', '/etc'])
def test_resolve_world_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        main.resolve_world(name)


def test_resolve_world_unknown_world():
    with pytest.raises(FileNotFoundError):
        main.resolve_world('no_such_world')


def test_resolve_world_bundled_worlds():
    for world_id in ('allizium', 'station_demo'):
        world_dir, world_file = main.resolve_world(world_id)
        assert world_dir.name == world_id
        assert world_file.name == 'world.json'


def test_load_world_prompt(tmp_path):
    assert main.load_world_prompt(tmp_path) == ''
    (tmp_path / 'system_prompt.txt').write_text('\n  Тон: мрачный  \n', encoding='utf-8')
    assert main.load_world_prompt(tmp_path) == 'Тон: мрачный'


def test_read_command_returns_none_on_eof(monkeypatch):
    def eof(_prompt):
        raise EOFError

    monkeypatch.setattr('builtins.input', eof)
    assert main.read_command() is None
