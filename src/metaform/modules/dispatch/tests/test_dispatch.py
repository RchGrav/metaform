"""dispatch starts an agent on a ticket through ACP, BASE-052. The agent here is a fake ACP agent process,
fake_agent.py, so no model is called."""
from __future__ import annotations

import ast
import json
import os
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('simulation')

HERE = Path(__file__).parent
MODULE = HERE.parent
FAKE = HERE / 'fake_agent.py'
ROOT = Path(__file__).parents[5]
PUBLIC = {'metaform.module', 'metaform.settings', 'metaform.data', 'metaform.events', 'metaform.nonce'}
NODE = 'code.engine'
LINKED = 'code.store'
LIMIT = 60


def eventually(check, limit=LIMIT):
    """What `check` returns once it is truthy; the test fails when it is not within the limit."""
    deadline = time.monotonic() + limit
    while True:
        found = check()
        if found:
            return found
        if time.monotonic() > deadline:
            raise AssertionError(f'not within {limit} s')
        time.sleep(0.05)


def alive(pid):
    if os.name == 'nt':
        listed = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True, check=False).stdout
        return str(pid) in listed
    try:
        state = Path(f'/proc/{pid}/stat').read_text().split(')')[-1].split()[0]
        return state != 'Z'
    except OSError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Dispatch:
    """One ticket at NODE in the project proj, dispatch enabled, and claude's start command the fake agent."""

    def __init__(self, run, home, folder, tmp_path):
        from metaform.data import Node, Store
        self.run, self.home, self.folder = run, home, folder
        self.log = tmp_path / 'fake.jsonl'
        run('enable', 'dispatch')
        run('set', '--dispatch-claude', f'"{sys.executable}" "{FAKE}"', cwd=folder)
        self.store = Store('proj')
        self.store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
        self.store.add_element('parts', NODE)
        self.store.add_element('parts', LINKED)
        self.node = Node('element', NODE)
        self.work_id = self.store.add_work(self.node, 'missing', task='Write notes.txt',
                                           links=[Node('element', LINKED)]).work_id
        self.process = None

    def env(self, mode):
        return {**os.environ, 'METAFORM_HOME': str(self.home), 'FAKE_ACP_LOG': str(self.log),
                'FAKE_ACP_MODE': mode, 'FAKE_ACP_WORK': self.work_id, 'FAKE_SECRET': 'the-person-own-value'}

    def start(self, mode='ask'):
        """`metaform dispatch run <id> claude`, the runner, in the foreground of its own process."""
        self.process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', self.work_id, 'claude'],
                                        cwd=self.folder, env=self.env(mode), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        return self

    def entries(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding='utf-8').splitlines() if line.strip()]

    def received(self, method):
        return [entry['message'] for entry in self.entries() if entry.get('message', {}).get('method') == method]

    def logged(self, key):
        return [entry[key] for entry in self.entries() if key in entry]

    def items(self, kind):
        from metaform.data import Item
        try:
            found = self.store.layer_items('dispatch', self.node, limit=0).results
        except Exception:  # noqa: BLE001  no layer yet
            return []
        return [item for item in found if isinstance(item, Item) and (item.extra or {}).get('dispatch') == kind]

    def session(self):
        return eventually(lambda: next(iter(self.items('session')), None))

    def ticket(self):
        return self.store.ticket(self.work_id).work

    def questions(self, open=True):
        return self.store.messages(self.node, 'question', open, limit=0).results

    def stop(self):
        return self.run('dispatch', 'stop', self.work_id, '--json', cwd=self.folder)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        for pid in self.logged('grandchild'):
            if alive(pid):
                os.kill(pid, signal.SIGTERM)


@pytest.fixture
def dispatch(run, home, project_folder, tmp_path):
    made = Dispatch(run, home, project_folder, tmp_path)
    yield made
    made.close()


# ------------------------------------------------------------------ the module itself

@pytest.mark.req('BASE-052')
@pytest.mark.req('BASE-004')
@pytest.mark.kind('fixture')
def test_dispatch_is_made_from_the_template_and_imports_only_the_public_base_and_acp():
    from metaform.modules import dispatch
    assert dispatch.MODULE.id == 'dispatch' and dispatch.SHIPS_DISABLED is True
    assert (MODULE / '.github' / 'workflows' / 'checks.yml').read_text(encoding='utf-8') == \
        (MODULE.parent / 'template' / '.github' / 'workflows' / 'checks.yml').read_text(encoding='utf-8')
    assert any(requirement.startswith('agent-client-protocol') for requirement in dispatch.DEPENDENCIES)
    chassis = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['dependencies']
    assert not any('agent-client-protocol' in requirement for requirement in chassis)
    for source in MODULE.rglob('*.py'):
        if 'tests' in source.parts:
            continue
        for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else \
                [node.module or ''] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            if isinstance(node, ast.ImportFrom) and node.module == 'metaform':
                names = [f'metaform.{alias.name}' for alias in node.names]
            for name in names:
                assert not name.startswith('metaform') or name in PUBLIC, (source, name)


@pytest.mark.req('BASE-052')
@pytest.mark.kind('fixture')
def test_each_agent_has_its_start_command_as_a_setting():
    from metaform import settings
    from metaform.modules import dispatch  # noqa: F401  declares its settings
    assert settings.SCHEMA['dispatch_claude'].default == 'npx -y @agentclientprotocol/claude-agent-acp'
    assert settings.SCHEMA['dispatch_codex'].default == 'npx -y @agentclientprotocol/codex-acp'
    assert settings.SCHEMA['dispatch_gemini'].default == 'gemini --acp'


@pytest.mark.req('BASE-052')
@pytest.mark.req('QUAL-002')
@pytest.mark.kind('fixture')
def test_on_windows_npx_is_found_as_npx_cmd(monkeypatch):
    from metaform.modules import dispatch
    found = r'C:\Program Files\nodejs\npx.cmd'
    monkeypatch.setattr(dispatch.shutil, 'which', lambda name: found if name == 'npx' else None)
    assert dispatch.argv('npx -y @agentclientprotocol/claude-agent-acp', system='nt') == \
        [found, '-y', '@agentclientprotocol/claude-agent-acp']
    assert dispatch.argv(r'"C:\Tools\gem ini.exe" --acp', system='nt')[1:] == ['--acp']


@pytest.mark.req('BASE-052')
@pytest.mark.req('QUAL-002')
@pytest.mark.kind('fixture')
def test_the_agent_starts_in_its_own_process_group_and_stopping_ends_the_group(monkeypatch):
    from metaform.modules import dispatch
    assert dispatch.group_options('posix') == {'start_new_session': True}
    assert dispatch.group_options('nt')['creationflags'] & 0x00000200  # CREATE_NEW_PROCESS_GROUP
    ran = []
    monkeypatch.setattr(dispatch.subprocess, 'run', lambda command, **kwargs: ran.append(command))
    dispatch.end_group(4321, 'nt')
    assert ran == [['taskkill', '/T', '/F', '/PID', '4321']]
    if os.name != 'nt':
        killed = []
        monkeypatch.setattr(dispatch.os, 'killpg', lambda group, sent: killed.append((group, sent)))
        dispatch.end_group(4321, 'posix')
        assert killed == [(4321, signal.SIGKILL)]


# ------------------------------------------------------------------ a dispatched session

@pytest.mark.req('BASE-052')
@pytest.mark.req('QUAL-002')
def test_session_new_is_in_the_project_folder_with_metaform_mcp_and_the_person_environment(dispatch):
    dispatch.start('hold')
    new = eventually(lambda: dispatch.received('session/new'))[0]['params']
    assert Path(new['cwd']).resolve() == dispatch.folder.resolve()
    [server] = new['mcpServers']
    assert server['name'] == 'metaform' and Path(server['command']).is_absolute()
    assert server['args'] == ['-m', 'metaform', 'mcp', 'serve']
    init = dispatch.received('initialize')[0]['params']
    assert init['protocolVersion'] == 1
    capabilities = init.get('clientCapabilities', {})  # the SDK leaves out a capability that is off
    assert not any(capabilities.get('fs', {}).values()) and not capabilities.get('terminal')
    assert {entry['secret'] for entry in dispatch.entries() if 'secret' in entry} == {'the-person-own-value'}
    assert not any(entry['crlf'] for entry in dispatch.entries() if 'crlf' in entry)
    assert {tuple(entry['argv']) for entry in dispatch.entries() if 'argv' in entry} == {(str(FAKE),)}, \
        'no text of the ticket goes in an argument'
    eventually(lambda: dispatch.ticket().taken)
    second = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'run', dispatch.work_id, 'claude'],
                            cwd=dispatch.folder, env=dispatch.env('hold'), capture_output=True, text=True,
                            check=False)
    assert second.returncode != 0 and 'taken' in second.stdout + second.stderr
    assert len(dispatch.received('initialize')) == 1, 'one session per ticket'
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('BASE-050')
def test_the_ticket_is_taken_for_the_agent_with_a_nonce_and_one_prompt(dispatch, run):
    from metaform import nonce
    dispatch.start('hold')
    [prompt] = eventually(lambda: dispatch.received('session/prompt'))
    blocks = prompt['params']['prompt']
    assert len(blocks) == 1 and blocks[0]['type'] == 'text'
    assert f'metaform map work id={dispatch.work_id}' in blocks[0]['text']
    assert prompt['params']['sessionId'] == 'fake-session-1'
    ticket = dispatch.ticket()
    assert ticket.taken and ticket.taken_by == 'claude fake-session-1'
    session = dispatch.session().extra
    assert session['work_id'] == dispatch.work_id and session['session_id'] == 'fake-session-1'
    held = nonce.read(session['nonce'])
    assert held is not None and held.module == 'dispatch' and held.function == 'handoff'
    assert held.value['work_id'] == dispatch.work_id
    read = run(session['nonce'], cwd=dispatch.folder).stdout
    assert read.startswith(blocks[0]['text'].strip())
    assert NODE in read and LINKED in read, 'the nonce hands the agent the namespace nodes of its work'
    dispatch.stop()
    closed = run(session['nonce'], cwd=dispatch.folder, ok=False)
    assert (closed.stdout + closed.stderr).strip() == 'Error: Invalid or Unknown Nonce'


@pytest.mark.req('BASE-052')
def test_session_updates_become_notes_at_the_ticket_node(dispatch):
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    notes = eventually(lambda: [item for item in dispatch.items('note')
                                if 'Read file' in str(item.value) and 'completed' in str(item.value)])
    tools = [item for item in dispatch.items('note') if (item.extra or {}).get('update') in ('tool_call',
                                                                                             'tool_call_update')]
    assert len(tools) == 1, 'one note per tool call, changed in place'
    assert notes[0].extra['work_id'] == dispatch.work_id
    eventually(lambda: [item for item in dispatch.items('note') if item.value == 'Hello from fake'])
    assert [item.value for item in dispatch.items('note') if item.extra['update'] == 'agent_thought_chunk'] == \
        ['Thinking it over']
    plans = [item.value for item in dispatch.items('note') if item.extra['update'] == 'plan']
    assert plans == ['Read (completed)\nWrite (pending)'], 'one plan note, kept at its latest'
    assert dispatch.ticket().steps_done == 0, 'the steps stay the agent own, MAP-053'
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
@pytest.mark.req('QUAL-015')
def test_a_permission_request_is_a_question_and_the_answer_from_another_process_reaches_the_agent(dispatch, run):
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    assert list(question.suggestions) == ['Allow once', 'Reject']
    assert 'Write notes.txt' in question.text and question.by == 'claude fake-session-1'
    assert not dispatch.logged('permission'), 'the agent waits'
    run('map', 'reply', question.message_id, 'answer=Allow once', cwd=dispatch.folder)
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}}
    eventually(lambda: [item for item in dispatch.items('note') if item.extra['update'] == 'turn'])
    assert dispatch.process.poll() is None, 'a turn that ends with the ticket open leaves the session running'
    assert dispatch.session().extra['state'] == 'running'
    dispatch.stop()


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-052')
def test_the_answer_reaches_the_agent_when_map_changed_is_fired_and_not_before(dispatch):
    from metaform.module import Context
    from metaform.modules import dispatch as module
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    dispatch.store.reply(question.message_id, 'Reject')  # written here, and announced by no command
    time.sleep(4)  # a poll would have read it by now
    assert not dispatch.logged('permission')
    told = module.relayed({'project': 'proj', 'metaform_id': None},
                          Context(module='dispatch', folder=dispatch.folder, project='proj', store=dispatch.store))
    assert told['told'] == 1
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'reject'}}
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
def test_an_answer_that_names_no_option_is_asked_again(dispatch, run):
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    run('map', 'reply', question.message_id, 'answer=maybe later', cwd=dispatch.folder)
    [again] = eventually(dispatch.questions)
    assert again.message_id != question.message_id and list(again.suggestions) == ['Allow once', 'Reject']
    assert 'maybe later' in again.text
    assert not dispatch.logged('permission')
    run('map', 'reply', again.message_id, 'answer=allow', cwd=dispatch.folder)  # an option's id is its answer too
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome['outcome']['optionId'] == 'allow'
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_person_message_reaches_the_agent_as_session_prompt(dispatch, run):
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    sent = json.loads(run('dispatch', 'message', dispatch.work_id, 'also', 'run', 'the', 'tests', '--json',
                          cwd=dispatch.folder).stdout)
    assert sent['sent'] is True
    prompts = eventually(lambda: dispatch.received('session/prompt')[1:])
    assert prompts[0]['params']['prompt'] == [{'type': 'text', 'text': 'also run the tests'}]
    assert prompts[0]['params']['sessionId'] == 'fake-session-1'
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('QUAL-002')
def test_stop_cancels_the_session_and_ends_the_agent_process_group(dispatch):
    dispatch.start('hold')
    [grandchild] = eventually(lambda: dispatch.logged('grandchild'))
    assert alive(grandchild)
    stopped = json.loads(dispatch.stop().stdout)
    assert stopped['stopped'] is True
    assert dispatch.received('session/cancel') == [
        {'jsonrpc': '2.0', 'method': 'session/cancel', 'params': {'sessionId': 'fake-session-1'}}]
    assert dispatch.process.wait(LIMIT) == 0
    eventually(lambda: not alive(grandchild))
    assert dispatch.session().extra['state'] == 'ended'


@pytest.mark.req('BASE-052')
def test_the_session_ends_when_a_turn_ends_with_the_ticket_done(dispatch):
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT) == 0, dispatch.process.stderr.read().decode()
    assert dispatch.logged('done') == [0]
    assert dispatch.ticket().done
    assert dispatch.session().extra['state'] == 'ended'


@pytest.mark.req('BASE-052')
@pytest.mark.req('QUAL-015')
def test_start_returns_at_once_and_the_runner_goes_on_without_it(dispatch, run):
    started = json.loads(run('dispatch', 'start', dispatch.work_id, 'claude', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout)
    assert started['state'] == 'starting' and started['work_id'] == dispatch.work_id
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    eventually(lambda: dispatch.logged('grandchild'))
    assert json.loads(dispatch.stop().stdout)['stopped'] is True


@pytest.mark.req('BASE-052')
def test_start_refuses_a_ticket_already_taken(dispatch, run):
    dispatch.store.take_work(dispatch.work_id, by='someone')
    refused = run('dispatch', 'start', dispatch.work_id, 'claude', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'taken' in refused.stdout + refused.stderr
    assert not dispatch.log.exists()


@pytest.mark.req('BASE-052')
def test_message_and_stop_name_the_next_step_when_no_agent_runs(dispatch, run):
    for args in (('message', dispatch.work_id, 'hello'), ('stop', dispatch.work_id)):
        refused = run('dispatch', *args, cwd=dispatch.folder, ok=False)
        assert refused.returncode != 0
        assert f'metaform dispatch start {dispatch.work_id}' in refused.stdout + refused.stderr


@pytest.mark.req('BASE-052')
@pytest.mark.req('BASE-050')
def test_an_agent_makes_a_handoff_nonce_that_hands_the_next_agent_the_work_and_its_nodes(dispatch, run):
    from metaform import nonce
    made = run('dispatch', 'handoff', f'id={dispatch.work_id}', cwd=dispatch.folder).stdout
    [number] = [word for word in made.replace('`', ' ').split() if len(word) == 7 and word.isdigit()]
    held = nonce.read(number)
    assert held is not None and held.module == 'dispatch' and held.function == 'handoff'
    assert held.value['work_id'] == dispatch.work_id
    read = run(number, cwd=dispatch.folder).stdout
    assert f'metaform map work id={dispatch.work_id}' in read
    assert NODE in read and LINKED in read
    assert not dispatch.ticket().taken, 'making a hand-off takes nothing'


@pytest.mark.req('BASE-052')
def test_stop_answers_a_waiting_permission_request_as_cancelled(dispatch):
    dispatch.start('ask')
    eventually(dispatch.questions)
    assert json.loads(dispatch.stop().stdout)['stopped'] is True
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'cancelled'}}
    assert dispatch.process.wait(LIMIT) == 0
    assert dispatch.session().extra['how'] == 'stopped by the person'
