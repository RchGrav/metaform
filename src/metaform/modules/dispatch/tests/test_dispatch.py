"""dispatch starts an agent on a ticket through ACP, BASE-052. The agent here is a fake ACP agent process,
fake_agent.py, so no model is called."""
from __future__ import annotations

import ast
import json
import os
import shlex
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
PUBLIC = {'metaform.module', 'metaform.settings', 'metaform.data', 'metaform.events', 'metaform.nonce',
          'metaform.prompt_files'}
NODE = 'code.engine'
LINKED = 'code.store'
UNRELATED = 'code.ledger'  # a node a ticket neither is nor links
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

    def env(self, mode, **more):
        return {**os.environ, 'METAFORM_HOME': str(self.home), 'FAKE_ACP_LOG': str(self.log),
                'FAKE_ACP_MODE': mode, 'FAKE_ACP_WORK': self.work_id, 'FAKE_SECRET': 'the-person-own-value', **more}

    def start(self, mode='ask', **more):
        """`metaform dispatch run <id> claude`, the runner, in the foreground of its own process."""
        self.process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', self.work_id, 'claude'],
                                        cwd=self.folder, env=self.env(mode, **more), stdout=subprocess.PIPE,
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
        """The session rows, kind session, or the thread's lines, kind note, from the dispatch module's own tables,
        each as its value and its fields."""
        from types import SimpleNamespace

        from metaform.data import Store, StoreError
        try:
            with Store('proj', module='dispatch').tables(write=False) as tx:
                table = 'sessions' if kind == 'session' else 'lines'
                rows = sorted((dict(row) for row in tx.rows(table, limit=0).results), key=lambda row: row['seq'])
        except StoreError:
            return []
        if kind == 'session':
            return [SimpleNamespace(value=row.get('how') or row['state'], extra=row) for row in rows]
        return [SimpleNamespace(value=row['text'], extra={**row, 'update': row['kind']}) for row in rows]

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
                assert not name.startswith('xml'), (source, name, 'the prompt reader is metaform.prompt_files')


@pytest.mark.req('BASE-052')
@pytest.mark.kind('fixture')
def test_each_agent_has_its_start_command_as_a_setting(run):
    from metaform import loader, settings
    run('enable', 'dispatch')
    loader.get('dispatch')
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
    # Work f6adbefd: the session is dispatch's own field on the work record, shown when the ticket is read.
    on_record = json.loads(run('map', 'work', f'id={dispatch.work_id}', '--json', cwd=dispatch.folder).stdout)
    [shown] = on_record['dispatch']['sessions']
    assert (shown['session_id'], shown['agent'], shown['state']) == ('fake-session-1', 'claude', 'running')
    assert not {'port', 'token', 'pid', 'nonce'} & set(shown)
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
@pytest.mark.req('BASE-053')
def test_the_answer_reaches_the_agent_when_map_changed_is_fired_and_not_before(dispatch):
    from metaform import events
    from metaform.module import Context
    from metaform.modules import dispatch as module
    assert module.MODULE.subscriptions == (), 'the base relays map.changed to the runner; dispatch subscribes to nothing'
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    dispatch.store.reply(question.message_id, 'Reject')  # written here, and announced by no command
    session = dispatch.session().extra
    assert 'error' in module.tell(session, 'changed'), 'the control port takes no change; the base relays it'
    events.publish('map.changed', {'project': 'another', 'metaform_id': None},
                   Context(module='chassis', folder=dispatch.folder, project='another'))
    time.sleep(4)  # a poll would have read it by now, and a change to another project is not this runner's
    assert not dispatch.logged('permission')
    deliveries = events.publish('map.changed', {'project': 'proj', 'metaform_id': None},
                                Context(module='chassis', folder=dispatch.folder, project='proj'))
    assert [delivery['status'] for delivery in deliveries if delivery['module'] == 'dispatch'] == ['completed'], \
        'published in this process, handed by the base to the runner\'s listener'
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


def asked_by_the_agent(dispatch):
    """The question the fake agent asked with the real command line at UNRELATED, a node its ticket neither is nor
    links, while its first turn keeps working."""
    from metaform.data import Node
    [printed] = eventually(lambda: dispatch.logged('asked'))
    [mine] = dispatch.store.messages(Node('element', UNRELATED), 'question', True, limit=0).results
    assert mine.message_id in printed, 'the agent was shown the id of the question it asked'
    return mine


def told(dispatch):
    """The text of each prompt the agent was sent after its first."""
    return [message['params']['prompt'][0]['text'] for message in dispatch.received('session/prompt')[1:]]


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
@pytest.mark.req('QUAL-015')
def test_a_question_the_agent_asked_is_told_to_it_once_when_it_is_answered(dispatch, run):
    dispatch.store.add_element('parts', UNRELATED)
    dispatch.start('question', FAKE_ACP_ASK_AT=UNRELATED, FAKE_ACP_QUESTION_HOLD='1')
    mine = asked_by_the_agent(dispatch)
    run('map', 'tell', NODE, 'A change before the answer', 'by=test', cwd=dispatch.folder)  # the runner checks
    time.sleep(1)
    assert told(dispatch) == [], 'a change to the map before the answer tells the agent nothing'
    run('map', 'reply', mine.message_id, 'answer=Yes, keep it', cwd=dispatch.folder)
    [text] = eventually(lambda: told(dispatch))
    assert mine.message_id in text and 'Is the store kept?' in text and 'Yes, keep it' in text
    assert dispatch.received('session/prompt')[1]['params']['sessionId'] == 'fake-session-1'
    eventually(lambda: [item for item in dispatch.items('note') if item.extra['update'] == 'answered'])
    run('map', 'tell', NODE, 'A change after the answer', 'by=test', cwd=dispatch.folder)  # the runner checks again
    time.sleep(1)
    assert told(dispatch) == [text], 'the answer is told once'
    assert [item.value for item in dispatch.items('note') if item.extra['update'] == 'answered'] == [text]
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
def test_a_question_another_asked_while_the_agent_was_idle_is_not_told_to_it_though_it_read_it(dispatch, run):
    dispatch.store.add_element('parts', UNRELATED)
    dispatch.start('question', FAKE_ACP_ASK_AT=UNRELATED, FAKE_ACP_QUESTION_HOLD='1')
    mine = asked_by_the_agent(dispatch)
    time.sleep(1.1)  # the store keeps a question's time to the second
    other = dispatch.store.ask(dispatch.node, 'Is the engine kept?', by='another agent')
    time.sleep(1.1)
    run('dispatch', 'message', dispatch.work_id, 'read the questions', cwd=dispatch.folder)
    [listed] = eventually(lambda: dispatch.logged('listed'))
    assert other.message_id in listed, 'the agent read the other question in a tool call of its next turn'
    run('map', 'reply', other.message_id, 'answer=No', cwd=dispatch.folder)
    run('map', 'reply', mine.message_id, 'answer=Yes, keep it', cwd=dispatch.folder)
    eventually(lambda: told(dispatch)[1:])
    time.sleep(1)
    answered = told(dispatch)[1:]  # after the person's message
    assert len(answered) == 1 and mine.message_id in answered[0] and other.message_id not in answered[0], answered
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
@pytest.mark.req('CLI-003')
def test_the_help_shows_how_a_message_that_is_a_switch_name_reaches_the_agent_as_written(dispatch, run):
    page = run('help', 'dispatch', 'message').stdout
    example = next((line.strip() for line in page.splitlines()
                    if line.strip().startswith('metaform dispatch message') and ' -- ' in line), None)
    assert example is not None, page
    words = shlex.split(example)[3:]
    assert words[0] == '198452e1...' and words[1:] == ['--', '--json'], example
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    run('dispatch', 'message', dispatch.work_id, *words[1:], cwd=dispatch.folder)
    prompts = eventually(lambda: dispatch.received('session/prompt')[1:])
    assert prompts[0]['params']['prompt'] == [{'type': 'text', 'text': '--json'}]
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
def test_start_returns_at_once_and_the_runner_goes_on_without_it(dispatch, run, dispatch_runners):
    started = json.loads(run('dispatch', 'start', dispatch.work_id, 'claude', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
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
def test_a_second_start_on_one_ticket_is_refused_at_once(dispatch, run, dispatch_runners):
    """Found 2026-10-03 with the ghost agents: f566b181 had two sessions from two starts, since start checked the
    ticket and the runner took it only after the agent had started. Start takes the ticket in the write that checks it."""
    first = json.loads(run('dispatch', 'start', dispatch.work_id, 'claude', '--json', cwd=dispatch.folder,
                           env=dispatch.env('hold')).stdout)
    dispatch_runners.append((first, dispatch.folder, dispatch.log))
    assert dispatch.ticket().taken, 'the ticket is taken when start returns, before the agent has started'
    second = run('dispatch', 'start', dispatch.work_id, 'claude', cwd=dispatch.folder, ok=False,
                 env=dispatch.env('hold'))
    assert second.returncode != 0 and 'taken' in second.stdout + second.stderr
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    assert len(dispatch.items('session')) == 1
    assert json.loads(dispatch.stop().stdout)['stopped'] is True


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


@pytest.mark.req('BASE-052')
def test_dispatch_prompts_approve_all_answers_every_request_without_asking(dispatch, run):
    """Rich, 2026-10-03: a setting sets the default behavior for an agent's interactive prompts: approve-all,
    approve-reads or ask_all. With approve-all, Metaform answers each request with its allow option, and the thread
    says so."""
    run('set', '--dispatch-prompts=approve-all', cwd=dispatch.folder)
    dispatch.start('ask')
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}}
    assert not dispatch.questions()
    assert eventually(lambda: [item for item in dispatch.items('note') if 'Write notes.txt' in str(item.value)
                               and item.extra['update'] == 'approved'])
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_dispatch_prompts_approve_reads_answers_a_read_without_asking(dispatch, run):
    run('set', '--dispatch-prompts=approve-reads', cwd=dispatch.folder)
    dispatch.start('ask', FAKE_ACP_ASK_KIND='read', FAKE_ACP_ASK_TITLE='Read notes.txt')
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}} and not dispatch.questions()
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_dispatch_prompts_approve_reads_asks_for_anything_but_a_read(dispatch, run):
    run('set', '--dispatch-prompts=approve-reads', cwd=dispatch.folder)
    dispatch.start('ask')  # an edit is no read: asked as ask_all asks it
    [question] = eventually(dispatch.questions)
    assert 'Write notes.txt' in question.text and not dispatch.logged('permission')
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_dispatch_prompts_is_read_at_each_request_so_a_change_reaches_a_running_agent(dispatch, run):
    from metaform.modules.dispatch import runner
    source = Path(runner.__file__).read_text(encoding='utf-8')
    request = source[source.index('async def request_permission'):source.index('async def ask(')]
    assert "'dispatch_prompts'" in request, 'the setting is read when the request arrives, not at start'
    from metaform import loader, settings
    loader.get('dispatch')  # a cached direct import cannot restore settings withdrawn by loader.reset()
    found = settings.SCHEMA['dispatch_prompts']
    assert list(found.choices) == ['approve-all', 'approve-reads', 'ask_all'] and found.default == 'ask_all'


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-034')
def test_a_dispatched_agent_writes_nothing_on_the_map_and_its_session_and_transcript_are_dispatch_tables(dispatch):
    """Rich, 2026-10-03: a node holds one note, so agents keep what they learn as memories; an agent's working log
    is no pile of items at the node. The session and its transcript are the dispatch module's own tables, STORE-045."""
    dispatch.start('ask')
    eventually(dispatch.questions)
    assert 'dispatch' not in [layer.name for layer in dispatch.store.layers(limit=0).results]
    from metaform.data import Store
    with Store('proj', module='dispatch').tables(write=False) as tx:
        sessions = list(tx.rows('sessions', limit=0).results)
        lines = list(tx.rows('lines', limit=0).results)
    assert [(row['work_id'], row['state']) for row in sessions] == [(dispatch.work_id, 'running')]
    assert [row['text'] for row in lines if row['kind'] == 'agent_message_chunk'] == ['Hello from fake']
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-035')
def test_a_session_that_ends_without_finishing_its_ticket_releases_it(dispatch):
    """Rich, 2026-10-03: a figure circled a node with no agent behind it, because a stopped agent left its ticket
    taken. A session that ends with its ticket not done gives the ticket back, so it waits for the next agent."""
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    assert dispatch.ticket().taken
    dispatch.stop()
    eventually(lambda: dispatch.ticket().taken is None or None)
    assert dispatch.ticket().done is None


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-035')
def test_a_session_ends_when_its_ticket_is_done_whatever_turn_closed_it(dispatch, run):
    """Found 2026-10-03: an agent closed its ticket in a turn it woke itself into, and the runner, which looked only when
    a turn it sent ended, kept the session idling. A map change tells the runner to look, and a done ticket ends it."""
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    run('map', 'reply', question.message_id, 'answer=Allow once', cwd=dispatch.folder)
    eventually(lambda: [item for item in dispatch.items('note') if item.extra['update'] == 'turn'])  # idle, ticket open
    assert dispatch.session().extra['state'] == 'running'
    run('map', 'work', 'op=done', f'id={dispatch.work_id}', 'resolution=closed elsewhere', cwd=dispatch.folder)
    assert eventually(lambda: dispatch.session().extra['state'] == 'ended' or None)
    assert dispatch.session().extra['how'] == 'the ticket is done'


@pytest.mark.req('BASE-053')
@pytest.mark.req('VIEW-018')
def test_a_line_of_the_thread_announces_only_dispatchs_tables_and_a_write_to_the_map_announces_the_map(dispatch):
    """A line the runner writes to its thread changes no map, so its map.changed names the dispatch tables and an open
    page reads only its agents again; a question the runner asks is a write to the map and is announced plainly."""
    from metaform import relay
    heard = []
    with relay.listen('probe', heard.append):
        dispatch.start('ask')
        eventually(dispatch.questions)
        eventually(lambda: [one for one in heard if one.get('tables') == 'dispatch'])
        eventually(lambda: [one for one in heard if 'tables' not in one])
    assert {one.get('tables') for one in heard} <= {'dispatch', None}, heard
    dispatch.stop()


@pytest.mark.req('VIEW-039')
def test_the_sessions_read_leaves_the_threads_out_when_asked(dispatch, run):
    """The agents key needs only the sessions; the threads of every session are read only for the window that shows
    one."""
    dispatch.start('ask')
    eventually(dispatch.questions)
    whole = json.loads(run('dispatch', 'sessions', '--json', cwd=dispatch.folder).stdout)
    assert whole['sessions'] and whole['lines']
    bare = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)
    assert bare['sessions'] == whole['sessions'][:len(bare['sessions'])] and bare['lines'] == []
    dispatch.stop()


# ------------------------------------------------------------------ one agent per glyph, VIEW-040

def glyphed(dispatch, run, *tickets):
    """Tickets at NODE, each given as (task, glyph, held), the glyph set through the map module as the board's
    Distribute and `map work op=edit glyph=` set it; a glyph of None leaves the ticket with none."""
    made = []
    for task, glyph, held in tickets:
        work_id = dispatch.store.add_work(dispatch.node, 'missing', task=task, held=held).work_id
        if glyph is not None:
            run('map', 'work', 'op=edit', f'id={work_id}', f'glyph={glyph}', cwd=dispatch.folder)
        made.append(work_id)
    return made


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-052')
def test_one_agent_per_glyph_works_the_glyphs_tickets_in_turn_in_board_order(dispatch, run):
    """Rich, 2026-10-03, VIEW-040: tickets with the same glyph are one agent's, done one at a time. The agent started on
    a ticket with a glyph takes that glyph's tickets one after another in board order, To do before Backlog, each by
    its place, the next taken when the one before is done; a ticket of another glyph, one with none, and one taken
    by someone else are not its own."""
    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    other, held, later, top, loose, busy = glyphed(
        dispatch, run, ('Another agent', 'moth', False), ('Held', 'kite', True), ('Later', 'kite', False),
        ('Top', 'kite', False), ('No glyph', None, False), ('Busy', 'kite', False))
    dispatch.store.move_work(top, 'todo', 0)
    dispatch.store.move_work(held, 'backlog', 0)  # placed first in Backlog, and still after every To do ticket
    dispatch.store.take_work(busy, by='someone')
    [unplaced] = glyphed(dispatch, run, ('Unplaced', 'kite', False))  # in To do with no place: after those placed
    assert dispatch.store.ticket(unplaced).work.position is None and dispatch.store.ticket(held).work.position == 0
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT * 5) == 0, dispatch.process.stderr.read().decode()
    worked = [dispatch.work_id, top, later, unplaced, held]
    assert dispatch.logged('work') == worked
    order = [('start' if entry.get('message', {}).get('method') == 'initialize' else 'done')
             for entry in dispatch.entries() if 'done' in entry or entry.get('message', {}).get('method') == 'initialize']
    assert order == ['start', 'done'] * 5, 'one agent at a time: each starts after the ticket before it is done'
    sessions = [item.extra for item in dispatch.items('session')]
    assert [session['work_id'] for session in sessions] == worked
    assert {(session['state'], session['how']) for session in sessions} == {('ended', 'the ticket is done')}
    assert all(dispatch.store.ticket(work_id).work.done for work_id in worked)
    for work_id in (other, loose):
        assert dispatch.store.ticket(work_id).work.taken is None
    assert dispatch.store.ticket(busy).work.taken_by == 'someone'


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-052')
def test_a_ticket_with_no_glyph_is_worked_alone(dispatch, run):
    """VIEW-040: a ticket with no glyph is no agent's lane; the agent started on it ends with it, and the tickets with no
    glyph waiting beside it stay where they are."""
    [beside] = glyphed(dispatch, run, ('Beside', None, False))
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT) == 0, dispatch.process.stderr.read().decode()
    assert dispatch.logged('work') == [dispatch.work_id]
    assert dispatch.store.ticket(beside).work.taken is None


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-052')
def test_a_ticket_whose_glyph_has_an_agent_at_work_is_not_started_and_another_glyphs_is(dispatch, run):
    """VIEW-040: one agent per glyph. While the glyph's agent works one of its tickets, start and run refuse another
    ticket of that glyph and name the ticket being worked; a ticket of another glyph starts its own agent. Stopping the
    agent ends its turn through the glyph's tickets."""
    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    later, other = glyphed(dispatch, run, ('Later', 'kite', False), ('Another agent', 'moth', False))
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    for verb in ('start', 'run'):
        refused = run('dispatch', verb, later, 'claude', cwd=dispatch.folder, env=dispatch.env('done'), ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and 'kite' in said and dispatch.work_id in said, said
    assert dispatch.store.ticket(later).work.taken is None
    own = run('dispatch', 'run', other, 'claude', '--json', cwd=dispatch.folder, env=dispatch.env('done'))
    assert json.loads(own.stdout)['work_id'] == other
    assert dispatch.store.ticket(other).work.done
    dispatch.stop()
    assert dispatch.process.wait(LIMIT) == 0
    assert dispatch.store.ticket(later).work.taken is None, 'a stopped agent takes no further ticket'


# ------------------------------------------------------------------ eligible agents, ticket bd96cbd1

def eligible(dispatch, run, work_id, *agents):
    run('map', 'work', 'op=edit', f'id={work_id}', 'eligible=' + json.dumps(list(agents)), cwd=dispatch.folder)


@pytest.mark.req('MAP-058')
@pytest.mark.req('BASE-052')
def test_start_and_run_refuse_an_agent_the_ticket_does_not_list_and_name_the_ones_it_does(dispatch, run):
    """Ticket bd96cbd1: explicit dispatch honors the eligible agents. Codex started on a ticket only Claude is
    eligible for is refused, by start and by run, with claude named, and the ticket stays untaken."""
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE}"', cwd=dispatch.folder)
    eligible(dispatch, run, dispatch.work_id, 'claude')
    for verb in ('start', 'run'):
        refused = run('dispatch', verb, dispatch.work_id, 'codex', cwd=dispatch.folder, env=dispatch.env('done'),
                      ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and 'claude' in said and 'codex' in said, said
        assert dispatch.ticket().taken is None
    assert dispatch.items('session') == []


@pytest.mark.req('MAP-058')
@pytest.mark.req('VIEW-040')
def test_the_glyphs_agent_takes_only_the_tickets_it_is_eligible_for_and_the_others_keep_their_glyph(dispatch, run):
    """Ticket bd96cbd1: automatic selection of the next ticket honors the eligible agents while keeping the glyph
    assignment and the board order. The claude agent of glyph kite works its own and Any tickets in board order and
    passes a ticket only Codex is eligible for, which keeps glyph kite and stays untaken."""
    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    codex_only, anyone, claude_only = glyphed(
        dispatch, run, ('Codex only', 'kite', False), ('Anyone', 'kite', False), ('Claude only', 'kite', False))
    eligible(dispatch, run, codex_only, 'codex')
    eligible(dispatch, run, claude_only, 'claude', 'gemini')
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT * 4) == 0, dispatch.process.stderr.read().decode()
    assert dispatch.logged('work') == [dispatch.work_id, anyone, claude_only]
    skipped = json.loads(run('map', 'work', f'id={codex_only}', '--json', cwd=dispatch.folder).stdout)
    assert skipped['taken'] is None and skipped['map']['glyph'] == 'kite'


@pytest.mark.req('MAP-058')
@pytest.mark.req('VIEW-042')
def test_autostart_starts_each_ticket_with_an_agent_eligible_for_it(dispatch, run, monkeypatch):
    """Ticket bd96cbd1: an automatic start honors the eligible agents. The configured agent starts the tickets it is
    eligible for; a ticket that lists other agents is started with the first of them, so it is not left waiting."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    claude_only, = glyphed(dispatch, run, ('Claude only', None, False))
    eligible(dispatch, run, claude_only, 'claude')
    run('set', '--dispatch-autostart', '--dispatch-agent', 'codex', cwd=dispatch.folder)
    launched = []
    monkeypatch.setattr(module, 'start', lambda ctx: launched.append((ctx.nouns['id'], ctx.nouns['agent'])) or
                        {'work_id': ctx.nouns['id']})
    module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert launched == [(dispatch.work_id, 'codex'), (claude_only, 'claude')]
