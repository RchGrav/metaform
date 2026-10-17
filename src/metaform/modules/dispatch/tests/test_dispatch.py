"""dispatch starts an agent on a ticket through ACP, BASE-052. The agent here is a fake ACP agent process,
fake_agent.py, so no model is called."""
from __future__ import annotations

import ast
import asyncio
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import acp
import pytest

pytestmark = pytest.mark.kind('simulation')

HERE = Path(__file__).parent
MODULE = HERE.parent
FAKE = HERE / 'fake_agent.py'
ROOT = Path(__file__).parents[5]
PUBLIC = {'metaform.module', 'metaform.settings', 'metaform.data', 'metaform.events',
          'metaform.prompt_files', 'metaform.home', 'metaform.jev'}  # Jev, the decision service
NODE = 'code.engine'
LINKED = 'code.store'
UNRELATED = 'code.ledger'  # a node a ticket neither is nor links


def skip_while_unlocked():
    """A test of the lock on unlinked files is skipped while Rich has it off, code#1e."""
    from metaform.modules.dispatch.runner import LINK_LOCK
    if not LINK_LOCK:
        pytest.skip('the lock on unlinked files is off until the rules and prompts for linking are in place, code#1e')


def skip_while_unsandboxed():
    """A test of the command sandbox is skipped while it is off, kept apart from the lock after the 2026-10-15
    crash."""
    from metaform.modules.dispatch.runner import SHELL_SANDBOX
    skip_while_unlocked()
    if not SHELL_SANDBOX:
        pytest.skip('the command sandbox is off until the person turns it on after one agent has run with it')
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


def end_agent(log, forced):
    """End the fake agent a test's runner started, and the child it started, with their process group, as the runner's
    own end does, BASE-052: the agent has a group of its own, so ending the runner alone leaves it behind. After the
    runner was ended by force, read its log until the agent has logged its PID, for up to 5 s, since an agent already
    starting can log it late. Once its PID is known, ending its group also ends a child it started and has not logged
    yet, which runs in that group. Returns the PIDs found."""
    from metaform.modules.dispatch import end_group
    children = set()
    agent = False
    deadline = time.monotonic() + 5
    while True:
        try:
            if log.exists():
                for line in log.read_text(encoding='utf-8').splitlines():
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:  # teardown can meet a line the agent is still writing
                        continue
                    agent = agent or 'pid' in entry
                    children.update(entry[key] for key in ('pid', 'grandchild') if key in entry)
        finally:
            for child in children:  # an agent that ended on its own still names the group its child runs in
                end_group(child)
        if not forced or agent or time.monotonic() >= deadline:
            return children
        time.sleep(0.05)


def gone(pids, limit=5):
    """Whether every one of the PIDs has ended within the limit."""
    deadline = time.monotonic() + limit
    while any(alive(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not any(alive(pid) for pid in pids)


class Dispatch:
    """One ticket at NODE in the project proj, dispatch enabled, and claude's start command the fake agent."""

    def __init__(self, run, home, folder, tmp_path):
        from metaform.data import Node, Store
        self.run, self.home, self.folder = run, home, folder
        self.log = tmp_path / 'fake.jsonl'
        run('enable', 'dispatch')
        for agent in ('claude', 'codex', 'gemini'):  # every agent is the fake, so no test ever starts a real one
            run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{FAKE}"', cwd=folder)
        self.store = Store('proj')
        self.store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
        self.store.add_element('parts', NODE)
        self.store.add_element('parts', LINKED)
        self.node = Node('element', NODE)
        self.id = self.store.add_work(self.node, 'unbuilt', task='Write notes.txt',
                                           links=[Node('element', LINKED)]).id
        self.process = None

    def env(self, mode, **more):
        return {**os.environ, 'METAFORM_HOME': str(self.home), 'FAKE_ACP_LOG': str(self.log),
                'FAKE_ACP_MODE': mode, 'FAKE_ACP_WORK': self.id, 'FAKE_SECRET': 'the-person-own-value', **more}

    def start(self, mode='ask', *nouns, **more):
        """`metaform dispatch run <id> claude`, the runner, in the foreground of its own process; nouns such as
        system=true go after it."""
        self.process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', self.id, 'claude',
                                         *nouns], cwd=self.folder, env=self.env(mode, **more), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        return self

    def entries(self):
        """Each whole line the fake agent has logged. The agent appends while a test reads, and a long line, such as
        a logged prompt, can be read half written; only what ends in a newline is complete, so the rest is left for
        the next read rather than parsed, whatever the timing."""
        if not self.log.exists():
            return []
        written = self.log.read_bytes()
        whole = written[:written.rfind(b'\n') + 1].decode('utf-8')
        return [json.loads(line) for line in whole.splitlines() if line.strip()]

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
                table = 'agent_sessions' if kind == 'session' else 'session_lines'
                rows = [dict(row) for row in tx.rows(table, limit=0).results]
            if kind != 'session':  # with the signals and a ticket's progress, which are kept beside the map
                with Store('proj', module='dispatch').tables(write=False) as tx:
                    rows += [dict(row) for row in tx.rows('lines', limit=0).results]
            rows.sort(key=lambda row: row['seq'])
        except StoreError:
            return []
        if kind == 'session':
            return [SimpleNamespace(value=row.get('how') or row['state'], extra=row) for row in rows]
        return [SimpleNamespace(value=row['text'], extra={**row, 'update': row['kind']}) for row in rows]

    def session(self):
        return eventually(lambda: next(iter(self.items('session')), None))

    def ticket(self):
        return self.store.ticket(self.id).work

    def questions(self, open=True):
        return self.store.messages(self.node, 'question', open, limit=0).results

    def stop(self):
        """Stop the agent. A session ends by itself when a turn ends with its ticket open, so a stop that finds none
        running is cleanup already done; a test that needs the stop's own report reads its JSON."""
        result = self.run('dispatch', 'stop', self.id, '--json', cwd=self.folder, ok=False)
        if result.returncode != 0 and 'No agent is running' not in result.stdout + result.stderr:
            raise AssertionError(f'metaform dispatch stop failed ({result.returncode}):\n{result.stdout}{result.stderr}')
        return result

    def close(self):
        forced = self.process is not None and self.process.poll() is None
        if forced:
            self.process.kill()
            self.process.wait()
        assert gone(end_agent(self.log, forced)), 'the fake agent or its child survived its runner'


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
    chassis = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['metaform']['chassis-dependencies']
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
    # each pinned at the version the ACP Registry lists for claude-acp, codex-acp and gemini, P013
    assert settings.SCHEMA['dispatch_claude'].default == 'npx -y @agentclientprotocol/claude-agent-acp@0.89.1'
    assert settings.SCHEMA['dispatch_codex'].default == 'npx -y @agentclientprotocol/codex-acp@2.2.2'
    assert settings.SCHEMA['dispatch_gemini'].default == 'npx -y @google/gemini-cli@0.63.0 --acp'


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

def test_a_worker_s_first_turn_tells_the_prompt_versions_it_carried_and_agents_keeps_them(dispatch):
    """Ticket 3a1306bd: dispatch serves its prompts through the prompt store and its runner tells each turn's versions
    on prompt.sent, which the agents module keeps for its sent verb."""
    dispatch.start('hold')
    eventually(lambda: dispatch.received('session/prompt'))
    session = dispatch.session().extra['session_id']

    def kept():
        found = dispatch.run('agents', 'sent', f'session={session}', '--json', cwd=dispatch.folder, ok=False)
        return json.loads(found.stdout) if found.returncode == 0 else None
    sent = eventually(kept)
    assert (sent['role'], sent['agent'], sent['work_id']) == ('worker', 'claude', dispatch.id)
    assert {'name': 'dispatch:work', 'versions': [1]} in sent['prompts']
    dispatch.stop()


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
    # the runner's own files and terminals, P019, on by default and confined to the folder
    assert all(capabilities['fs'].values()) and capabilities['terminal'] is True
    assert {entry['secret'] for entry in dispatch.entries() if 'secret' in entry} == {'the-person-own-value'}
    assert not any(entry['crlf'] for entry in dispatch.entries() if 'crlf' in entry)
    assert {tuple(entry['argv']) for entry in dispatch.entries() if 'argv' in entry} == {(str(FAKE),)}, \
        'no text of the ticket goes in an argument'
    eventually(lambda: dispatch.ticket().taken)
    second = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'run', dispatch.id, 'claude'],
                            cwd=dispatch.folder, env=dispatch.env('hold'), capture_output=True, text=True,
                            check=False)
    assert second.returncode != 0 and 'taken' in second.stdout + second.stderr
    assert len(dispatch.received('initialize')) == 1, 'one session per ticket'
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_the_mcp_server_is_named_metaform_variables_and_codex_runs_it_over_its_own_config(dispatch):
    dispatch.start('hold', METAFORM_PROBE='kept')
    [server] = eventually(lambda: dispatch.received('session/new'))[0]['params']['mcpServers']
    given = {entry['name']: entry['value'] for entry in server['env']}
    assert given['METAFORM_HOME'] == str(dispatch.home) and given['METAFORM_PROBE'] == 'kept'
    assert all(name.startswith('METAFORM_') for name in given), 'only Metaform variables are named'
    assert (given['METAFORM_ROLE'], given['METAFORM_WORK'], given['METAFORM_NODE']) == ('worker', dispatch.id, NODE)
    assert given['METAFORM_SESSION'] == dispatch.session().extra['runner'], 'the identity reaches the server itself'
    assert {entry['filtering'] for entry in dispatch.entries() if 'filtering' in entry} == {'true'}
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('BASE-050')
def test_the_ticket_is_taken_for_the_agent_with_one_prompt_and_its_handoff_read_by_ticket_id(dispatch, run):
    dispatch.start('hold')
    [prompt] = eventually(lambda: dispatch.received('session/prompt'))
    blocks = prompt['params']['prompt']
    assert [block['type'] for block in blocks] == ['text', 'resource_link', 'resource_link'], 'one prompt, its links typed'
    memory, _, handed = blocks[0]['text'].partition(f'\n\nWork ticket {dispatch.id} with the map_work tool')
    assert memory.startswith('Follow these steps for each interaction:\n') and handed, \
        "the owner's memory prompt first, then the work sentence, CTX-028"
    assert f'   - This is {NODE} (' in memory and '{' not in memory, "filled with the ticket's element, CTX-027"
    assert prompt['params']['sessionId'] == 'fake-session-1'
    ticket = dispatch.ticket()
    assert ticket.taken and ticket.taken_by == 'claude fake-session-1'
    session = dispatch.session().extra
    assert session['work_id'] == dispatch.id and session['session_id'] == 'fake-session-1'
    # Work f6adbefd: the session is dispatch's own field on the work record, shown when the ticket is read.
    on_record = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    [shown] = on_record['dispatch']['sessions']
    assert (shown['session_id'], shown['agent'], shown['state']) == ('fake-session-1', 'claude', 'running')
    assert not {'port', 'token', 'pid', 'nonce', 'recovery'} & set(shown)
    assert session['nonce'] is None, 'the session and its identity carry the work; no nonce is requested'
    assert (session['recovery']['work_id'], session['recovery']['session_id']) == (dispatch.id, 'fake-session-1')
    read = run('dispatch', 'handoff', f'id={dispatch.id}', cwd=dispatch.folder).stdout
    assert read.partition('\n')[0] == f'Work ticket {dispatch.id} with the map_work tool{handed}'.partition('\n')[0], \
        'the same work line on every surface'
    assert NODE in read and LINKED in read, 'the handoff gives the agent the namespace nodes of its work'
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_session_updates_become_notes_at_the_ticket_node(dispatch):
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    notes = eventually(lambda: [item for item in dispatch.items('note')
                                if 'Read file' in str(item.value) and 'completed' in str(item.value)])
    tools = [item for item in dispatch.items('note') if (item.extra or {}).get('update') in ('tool_call',
                                                                                             'tool_call_update')]
    assert len(tools) == 1, 'one note per tool call, changed in place'
    assert notes[0].extra['work_id'] == dispatch.id
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
    run('map', 'reply', question.id, 'answer=Allow once', cwd=dispatch.folder)
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}}
    from metaform.modules.dispatch import (
        tell,  # the turn ends with the ticket open: the session stays, idle and reachable
    )
    eventually(lambda: tell(dispatch.session().extra, 'status')['activity'] == 'idle' or None)
    assert dispatch.process.poll() is None and dispatch.ticket().taken, 'nothing restarts by itself'
    dispatch.stop()


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-052')
@pytest.mark.req('BASE-053')
def test_the_answer_reaches_the_agent_when_map_changed_is_fired_and_not_before(dispatch):
    from metaform import events
    from metaform.module import Context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.progress import changed as progress_changed
    assert [one.handler for one in module.MODULE.subscriptions if one.topic == 'map.changed'] == [progress_changed], \
        'the base relays map.changed to the runner; dispatch\'s one map.changed subscriber is progress, no relay'
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    dispatch.store.reply(question.id, 'Reject')  # written here, and announced by no command
    session = dispatch.session().extra
    assert 'error' in module.tell(session, 'changed'), 'the control port takes no change; the base relays it'
    events.publish('map.changed', {'project': 'another', 'base_id': None},
                   Context(module='chassis', folder=dispatch.folder, project='another'))
    time.sleep(4)  # a poll would have read it by now, and a change to another project is not this runner's
    assert not dispatch.logged('permission')
    deliveries = events.publish('map.changed', {'project': 'proj', 'base_id': None},
                                Context(module='chassis', folder=dispatch.folder, project='proj'))
    assert [delivery['status'] for delivery in deliveries if delivery['module'] == 'dispatch'] == ['completed'] * 2, \
        'published in this process: once to dispatch\'s progress subscriber, once handed by the base to the runner\'s listener'
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'reject'}}
    dispatch.stop()


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-053')
def test_a_ticket_change_reads_one_work_record_without_loading_its_context(dispatch, monkeypatch):
    """A runner needs completion and steps, even when its ticket links a context it must not rebuild per event."""
    from metaform.data import Store
    from metaform.data import store as stores
    from metaform.module import context
    from metaform.modules.dispatch import runner

    store = Store('proj', module='dispatch')
    session = runner.Session(context('dispatch', dispatch.folder, project='proj'), store,
                             dispatch.ticket(), 'claude', ['true'])
    store.plan_work(dispatch.id, 2)
    store.step_work(dispatch.id, 'Measured the event cost.')
    reads = []
    invoke = stores.operations.invoke

    def observed(tx, name, *given, **more):
        from metaform import home

        reads.append(name)
        assert name != 'ticket', 'progress must not rebuild the ticket and linked-node contexts'
        assert home.in_registry_scope(), 'one work read must share its registry validation'
        return invoke(tx, name, *given, **more)

    monkeypatch.setattr(stores.operations, 'invoke', observed)
    asyncio.run(session.check())
    assert reads == ['work'], reads
    assert session.progress_steps == 1


@pytest.mark.req('STORE-042')
@pytest.mark.req('STORE-029')
def test_dispatch_work_reads_keep_completion_missing_ids_and_newer_store_errors(dispatch, monkeypatch):
    from metaform.data import NewerStore
    from metaform.data import store as stores
    from metaform.module import Stop
    from metaform.modules.dispatch import ticket

    before = dispatch.ticket()
    assert ticket(dispatch.store, dispatch.id) == before
    dispatch.store.finish_work(dispatch.id, 'Completed the measurement.')
    assert ticket(dispatch.store, dispatch.id) == dispatch.ticket()
    with pytest.raises(Stop, match='No work record has the id missing'):
        ticket(dispatch.store, 'missing')

    def refused(*given, **more):
        raise NewerStore('The store is newer than this runner.', 'install it')

    monkeypatch.setattr(stores.operations, 'invoke', refused)
    with pytest.raises(NewerStore):
        ticket(dispatch.store, dispatch.id)


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-053')
def test_a_burst_of_changes_for_other_sessions_makes_the_runner_read_nothing(dispatch, monkeypatch):
    """code.dispatcher.agent#38: 200 map.changed for other tickets and sessions, their thread lines and steps, read
    nothing in this runner; a step on its own ticket is read."""
    from metaform.data import Store
    from metaform.data import store as stores
    from metaform.module import context
    from metaform.modules.dispatch import runner
    reads = []
    for name in ('_read', '_write', 'tables'):
        held = getattr(stores.Store, name)
        monkeypatch.setattr(stores.Store, name, lambda self, *given, _held=held, _name=name, **more:
                            reads.append(_name) or _held(self, *given, **more))
    monkeypatch.setattr(runner, 'module_read', lambda *given, **more: reads.append('module_read') or {'runs': []})

    async def burst():
        session = runner.Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                                 dispatch.ticket(), 'claude', ['true'])
        session.session_id = 'this-session'
        reads.clear()
        for number in range(100):
            other = {'work_ids': [f'other-{number % 7}'], 'session_ids': [f'session-{number % 7}']}
            session.changed_elsewhere({'project': 'proj', 'base_id': None, 'tables': 'dispatch',
                                       'dispatch_tables': ['dispatch.lines'], 'kinds': ['line'], **other})
            session.changed_elsewhere({'project': 'proj', 'base_id': None, 'tables': ['work', 'work_steps'],
                                       'kinds': ['ticket'], **other, 'session_ids': []})
        await asyncio.gather(*list(session.tasks))
        heard = list(reads)
        mine = {'project': 'proj', 'base_id': None, 'tables': ['work', 'work_steps'], 'work_ids': [dispatch.id],
                'session_ids': [], 'kinds': ['ticket']}
        session.changed_elsewhere(mine)
        await asyncio.gather(*list(session.tasks))
        once = list(reads)
        reads.clear()
        for _ in range(50):  # a burst of its own: one check, and one more for those that came during it
            session.changed_elsewhere(mine)
        while session.tasks:
            await asyncio.gather(*list(session.tasks))
        return heard, once, list(reads)
    others, own, burst_of_own = asyncio.run(burst())
    assert others == [], f'{len(others)} store reads for 200 changes that were not this session\'s'
    assert own, 'a step on its own ticket is read'
    assert len(burst_of_own) <= 2 * len(own), f'{len(burst_of_own)} reads for 50 changes, {len(own)} for one'


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-053')
def test_the_persons_answer_to_its_own_permission_request_reaches_the_runner_within_100_ms(dispatch, run):
    """code.dispatcher.agent#38: with changes filtered by ticket and session, the answer still arrives at once."""
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    run('map', 'reply', question.id, 'answer=Allow once', cwd=dispatch.folder)
    answered = time.monotonic()
    while not dispatch.logged('permission') and time.monotonic() - answered < 5:
        time.sleep(0.002)
    took = time.monotonic() - answered
    assert dispatch.logged('permission'), 'the answer reached the agent'
    assert took < 0.1, f'the answer took {took * 1000:.0f} ms'
    dispatch.stop()


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-053')
def test_a_launch_waited_on_answers_from_the_runners_own_change_or_its_exit(dispatch, run, dispatch_runners):
    """code.dispatcher.agent#38: `dispatch intake wait=true` reads the session rows when the runner says it wrote one
    for its launch, or when it exits, never on a timer: running with its session, or failed at once."""
    started = json.loads(run('dispatch', 'intake', 'agent=claude', 'wait=true', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold', FAKE_ACP_INTAKE='1')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    assert started['state'] == 'running' and started['session_id'], started
    run('dispatch', 'stop', started['work_id'], cwd=dispatch.folder)
    eventually(lambda: not alive(started['pid']))
    run('set', '--dispatch-claude', f'"{sys.executable}" -c "raise SystemExit(3)"', cwd=dispatch.folder)
    began = time.monotonic()
    failed = json.loads(run('dispatch', 'intake', 'agent=claude', 'wait=true', '--json', cwd=dispatch.folder,
                            ok=False).stdout)
    dispatch_runners.append((failed, dispatch.folder, dispatch.log))
    assert failed['state'] == 'failed' and time.monotonic() - began < 30, failed


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
def test_an_answer_that_names_no_option_is_asked_again(dispatch, run):
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    run('map', 'reply', question.id, 'answer=maybe later', cwd=dispatch.folder)
    [again] = eventually(dispatch.questions)
    assert again.id != question.id and list(again.suggestions) == ['Allow once', 'Reject']
    assert 'maybe later' in again.text
    assert not dispatch.logged('permission')
    run('map', 'reply', again.id, 'answer=allow', cwd=dispatch.folder)  # an option's id is its answer too
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome['outcome']['optionId'] == 'allow'
    dispatch.stop()


def asked_by_the_agent(dispatch):
    """The question the fake agent asked with the real command line at UNRELATED, a node its ticket neither is nor
    links, while its first turn keeps working."""
    from metaform.data import Node
    [printed] = eventually(lambda: dispatch.logged('asked'))
    [mine] = dispatch.store.messages(Node('element', UNRELATED), 'question', True, limit=0).results
    assert mine.id in printed, 'the agent was shown the id of the question it asked'
    return mine


def told(dispatch):
    """The text of each prompt the agent was sent after its first."""
    return [message['params']['prompt'][0]['text'] for message in dispatch.received('session/prompt')[1:]]


@pytest.mark.req('BASE-052')
def test_a_person_message_reaches_the_agent_as_session_prompt(dispatch, run, tmp_path):
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    sent = json.loads(run('dispatch', 'message', dispatch.id, 'also', 'run', 'the', 'tests', '--json',
                          cwd=dispatch.folder).stdout)
    assert sent['sent'] is True
    assert len(dispatch.received('session/prompt')) == 1
    (gates / '1').touch()
    prompts = eventually(lambda: dispatch.received('session/prompt')[1:])
    assert prompts[0]['params']['prompt'] == [{'type': 'text', 'text': 'also run the tests'}]
    assert prompts[0]['params']['sessionId'] == 'fake-session-1'
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_broadcast_reaches_each_running_agent_as_the_persons_message_and_is_kept_once(dispatch, run, tmp_path):
    from metaform.data import Store
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    kept = json.loads(run('dispatch', 'broadcast', '--json', '--', 'stop and commit', cwd=dispatch.folder).stdout)
    session_id = dispatch.session().extra['session_id']
    assert [(one['session_id'], one['delivered']) for one in kept['recipients']] == [(session_id, True)]
    (gates / '1').touch()
    prompts = eventually(lambda: dispatch.received('session/prompt')[1:])
    assert prompts[0]['params']['prompt'] == [{'type': 'text', 'text': 'stop and commit'}]

    def marked():
        with Store('proj', module='dispatch').tables(write=False) as tx:
            return [dict(row) for row in tx.rows('session_lines', {'session_id': session_id}, limit=0).results
                    if row['name'] == f'broadcast:{kept["id"]}']
    [line] = eventually(marked)
    assert (line['kind'], line['text']) == ('person', 'stop and commit')
    listed = json.loads(run('dispatch', 'broadcasts', '--json', cwd=dispatch.folder).stdout)['broadcasts']
    assert [(one['id'], one['text'], len(one['recipients'])) for one in listed] == [(kept['id'], 'stop and commit', 1)]
    dispatch.stop()
    refused = run('dispatch', 'broadcast', '--', 'anyone?', cwd=dispatch.folder, ok=False)
    assert 'No agent is working on this project.' in refused.stderr


@pytest.mark.req('BASE-052')
def test_a_second_writer_on_the_session_never_ends_the_runner_and_lines_keep_one_order(dispatch, run, tmp_path):
    """code.dispatcher.agent#12: another writer on the session, as a second runner resuming it, numbers lines from its
    own count; the runner's next lines take the numbers after them and it goes on."""
    from metaform.data import Store
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    session_id = dispatch.session().extra['session_id']
    last = max((line.extra['seq'] for line in dispatch.items('note')), default=0)
    with Store('proj', module='dispatch').tables() as tx:
        for seq in range(last + 1, last + 4):
            tx.insert('session_lines', {'session_id': session_id, 'name': f'line:{seq}', 'work_id': dispatch.id,
                                'kind': 'stderr', 'text': 'the other writer', 'seq': seq})
    run('dispatch', 'message', dispatch.id, 'also', 'run', 'the', 'tests', cwd=dispatch.folder)
    (gates / '1').touch()
    eventually(lambda: dispatch.received('session/prompt')[1:])
    lines = eventually(lambda: [line for line in dispatch.items('note') if line.value == 'also run the tests'])
    assert lines[0].extra['seq'] > last + 3
    assert dispatch.process.poll() is None
    seqs = [line.extra['seq'] for line in dispatch.items('note') if line.extra['session_id'] == session_id]
    assert len(seqs) == len(set(seqs))
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.parametrize('declared', [True, False])
def test_a_spoken_message_carries_its_recording_only_to_an_agent_that_declares_audio(dispatch, run, home, tmp_path,
                                                                                    declared):
    import base64
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates), **({'FAKE_ACP_AUDIO': '1'} if declared else {}))
    eventually(lambda: dispatch.received('session/prompt'))
    clips = home / 'run' / 'voice' / 'clips'
    clips.mkdir(parents=True)
    clip = clips / ('ab' * 16 + '.wav')
    clip.write_bytes(b'RIFF-fake-wav')
    sent = json.loads(run('dispatch', 'message', dispatch.id, f'audio={clip}', '--json', '--', 'run the tests',
                          cwd=dispatch.folder).stdout)
    assert sent['audio'] is declared
    assert not clip.exists()  # read and removed, sent or not
    (gates / '1').touch()
    prompts = eventually(lambda: dispatch.received('session/prompt')[1:])
    blocks = [{'type': 'text', 'text': 'run the tests'}]
    if declared:
        blocks.append({'type': 'audio', 'mimeType': 'audio/wav', 'data': base64.b64encode(b'RIFF-fake-wav').decode()})
    assert prompts[0]['params']['prompt'] == blocks
    dispatch.stop()


@pytest.mark.req('VIEW-005')
def test_an_agents_timer_wakes_its_own_session_with_its_note_and_can_be_listed_and_taken_back(dispatch, run, tmp_path):
    """An agent's timer is held by its own session's runner: set from that session it wakes it with the note as a
    turn; listed and cancelled by id; refused to a caller that is not that running session."""
    gates = tmp_path / 'turns'
    gates.mkdir()
    for number in range(4):                                          # each turn ends as soon as it is sent
        (gates / str(number)).touch()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    found = json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', 'thread=false', '--json',
                           cwd=dispatch.folder).stdout)['sessions'][-1]
    own = {'METAFORM_WORK': dispatch.id, 'METAFORM_SESSION': found['runner']}
    refused = run('dispatch', 'timer', 'seconds=1', '--', 'x', cwd=dispatch.folder, ok=False,
                  env={'METAFORM_WORK': dispatch.id, 'METAFORM_SESSION': 'not-its-runner'})
    assert 'not running here' in refused.stderr
    later = json.loads(run('dispatch', 'timer', 'seconds=60', '--json', '--', 'later', cwd=dispatch.folder, env=own).stdout)
    listed = json.loads(run('dispatch', 'timer', '--json', cwd=dispatch.folder, env=own).stdout)
    assert [one['timer'] for one in listed['timers']] == [later['timer']]
    taken = json.loads(run('dispatch', 'timer', f'cancel={later["timer"]}', '--json', cwd=dispatch.folder,
                           env=own).stdout)
    assert taken['cancelled'] is True
    assert json.loads(run('dispatch', 'timer', '--json', cwd=dispatch.folder, env=own).stdout)['timers'] == []
    soon = json.loads(run('dispatch', 'timer', 'seconds=1', '--json', '--', 'look where the person points',
                          cwd=dispatch.folder, env=own).stdout)
    assert (soon['work_id'], soon['session_id']) == (dispatch.id, found['session_id'])
    woke = eventually(lambda: [one for one in dispatch.received('session/prompt')
                               if f'Your timer {soon["timer"]}' in json.dumps(one)])
    assert 'look where the person points' in woke[0]['params']['prompt'][0]['text']
    assert woke[0]['params']['sessionId'] == dispatch.received('session/prompt')[0]['params']['sessionId']
    dispatch.stop()


def test_a_metaform_calls_structured_result_is_kept_for_the_view_that_paints_it():
    """A view paints its call's result from the structured content before it reads anything, so the thread keeps it
    where the agent passed it on, and keeps none too large for the thread."""
    from metaform.modules.dispatch.runner import CALLED_MOST, metaform_called
    said = {'content': [{'type': 'text', 'text': 'the item'}], 'structuredContent': {'item': 'code.alarm#1'}}
    called = metaform_called({'rawInput': {'item': 'code.alarm#1'}}, {'status': 'completed', 'rawOutput': said},
                             'mcp__metaform__map_item')
    assert called == {'tool': 'map_item', 'input': {'item': 'code.alarm#1'}, 'result': {
        'content': [{'type': 'text', 'text': 'the item'}], 'isError': False, 'structuredContent': {'item': 'code.alarm#1'}}}
    large = {**said, 'structuredContent': {'body': 'x' * CALLED_MOST}}
    assert 'structuredContent' not in metaform_called({}, {'status': 'completed', 'rawOutput': large},
                                                      'mcp__metaform__map_item')['result']


@pytest.mark.req('VIEW-039')
def test_an_agent_attaches_a_file_of_the_project_to_its_own_chat_and_the_person_downloads_those_bytes(
        dispatch, run, home, tmp_path):
    """code.interface.graphical#18: an agent's file reaches its own chat as an attachment line, its bytes copied apart
    by session and id, so a second file of the same name, or a change to the first, replaces nothing; the web server
    gives back exactly those bytes by session and id, and no other project's or path's. A caller that is not the
    running session, a file outside the project and a missing file are refused, and attach nothing."""
    import http.client
    import threading

    from metaform import home as metaform_home
    from metaform.modules.web.server import Server
    gates = tmp_path / 'turns'
    gates.mkdir()
    (gates / '0').touch()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    found = json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', 'thread=false', '--json',
                           cwd=dispatch.folder).stdout)['sessions'][-1]
    own = {'METAFORM_WORK': dispatch.id, 'METAFORM_SESSION': found['runner']}
    report = Path(dispatch.folder) / 'artifacts' / 'metaform-agent-embodiment-research-brief-2026-10-13.txt'
    report.parent.mkdir(exist_ok=True)
    first_bytes = 'The brief, é and ✓\r\n'.encode() + bytes(range(256))
    report.write_bytes(first_bytes)
    relative = 'path=artifacts/metaform-agent-embodiment-research-brief-2026-10-13.txt'
    refused = run('dispatch', 'attach', relative, cwd=dispatch.folder, ok=False,
                  env={'METAFORM_WORK': dispatch.id, 'METAFORM_SESSION': 'not-its-runner'})
    assert 'not running here' in refused.stderr
    outside = tmp_path / 'secret.txt'
    outside.write_text('not the project')
    assert 'outside the project' in run('dispatch', 'attach', f'path={outside}', cwd=dispatch.folder, ok=False,
                                        env=own).stderr
    assert 'No file at' in run('dispatch', 'attach', 'path=artifacts/none.txt', cwd=dispatch.folder, ok=False,
                               env=own).stderr
    first = json.loads(run('dispatch', 'attach', relative, '--json', cwd=dispatch.folder, env=own).stdout)['attached']
    report.write_bytes(b'a later report under the same name')
    second = json.loads(run('dispatch', 'attach', relative, '--json', cwd=dispatch.folder, env=own).stdout)['attached']
    assert first['name'] == second['name'] == report.name and first['id'] != second['id']
    assert (first['size'], first['session_id'], first['work_id']) == (len(first_bytes), found['session_id'], dispatch.id)
    project = next(one.project_id for one in metaform_home.projects() if Path(one.path) == Path(dispatch.folder))
    kept = metaform_home.project_folder(project) / 'published'
    assert str(kept).startswith(str(home))                           # in the Metaform home, never the source tree
    lines = json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)['lines']
    attached = [line['data'] for line in lines if line['kind'] == 'attachment']
    assert [one['id'] for one in attached] == [first['id'], second['id']]
    server = Server('127.0.0.1', 0, None)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def get(query):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=10)
        connection.request('GET', f'/api/attachment?{query}', headers={'Host': f'127.0.0.1:{server.server_address[1]}'})
        answer = connection.getresponse()
        return answer.status, answer.read(), dict(answer.getheaders())

    try:
        status, body, headers = get(f'project={project}&session={found["session_id"]}&id={first["id"]}')
        assert status == 200 and body == first_bytes                     # the bytes attached, not the file's now
        assert headers['Content-Disposition'].startswith(f'attachment; filename="{report.name}"')
        assert get(f'project={project}&session={found["session_id"]}&id={second["id"]}')[1] == report.read_bytes()
        assert get(f'project={project}&session=another&id={first["id"]}')[0] == 404
        assert get(f'project=elsewhere&session={found["session_id"]}&id={first["id"]}')[0] == 404
        assert get(f'project={project}&session=..&id=../../etc')[0] == 400
        (kept / found['session_id'] / first['id'] / report.name).unlink()
        assert get(f'project={project}&session={found["session_id"]}&id={first["id"]}&check=1')[0] == 404
    finally:
        server.shutdown()
        server.server_close()
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.parametrize('declared', [True, False])
def test_a_frame_the_person_sends_reaches_only_an_agent_that_declares_images_and_only_that_session(
        dispatch, run, home, tmp_path, declared):
    """A frame of the person's shared screen goes beside their words as an ACP image block to the session the message
    names, only where its agent declared promptCapabilities.image; never from an agent, nor from outside run/captures."""
    import base64
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates), **({'FAKE_ACP_IMAGE': '1'} if declared else {}))
    eventually(lambda: dispatch.received('session/prompt'))
    frames = home / 'run' / 'captures'
    frames.mkdir(parents=True)
    frame = frames / ('cd' * 16 + '.jpg')
    frame.write_bytes(b'\xff\xd8\xff-fake-jpeg')
    outside = tmp_path / 'elsewhere.jpg'
    outside.write_bytes(b'\xff\xd8\xff-fake-jpeg')
    refused = run('dispatch', 'message', dispatch.id, f'image={outside}', '--', 'look', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'a frame goes with a person' in refused.stderr.lower()
    sent = json.loads(run('dispatch', 'message', dispatch.id, f'image={frame}', '--json', '--', 'what is this',
                          cwd=dispatch.folder).stdout)
    assert sent['image'] is declared
    assert not frame.exists()  # read and removed, sent or not
    (gates / '1').touch()
    prompts = eventually(lambda: dispatch.received('session/prompt')[1:])
    blocks = [{'type': 'text', 'text': 'what is this'}]
    if declared:
        blocks.append({'type': 'image', 'mimeType': 'image/jpeg',
                       'data': base64.b64encode(b'\xff\xd8\xff-fake-jpeg').decode()})
    assert prompts[0]['params']['prompt'] == blocks
    assert prompts[0]['params']['sessionId'] == dispatch.received('session/prompt')[0]['params']['sessionId']
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('CLI-003')
def test_the_help_shows_how_a_message_that_is_a_switch_name_reaches_the_agent_as_written(dispatch, run, tmp_path):
    page = run('help', 'dispatch', 'message').stdout
    example = next((line.strip() for line in page.splitlines()
                    if line.strip().startswith('metaform dispatch message') and ' -- ' in line), None)
    assert example is not None, page
    words = shlex.split(example)[3:]
    assert words[0] == '198452e1...' and words[1:] == ['--', '--json'], example
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    run('dispatch', 'message', dispatch.id, *words[1:], cwd=dispatch.folder)
    (gates / '1').touch()
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
    started = json.loads(run('dispatch', 'start', dispatch.id, 'claude', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    assert started['state'] == 'starting' and started['work_id'] == dispatch.id
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    eventually(lambda: dispatch.logged('grandchild'))
    assert json.loads(dispatch.stop().stdout)['stopped'] is True


@pytest.mark.req('BASE-052')
def test_start_refuses_a_ticket_already_taken(dispatch, run):
    dispatch.store.take_work(dispatch.id, by='someone')
    refused = run('dispatch', 'start', dispatch.id, 'claude', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'taken' in refused.stdout + refused.stderr
    assert not dispatch.log.exists()


@pytest.mark.req('VIEW-039')
def test_start_refuses_a_ticket_when_every_agent_slot_is_in_use(dispatch, run):
    """Found 2026-10-16: Start all started 46 agents with six slots, since only autostart counted them. The slots are
    the runners that run now, UX review round 1, 2026-10-17: a runner at work holds the one slot."""
    run('set', '--dispatch-agents', '1', cwd=dispatch.folder)
    other = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Another change').id
    dispatch.start('hold')
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    assert json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)['free'] == 0
    refused = run('dispatch', 'start', other, 'claude', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'Every agent slot is in use' in refused.stdout + refused.stderr
    assert 'held by ' + dispatch.id[:8] in refused.stdout + refused.stderr, 'it names what holds the slot'
    assert not dispatch.store.ticket(other).work.taken
    dispatch.stop()


@pytest.mark.req('VIEW-039')
def test_a_runner_reserved_past_the_agent_slots_gives_its_ticket_back(dispatch, run):
    """Found 2026-10-16: an MCP server on code from before the slot check went on starting tickets past the limit; the
    runner it launches, on the code on disk, refuses to begin."""
    run('set', '--dispatch-agents', '1', cwd=dispatch.folder)
    other = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Another change').id
    dispatch.start('hold')
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    dispatch.store.take_work(other, by='dispatch starting 1')
    refused = run('dispatch', 'run', other, 'claude', 'reservation=dispatch starting 1', cwd=dispatch.folder,
                  ok=False, env=dispatch.env('hold'))
    assert refused.returncode != 0 and 'Every agent slot is in use' in refused.stdout + refused.stderr
    assert not dispatch.store.ticket(other).work.taken and len(dispatch.received('session/new')) == 1
    dispatch.stop()


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-045')
def test_summoned_agents_started_at_once_never_pass_the_slots_and_stop_all_ends_every_one(dispatch, run):
    """UX review round 1, 2026-10-17 (dispatch-concurrency F3 and F5, forensic cause 3): eight chats summoned at once
    with two slots all started, since each checked the room and then started, and nothing stopped every agent at once.
    The one gate admits the person's one plus the two slots; Stop all ends them and turns Autostart off, so nothing
    starts in their place."""
    from metaform.modules import dispatch as module
    run('set', '--dispatch-agents', '2', cwd=dispatch.folder)
    command = [sys.executable, '-m', 'metaform', 'dispatch', 'talk', f'id={dispatch.id}', '--json']
    calls = [subprocess.Popen(command, cwd=dispatch.folder, env=dispatch.env('hold'), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) for _ in range(8)]
    said = [call.communicate(timeout=120) for call in calls]
    started = [json.loads(out) for out, _ in said if out.strip()]
    refused = [error for out, error in said if not out.strip()]
    assert len(started) == 3 and all(one['state'] == 'starting' for one in started), said
    assert len(refused) == 5 and all('Every agent slot is in use' in error for error in refused), refused
    assert len(module.launches()) == 3, 'the ledger holds the three it admitted'
    for one in started:
        assert Path(one['log']).parent == dispatch.home / 'run' / 'dispatch' / 'logs', 'logs are kept in the home'
        assert Path(one['log']).stat().st_mode & 0o777 == 0o600 or os.name == 'nt', 'and private to their owner'
    eventually(lambda: len([row for row in dispatch.items('session') if row.extra['state'] == 'running']) == 3)
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    stopped = json.loads(run('dispatch', 'stop-all', '--json', cwd=dispatch.folder).stdout)
    assert len(stopped['stopped']) == 3 and stopped['failed'] == [], stopped
    assert 'proj:dispatch_autostart' in stopped['turned_off']
    eventually(lambda: not module.launches())
    assert not [row for row in dispatch.items('session') if row.extra['state'] == 'running']
    again = json.loads(run('dispatch', 'autostart', '--json', cwd=dispatch.folder, env=dispatch.env('hold')).stdout)
    assert again['started'] == [] and again.get('retried', []) == [], 'nothing starts in their place'


@pytest.mark.req('VIEW-039')
def test_the_machine_ceiling_counts_the_agents_of_every_project_of_the_home(dispatch, run):
    """UX review round 1, 2026-10-17 (dispatch-concurrency F4, runaway-and-load F2): each project counted only its own
    agents, so two projects ran twice the agents. An agent another project of this home runs takes the machine's one
    slot, and a start here is refused though this project's own slots are free."""
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.recovery import identity
    run('set', '--dispatch-machine-agents', '1', cwd=dispatch.folder)
    elsewhere = module.ledger() / f'{os.getpid()}.json'  # this live process, as another project's runner
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    elsewhere.write_text(json.dumps({'pid': os.getpid(), 'born': identity(os.getpid()) or '', 'project': 'other',
                                     'work_id': 'w', 'kind': 'worker'}))
    try:
        listed = json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)
        assert listed['free'] == 0 and listed['slots']['machine_used'] == 1 and listed['slots']['used'] == 0
        refused = run('dispatch', 'start', dispatch.id, 'claude', cwd=dispatch.folder, ok=False,
                      env=dispatch.env('hold'))
        assert refused.returncode != 0 and 'running on this machine across 1 project' in refused.stderr
        assert 'dispatch_machine_agents' in refused.stderr and not dispatch.ticket().taken
    finally:
        elsewhere.unlink()
    assert run('set', '--dispatch-machine-agents', '65', cwd=dispatch.folder, ok=False).returncode != 0
    assert run('set', '--dispatch-agents', '40', cwd=dispatch.folder, ok=False).returncode != 0, 'at most 17'


@pytest.mark.req('VIEW-045')
def test_the_days_budget_stops_a_summoned_agent_at_the_gate(dispatch, run):
    """UX review round 1, 2026-10-17 (settings-govern-behavior F4): the day's budget was checked only for workers, so
    a chat, an issue's sentinel or an intake started past it. Every start goes through the one gate, which checks it."""
    from metaform.data import Store
    from metaform.modules import dispatch as module
    run('set', '--dispatch-budget-day', '100', cwd=dispatch.folder)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('spending', {'session_id': 'earlier', 'seq': 1, 'work_id': dispatch.id, 'run': 'r',
                               'day': module.today(), 'tokens': 5000})
    refused = run('dispatch', 'talk', f'id={dispatch.id}', cwd=dispatch.folder, ok=False, env=dispatch.env('hold'))
    assert refused.returncode != 0 and 'budget per day is reached' in refused.stderr
    assert not module.launches() and not dispatch.log.exists()
    said = run('set', '--dispatch-budget-cost-day', '100', cwd=dispatch.folder)  # settings-govern-behavior F6
    assert 'Codex reports no cost' in said.stdout + said.stderr, 'a limit that does not hold an agent says so'


@pytest.mark.req('VIEW-042')
def test_the_persons_stop_turns_autostart_off_and_reset_leaves_the_ticket_they_stopped(dispatch, run):
    """UX review round 1, 2026-10-17: each stop with Autostart on started the next waiting ticket in its place
    (interrupt-failure-recovery F6), and Reset agents put the tickets the person stopped back in To do, where
    autostart started them again (web-gui-controls F7). An agent's stop over MCP changes no setting."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    dispatch.start('hold')
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    agent = context('dispatch', dispatch.folder, project='proj', surface='mcp')
    assert module.paused(agent, dispatch.store, None) is False, 'an agent changes no setting of the person'
    stopped = json.loads(dispatch.stop().stdout)
    assert stopped['stopped'] is True and stopped['autostart'] is False and 'Autostart agents is now off' in \
        stopped['notice']
    assert context('dispatch', dispatch.folder, project='proj').setting('dispatch_autostart') is False
    eventually(lambda: dispatch.session().extra['state'] == 'ended' or None)
    reset = json.loads(run('dispatch', 'reset', '--json', cwd=dispatch.folder).stdout)
    assert dispatch.id not in reset['released'] and reset['kept_for_you'] == [dispatch.id]
    assert dispatch.ticket().taken_by == 'claude fake-session-1', 'it waits for the person'


@pytest.mark.req('BASE-052')
def test_a_second_start_on_one_ticket_is_refused_at_once(dispatch, run, dispatch_runners):
    """Found 2026-10-03 with the ghost agents: f566b181 had two sessions from two starts, since start checked the
    ticket and the runner took it only after the agent had started. Start takes the ticket in the write that checks it."""
    first = json.loads(run('dispatch', 'start', dispatch.id, 'claude', '--json', cwd=dispatch.folder,
                           env=dispatch.env('hold')).stdout)
    dispatch_runners.append((first, dispatch.folder, dispatch.log))
    assert dispatch.ticket().taken, 'the ticket is taken when start returns, before the agent has started'
    second = run('dispatch', 'start', dispatch.id, 'claude', cwd=dispatch.folder, ok=False,
                 env=dispatch.env('hold'))
    assert second.returncode != 0 and 'taken' in second.stdout + second.stderr
    eventually(lambda: dispatch.ticket().taken_by == 'claude fake-session-1')
    eventually(lambda: dispatch.items('session'))  # the runner takes the ticket, then writes its session row
    assert len(dispatch.items('session')) == 1
    assert json.loads(dispatch.stop().stdout)['stopped'] is True


@pytest.mark.req('BASE-052')
def test_message_and_stop_name_the_next_step_when_no_agent_runs(dispatch, run):
    for args in (('message', dispatch.id, 'hello'), ('stop', dispatch.id)):
        refused = run('dispatch', *args, cwd=dispatch.folder, ok=False)
        assert refused.returncode != 0
        assert f'metaform dispatch start {dispatch.id}' in refused.stdout + refused.stderr


@pytest.mark.req('BASE-052')
@pytest.mark.req('BASE-050')
def test_an_agent_hands_work_on_by_ticket_id_and_the_next_agent_reads_the_work_and_its_nodes(dispatch, run):
    read = run('dispatch', 'handoff', f'id={dispatch.id}', cwd=dispatch.folder).stdout
    assert f'Work ticket {dispatch.id} with the map_work tool' in read
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
    """A setting sets the default behavior for an agent's interactive prompts: approve-all,
    approve-reads or ask_all. With approve-all, Metaform answers each request with its allow option, and the thread
    says so."""
    run('set', '--dispatch-prompts=approve-all', '--confirm', cwd=dispatch.folder)
    dispatch.start('ask')
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}}
    assert not dispatch.questions()
    assert eventually(lambda: [item for item in dispatch.items('note') if 'Write notes.txt' in str(item.value)
                               and item.extra['update'] == 'approved'])
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_launchs_own_prompts_answer_over_the_project_setting_and_only_the_person_gives_them(dispatch, run):
    """The person's start gives its launch its own prompts and mode, over dispatch_prompts and dispatch_agent_options;
    an agent over MCP is refused them, and a value dispatch_prompts or the agent does not offer is refused."""
    from metaform.data import Store
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('catalog', {'agent': 'claude', 'version': '9', 'name': 'Claude Code', 'seen': '2026-10-14T00:00:00Z',
                              'seq': 1, 'settings': [{'id': 'mode', 'category': 'mode', 'type': 'select',
                                                      'options': [{'value': 'default'}, {'value': 'plan'}]}]})
    for nouns, said in (({'prompts': 'approve-all'}, 'the person'), ({'prompts': 'yes'}, 'ask_all'),
                        ({'mode': 'bogus'}, 'default, plan')):
        with pytest.raises(Stop, match=said):
            module.launch_permissions(context('dispatch', dispatch.folder, project='proj', nouns=nouns,
                                              surface='mcp' if said == 'the person' else 'cli'), dispatch.store, 'claude')
    given, _ = module.launch_permissions(context('dispatch', dispatch.folder, project='proj',
                                                 nouns={'prompts': 'approve-all', 'mode': 'plan'}), dispatch.store,
                                         'claude')
    module.keep_launch(dispatch.store, dispatch.id, given)
    shown = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert shown['dispatch']['options'] == {'prompts': 'approve-all', 'mode': 'plan'}
    dispatch.start('ask')  # dispatch_prompts is still ask_all
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}} and not dispatch.questions()
    assert eventually(lambda: [item for item in dispatch.items('note')
                               if "this launch's prompts=approve-all" in str(item.value)])
    dispatch.stop()
    module.keep_launch(dispatch.store, dispatch.id, {'prompts': None, 'mode': None})  # the next start leaves them
    assert module.launch_options(dispatch.store, dispatch.id) == {}


@pytest.mark.req('BASE-052')
def test_a_sessions_own_prompts_answer_its_waiting_request_and_its_later_ones(dispatch, run, tmp_path):
    """The person chooses how one session's requests are answered from now on, code.interface.graphical#72: a choice
    that does not approve the waiting request leaves it waiting, approve-all needs confirm=true and then answers it and
    the session's later request without asking; the session's read says what is in force and whose choice it is, and an
    agent over MCP is refused the choice."""
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import tell
    again = tmp_path / 'again'
    dispatch.start('ask', FAKE_ACP_ASK_AGAIN=str(again))
    eventually(dispatch.questions)
    assert tell(dispatch.session().extra, 'status')['prompts_from'] == 'project'
    run('dispatch', 'prompts', dispatch.id, 'approve-reads', cwd=dispatch.folder)  # an edit is no read: still asked
    status = tell(dispatch.session().extra, 'status')
    assert (status['prompts'], status['prompts_from']) == ('approve-reads', 'session')
    assert dispatch.questions() and not dispatch.logged('permission')
    refused = run('dispatch', 'prompts', dispatch.id, 'approve-all', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'confirm=true' in refused.stdout + refused.stderr
    with pytest.raises(Stop, match='the person'):
        module.session_prompts(context('dispatch', dispatch.folder, project='proj', surface='mcp',
                                       nouns={'id': dispatch.id, 'prompts': 'approve-all', 'confirm': True}))
    chosen = json.loads(run('dispatch', 'prompts', dispatch.id, 'approve-all', 'confirm=true', '--json',
                            cwd=dispatch.folder).stdout)
    assert chosen['prompts'] == 'approve-all' and len(chosen['approved']) == 1
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}} and not dispatch.questions()
    again.touch()  # the session's later request is approved without asking
    [later] = eventually(lambda: dispatch.logged('permission_again'))
    assert later == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}} and not dispatch.questions()
    said = [str(item.value) for item in dispatch.items('note')]
    assert 'Permission requests in this session: approve-all, chosen by the person.' in said
    assert any('Write more.txt: approved by this session' in line for line in said)
    found = json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', 'thread=false', '--json',
                           cwd=dispatch.folder).stdout)['sessions']
    assert [(one['prompts'], one['prompts_from']) for one in found if one['state'] == 'running'] \
        == [('approve-all', 'session')]
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
    answering = source[source.index('async def answering'):source.index('def answered_by')]
    assert 'await self.answering()' in request and "'dispatch_prompts'" in answering, \
        'the setting is read when the request arrives, not at start'
    from metaform import loader, settings
    loader.get('dispatch')  # a cached direct import cannot restore settings withdrawn by loader.reset()
    found = settings.SCHEMA['dispatch_prompts']
    assert list(found.choices) == ['approve-all', 'approve-reads', 'ask_all'] and found.default == 'ask_all'


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-034')
def test_a_dispatched_agent_writes_nothing_on_the_map_and_its_session_and_transcript_are_dispatch_tables(dispatch):
    """A node holds one note, so agents keep what they learn as memories; an agent's working log
    is no pile of items at the node. The session and its transcript are the dispatch module's own tables, STORE-045."""
    dispatch.start('ask')
    eventually(dispatch.questions)
    assert 'dispatch' not in [layer.name for layer in dispatch.store.layers(limit=0).results]
    from metaform.data import Store
    with Store('proj', module='dispatch').tables(write=False) as tx:
        sessions = list(tx.rows('agent_sessions', limit=0).results)
        lines = list(tx.rows('session_lines', limit=0).results)
    assert [(row['work_id'], row['state']) for row in sessions] == [(dispatch.id, 'running')]
    assert [row['text'] for row in lines if row['kind'] == 'agent_message_chunk'] == ['Hello from fake']
    dispatch.stop()


@pytest.mark.req('VIEW-045')
def test_raising_an_issue_holds_it_on_a_ticket_at_the_node_and_starts_the_sentinel_with_the_report(dispatch, run):
    """The person says what is wrong on a node; a sentinel starts with their words and nothing else
    is written. The issue's ticket is held, so no worker takes it."""
    report = 'The alarm plays twice when the timer ends.'
    started = json.loads(run('dispatch', 'raise', NODE, '--json', '--', report, cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout)
    assert started['conversation'] and started['work_id'] != dispatch.id
    issue = dispatch.store.ticket(started['work_id']).work
    assert (issue.note, issue.held, issue.task) == (report, True, f'Issue raised by the person: {report}')
    assert issue.taken is None and issue.condition == ''
    [prompt] = eventually(lambda: dispatch.received('session/prompt'))
    text = prompt['params']['prompt'][0]['text']
    assert 'SENTINEL' in text and report in text and NODE in text
    again = json.loads(run('dispatch', 'raise', NODE, '--json', '--', 'A second one.', cwd=dispatch.folder,
                           env=dispatch.env('hold')).stdout)
    assert again['conversation'] and again['state'] == 'starting'  # a running sentinel never turns another away
    eventually(lambda: [p for p in dispatch.received('session/prompt') if 'A second one.' in str(p)] or None)
    run('dispatch', 'stop', started['work_id'], cwd=dispatch.folder)
    run('dispatch', 'stop', again['work_id'], cwd=dispatch.folder)


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-059')
def test_the_sentinel_is_served_from_the_skill_registry_with_or_without_the_workflow_module(dispatch, run):
    from metaform.module import context
    from metaform.modules import dispatch as module
    run('disable', 'workflow', cwd=dispatch.folder)
    alone = module.workflow_skill(context('dispatch', dispatch.folder, project='proj'), 'sentinel', 'x')
    assert 'SENTINEL' in alone and '<<DATA: Input>>\nx\n<<END DATA>>' in alone
    run('enable', 'workflow', cwd=dispatch.folder)
    assert module.workflow_skill(context('dispatch', dispatch.folder, project='proj'), 'sentinel', 'x') == alone


@pytest.mark.req('LAYER-029')
@pytest.mark.req('VIEW-045')
def test_a_work_claim_holds_its_part_of_the_map_from_its_first_ticket_taken_until_its_work_has_landed(dispatch, run):
    """A chosen proposal reserves the nodes it touches: once a ticket of it is taken no other ticket there starts and
    an issue raised there waits; when its tickets are done the claim ends. The sentinel's proposals are kept for the
    page with the addresses each would reserve."""
    from metaform.data import Node
    claims = lambda: json.loads(run('dispatch', 'claims', '--json', cwd=dispatch.folder).stdout)
    made = json.loads(run('dispatch', 'claim', 'Quieter alarm', f'nodes=["{NODE}"]', f'work=["{dispatch.id}"]',
                          '--json', cwd=dispatch.folder).stdout)
    assert (made['state'], made['nodes'], made['work']) == ('proposed', [NODE], [dispatch.id])
    dispatch.store.take_work(dispatch.id, by='claude')
    assert claims()['claims'][0]['state'] == 'active'
    other = dispatch.store.add_work(Node('element', NODE), 'unbuilt', task='Another change').id
    refused = run('dispatch', 'start', other, 'claude', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'claimed by "Quieter alarm"' in refused.stderr + refused.stdout
    run('enable', 'workflow', cwd=dispatch.folder)
    queued = json.loads(run('dispatch', 'raise', NODE, '--json', '--', 'Too loud still.', cwd=dispatch.folder).stdout)
    assert queued['state'] == 'queued' and 'claim Quieter alarm' in queued['waiting_on']
    proposals = [{'title': 'Lower the gain', 'grounds': 'alarm.c:12 sets 0 dB', 'disruption': 'the alarm only',
                  'reach': [NODE], 'benefit': 'quieter at once', 'tradeoff': 'none'}]
    run('dispatch', 'propose', queued['work_id'], f'proposals={json.dumps(proposals)}', cwd=dispatch.folder)
    assert claims()['proposals'][queued['work_id']] == proposals
    dispatch.store.finish_work(dispatch.id, 'Landed')
    assert claims()['claims'][0]['state'] == 'ended'


@pytest.mark.req('VIEW-045')
def test_summoned_agents_are_one_plus_the_free_agent_slots_and_the_next_issue_waits_for_a_slot(dispatch, run):
    """One summoned agent is always the person's and more use the free slots: with one slot and no work, two
    sentinels start and a third waits until one ends."""
    run('enable', 'workflow', cwd=dispatch.folder)
    run('set', '--dispatch-agents', '1', cwd=dispatch.folder)
    raised = [json.loads(run('dispatch', 'raise', NODE, '--json', '--', f'Issue {n}.', cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout) for n in (1, 2, 3)]
    assert [one['state'] for one in raised] == ['starting', 'starting', 'queued']
    assert raised[2]['waiting_on'] == 'a free agent slot'
    for one in raised[:2]:
        eventually(lambda one=one: [p for p in dispatch.received('session/prompt') if f"Issue {raised.index(one) + 1}."
                                    in str(p)] or None)
    run('dispatch', 'stop', raised[0]['work_id'], cwd=dispatch.folder)
    eventually(lambda: run('dispatch', 'autostart', '--json', cwd=dispatch.folder, env=dispatch.env('hold')) and
               [p for p in dispatch.received('session/prompt') if 'Issue 3.' in str(p)] or None)
    for one in raised[1:]:
        run('dispatch', 'stop', one['work_id'], cwd=dispatch.folder, ok=False)


@pytest.mark.req('VIEW-045')
def test_an_issue_raised_on_a_node_in_use_waits_until_that_work_is_complete(dispatch, run):
    """An issue on a node an agent is working on is queued, not refused; its sentinel starts when the work is done."""
    run('enable', 'workflow', cwd=dispatch.folder)
    dispatch.start('hold')
    eventually(lambda: dispatch.ticket().taken)
    queued = json.loads(run('dispatch', 'raise', NODE, '--json', '--', 'It drifts.', cwd=dispatch.folder,
                            env=dispatch.env('hold')).stdout)
    assert (queued['state'], queued['waiting_on']) == ('queued', [dispatch.id])
    run('map', 'work', 'op=done', 'why=Closed by the test.', f'id={dispatch.id}', 'resolution=landed', cwd=dispatch.folder)
    run('dispatch', 'autostart', cwd=dispatch.folder, env=dispatch.env('hold'))
    from metaform.data import Store
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert all(row['started'] for row in tx.rows('raised', limit=0).results)  # launched, no longer waiting
    [prompt] = eventually(lambda: [p for p in dispatch.received('session/prompt') if 'It drifts.' in str(p)] or None)
    assert NODE in prompt['params']['prompt'][0]['text']
    dispatch.stop()
    run('dispatch', 'stop', queued['work_id'], cwd=dispatch.folder)


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-035')
def test_a_session_that_ends_without_finishing_its_ticket_leaves_it_taken_for_the_person(dispatch):
    """Change order of 2026-10-07: a ticket an agent stopped on stays taken, with what the agent wrote on it, until
    the person puts it back. Autostart restarted such tickets without limit, 981 sessions in a day on one ticket."""
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    assert dispatch.ticket().taken
    dispatch.stop()
    eventually(lambda: dispatch.session().extra['state'] == 'ended' or None)
    assert dispatch.ticket().taken and dispatch.ticket().done is None, 'it waits for the person, not the next agent'


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-035')
def test_a_session_ends_when_its_ticket_is_done_whatever_turn_closed_it(dispatch, run):
    """Found 2026-10-03: an agent's ticket was closed by another turn and the runner kept the session. The ticket is
    closed elsewhere while the agent waits on a permission prompt; when that turn ends the session ends as done."""
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    run('map', 'work', 'op=done', 'why=Closed by the test.', f'id={dispatch.id}', 'resolution=closed elsewhere', cwd=dispatch.folder)
    run('map', 'reply', question.id, 'answer=Allow once', cwd=dispatch.folder)
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
    [session] = [one['session_id'] for one in bare['sessions'] if one['state'] == 'running']
    assert bare['states'][session] == whole['states'][session] and len(bare['states'][session]) > 2
    dispatch.stop()
    ended = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)['states']
    assert set(ended.get(session, {})) <= {'about', 'intake'}, 'an ended session keeps only what names it'


@pytest.mark.req('VIEW-039')
@pytest.mark.req('STORE-005')
def test_the_agents_key_read_makes_the_same_few_queries_however_many_sessions_have_ended(dispatch, run, monkeypatch):
    """code.dispatcher.agent#3b, 2026-10-16: the agents key read each session's state line in a query of its own and
    every line of every thread to find the signals, 0.25 s of the server's time on the live home. Its lines are now
    read in one query for the states and one for the signals, whatever the number of sessions, and a later read in
    the same process reads no ended session's state again."""
    from metaform.data import Store, tables
    from metaform.modules.dispatch import signals
    store = Store('proj', module='dispatch')
    with store.tables() as tx:
        for number in range(40):
            session_id = f'ended-{number}'
            tx.insert('agent_sessions', {'session_id': session_id, 'work_id': dispatch.id, 'agent': 'claude',
                                         'state': 'ended', 'how': 'the agent ended its turn', 'started': '2026-10-16T00:00:00Z',
                                         'seq': number + 1})
            state = {'commands': [{'name': f'command-{one}'} for one in range(50)], 'about': 'system' if number < 2
                     else None, 'intake': None}
            tx.insert('session_lines', {'session_id': session_id, 'name': 'state', 'work_id': dispatch.id,
                                        'kind': 'state', 'text': json.dumps(state), 'seq': 1})
            tx.insert('session_lines', {'session_id': session_id, 'name': 'line:2', 'work_id': dispatch.id,
                                        'kind': 'agent_message_chunk', 'text': 'Done.', 'seq': 2})
    signals.record(store, 'stopped-open', work_id=dispatch.id, session_id='ended-39')
    from metaform.modules.dispatch import carry_conversations
    carry_conversations(store)  # what the metaform holds of the conversations, none here, is carried once by itself
    executed = []
    plain = tables.TableTx._execute

    def counted(tx, sql, params):
        executed.append(sql)
        return plain(tx, sql, params)

    monkeypatch.setattr(tables.TableTx, '_execute', counted)
    from metaform import module as chassis
    from metaform.modules.dispatch import read_sessions
    ctx = chassis.context('dispatch', dispatch.folder, project='proj', nouns={'thread': False})
    read = read_sessions(ctx)
    lines = [sql for sql in executed if 'FROM "dispatch.lines"' in sql or 'FROM "dispatch.session_lines"' in sql]
    assert len(lines) == 2 and all(' WHERE ' in sql for sql in lines), lines
    assert len(read['sessions']) == 40 and [one['signal'] for one in read['signals']] == ['stopped-open']
    assert read['states'] == {f'ended-{number}': {'about': 'system' if number < 2 else None, 'intake': None}
                              for number in range(40)}
    executed.clear()
    assert read_sessions(ctx)['states'] == read['states']
    assert len([sql for sql in executed if 'FROM "dispatch.lines"' in sql or 'FROM "dispatch.session_lines"' in sql]) \
        == 1, executed  # the signals alone
    shown = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)
    assert shown['states'] == read['states'] and shown['signals'] == read['signals']


# ------------------------------------------------------------------ one agent per glyph, VIEW-040

def glyphed(dispatch, run, *tickets):
    """Tickets at NODE, each given as (task, glyph, held), the glyph set through the map module as the board's
    Distribute and `map work op=edit glyph=` set it; a glyph of None leaves the ticket with none."""
    made = []
    for task, glyph, held in tickets:
        work_id = dispatch.store.add_work(dispatch.node, 'unbuilt', task=task, held=held).id
        if glyph is not None:
            run('map', 'work', 'op=edit', f'id={work_id}', f'glyph={glyph}', cwd=dispatch.folder)
        made.append(work_id)
    return made


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-052')
@pytest.mark.cli_process
def test_one_agent_per_glyph_works_the_glyphs_tickets_in_turn_in_board_order(dispatch, run):
    """VIEW-040: tickets with the same glyph are one agent's, done one at a time. The agent started on
    a ticket with a glyph takes that glyph's tickets one after another in board order, To do before Backlog, each by
    its place, the next taken when the one before is done; a ticket of another glyph, one with none, and one taken
    by someone else are not its own."""
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
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
    worked = [dispatch.id, top, later, unplaced, held]
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
    assert dispatch.logged('work') == [dispatch.id]
    assert dispatch.store.ticket(beside).work.taken is None


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-052')
def test_a_ticket_whose_glyph_has_an_agent_at_work_is_not_started_and_another_glyphs_is(dispatch, run):
    """VIEW-040: one agent per glyph. While the glyph's agent works one of its tickets, start and run refuse another
    ticket of that glyph and name the ticket being worked; a ticket of another glyph starts its own agent. Stopping the
    agent ends its turn through the glyph's tickets."""
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    later, other = glyphed(dispatch, run, ('Later', 'kite', False), ('Another agent', 'moth', False))
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    for verb in ('start', 'run'):
        refused = run('dispatch', verb, later, 'claude', cwd=dispatch.folder, env=dispatch.env('done'), ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and 'kite' in said and dispatch.id in said, said
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
    eligible(dispatch, run, dispatch.id, 'claude')
    for verb in ('start', 'run'):
        refused = run('dispatch', verb, dispatch.id, 'codex', cwd=dispatch.folder, env=dispatch.env('done'),
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
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    codex_only, anyone, claude_only = glyphed(
        dispatch, run, ('Codex only', 'kite', False), ('Anyone', 'kite', False), ('Claude only', 'kite', False))
    eligible(dispatch, run, codex_only, 'codex')
    eligible(dispatch, run, claude_only, 'claude', 'gemini')
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT * 4) == 0, dispatch.process.stderr.read().decode()
    assert dispatch.logged('work') == [dispatch.id, anyone, claude_only]
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
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: launched.append((ctx.nouns['id'],
                                                                                    ctx.nouns['agent'])) or
                        {'work_id': ctx.nouns['id']})
    module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert launched == [(dispatch.id, 'codex'), (claude_only, 'claude')]


@pytest.mark.req('VIEW-042')
@pytest.mark.parametrize(('address', 'receiver', 'default'), [('code.interface.graphical', None, 'claude'),
                                                               ('code.dispatcher.agent', None, 'claude'),
                                                               (None, 'code.interface.graphical', 'gemini')])
def test_a_ticket_with_no_agent_of_its_own_starts_with_the_default_agent_whatever_its_area(address, receiver, default):
    """UX review round 1, 2026-10-17 (web-gui-controls F6): autostart chose Claude for front-end words in a ticket's
    address and Codex for the rest, while the person's Default agent said Claude Code. A ticket the card gives an agent
    keeps it."""
    from metaform.data import WorkRecord
    from metaform.modules.dispatch import preferred
    record = WorkRecord(id='w', node_kind='element' if address else 'join', node_id='n', address=address,
                        receiver_address=receiver, provider_address=None, condition='', note=None, task='Fix it.',
                        held=False, reviewed=False, created='2026-10-14T00:00:00Z', done=None, resolution=None)
    assert preferred(record, None, default) == default
    assert preferred(record, {'agent': 'codex'}, default) == 'codex'


@pytest.mark.req('MAP-046')
@pytest.mark.req('VIEW-042')
def test_a_marker_starts_with_its_note_as_task_once_its_node_has_no_taken_ticket_and_one_at_a_time(
        dispatch, run, monkeypatch):
    """Ticket adaf488c: an open trouble, broken or missing marker with no task was never started, so nobody fixed
    it. It waits behind a ticket taken at its node, and its node starts one marker at a time."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    broken = dispatch.store.add_work(dispatch.node, 'broken', note='It never sounds.').id
    dispatch.store.add_work(dispatch.node, 'missing', note='No display.')
    dispatch.store.take_work(dispatch.id, by='claude')
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    launched = []
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: launched.append(ctx.nouns['id']) or
                        {'work_id': ctx.nouns['id']})
    module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert launched == []
    dispatch.store.finish_work(dispatch.id, 'Done.')
    for _ in range(2):
        module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert launched == [broken]
    read = json.loads(run('map', 'work', f'id={broken}', '--json', cwd=dispatch.folder).stdout)
    assert read['task'] == f'It never sounds.\n\n{module.MARKERS["broken"]}'


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_interrupt_keeps_the_session_and_delivers_queued_messages_in_order(dispatch, run, tmp_path):
    from metaform.modules.dispatch import tell
    gates = tmp_path / 'interrupt-turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    held = dispatch.session().extra
    before = dispatch.ticket()
    refused = run('dispatch', 'interrupt', dispatch.id, 'session=another-session', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'no longer the running session' in refused.stderr
    assert not dispatch.received('session/cancel')
    run('dispatch', 'message', dispatch.id, 'Queued correction', cwd=dispatch.folder)
    run('dispatch', 'message', dispatch.id, 'Second correction', cwd=dispatch.folder)
    result = json.loads(run('dispatch', 'interrupt', dispatch.id, '--json', cwd=dispatch.folder).stdout)
    assert result['requested'] is True and result['session_id'] == held['session_id']
    eventually(lambda: len(dispatch.received('session/prompt')) == 2)
    assert dispatch.received('session/prompt')[-1]['params']['prompt'] == [{'type': 'text', 'text': 'Queued correction'}]
    assert tell(held, 'status')['activity'] == 'working', 'the next turn must not inherit cancellation'
    (gates / '2').touch()
    eventually(lambda: len(dispatch.received('session/prompt')) == 3)
    assert dispatch.received('session/prompt')[-1]['params']['prompt'] == [{'type': 'text', 'text': 'Second correction'}]
    assert tell(held, 'status')['activity'] == 'working'
    (gates / '3').touch()
    eventually(lambda: tell(held, 'status')['activity'] == 'idle')
    assert alive(dispatch.logged('pid')[0])
    assert dispatch.ticket().taken_by == before.taken_by
    assert dispatch.session().extra['state'] == 'running'
    idle = json.loads(run('dispatch', 'interrupt', dispatch.id, '--json', cwd=dispatch.folder).stdout)
    assert idle['requested'] is False and len(dispatch.received('session/cancel')) == 1
    run('dispatch', 'message', dispatch.id, 'Continue', cwd=dispatch.folder)
    eventually(lambda: len(dispatch.received('session/prompt')) == 4)
    (gates / '4').touch()
    eventually(lambda: tell(held, 'status')['activity'] == 'idle')
    assert not dispatch.logged('replaced')
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_interrupt_cancels_waiting_permission_without_ending_the_session(dispatch, run):
    from metaform.modules.dispatch import tell
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    held = dispatch.session().extra
    assert tell(held, 'status')['activity'] == 'waiting'
    result = json.loads(run('dispatch', 'interrupt', dispatch.id, '--json', cwd=dispatch.folder).stdout)
    assert result['requested'] is True
    eventually(lambda: dispatch.logged('permission'))
    assert dispatch.logged('permission')[0]['outcome'] == {'outcome': 'cancelled'}
    assert not dispatch.questions(), 'cancelled requests must no longer offer live answer controls'
    [closed] = dispatch.questions(open=False)
    assert closed.id == question.id and closed.closed, 'the cancelled permission stays in history'
    eventually(lambda: tell(held, 'status')['activity'] == 'idle')
    assert dispatch.process.poll() is None and dispatch.ticket().taken
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_an_interrupted_turn_is_not_followed_by_a_recording_turn(dispatch, run):
    """P033: the person interrupts to say something, so no on_stopped_open turn follows; their next message gets its
    turn, and when that one stops with the ticket open the one recording turn of the session follows it."""
    from metaform.modules.dispatch import prompt

    def stopped_open():
        said = run('dispatch', 'signals', '--json', cwd=dispatch.folder).stdout
        return [one for one in json.loads(said)['signals'] if one['signal'] == 'stopped-open']
    run('set', '--dispatch-record-on-stop', 'always', cwd=dispatch.folder)
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    run('dispatch', 'interrupt', dispatch.id, cwd=dispatch.folder)
    eventually(stopped_open)
    assert len(turns(dispatch)) == 1, 'no recording turn after the interrupt'
    run('dispatch', 'message', dispatch.id, 'Carry on', cwd=dispatch.folder)
    eventually(lambda: len(turns(dispatch)) == 3)
    assert turns(dispatch)[1:] == ['Carry on', prompt('on_stopped_open', node=NODE)]
    eventually(stopped_open)
    assert len(turns(dispatch)) == 3
    dispatch.stop()


# ------------------------------------------------------------------ what ACP gives beyond text

def rich(dispatch):
    """The fake agent made rich, editing src/engine.py, a file the sources layer places at NODE."""
    from metaform.data import Node
    edited = dispatch.folder / 'src' / 'engine.py'
    edited.parent.mkdir(exist_ok=True)
    edited.write_text('one\n', encoding='utf-8')
    dispatch.store.layer('sources', 'intake', 'refs', kind='layer', mutable=True, hideable=True, ready=True)
    dispatch.store.add_item('sources', Node('element', NODE), NODE, refs=[{'key': 'path', 'value': 'src/engine.py:1'}])
    return {'FAKE_ACP_RICH': '1', 'FAKE_ACP_RICH_PATH': str(edited)}


def read(run, dispatch, work_id=None):
    return json.loads(run('dispatch', 'sessions', f'id={work_id or dispatch.id}', '--json', cwd=dispatch.folder).stdout)


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_the_session_state_and_each_edit_are_structured_and_a_file_is_placed_on_the_map_by_its_refs(dispatch, run):
    """The agent's settings, commands, usage and plan are the session's state, and an edit is its diff and its
    location, each file at the node whose refs name it, so the page shows what the agent touches on the map."""
    dispatch.start('hold', **rich(dispatch))
    eventually(lambda: dispatch.logged('grandchild'))
    found = eventually(lambda: got if (got := read(run, dispatch))['states'].get('fake-session-1', {}).get('usage')
                       else None)
    state = found['states']['fake-session-1']
    assert state['agent_info']['name'] == 'fake-agent' and state['capabilities']['load'] is False
    assert Path(state['cwd']).resolve() == dispatch.folder.resolve()
    assert [(one['id'], one['source'], one['current']) for one in state['settings']] == \
        [('mode', 'mode', 'default'), ('model', 'option', 'small'), ('reasoning', 'option', 'low')]
    assert state['commands'] == [{'name': 'review', 'description': 'Review the changes', 'hint': 'what to review'}]
    assert state['usage'] == {'used': 1200, 'size': 200000, 'cost': None}
    assert [entry['status'] for entry in state['plan']] == ['completed', 'pending']
    assert [(one['address'], one['action']) for one in state['touched']] == [(NODE, 'edit')]
    [edit] = [line for line in found['lines'] if line['name'] == 'tool:t-edit']
    assert edit['text'] == 'Edit engine (completed)', 'the thread reads as it did'
    detail = edit['data']
    assert detail['status'] == 'completed' and detail['locations'][0]['line'] == 2
    [diff] = detail['diffs']
    assert (diff['path'], diff['added'], diff['removed'], diff['created']) == ('src/engine.py', 1, 0, False)
    assert '+two' in diff['patch'] and [node['address'] for node in diff['nodes']] == [NODE]
    assert not [line for line in found['lines'] if line['kind'] in ('state', 'tool_detail')]
    dispatch.stop()


@pytest.mark.req('VIEW-005')
def test_where_a_tool_call_reached_rides_once_on_the_sessions_next_change_from_the_tickets_node(dispatch):
    """The open pages draw an agent's request going to each part of the map its tool call reached: the runner adds
    them to the next map.changed it fires, once for each part a call reaches, and fires nothing more for them."""
    from metaform import relay
    heard = []
    with relay.listen('probe', heard.append):
        dispatch.start('hold', **rich(dispatch))
        eventually(lambda: dispatch.logged('grandchild'))
        flows = eventually(lambda: [flow for one in heard for flow in one.get('flow') or []])
    node = dispatch.store.element(NODE)
    ticket = dispatch.ticket()
    assert [(flow['to'], flow['action'], flow['from']) for flow in flows] == \
        [([{'kind': 'element', 'id': node.id}], 'edit', {'kind': ticket.node_kind, 'id': ticket.node_id})]
    assert all(one.get('tables') == 'dispatch' for one in heard if one.get('flow'))
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_the_person_sets_a_running_sessions_mode_and_model_and_a_choice_it_does_not_offer_is_refused(dispatch, run):
    dispatch.start('hold', **rich(dispatch))
    eventually(lambda: dispatch.logged('grandchild'))
    set_model = json.loads(run('dispatch', 'configure', dispatch.id, 'model', '--json', '--', 'Large',
                               cwd=dispatch.folder).stdout)
    assert set_model['value'] == 'large'
    [asked] = dispatch.received('session/set_config_option')
    assert (asked['params']['sessionId'], asked['params']['configId'], asked['params']['value']) == \
        ('fake-session-1', 'model', 'large')
    run('dispatch', 'configure', dispatch.id, 'mode', '--', 'plan', cwd=dispatch.folder)
    assert dispatch.received('session/set_mode')[0]['params']['modeId'] == 'plan'
    settings = eventually(lambda: state if (state := read(run, dispatch)['states']['fake-session-1'])['settings'][0][
        'current'] == 'plan' else None)['settings']
    assert [one['current'] for one in settings] == ['plan', 'large', 'low']
    assert [line['text'] for line in read(run, dispatch)['lines'] if line['kind'] == 'setting'] == \
        ['Model set to Large.', 'Mode set to Plan.']
    refused = run('dispatch', 'configure', dispatch.id, 'model', '--', 'huge', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'Small (small), Large (large)' in refused.stderr
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_a_permission_request_is_a_choice_among_its_options_that_the_person_answers_from_the_page(dispatch, run):
    """The page gets the request with its options and answers with one; the question at the node is closed with
    it, so its history reads the same as an answer given there. An option it does not offer is refused."""
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    [line] = eventually(lambda: [one for one in read(run, dispatch)['lines'] if one['kind'] == 'permission'])
    asked = line['data']
    assert (asked['request'], asked['message_id'], asked['state']) == (question.id, question.id, 'waiting')
    assert [(one['option_id'], one['name'], one['kind']) for one in asked['options']] == \
        [('allow', 'Allow once', 'allow_once'), ('reject', 'Reject', 'reject_once')]
    refused = run('dispatch', 'permit', dispatch.id, question.id, '--', 'maybe', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'Allow once (allow), Reject (reject)' in refused.stderr
    assert not dispatch.logged('permission')
    answered = json.loads(run('dispatch', 'permit', dispatch.id, question.id, '--json', '--', 'allow',
                              cwd=dispatch.folder).stdout)
    assert (answered['chosen'], answered['answer']) == ('allow', 'Allow once')
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}}
    [closed] = dispatch.questions(open=False)
    assert closed.id == question.id and closed.answer == 'Allow once'
    assert [one['data']['state'] for one in read(run, dispatch)['lines'] if one['kind'] == 'permission'] == ['answered']
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_an_ended_session_is_resumed_in_place_where_its_agent_can_load_it(dispatch, run, dispatch_runners):
    """The agent loads its own session again: the same session id, its thread going on with nothing replayed into
    it twice, and its ticket still its own; a session whose agent offered no way back is refused with a fresh agent
    that reads its thread as the next step."""
    from metaform.data import Store
    dispatch.start('hold', FAKE_ACP_LOAD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    dispatch.stop()
    assert dispatch.process.wait(30) == 0
    assert dispatch.session().extra['state'] == 'ended' and dispatch.ticket().taken_by == 'claude fake-session-1'
    before = len(read(run, dispatch)['lines'])
    started = json.loads(run('dispatch', 'resume', dispatch.id, '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold', FAKE_ACP_LOAD='1')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    assert (started['state'], started['session_id'], started['conversation']) == ('starting', 'fake-session-1', False)
    [load] = eventually(lambda: dispatch.received('session/load'))
    assert load['params']['sessionId'] == 'fake-session-1'
    assert Path(load['params']['cwd']).resolve() == dispatch.folder.resolve()
    eventually(lambda: dispatch.session().extra['state'] == 'running')
    assert len(dispatch.items('session')) == 1, 'the ended session itself runs again'
    resumed = read(run, dispatch)['states']['fake-session-1']
    assert resumed['resumed'] == 'load'
    assert [entry['status'] for entry in resumed['plan']] == ['completed', 'pending'] \
        and resumed['before_resume'] == ['plan'], 'what the agent last reported stays, marked as before the resume'
    run('dispatch', 'message', dispatch.id, 'Carry on', cwd=dispatch.folder)
    prompt = eventually(lambda: dispatch.received('session/prompt')[1:])[0]
    assert prompt['params']['sessionId'] == 'fake-session-1'
    lines = read(run, dispatch)['lines']
    assert not [line for line in lines if 'Replayed history' in line['text']], 'a replay is never written again'
    assert [line['text'] for line in lines[before:] if line['kind'] == 'person'] == ['Carry on']
    with Store('proj', module='dispatch').tables() as tx:  # a session that kept no state, as one older than it
        tx.insert('agent_sessions', {'session_id': 'older', 'work_id': dispatch.id, 'agent': 'codex', 'state': 'ended',
                               'started': '2026-10-01T00:00:00Z', 'seq': 1})
    refused = run('dispatch', 'resume', dispatch.id, 'session=older', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and f'dispatch talk session={dispatch.id}:older' in refused.stdout + refused.stderr
    run('dispatch', 'stop', dispatch.id, cwd=dispatch.folder)


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_the_agents_are_listed_with_whether_each_is_found_here_and_the_default_a_start_leaves_as_it_is(
        dispatch, run, dispatch_runners):
    listed = json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)
    assert [(one['agent'], one['label'], one['available'], one['default']) for one in listed['agents']] == \
        [('claude', 'Claude Code', True, True), ('codex', 'Codex', True, False), ('gemini', 'Gemini CLI', True, False)]
    assert listed['default'] == 'claude' and listed['room'] == 6, 'Claude Code by default, UX review round 1'
    run('set', '--dispatch-gemini', 'metaform-no-such-acp-adapter --acp', cwd=dispatch.folder)
    gemini = json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)['agents'][2]
    assert (gemini['available'], gemini['path'], gemini['next']) == \
        (False, None, 'metaform set --dispatch-gemini "<command>"')
    started = json.loads(run('dispatch', 'start', dispatch.id, 'codex', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    assert json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)['default'] == 'claude', \
        'the person sets the default; starting another agent on a ticket leaves it'


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
def test_an_intake_agent_follows_the_served_intake_holds_no_ticket_and_one_runs_at_a_time(dispatch, run,
                                                                                         dispatch_runners):
    """Its first turn is the intake exactly as `intake prompt` serves it, with what the person asked for; it takes
    no ticket, counts as a summoned agent, and a permission it asks for, with no node to ask at, is a choice on the
    page that the person answers. A second intake while it runs is refused."""
    served = run('intake', 'prompt', 'text=the engine only', cwd=dispatch.folder).stdout
    room = json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)['room']
    started = json.loads(run('dispatch', 'intake', 'agent=claude', '--json', '--', 'the engine only',
                             cwd=dispatch.folder, env=dispatch.env('ask', FAKE_ACP_ASK_HOLD='1')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    work_id = started['work_id']
    assert work_id.startswith('intake-') and started['intake'] and started['conversation']
    [prompt] = eventually(lambda: dispatch.received('session/prompt'))
    [block] = prompt['params']['prompt']
    assert block['type'] == 'text' and block['text'].strip() == served.strip(), 'the intake as served, nothing added'
    from metaform.data import Store
    with Store(dispatch.store.project_id, module='dispatch').tables(write=False) as tx:
        kept = tx.get('raised', {'work_id': work_id})
    assert kept is None or kept['asked'] is None, 'what the person asked is cleared from the launch once read'
    assert dispatch.store.work(open=True, limit=0).results == (dispatch.ticket(),), 'no ticket is written or taken'
    assert not dispatch.ticket().taken
    [line] = eventually(lambda: [one for one in read(run, dispatch, work_id)['lines'] if one['kind'] == 'permission'])
    assert line['data']['message_id'] is None and not dispatch.questions(), 'no node to ask at'
    assert json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)['room'] == room - 1
    refused = run('dispatch', 'intake', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and f'dispatch stop {work_id}' in refused.stdout + refused.stderr
    run('dispatch', 'permit', work_id, line['data']['request'], '--', 'Reject', cwd=dispatch.folder)
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'reject'}}
    run('dispatch', 'stop', work_id, cwd=dispatch.folder)


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
@pytest.mark.skipif(os.name == 'nt', reason='the slow start is a POSIX shell script')
def test_an_intake_starting_is_listed_held_against_a_second_for_its_whole_launch_and_stopped(dispatch, run, tmp_path):
    """UX review round 1, 2026-10-17 (cross-surface F1, F2, F5): an intake launched from the command line, its agent
    slow to start, is listed as starting by `dispatch sessions` for every surface; a second start is refused for as
    long as its runner lives, its launch row made 200 s old as well, naming the stop that works; a second runner on
    another intake work id ends before its agent starts; and stop ends it while starting, no session ever made."""
    from metaform.data import Store
    from metaform.modules.dispatch import end_group
    slow = tmp_path / 'slow-agent.sh'
    slow.write_text(f'#!/bin/sh\nsleep 60\nexec "{sys.executable}" "{FAKE}" "$@"\n', encoding='utf-8')
    slow.chmod(0o755)
    run('set', '--dispatch-claude', str(slow), cwd=dispatch.folder)
    started = json.loads(run('dispatch', 'intake', 'agent=claude', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold')).stdout)
    work_id, runner = started['work_id'], started['pid']
    try:
        listed = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)
        [row] = [one for one in listed['sessions'] if one['work_id'] == work_id]
        assert (row['state'], row['session_id'], row['agent']) == ('starting', None, 'claude'), row
        assert eventually(lambda: Store('proj').intake_agent()) and Store('proj').intake_agent()['work'] == work_id
        with Store('proj', module='dispatch').tables() as tx:  # older than any window of time a check could keep
            tx.update('raised', {'work_id': work_id}, {'started': time.time() - 200})
        refused = run('dispatch', 'intake', 'agent=claude', cwd=dispatch.folder, ok=False)
        assert refused.returncode != 0 and f'dispatch stop {work_id}' in refused.stdout + refused.stderr
        assert 'is starting on the intake' in refused.stdout + refused.stderr
        other = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'run', 'intake-' + '0' * 32, 'claude',
                                'system=true', 'intake=true'], cwd=dispatch.folder, env=dispatch.env('hold'),
                               capture_output=True, text=True, timeout=60, check=False)
        assert other.returncode != 0 and 'already at work' in other.stdout + other.stderr
        stopped = json.loads(run('dispatch', 'stop', work_id, '--json', cwd=dispatch.folder).stdout)
        assert stopped['stopped'] is True and stopped['how'] == 'stopped while starting', stopped
        assert gone([runner], limit=10), 'its runner and the slow start it ran are ended'
    finally:
        end_group(runner)
    listed = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)
    assert [one for one in listed['sessions'] if one['work_id'].startswith('intake-')] == []
    assert dispatch.items('session') == [], 'no session was ever made'


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
def test_an_agent_over_mcp_cannot_answer_a_permission_question_at_its_node(dispatch):
    """A permission request is the person's to answer: `map reply` over MCP, the agent's own surface, refuses its
    question at the node, which stays open, and the agent goes on waiting."""
    from metaform.data import StoreError
    from metaform.module import call, context, surface
    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    reply = next(verb for module in surface(dispatch.folder) if module.id == 'map'
                 for verb in module.verbs if verb.name == 'reply')
    with pytest.raises(StoreError, match='only the person answers it'):
        call(reply.run, context('map', dispatch.folder, project='proj', surface='mcp',
                                nouns={'id': question.id, 'answer': 'Allow once'}))
    assert [one.id for one in dispatch.questions()] == [question.id] and not dispatch.logged('permission')
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_the_handoff_asks_to_record_at_the_node_only_while_memory_is_on(tmp_path):
    """The handoff carries the owner's sentence with both scope forms while memory is on the folder's surface, and
    leaves it out when memory is not there, so no agent is told to use a command it does not have."""
    from unittest import mock

    from metaform.modules.dispatch import handoff_prompt
    with mock.patch('metaform.instructions.surfaced', return_value=[mock.Mock(id='memory')]):
        text = handoff_prompt('w1', tmp_path)
    assert 'Record what happened in the work as memory at the ticket\'s node' in text
    assert 'as steps 5 and 6 of the memory prompt say' in text
    assert 'node=<the address under at in the ticket read>' in text and 'receiver=<its receiver>' in text
    with mock.patch('metaform.instructions.surfaced', return_value=[]):
        assert 'memory tool' not in handoff_prompt('w1', tmp_path)


def waiter(dispatch, *nouns):
    """`metaform dispatch wait` in a process of its own, returned once its listener is recorded, so a change made
    after this is heard through BASE-053 rather than found by the first read."""
    process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'wait', *nouns, '--json'],
                               cwd=dispatch.folder, env=dispatch.env('done'), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding='utf-8')
    listeners = dispatch.home / 'run' / 'listeners'
    eventually(lambda: process.poll() is not None or list(listeners.glob(f'dispatch-{process.pid}-*.json')))
    return process


def answered(process):
    try:
        out, err = process.communicate(timeout=LIMIT)
    finally:
        process.kill()
    assert process.returncode == 0, err
    return json.loads(out)


@pytest.mark.req('BASE-052')
@pytest.mark.req('QUAL-015')
def test_dispatch_wait_answers_done_when_the_agent_finishes_its_ticket(dispatch):
    waiting = waiter(dispatch, 'until=done', f'id={dispatch.id}')
    assert waiting.poll() is None  # it blocks while the ticket is open
    dispatch.start('done')
    answer = answered(waiting)
    assert answer['state'] == 'done' and answer['work_id'] == dispatch.id and answer['next'] is None
    assert dispatch.ticket().done


@pytest.mark.req('BASE-052')
def test_dispatch_wait_with_no_id_names_the_second_of_two_tickets_that_woke_it(dispatch, run):
    from metaform.data import Node
    second = dispatch.store.add_work(Node('element', LINKED), 'unbuilt', task='Write more.txt').id
    waiting = waiter(dispatch, 'until=done')
    assert waiting.poll() is None
    run('map', 'work', 'op=done', 'why=Closed by the test.', f'id={second}', 'resolution=written', cwd=dispatch.folder)
    answer = answered(waiting)
    assert answer['work_id'] == second and [found['work_id'] for found in answer['woke']] == [second]
    assert answer['next'].startswith('metaform dispatch wait until=done since=')


@pytest.mark.req('BASE-052')
def test_dispatch_wait_answers_pending_with_the_next_call_at_its_limit(dispatch, run):
    answer = answered(waiter(dispatch, 'until=stopped', f'id={dispatch.id}', '--dispatch-wait-seconds', '1'))
    assert answer['state'] == 'pending' and answer['next'] == f'metaform dispatch wait until=stopped id={dispatch.id}'


def heard_by(monkeypatch):
    """The handlers a wait or a launch listens with, captured in place of the relay's listener, so the test hands
    each one changes as they would arrive from another process."""
    import contextlib

    from metaform import events
    handlers = []
    monkeypatch.setattr(events, 'listen', lambda module, handler: handlers.append(handler) or contextlib.nullcontext())
    return handlers


# changes that close no ticket of proj and write no session row: memory writes that name no ticket or say nothing of
# tickets, another ticket's thread lines, and another project's writes, its session rows and its tickets included
UNCONCERNED = [
    {'project': 'proj', 'base_id': None, 'tables': ['memory.entities', 'memory.observations'], 'work_ids': []},
    {'project': 'proj', 'base_id': None, 'tables': ['memory.observations']},
    {'project': 'proj', 'base_id': None, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines'],
     'work_ids': ['other'], 'session_ids': ['other-session'], 'kinds': ['line']},
    {'project': 'elsewhere', 'base_id': None, 'tables': ['work'], 'work_ids': ['theirs'], 'kinds': ['ticket']},
    {'project': 'elsewhere', 'base_id': None, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.sessions']},
    {'project': 'elsewhere', 'base_id': None}]


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-053')
def test_a_wait_on_every_ticket_reads_nothing_for_changes_not_its_own_and_one_ticket_for_one(dispatch, monkeypatch):
    """code.dispatcher.agent#4c: a burst of 120 changes that close no ticket of the project, heard by `dispatch wait`
    with no id, reads nothing until its limit; a change naming one ticket reads that ticket, never the collection."""
    import threading

    from metaform.data import store as stores
    from metaform.module import context
    from metaform.modules import dispatch as module
    handlers = heard_by(monkeypatch)
    held_awaited, reads, passes = module.awaited, [], []
    reading, first = threading.Event(), threading.Event()

    def counted(store, until, work_id, since, *named):
        passes.append(set(named[0]) if named and named[0] is not None else None)
        reading.set()
        first.wait(LIMIT)  # the first read runs while the changes arrive, so each is heard, not found by it
        return held_awaited(store, until, work_id, since, *named)
    monkeypatch.setattr(module, 'awaited', counted)
    invoke = stores.operations.invoke  # each store read of tickets, the collection `work` or one `ticket`
    monkeypatch.setattr(stores.operations, 'invoke', lambda tx, name, *given, **more:
                        (name in ('work', 'ticket') and reads.append(name)) or invoke(tx, name, *given, **more))

    async def waited(changes):
        for event in (reading, first):
            event.clear()
        handlers.clear()
        passes.clear()
        reads.clear()
        ctx = context('dispatch', dispatch.folder, project='proj', nouns={'until': 'done'},
                      switches={'dispatch_wait_seconds': 1})
        task = asyncio.ensure_future(module.wait(ctx))
        assert await asyncio.to_thread(reading.wait, LIMIT)
        [told] = handlers
        for change in changes:
            told(change)
        first.set()
        return await task
    burst = UNCONCERNED * 20
    answer = asyncio.run(waited(burst))
    assert answer['state'] == 'pending' and passes == [None], f'{len(passes) - 1} reads again for {len(burst)} changes'
    mine = {'project': 'proj', 'base_id': None, 'tables': ['work', 'work_steps'], 'work_ids': [dispatch.id],
            'session_ids': [], 'kinds': ['ticket']}
    answer = asyncio.run(waited([*burst, mine]))
    assert answer['state'] == 'pending' and passes == [None, {dispatch.id}], passes
    assert reads.count('work') == 1 and 'ticket' in reads, reads  # only the first read is of every ticket


@pytest.mark.req('QUAL-015')
@pytest.mark.req('BASE-053')
def test_a_launch_waited_on_reads_its_session_rows_only_for_a_change_of_its_own(dispatch, monkeypatch):
    """code.dispatcher.agent#4c: while `dispatch start wait=true` waits for its runner, a burst of 120 changes of
    other projects, of other tickets, or that wrote no session row, reads no session row until the start limit; one
    naming its ticket and dispatch.sessions reads them once."""
    import threading

    from metaform.data import Store
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import runner
    handlers = heard_by(monkeypatch)
    monkeypatch.setattr(runner, 'START_LIMIT', 1)  # the launch's deadline, which ends a wait nothing woke
    monkeypatch.setattr(module, 'runner_of', lambda pid: dispatch.id)  # its runner is alive throughout
    reads, reading, first = [], threading.Event(), threading.Event()

    def rows(store, work_id, verify=True):
        reads.append(work_id)
        reading.set()
        first.wait(LIMIT)  # the first read runs while the changes arrive
        return [{'state': 'running', 'session_id': 'mine'}] if len(reads) > 1 else []
    monkeypatch.setattr(module, 'sessions', rows)

    def launch(changes):
        for event in (reading, first):
            event.clear()
        handlers.clear()
        reads.clear()
        out = {}
        thread = threading.Thread(target=lambda: out.update(module.launched(Store('proj'), dispatch.id, 0)))
        thread.start()
        assert reading.wait(LIMIT)
        [told] = handlers
        for change in changes:
            told(change)
        first.set()
        thread.join(LIMIT)
        return out
    burst = UNCONCERNED * 20
    assert launch(burst)['state'] == 'failed' and reads == [dispatch.id], f'{len(reads) - 1} reads for {len(burst)}'
    mine = {'project': 'proj', 'base_id': None, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.sessions'],
            'work_ids': [dispatch.id], 'session_ids': ['mine'], 'kinds': ['session']}
    assert launch([*burst, mine]) == {'state': 'running', 'session_id': 'mine'} and reads == [dispatch.id] * 2


@pytest.mark.req('BASE-052')
def test_session_identity_reaches_the_agent_and_its_mcp_server(dispatch):
    dispatch.start('hold')
    [server] = eventually(lambda: dispatch.received('session/new'))[0]['params']['mcpServers']
    given = {entry['name']: entry['value'] for entry in server['env']}
    runner = eventually(lambda: dispatch.session().extra['runner'])
    assert given['METAFORM_HOME'] == str(dispatch.home)
    assert [given[name] for name in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE')] == \
        ['worker', runner, dispatch.id, NODE]
    assert {(entry['role'], entry['runner']) for entry in dispatch.entries() if 'role' in entry} == {('worker', runner)}
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
def test_dispatch_authority_refuses_a_worker_and_marks_an_agents_message_as_its_own(dispatch, run):
    """A worker stops no other ticket's agent, by the role its runner gave it; the system agent may message one, and
    its words are its own line in the thread, never the person's."""
    dispatch.start('hold')
    eventually(lambda: dispatch.received('session/prompt'))
    refused = run('dispatch', 'stop', dispatch.id, cwd=dispatch.folder, ok=False, env={'METAFORM_ROLE': 'worker'})
    assert refused.returncode != 0 and 'A worker agent starts, stops and messages no agent' in \
        refused.stdout + refused.stderr
    run('dispatch', 'message', dispatch.id, 'Look', 'again', cwd=dispatch.folder, env={'METAFORM_ROLE': 'system'})
    told = eventually(lambda: [line for line in dispatch.items('note') if line.extra['update'] in ('message', 'person')])
    assert [(line.extra['update'], line.value) for line in told] == [('message', 'From the system agent: Look again')]
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('MAP-050')
def test_workers_send_each_other_peer_notes_kept_on_both_tickets_and_still_steer_no_one(dispatch, run, tmp_path):
    """Peer notes, code.dispatcher.agent#32: A sees B at work and in the file it edited; A's note reaches B at B's next
    turn, marked as a fellow agent's, a pulse of the flow between them, kept in both threads, its delivery queued,
    delivered and read; A asks B by the file and waits, and B's threaded reply comes back in A's call, never again as
    a turn; an ask nobody answers says so; A still cannot stop or message B; the pair cap refuses with its reason."""
    import re

    from metaform import events
    from metaform.data import Node, Store
    from metaform.modules.dispatch.peering import NOTE_MOST, PAIR_HOURLY
    a_gates, b_gates = tmp_path / 'a-turns', tmp_path / 'b-turns'
    a_gates.mkdir()
    b_gates.mkdir()
    for number in range(20):  # A's turns end as soon as they are sent; B's are held until the test lets each end
        (a_gates / str(number)).touch()
    other = Dispatch.__new__(Dispatch)
    other.run, other.home, other.folder, other.store, other.process = run, dispatch.home, dispatch.folder, \
        dispatch.store, None
    # one log for both fake agents, so the second takes a session id of its own, fake-session-2
    other.log, other.node = dispatch.log, Node('element', LINKED)
    other.id = dispatch.store.add_work(other.node, 'unbuilt', task='Write the store.', title='Shared store').id
    heard = []
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(a_gates))
    try:
        eventually(lambda: dispatch.received('session/prompt'))
        other.start('replace', FAKE_ACP_TURN_GATES=str(b_gates))
        eventually(lambda: len(dispatch.received('session/prompt')) > 1)

        def own(work_id):
            row = json.loads(run('dispatch', 'sessions', f'id={work_id}', 'thread=false', '--json',
                                 cwd=dispatch.folder).stdout)['sessions'][-1]
            return {'METAFORM_WORK': work_id, 'METAFORM_SESSION': row['runner'], 'METAFORM_ROLE': 'worker'}, \
                row['session_id']
        (a, a_session), (b, b_session) = own(dispatch.id), own(other.id)

        def prompts(session_id):
            return [one['params']['prompt'][0]['text'] for one in dispatch.received('session/prompt')
                    if one['params']['sessionId'] == session_id]

        def states(env, note):
            return json.loads(run('dispatch', 'notes', f'note={note}', '--json', cwd=dispatch.folder,
                                  env=env).stdout)['notes'][-1]['states']

        # B's tool call edited src/shared.js, as a runner records it
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('session_lines', {'session_id': b_session, 'name': 'detail:edit-1', 'work_id': other.id,
                                'kind': 'tool_detail', 'seq': 10 ** 6, 'text': json.dumps(
                                    {'kind': 'edit', 'diffs': [{'path': 'src/shared.js', 'added': 2, 'removed': 1}],
                                     'locations': [{'path': 'src/shared.js', 'line': 42}]})})
        present = json.loads(run('dispatch', 'peers', '--json', cwd=dispatch.folder, env=a).stdout)['peers']
        assert {one['work_id'] for one in present} == {dispatch.id, other.id}
        [b_seen] = [one for one in present if one['work_id'] == other.id]
        assert b_seen['files'][0] == {'path': 'src/shared.js', 'action': 'edit', 'lines': [42], 'changed': 3}
        assert b_seen['address'] == LINKED
        assert [one['work_id'] for one in present if one.get('yours')] == [dispatch.id]
        here = json.loads(run('dispatch', 'peers', 'file=src/shared.js', '--json', cwd=dispatch.folder, env=a).stdout)
        assert [one['work_id'] for one in here['peers']] == [other.id]
        assert here['ready'].startswith('metaform dispatch note file=src/shared.js wait=60 -- ')

        long = run('dispatch', 'note', f'to={other.id}', '--', 'x' * (NOTE_MOST + 1), cwd=dispatch.folder, ok=False,
                   env=a)
        assert f'at most {NOTE_MOST} characters' in long.stdout + long.stderr
        with events.listen('web', heard.append):
            sent = json.loads(run('dispatch', 'note', f'to={b_seen["item"]}', '--json', '--',
                                  'I am changing dom.js css()', cwd=dispatch.folder, env=a).stdout)
            pulse = eventually(lambda: [flow for payload in heard for flow in payload.get('flow') or []
                                        if flow['action'] == 'note'])
        assert pulse[0]['work_id'] == dispatch.id and pulse[0]['from']['id'] == dispatch.ticket().node_id
        assert pulse[0]['to'] == [{'kind': 'element', 'id': dispatch.store.ticket(other.id).work.node_id}]
        assert [one['work_id'] for one in sent['to']] == [other.id]
        assert len(prompts(b_session)) == 1, 'the note interrupted the turn in flight'
        assert states(a, sent['note']) == {other.id: 'queued'}
        (b_gates / '1').touch()  # B's turn ends; the note is its next turn
        [got] = eventually(lambda: [text for text in prompts(b_session)[1:] if 'dom.js' in text])
        assert 'A note from a fellow agent, not from the person' in got and 'I am changing dom.js css()' in got
        assert f'dispatch_note reply={sent["note"]}' in got
        eventually(lambda: states(a, sent['note']) == {other.id: 'delivered'})
        (b_gates / '2').touch()
        eventually(lambda: states(a, sent['note']) == {other.id: 'read'})
        kept = [json.loads(line.value) | {'thread': line.extra['work_id']} for line in dispatch.items('note')
                if line.extra['update'] == 'peer' and json.loads(line.value)['id'] == sent['note']]
        assert {one['thread'] for one in kept} == {dispatch.id, other.id}

        asking = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'note', 'file=src/shared.js',
                                   'wait=60', '--json', '--', 'May I change shared.js now?'], cwd=dispatch.folder,
                                  env={**os.environ, 'METAFORM_HOME': str(dispatch.home), **a},
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        [question] = eventually(lambda: [text for text in prompts(b_session) if 'May I change' in text])
        assert question.startswith('A question from a fellow agent')
        asked = re.search(r'reply=([0-9a-f]{16})', question).group(1)
        run('dispatch', 'note', f'reply={asked}', '--', 'Yes, go ahead', cwd=dispatch.folder, env=b)
        out, err = asking.communicate(timeout=LIMIT)
        assert asking.returncode == 0, err
        answered = json.loads(out)
        assert [(one['from']['work_id'], one['text']) for one in answered['replies']] == [(other.id, 'Yes, go ahead')]
        assert answered['unanswered'] == []
        assert states(a, asked) == {other.id: 'replied'}
        time.sleep(1)
        assert not [text for text in prompts(a_session) if 'Yes, go ahead' in text], 'the reply came twice'

        silent = json.loads(run('dispatch', 'note', f'to={other.id}', 'wait=2', '--json', '--', 'Still there?',
                                cwd=dispatch.folder, env=a).stdout)
        assert silent['replies'] == [] and 'No reply came from' in silent['said']

        for refused in (run('dispatch', 'stop', other.id, cwd=dispatch.folder, ok=False, env=a),
                        run('dispatch', 'message', other.id, 'stop', 'now', cwd=dispatch.folder, ok=False, env=a)):
            assert refused.returncode != 0 and 'A worker agent starts, stops and messages no agent' in \
                refused.stdout + refused.stderr
        assert other.process.poll() is None

        for number in range(PAIR_HOURLY - 4):  # four of the pair's notes are sent already
            run('dispatch', 'note', f'to={other.id}', '--', f'more {number}', cwd=dispatch.folder, env=a)
        capped = run('dispatch', 'note', f'to={other.id}', '--', 'one too many', cwd=dispatch.folder, ok=False, env=a)
        said = capped.stdout + capped.stderr
        assert capped.returncode != 0
        assert f'have sent each other {PAIR_HOURLY} notes in the last hour, and the most is {PAIR_HOURLY}' in said
        assert 'The next can go at' in said
    finally:
        run('dispatch', 'stop', other.id, cwd=dispatch.folder, ok=False)
        dispatch.stop()
        if other.process is not None and other.process.poll() is None:
            other.process.kill()
            other.process.wait()


@pytest.mark.req('BASE-052')
def test_session_identity_the_runner_inherited_is_replaced_with_its_own(dispatch):
    dispatch.start('hold', METAFORM_ROLE='system', METAFORM_SESSION='x', METAFORM_NODE='code.ledger')
    [server] = eventually(lambda: dispatch.received('session/new'))[0]['params']['mcpServers']
    given = {entry['name']: entry['value'] for entry in server['env']}
    runner = eventually(lambda: dispatch.session().extra['runner'])
    assert runner != 'x' and (given['METAFORM_ROLE'], given['METAFORM_SESSION']) == ('worker', runner)
    assert given['METAFORM_NODE'] == NODE
    assert {(entry['role'], entry['runner']) for entry in dispatch.entries() if 'role' in entry} == {('worker', runner)}
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('MCP-010')
def test_session_identity_needs_a_chosen_server_and_a_refused_start_leaves_the_ticket_in_to_do(dispatch, run,
                                                                                               user_module):
    user_module('bridge', '''
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='bridge', summary='A server.', purpose='A server.', mcp_server='listen',
                        verbs=(Verb('listen', lambda ctx: None, 'Serve.', surfaces=('cli',), transport=True),))
    ''')
    refused = run('dispatch', 'start', dispatch.id, 'claude', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'metaform set --install-server' in refused.stdout + refused.stderr
    assert dispatch.ticket().column == 'todo'
    dispatch.store.take_work(dispatch.id, by='dispatch starting r')
    ran = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'run', dispatch.id, 'claude',
                          'reservation=dispatch starting r'], cwd=dispatch.folder, env=dispatch.env('hold'),
                         capture_output=True, text=True, check=False)
    assert ran.returncode != 0 and 'metaform set --install-server' in ran.stdout + ran.stderr
    assert dispatch.ticket().column == 'todo' and not dispatch.log.exists()


TRIAL = FAKE.with_name('trial_prompts.xml')  # carries a stand-in on_ticket_done, which ships empty


def turns(dispatch):
    return [prompt['params']['prompt'][0]['text'] for prompt in dispatch.received('session/prompt')]


@pytest.mark.req('BASE-052')
def test_record_on_finish_gives_a_worker_that_recorded_nothing_one_more_turn(dispatch):
    dispatch.start('done', METAFORM_PROMPTS=str(TRIAL))
    assert dispatch.process.wait(30) == 0
    assert dispatch.ticket().done
    assert turns(dispatch)[1:] == [f'Test record prompt. Node: {NODE}.']


@pytest.mark.req('BASE-052')
def test_record_on_finish_sends_nothing_once_the_session_recorded_at_its_node(dispatch):
    dispatch.start('done', METAFORM_PROMPTS=str(TRIAL), FAKE_ACP_RECORD=NODE)
    assert dispatch.process.wait(30) == 0
    assert dispatch.logged('recorded') == [0]
    assert len(turns(dispatch)) == 1


@pytest.mark.req('BASE-052')
def test_record_on_finish_off_sends_nothing(dispatch, run):
    run('set', '--dispatch-record-on-finish', 'off', cwd=dispatch.folder)
    dispatch.start('done', METAFORM_PROMPTS=str(TRIAL))
    assert dispatch.process.wait(30) == 0
    assert len(turns(dispatch)) == 1


@pytest.mark.req('MCP-039')
@pytest.mark.req('BASE-050')
def test_the_handoff_is_the_brief_the_ticket_its_node_and_counts_under_three_kilobytes(dispatch, run):
    """The hand-off informs and does not dump: the work line with the owner's sentence on memory at the node, then the
    ticket's fields, the nodes it links by address, the node's brief with the counts there and the MCP calls that
    read them, and the metaform:// links of the node and the ticket, never the JSON of what is held. The full
    worker's brief is no longer sent; full=true reads it on demand."""
    from metaform.modules.dispatch import handoff_prompt, prompt
    from metaform.modules.dispatch.runner import LINK_LOCK
    dispatch.start('hold')
    [sent] = eventually(lambda: dispatch.received('session/prompt'))
    memory, _, text = sent['params']['prompt'][0]['text'].partition('\n\n')
    assert memory.startswith('Follow these steps for each interaction:'), 'the memory prompt ahead of it, CTX-028'
    first, _, rest = text.partition('\n\n')
    assert first == (f'Work ticket {dispatch.id} with the map_work tool. Record what happened in the work at {NODE} as '
                     "memory, and what is now known to be true of the project in the map's knowledge layers, as the "
                     'memory prompt says.')
    assert text.endswith(f'\n\n{prompt("work_link")}') is LINK_LOCK, \
        'the rule on writing files ends the first prompt, and is left out while the lock is off, #47 and code#1e'
    assert f'ticket: {dispatch.id}' in rest and f'linked: {LINKED}' in rest
    assert f'▶ {NODE}' in rest and f'map_work node={NODE}' in rest and 'metaform map work' not in text, \
        'the reads are named as the MCP calls the agent makes'
    assert f'Links: metaform://{NODE}  metaform://{NODE}/items/1' in rest
    assert [(one['type'], one['uri']) for one in sent['params']['prompt'][1:]] == [
        ('resource_link', f'metaform://{NODE}'), ('resource_link', f'metaform://{NODE}/items/1')], \
        'the links go as ACP resource links beside the text too'
    assert rest.count('engine code') == 1, 'the node is named once in its brief'
    assert '{' not in rest, 'counts with calls, never what is held'
    assert len(rest.encode('utf-8')) < 3000
    dispatch.stop()
    read = run('dispatch', 'handoff', f'id={dispatch.id}', cwd=dispatch.folder).stdout
    brief = handoff_prompt(dispatch.id, Path(dispatch.folder))
    assert read.startswith(first) and brief not in read and f'metaform map work node={NODE}' in read, \
        'read on the command line, the same hand-off with its reads named as commands'
    full = run('dispatch', 'handoff', f'id={dispatch.id}', 'full=true', cwd=dispatch.folder).stdout
    assert full.startswith(brief) and full.endswith(read)


@pytest.mark.req('VIEW-034')
def test_the_handoff_carries_the_persons_note_at_the_node_whole_and_nothing_when_none_is_set(dispatch, run):
    """code.graph.knowledge#d: the person's note is where they write something for agents at a node, so until pushed
    delivery is built, the ticket's first message carries it whole whenever it is set."""
    from tests.storekit import page_note
    assert "the person's note here" not in run('dispatch', 'handoff', f'id={dispatch.id}', cwd=dispatch.folder).stdout
    whole = 'Ask before changing the engine. ' + 'x' * 2000
    page_note('proj', f'element:{NODE}', whole)
    read = run('dispatch', 'handoff', f'id={dispatch.id}', cwd=dispatch.folder).stdout
    assert f"the person's note here: {whole}\n" in read


# ------------------------------------------------------------------ the ACP harness in full, Phase 2

@pytest.mark.req('BASE-052')
def test_an_agents_options_are_kept_offered_as_settings_and_applied_with_the_tickets_own(dispatch, run):
    """P199 and P015: what session/new offered is kept per agent and version and offered as the choices of the
    agent's own settings, dispatch_claude_model and the rest; the agent's default and the ticket's own effort are set
    with session/set_config_option when the session starts, and a choice already current is not sent again."""
    from metaform import settings
    from metaform.data import Store
    empty = json.loads(run('dispatch', 'options', 'agent=claude', '--json', cwd=dispatch.folder).stdout)['agents'][0]
    assert empty['version'] is None and empty['next'] == 'metaform dispatch options agent=claude prime=true'
    assert settings.SCHEMA['dispatch_claude_model'].options(dispatch.folder) == ['default'], 'none offered yet'
    with Store('proj', module='dispatch').tables() as tx:  # what an earlier session offered
        tx.insert('catalog', {'agent': 'claude', 'version': '0.9', 'name': 'Claude', 'seen': '2026-10-12T00:00:00Z',
                              'seq': 1, 'settings': [
                                  {'id': 'model', 'category': 'model', 'type': 'select',
                                   'options': [{'value': 'small'}, {'value': 'large'}]},
                                  {'id': 'reasoning', 'category': 'thought_level', 'type': 'select',
                                   'options': [{'value': 'low'}, {'value': 'high'}]}]})
    run('set', '--dispatch-claude-model', 'large', '--dispatch-claude-effort', 'low', cwd=dispatch.folder)
    run('dispatch', 'tune', dispatch.id, 'effort=high', cwd=dispatch.folder)
    dispatch.start('hold', **rich(dispatch))
    eventually(lambda: dispatch.logged('grandchild'))
    sent = [(one['params']['configId'], one['params']['value']) for one in dispatch.received('session/set_config_option')]
    assert sent == [('model', 'large'), ('reasoning', 'high')], 'the ticket\'s effort goes over the agent\'s default'
    listed = json.loads(run('dispatch', 'options', 'agent=claude', '--json', cwd=dispatch.folder).stdout)['agents'][0]
    assert listed['version'] == '1.0' and listed['next'] is None
    effort = next(one for one in listed['settings'] if one['key'] == 'thought_level')
    assert (effort['name'], effort['chosen'], [one['value'] for one in effort['choices']]) == ('Effort', 'low',
                                                                                              ['low', 'high'])
    assert effort['setting'] == 'dispatch_claude_effort'
    assert settings.SCHEMA['dispatch_claude_effort'].options(dispatch.folder) == ['default', 'low', 'high']
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_priming_reads_an_agents_options_without_a_prompt(dispatch, run):
    primed = json.loads(run('dispatch', 'options', 'agent=claude', 'prime=true', '--json', cwd=dispatch.folder,
                            env=dispatch.env('hold', FAKE_ACP_CLOSE='1', **rich(dispatch))).stdout)['agents'][0]
    assert [one['key'] for one in primed['settings']] == ['mode', 'model', 'thought_level']
    assert dispatch.received('session/new')[0]['params']['mcpServers'] == []
    made = dispatch.received('session/new')[0]
    assert [one['params']['sessionId'] for one in dispatch.received('session/close')] == ['fake-session-1']
    assert [one['params']['sessionId'] for one in dispatch.received('session/delete')] == ['fake-session-1'], \
        'the throwaway session is not left in the person\'s own session list'
    assert made['params']['mcpServers'] == []
    assert not dispatch.received('session/prompt'), 'priming spends no tokens'
    assert gone(dispatch.logged('pid')), 'the primed agent is ended'


@pytest.mark.req('BASE-052')
def test_stderr_steering_and_subagents_reach_the_thread(dispatch, run):
    """P014, P016: the agent's stderr is a line of its thread with a secret redacted; a message to a turn in flight
    is steered into it with _session/steering when advertised; a subagent is a child session with its own thread."""
    dispatch.start('hold', FAKE_ACP_STDERR='1', FAKE_ACP_STEER='1', FAKE_ACP_SUBAGENT='1')
    eventually(lambda: dispatch.logged('grandchild'))
    assert dispatch.received('initialize')[0]['params']['clientCapabilities']['subagents'] == {}
    found = eventually(lambda: got if (got := read(run, dispatch))['subagents'] and
                       any(line['kind'] == 'stderr' for line in got['lines']) else None)
    [stderr] = [line['text'] for line in found['lines'] if line['kind'] == 'stderr']
    assert 'fake agent starting' in stderr and 'api_key=[redacted]' in stderr and 'sk-abc' not in stderr
    [child] = found['subagents']
    assert (child['session_id'], child['name'], child['parent']) == ('child-1', 'Explorer', 'fake-session-1')
    eventually(lambda: [one for one in read(run, dispatch)['subagents'][0]['lines'] if one['text'] == 'Child words'])
    assert eventually(lambda: read(run, dispatch)['subagents'][0]['state'] == 'completed')
    [line] = [json.loads(one.value) for one in dispatch.items('note') if one.extra['name'] == 'subagent:child-1']
    assert line['fork'] is False, 'the agent\'s own subagent is no fork'
    sent = json.loads(run('dispatch', 'message', dispatch.id, '--json', '--', 'also check the tests',
                          cwd=dispatch.folder).stdout)
    assert sent['steered'] is True
    assert eventually(lambda: dispatch.logged('steered')) == ['also check the tests']
    assert len(dispatch.received('session/prompt')) == 1, 'steered into the turn, not queued behind it'
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_logged_out_agent_raises_login_needed_and_the_person_logs_it_in(dispatch, run):
    """P031: authStatus pushed as logged out raises login-needed naming dispatch login; login calls authenticate."""
    dispatch.start('hold', FAKE_ACP_AUTH='1')
    eventually(lambda: dispatch.logged('grandchild'))
    signal = eventually(lambda: [one for one in json.loads(run('dispatch', 'signals', '--json',
                                                                cwd=dispatch.folder).stdout)['signals']
                                 if one['signal'] == 'login-needed'])[0]
    assert signal['next'] == 'metaform dispatch login claude'
    dispatch.stop()
    listed = json.loads(run('dispatch', 'login', 'claude', '--json', cwd=dispatch.folder,
                            env=dispatch.env('hold', FAKE_ACP_AUTH='1')).stdout)
    assert [one['id'] for one in listed['methods']] == ['fake-login', 'fake-terminal'], \
        'asked as a client that can run a terminal login, so every method is listed'
    refused = run('dispatch', 'login', 'claude', 'method=fake-terminal', cwd=dispatch.folder, ok=False,
                  env=dispatch.env('hold', FAKE_ACP_AUTH='1'))
    assert refused.returncode != 0 and 'run this command in a terminal' in refused.stdout + refused.stderr
    logged = json.loads(run('dispatch', 'login', 'claude', 'method=fake-login', '--json', cwd=dispatch.folder,
                            env=dispatch.env('hold', FAKE_ACP_AUTH='1')).stdout)
    assert (logged['method'], logged['state']) == ('fake-login', 'logged in')
    assert dispatch.received('authenticate')[-1]['params']['methodId'] == 'fake-login'


@pytest.mark.req('BASE-052')
def test_cancel_sends_session_cancel_and_records_the_ticket_cancelled_not_done(dispatch, run):
    """P232: the turn is cancelled with session/cancel, the session ends as the person's, never to be retried, and
    the ticket reads as cancelled with its reason."""
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    run('dispatch', 'cancel', dispatch.id, '--', 'No longer needed', cwd=dispatch.folder)
    assert dispatch.received('session/cancel')
    assert dispatch.process.wait(LIMIT) == 0
    assert dispatch.session().extra['how'] == 'cancelled by the person'
    ticket = dispatch.ticket()
    assert ticket.done and ticket.resolution == 'Cancelled: No longer needed' and ticket.outcome == 'cancelled'
    shown = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert shown['outcome'] == 'cancelled', 'the ticket read itself says cancelled'
    listed = json.loads(run('map', 'work', 'open=false', '--json', cwd=dispatch.folder).stdout)
    rows = listed['results'] if isinstance(listed, dict) else listed
    assert [one['outcome'] for one in rows if one['id'] == dispatch.id] == ['cancelled'], 'and so does the list'
    waited = json.loads(run('dispatch', 'wait', 'until=done', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert (waited['state'], waited['next']) == ('cancelled', None)


@pytest.mark.req('BASE-052')
def test_a_dispatch_verb_bound_to_a_base_acts_on_the_ticket_in_that_base(run, project_folder, monkeypatch):
    """The page runs dispatch on the base it shows with METAFORM_BASE: a ticket of a base that is not active is found
    there, where without it dispatch reads the active base and finds no such ticket."""
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    Store('proj').add_element(None, 'code', name_length=1, name='code', role='DE')
    other = Store('proj').add_base('other', activate=False).id
    there = Store('proj', base=other)
    there.add_element(None, 'code', name_length=1, name='code', role='DE')
    work_id = there.add_work(Node('element', 'code'), 'unbuilt', task='Elsewhere').id
    refused = run('dispatch', 'cancel', work_id, cwd=project_folder, ok=False)
    assert refused.returncode != 0 and 'No work record' in refused.stdout + refused.stderr
    monkeypatch.setenv('METAFORM_BASE', other)
    run('dispatch', 'cancel', work_id, '--', 'Not needed', cwd=project_folder)
    assert there.ticket(work_id).work.outcome == 'cancelled'
    from metaform.modules import dispatch as module
    assert next(verb for verb in module.MODULE.verbs if verb.name == 'cancel').effect == 'remove', \
        'hosts confirm it, as destructive'


def test_a_day_cost_budget_still_counts_spend_after_switching_base(dispatch, run):
    """A base switch must not reset a project's day budget or hide the earlier run from spend reporting."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('spend', {'session_id': 'earlier', 'seq': 1, 'work_id': dispatch.id, 'run': 'run-a',
                            'day': module.today(), 'tokens': 80, 'cost': 0.07, 'currency': 'USD'})
    run('map', 'add-base', 'other', '--confirm', cwd=dispatch.folder)
    run('map', 'activate', 'other', '--confirm', cwd=dispatch.folder)
    run('set', '--dispatch-budget-cost-day=5', cwd=dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    reached = module.over_budget(ctx, Store('proj', module='dispatch'))
    assert reached is not None and reached['budget'] == 'day'
    assert (reached['spent'], reached['limit'], reached['currency']) == (7, 5, 'USD')
    shown = json.loads(run('dispatch', 'spend', '--json', cwd=dispatch.folder).stdout)
    assert (shown['today']['cost'], shown['today']['tokens']) == (0.07, 80)
    assert [(one['run'], one['cost']) for one in shown['runs']] == [('run-a', 0.07)]
    assert module.spent(Store('proj'), work_id=dispatch.id)['cost'] == 0.07
    # Removing the base the spend was made on does not reset the cap either: spend is the project's.
    run('map', 'remove-base', 'main', '--confirm', cwd=dispatch.folder)
    assert [base.name for base in Store('proj').bases(limit=0).results] == ['other']
    reached = module.over_budget(ctx, Store('proj', module='dispatch'))
    assert reached is not None and reached['budget'] == 'day'
    shown = json.loads(run('dispatch', 'spend', '--json', cwd=dispatch.folder).stdout)
    assert shown['today']['cost'] == 0.07


def test_spend_sums_each_base_preserving_filters_currencies_and_unmetered_sessions(dispatch):
    """Spend filters apply in every base, with separate currency totals and the existing unmetered accounting."""
    from metaform.data import Store
    from metaform.modules import dispatch as module
    first = Store('proj').bound_base().id
    second = Store('proj').add_base('other').id
    Store('proj').add_base('empty')
    for base, session, day, tokens, cost, currency, metered in (
            (first, 'usd', module.today(), 80, 0.07, 'USD', True),
            (second, 'eur', module.today(), 20, 0.03, 'EUR', True),
            (second, 'tokens-only', module.today(), 10, None, None, True),
            (second, 'unmetered', module.today(), 0, None, None, False),
            (second, 'old', '2000-01-01', 90, 0.09, 'USD', True)):
        with Store('proj', base=base, module='dispatch').tables() as tx:
            tx.insert('spend', {'session_id': session, 'seq': 1, 'work_id': dispatch.id, 'run': 'run-a',
                                'day': day, 'tokens': tokens, 'cost': cost, 'currency': currency, 'metered': metered})
    # Even a store explicitly bound to the first base sees the project's total.
    bound = Store('proj', base=first)
    held = module.spent(bound, day=module.today())
    assert held['tokens'] == 110
    assert held['cost'] is None and held['currency'] is None
    assert held['costs'] == {'USD': 0.07, 'EUR': 0.03}
    assert held['unmetered'] == {'tokens': ['unmetered'], 'cost': ['tokens-only', 'unmetered']}
    assert module.spent(bound, run='run-a')['tokens'] == 200
    assert module.spent(bound, work_id=dispatch.id)['costs'] == {'USD': 0.16, 'EUR': 0.03}
    assert module.spent(bound, run='absent')['tokens'] == 0


def test_carry_opens_only_a_metaform_written_since_its_last_carry(dispatch, monkeypatch):
    """A spend read opens no metaform's store that its last carry left unchanged; a legacy row written there later is
    still carried and counted, and only that metaform is opened for it."""
    from metaform.data import Store
    from metaform.modules import dispatch as module
    first = Store('proj').bound_base().id
    second = Store('proj').add_base('other').id
    Store('proj').add_base('third')
    module.spent(Store('proj'))
    opened: list[str] = []

    class Counted(Store):
        def __init__(self, project, **given):
            super().__init__(project, **given)
            self.base_id = given.get('base')

        def tables(self, **given):
            if self.module == 'dispatch' and self.base_id:
                opened.append(self.base_id)
            return super().tables(**given)

    monkeypatch.setattr(module, 'Store', Counted)
    module.spent(Store('proj'))
    module.spent(Store('proj'))
    assert opened == [], 'no metaform unchanged since its carry is opened again'
    with Store('proj', base=second, module='dispatch').tables() as tx:
        tx.insert('spend', {'session_id': 'late', 'seq': 1, 'work_id': dispatch.id, 'run': 'run-a',
                            'day': module.today(), 'tokens': 30, 'cost': None, 'currency': None})
    assert module.spent(Store('proj'))['tokens'] == 30
    assert set(opened) == {second} and first not in opened
    opened.clear()
    assert module.spent(Store('proj'))['tokens'] == 30
    assert opened == [], 'the carry left it unchanged since'


def test_budget_checks_read_spend_once_per_field(dispatch, run, monkeypatch):
    """Token and cost limits on the same field reuse one total instead of reopening every base twice."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    run('set', *(f'--{key.replace("_", "-")}=1000' for key, *_ in module.BUDGETS), cwd=dispatch.folder)
    reads = []

    def spent(store, **where):
        reads.append(where)
        return {'tokens': 1, 'costs': {'USD': 0.01}}

    monkeypatch.setattr(module, 'spent', spent)
    ctx = context('dispatch', dispatch.folder, project='proj')
    assert module.over_budget(ctx, Store('proj'), work_id=dispatch.id, run='run-a') is None
    assert reads == [{'work_id': dispatch.id}, {'run': 'run-a'}, {'day': module.today()}]


@pytest.mark.req('BASE-052')
def test_a_turns_tokens_are_spent_against_the_budgets(dispatch, run):
    """M01: each turn's tokens are summed per ticket, run and day; a budget reached raises the budget signal and
    refuses the next start."""
    run('set', '--dispatch-budget-ticket=500', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_USAGE='800')
    eventually(lambda: dispatch.logged('grandchild'))
    run('dispatch', 'interrupt', dispatch.id, cwd=dispatch.folder)
    spend = eventually(lambda: got if (got := json.loads(run('dispatch', 'spend', f'id={dispatch.id}', '--json',
                                                               cwd=dispatch.folder).stdout))['ticket']['tokens'] else None)
    assert (spend['ticket']['tokens'], spend['ticket']['budgets']['ticket'], spend['ticket']['unmetered']['tokens']) \
        == (800, 500, [])
    assert len(spend['ticket']['unmetered']['cost']) == 1, 'it reports tokens and no cost'
    run('set', '--dispatch-budget-cost-ticket=5', cwd=dispatch.folder)
    assert 'Codex' in json.loads(run('dispatch', 'spend', f'id={dispatch.id}', '--json',
                                     cwd=dispatch.folder).stdout)['notices'][0]
    assert eventually(lambda: [one for one in json.loads(run('dispatch', 'signals', '--json', cwd=dispatch.folder)
                                                         .stdout)['signals'] if one['signal'] == 'budget'])
    dispatch.stop()
    refused = run('dispatch', 'start', dispatch.id, 'claude', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'budget per ticket' in refused.stdout + refused.stderr


@pytest.mark.req('BASE-052')
def test_the_supervisor_resumes_a_stopped_session_with_backoff_then_hands_it_over(dispatch, monkeypatch):
    """P012: a worker's session that ended without the person's stop is resumed in place after the wait, up to
    dispatch_retries, then handed to the person; one the person stopped is never retried."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    dispatch.store.take_work(dispatch.id, None, 'claude s1')
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 's1', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'ended',
                               'how': 'the agent ended with exit code 1', 'started': '2026-10-11T00:00:00Z', 'seq': 1,
                               'origin': module.origin()})
        tx.insert('session_lines', {'session_id': 's1', 'name': 'state', 'work_id': dispatch.id, 'kind': 'state', 'seq': 1,
                            'text': json.dumps({'capabilities': {'load': True}, 'cwd': str(dispatch.folder)})})
    spawned = []
    monkeypatch.setattr(module, 'spawn', lambda store, work_id, agent, extra, name, **_: spawned.append(extra) or {'pid': 0})
    ctx = context('dispatch', dispatch.folder, project='proj')
    first = module.retry(ctx, dispatch.store)
    assert first['retried'] == [] and first['retry_due'] > time.time(), 'the first retry waits'

    def due():
        with Store('proj', module='dispatch').tables() as tx:
            tx.update('session_attempts', {'work_id': dispatch.id}, {'next_at': 0.0})
    due()
    assert [one['retry'] for one in module.retry(ctx, dispatch.store)['retried']] == [1]
    assert spawned == [['resume=s1', 'retry=true']]
    due()
    module.retry(ctx, dispatch.store)
    due()
    assert module.retry(ctx, dispatch.store)['retried'] == [], 'dispatch_retries is 2'
    [handed] = [one for one in module.read_signals(ctx)['signals'] if one['signal'] == 'handed-over']
    assert handed['next'] == f'metaform dispatch resume {dispatch.id} session=s1'
    with Store('proj', module='dispatch').tables() as tx:
        tx.delete('session_attempts', {'work_id': dispatch.id})
        tx.update('agent_sessions', {'session_id': 's1'}, {'how': 'stopped by the person'})
    assert module.retry(ctx, dispatch.store) == {'retried': []}, 'never a session the person stopped'


@pytest.mark.req('BASE-052')
def test_an_agents_question_is_put_to_the_person_and_the_answer_reaches_it_as_acp_elicitation(dispatch, run):
    """ACP's elicitation: the runner advertises both modes; a form question is asked at the ticket's node with its
    choices, never answered by dispatch_prompts, and the person's answer reaches the agent as accept with content
    its schema asks for. Asked in a terminal-free way: a question, not a permission."""
    run('set', '--dispatch-prompts', 'approve-all', '--confirm', cwd=dispatch.folder)
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='form')
    init = eventually(lambda: dispatch.received('initialize'))[0]['params']['clientCapabilities']
    assert init['elicitation'] == {'form': {}, 'url': {}} and init['session']['notices'] == {}
    [question] = eventually(dispatch.questions)
    assert 'Which colour?' in question.text and list(question.suggestions) == ['Red', 'Blue', 'decline']
    assert not dispatch.logged('elicited'), 'approve-all answers permissions, never a question'
    run('map', 'reply', question.id, 'answer=Blue', cwd=dispatch.folder)
    assert eventually(lambda: dispatch.logged('elicited')) == [{'action': 'accept', 'content': {'colour': 'blue'}}]
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_page_to_open_is_shown_with_its_host_and_consent_is_the_persons_answer(dispatch, run):
    """URL-mode elicitation, as an MCP server's sign-in asks it: the full address and its host are put to the person,
    Metaform opens nothing, accept is their consent, and elicitation/complete marks the line done. A session notice is
    a line of its own."""
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='url', FAKE_ACP_NOTICE='1')
    [question] = eventually(dispatch.questions)
    assert 'https://auth.example.com/login?state=x' in question.text and 'Host: auth.example.com' in question.text
    [line] = [one['data'] for one in read(run, dispatch)['lines'] if one['kind'] == 'elicitation']
    assert (line['url'], line['host'], line['state']) == ('https://auth.example.com/login?state=x',
                                                          'auth.example.com', 'waiting')
    run('dispatch', 'permit', dispatch.id, question.id, '--', 'accept', cwd=dispatch.folder)
    assert eventually(lambda: dispatch.logged('elicited')) == [{'action': 'accept'}]
    assert eventually(lambda: [one for one in read(run, dispatch)['lines']
                               if one['kind'] == 'elicitation' and one['data']['state'] == 'completed'])
    notices = [one['data'] for one in read(run, dispatch)['lines'] if one['kind'] == 'agent_notice']
    assert notices == [{'severity': 'warning', 'title': 'MCP server unavailable',
                        'description': 'Continuing without it.'}]
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_claudes_ask_user_question_is_one_question_with_its_choices_offered(dispatch, run):
    """claude-agent-acp sends AskUserQuestion as a choice field and an optional free-text "Other" beside it, nothing
    required: it is one question, its choices are the suggestions, and a choice named reaches the choice field."""
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='ask')
    [question] = eventually(dispatch.questions)
    assert list(question.suggestions) == ['Red', 'Blue', 'decline']
    [line] = [one['data'] for one in read(run, dispatch)['lines'] if one['kind'] == 'elicitation']
    assert line['tool_call_id'] == 't-ask'
    run('map', 'reply', question.id, 'answer=Blue', cwd=dispatch.folder)
    assert eventually(lambda: dispatch.logged('elicited')) == [{'action': 'accept', 'content': {'question_0': 'Blue'}}]
    dispatch.stop()


@pytest.mark.req('VIEW-045')
def test_a_workers_question_never_reaches_the_person_and_it_is_told_to_decide(dispatch, run):
    """Only the sentinel and the head agent ask the person: a worker's AskUserQuestion is answered at once, its own-words
    field telling it to decide and record why, with nothing at the node, in the thread or among the signals."""
    from metaform.modules.dispatch import prompt
    dispatch.start('hold', FAKE_ACP_ELICIT='ask')
    assert eventually(lambda: dispatch.logged('elicited')) == [
        {'action': 'accept', 'content': {'question_0_custom': prompt('decide')}}]
    assert not dispatch.questions() and not dispatch.questions(open=False)
    assert not [one for one in read(run, dispatch)['lines'] if one['kind'] == 'elicitation']
    said = run('dispatch', 'signals', 'active=false', '--json', cwd=dispatch.folder).stdout
    assert not [one for one in json.loads(said)['signals'] if one['signal'] == 'question-waiting']
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_question_asked_while_the_session_is_made_moves_to_the_session(dispatch, run):
    """A sign-in the agent asks for before it answers session/new: once the session is made, its line is in the
    session's thread and its question-waiting signal is the session's, so the session's end clears it."""
    def waiting():
        said = run('dispatch', 'signals', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout
        return [one for one in json.loads(said)['signals'] if one['signal'] == 'question-waiting']
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='setup')
    [line] = eventually(lambda: [one['data'] for one in read(run, dispatch)['lines'] if one['kind'] == 'elicitation'])
    assert (line['url'], line['state']) == ('https://auth.example.com/login?state=s', 'waiting')
    [signal] = eventually(lambda: [one for one in waiting() if one['session_id']])
    assert signal['session_id'] == 'fake-session-1' and len(waiting()) == 1, 'raised once, under the session'
    dispatch.stop()
    assert not waiting()


def test_a_bare_answer_fills_a_choice_or_the_free_text_companion_and_an_unreadable_one_is_never_an_empty_accept():
    """The answer's reading, against the shapes the adapters send: own words go to the companion, a choice and words
    to both, a form of several questions takes name: value, and an answer that fills no field is refused."""
    from metaform.modules.dispatch.runner import elicit_answer, elicit_fields
    claude = elicit_fields({'type': 'object', 'properties': {
        'question_0': {'type': 'string', 'title': 'Colour', 'oneOf': [{'const': 'Red', 'title': 'Red'},
                                                                       {'const': 'Blue', 'title': 'Blue'}]},
        'question_0_custom': {'type': 'string', 'title': 'Other'}}})
    assert elicit_answer(claude, 'I think blue') == ('accept', {'question_0_custom': 'I think blue'})
    assert elicit_answer(claude, 'Blue, but darker') == ('accept', {'question_0': 'Blue',
                                                                    'question_0_custom': 'but darker'})
    codex = elicit_fields({'type': 'object', 'required': ['q'], 'properties': {
        'q': {'type': 'string', 'title': 'Which?', 'oneOf': [{'const': 'pg', 'title': 'pg'},
                                                             {'const': 'None of the above', 'title': 'None of the above'}]},
        'q_note': {'type': 'string', 'title': 'Additional answer or note',
                   '_meta': {'codex': {'questionId': 'q', 'role': 'user_note', 'isSecret': True}}}}})
    assert codex[1]['note_of'] == 'q' and codex[1]['secret']
    assert elicit_answer(codex, 'None of the above: sqlite') == ('accept', {'q': 'None of the above',
                                                                             'q_note': 'sqlite'})
    with pytest.raises(ValueError, match='begin the answer'):
        elicit_answer(codex, 'sqlite')
    three = elicit_fields({'type': 'object', 'properties': {
        'a': {'type': 'string'}, 'b': {'type': 'integer', 'minimum': 1},
        'c': {'type': 'string', 'format': 'email', 'default': 'x@y.z'}}})
    with pytest.raises(ValueError, match='fills none'):
        elicit_answer(three, 'blah')
    with pytest.raises(ValueError, match='at least 1'):
        elicit_answer(three, 'a: hi; b: 0')
    assert elicit_answer(three, 'a: hi; b: 3') == ('accept', {'a': 'hi', 'b': 3, 'c': 'x@y.z'})


@pytest.mark.req('BASE-052')
def test_a_question_the_agent_withdraws_is_closed_and_the_silence_clock_goes_on(dispatch, run):
    """ACP's request cancellation: the agent's `$/cancel_request` for its waiting question closes the question at the
    node, clears question-waiting, marks the line withdrawn, answers the request with -32800, and the silence clock,
    paused while it waited, runs again."""
    run('set', '--dispatch-silence-seconds', '1', cwd=dispatch.folder)
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='withdraw')
    [answer] = eventually(lambda: dispatch.logged('elicited'))
    assert answer['error']['code'] == -32800
    assert not dispatch.questions() and dispatch.questions(open=False)

    def signals(name, active):
        said = run('dispatch', 'signals', f'active={str(active).lower()}', '--json', cwd=dispatch.folder).stdout
        return [one for one in json.loads(said)['signals'] if one['signal'] == name]
    assert eventually(lambda: signals('question-waiting', False)) and not signals('question-waiting', True)
    assert eventually(lambda: [one for one in read(run, dispatch)['lines']
                               if one['kind'] == 'elicitation' and one['data']['state'] == 'withdrawn'])
    assert eventually(lambda: signals('silent', True))
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_page_completed_out_of_band_closes_its_question(dispatch, run):
    """An MCP server's sign-in that finished in the browser before the person answered: elicitation/complete closes
    the waiting question, the agent gets accept, and the line says completed."""
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='complete')
    assert eventually(lambda: dispatch.logged('elicited')) == [{'action': 'accept'}]
    assert not dispatch.questions()
    assert eventually(lambda: [one for one in read(run, dispatch)['lines']
                               if one['kind'] == 'elicitation' and one['data']['state'] == 'completed'])
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_page_completed_before_its_question_is_asked_closes_it_as_it_is_asked(dispatch, run):
    """A sign-in done at once: elicitation/complete can reach the runner before the question it closes is asked, while
    the runner still reads its settings; the question is closed as completed the moment it is asked, and the agent
    gets accept instead of waiting on a question already done with."""
    dispatch.start('hold', 'system=true', FAKE_ACP_ELICIT='complete-first')
    assert eventually(lambda: dispatch.logged('elicited')) == [{'action': 'accept'}]
    assert not dispatch.questions()
    assert eventually(lambda: [one for one in read(run, dispatch)['lines']
                               if one['kind'] == 'elicitation' and one['data']['state'] == 'completed'])
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_token_budget_stops_a_turn_part_way_on_the_provisional_meter(dispatch, run):
    """M01: the adapters report a turn's tokens only at its end, but its context in use after each model call; the
    turn's estimate from those is held against the token budgets, so interrupt cancels a runaway turn part way."""
    run('set', '--dispatch-budget-ticket=1000', cwd=dispatch.folder)
    run('set', '--dispatch-budget-action', 'interrupt', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_USED='5000,9000')
    eventually(lambda: dispatch.received('session/cancel'))
    [budget] = [one for one in json.loads(run('dispatch', 'signals', '--json', cwd=dispatch.folder).stdout)['signals']
                if one['signal'] == 'budget']
    assert (budget['measure'], budget['provisional']) == ('tokens', 5500)
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_turn_silent_twice_is_signalled_twice(dispatch, run):
    """P040: the silence clock starts again whenever the agent speaks, so a turn that falls silent, speaks and falls
    silent again raises the silent signal, has it cleared, and raises it again."""
    run('set', '--dispatch-silence-seconds', '1', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_SILENT='3')

    def silent(active):
        said = run('dispatch', 'signals', f'active={str(active).lower()}', '--json', cwd=dispatch.folder).stdout
        return [one for one in json.loads(said)['signals'] if one['signal'] == 'silent']
    eventually(lambda: silent(True))
    assert not dispatch.logged('spoke'), 'raised while the agent was silent'
    eventually(lambda: silent(False))
    assert dispatch.logged('spoke'), 'cleared when it spoke'
    eventually(lambda: silent(True))  # raised again when it fell silent again
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_cost_budget_counts_each_reports_addition_and_interrupts_the_turn_when_asked(dispatch, run):
    """M01: usage_update's cost is the session's running total, so only what each report adds is kept; a cost
    budget reached during a turn raises the budget signal, and with dispatch_budget_action interrupt the turn is
    cancelled with session/cancel. The token and run budgets ship off."""
    from metaform import settings
    assert all(settings.SCHEMA[key].default == 0 for key in ('dispatch_budget_ticket', 'dispatch_budget_run',
                                                            'dispatch_budget_day', 'dispatch_budget_cost_day'))
    run('set', '--dispatch-budget-cost-ticket=5', cwd=dispatch.folder)
    run('set', '--dispatch-budget-action', 'interrupt', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_COST='0.02,0.07')
    eventually(lambda: dispatch.received('session/cancel'))
    spend = json.loads(run('dispatch', 'spend', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert (spend['ticket']['cost'], spend['ticket']['currency']) == (0.07, 'USD'), 'never the totals summed'
    [budget] = [one for one in json.loads(run('dispatch', 'signals', '--json', cwd=dispatch.folder).stdout)['signals']
                if one['signal'] == 'budget']
    assert (budget['measure'], budget['spent'], budget['limit']) == ('cost', 7, 5)
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.req('CLI-011')
def test_a_dispatched_agents_budget_refusal_points_to_its_ticket(dispatch, run, monkeypatch):
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    run('set', '--dispatch-budget-ticket', '1', cwd=dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    with module.own_store(dispatch.store).tables() as tx:
        tx.insert('spend', {'session_id': 'budget-check', 'seq': 1, 'work_id': dispatch.id,
                            'run': 'budget-check', 'day': module.today(), 'tokens': 1})
    monkeypatch.setenv('METAFORM_ROLE', 'system')
    with pytest.raises(Stop) as refused:
        module.budget_stop(ctx, dispatch.store, dispatch.id)
    assert refused.value.next_step.startswith('metaform map work op=edit')
    assert 'metaform set' not in refused.value.next_step
    monkeypatch.delenv('METAFORM_ROLE')
    with pytest.raises(Stop) as person:
        module.budget_stop(ctx, dispatch.store, dispatch.id)
    assert person.value.next_step.startswith('metaform set --dispatch-budget-ticket')


@pytest.mark.req('CLI-011')
def test_cancel_and_tune_refuse_an_agent_cli_unless_the_person_allows_control(dispatch, run):
    agent = {'METAFORM_ROLE': 'system'}
    for verb, nouns in (('cancel', ()), ('tune', ('model=large',))):
        refused = run('dispatch', verb, dispatch.id, *nouns, cwd=dispatch.folder, env=agent, ok=False)
        assert refused.returncode == 2
        assert "the person's decision" in refused.stderr
        assert 'Next: metaform map work op=edit' in refused.stderr
    assert not dispatch.ticket().done
    run('set', '--agents-may-set-control', cwd=dispatch.folder)
    run('dispatch', 'cancel', dispatch.id, cwd=dispatch.folder, env=agent)
    assert dispatch.ticket().outcome == 'cancelled'


@pytest.mark.req('BASE-052')
@pytest.mark.req('CLI-011')
def test_cancel_and_tune_are_the_persons_and_tune_takes_only_what_the_agent_offers(dispatch, run):
    """P232 and P015: over MCP an agent is refused cancel and tune while agents_may_set_control is off; tune refuses
    a value the ticket's agent did not offer at its last session, and the ticket read shows what it keeps; each of an
    agent's options is its own setting, so setting one leaves the others, and a value it never offered is refused
    with the list."""
    from metaform.data import Store
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    for verb, nouns in ((module.cancel, {'id': dispatch.id}), (module.tune, {'id': dispatch.id, 'model': 'large'})):
        with pytest.raises(Stop, match='the person'):
            verb(context('dispatch', dispatch.folder, project='proj', nouns=nouns, surface='mcp'))
    assert not dispatch.ticket().done
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('catalog', {'agent': 'codex', 'version': '9', 'name': 'Codex', 'seen': '2026-10-12T00:00:00Z',
                              'seq': 1, 'settings': [{'id': 'model', 'category': 'model', 'type': 'select',
                                                      'options': [{'value': 'small'}, {'value': 'large'}]}]})
    refused = run('dispatch', 'tune', dispatch.id, 'model=bogus', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'small, large' in refused.stdout + refused.stderr
    run('dispatch', 'tune', dispatch.id, 'model=large', cwd=dispatch.folder)
    shown = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert shown['dispatch']['options'] == {'model': 'large'}
    run('set', '--dispatch-codex-mode', 'default', cwd=dispatch.folder)
    run('set', '--dispatch-codex-model', 'large', cwd=dispatch.folder)
    from metaform import settings
    assert (settings.value('dispatch_codex_model', dispatch.folder),
            settings.state('dispatch_codex_mode', dispatch.folder)) == ('large', 'set'), 'the mode set before is kept'
    wrong = run('set', '--dispatch-codex-model', 'bogus', cwd=dispatch.folder, ok=False)
    assert wrong.returncode != 0 and 'Choices: default, small, large' in wrong.stdout + wrong.stderr


@pytest.mark.req('BASE-052')
def test_the_old_agent_options_move_once_into_each_options_own_setting(dispatch):
    """Rich, 2026-10-14: each stored dispatch_agent_options entry becomes its own setting at the same scope and the
    old setting is removed; an entry no setting holds is dropped and said; what only a list above a folder's own set
    stays default there, as the folder's list hid it; it runs once per home."""
    from metaform import home, settings
    from metaform.modules import dispatch as module
    scope = home.path_key(dispatch.folder)
    home.save('global', 'dispatch', 'dispatch_agent_options', ['claude.mode=bypassPermissions'])
    home.save(scope, 'dispatch', 'dispatch_agent_options', ['codex.mode=agent-full-access', 'claude.model_config=false',
                                                            'claude.unknown=x'])
    (home.home() / 'migrated-dispatch-agent-options').unlink(missing_ok=True)
    said = module.migrate_agent_options()
    assert (settings.value('dispatch_codex_mode', dispatch.folder),
            settings.value('dispatch_claude_fast', dispatch.folder)) == ('agent-full-access', 'false')
    assert settings.value('dispatch_claude_mode', dispatch.folder) == 'default', 'the folder\'s list hid the global one'
    assert home.stored(scope, 'dispatch', 'dispatch_agent_options') is None
    assert any('claude.unknown=x' in line and 'dropped' in line for line in said)
    assert module.migrate_agent_options() == [], 'once per home'


@pytest.mark.req('BASE-052')
def test_the_old_strengths_list_moves_once_into_each_agents_own_setting(dispatch, run):
    """Settings cleanup 2026-10-15: each entry of a stored dispatch_agent_strengths list becomes that agent's
    dispatch_<agent>_strengths at the same scope, words with commas whole; an agent the list left out keeps its own
    default rather than being wiped; an entry for no agent is dropped and said; it runs once per home. Setting one
    agent's strengths after leaves the others."""
    from metaform import home, settings
    from metaform.modules import dispatch as module
    scope = home.path_key(dispatch.folder)
    home.save(scope, 'dispatch', 'dispatch_agent_strengths', ['codex=exact code, and data', 'nobody=x'])
    with home.chassis(write=True) as db:  # the test home's own start carried nothing and marked it; undo the mark
        db.execute("DELETE FROM meta WHERE key='carried:dispatch-agent-strengths'")
    settings._carried.clear()
    said = module.carry_strengths()
    assert settings.value('dispatch_codex_strengths', dispatch.folder) == 'exact code, and data'
    assert settings.value('dispatch_claude_strengths', dispatch.folder) == module.STRENGTHS['claude'], 'left as it was'
    assert home.stored(scope, 'dispatch', 'dispatch_agent_strengths') is None
    assert any('nobody=x' in line and 'dropped' in line for line in said)
    assert module.carry_strengths() == [], 'once per home'
    run('set', '--dispatch-gemini-strengths', 'big reads, and logs', cwd=dispatch.folder)
    assert settings.value('dispatch_codex_strengths', dispatch.folder) == 'exact code, and data'


@pytest.mark.req('BASE-052')
def test_the_supervisor_hands_a_logged_out_session_over_at_once_and_keeps_its_run(dispatch, monkeypatch):
    """P012 and M01: a session whose agent needs a login is handed to the person with no retry, since only they can
    log it in; a retry goes on spending against the run of the session it resumes."""
    from metaform.data import Node, Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    other = dispatch.store.add_work(Node('element', LINKED), 'unbuilt', task='Write more.txt').id
    dispatch.store.take_work(dispatch.id, None, 'claude s1')
    dispatch.store.take_work(other, None, 'claude s2')
    state = json.dumps({'capabilities': {'load': True}, 'cwd': str(dispatch.folder)})
    with Store('proj', module='dispatch').tables() as tx:
        for session, work, how in (('s1', dispatch.id, 'it failed: Claude Code needs a login before it makes a session'),
                                   ('s2', other, 'the agent ended with exit code 1')):
            tx.insert('agent_sessions', {'session_id': session, 'work_id': work, 'agent': 'claude', 'state': 'ended',
                                   'how': how, 'started': '2026-10-11T00:00:00Z', 'seq': 1, 'origin': module.origin()})
            tx.insert('session_lines', {'session_id': session, 'name': 'state', 'work_id': work, 'kind': 'state', 'seq': 1,
                                'text': state})
        tx.insert('spending', {'session_id': 's2', 'seq': 1, 'work_id': other, 'run': 'run-a', 'day': '2026-10-11',
                               'tokens': 10})
    spawned = []
    monkeypatch.setattr(module, 'spawn', lambda store, work_id, agent, extra, name, **_: spawned.append(extra) or {'pid': 0})
    ctx = context('dispatch', dispatch.folder, project='proj')
    module.retry(ctx, dispatch.store)
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('session_attempts', {'work_id': other}, {'next_at': 0.0})
    module.retry(ctx, dispatch.store)
    assert spawned == [['resume=s2', 'retry=true', 'run=run-a']], 'the logged-out session is never retried'
    [handed] = [one for one in module.read_signals(ctx)['signals'] if one['signal'] == 'handed-over']
    assert handed['work_id'] == dispatch.id and 'login' in handed['reason']


def stay_connected(dispatch, run, monkeypatch, caps):
    """dispatch_stay_connected on, the held system ticket, and one system session s1 on it that ended on its own
    with the capabilities given; nothing is started: each runner spawned and each new conversation is only noted."""
    from metaform import settings
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    for agent in ('claude', 'codex', 'gemini'):  # the fake, before anything could start
        assert str(FAKE) in settings.value(f'dispatch_{agent}', dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    held = module.anchor(ctx, dispatch.store, NODE)  # this map has no roots, so the held ticket is at the node
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 's1', 'work_id': held, 'agent': 'claude', 'state': 'ended',
                               'how': 'the agent ended with exit code 1', 'started': '2026-10-11T00:00:00Z', 'seq': 1,
                               'origin': module.origin()})
        tx.insert('session_lines', {'session_id': 's1', 'name': 'state', 'work_id': held, 'kind': 'state', 'seq': 1,
                            'text': json.dumps({'capabilities': caps, 'cwd': str(dispatch.folder), 'about': 'system'})})
    started = []
    monkeypatch.setattr(module, 'spawn', lambda store, work_id, agent, extra, name, **_: started.append(extra) or {'pid': 0})
    monkeypatch.setattr(module, 'converse', lambda ctx, store, work_id, agent, extra: started.append(['new', agent])
                        or {'state': 'starting', 'work_id': work_id})
    assert module.stay_connected(ctx, dispatch.store) == {}, 'off by default: nothing starts'
    run('set', '--dispatch-stay-connected', cwd=dispatch.folder)
    return module, ctx, held, started


def due(work_id):
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('session_attempts', {'work_id': work_id}, {'next_at': 0.0})


@pytest.mark.req('VIEW-045')
def test_the_system_agent_kept_connected_is_resumed_in_place_with_backoff_then_waits_for_the_persons_call(
        dispatch, run, monkeypatch):
    """dispatch_stay_connected: the system agent that ended without the person's stop is resumed in place, as the
    person's own agent, after the wait, doubled each time, up to dispatch_retries; then it waits for their Call."""
    module, ctx, held, started = stay_connected(dispatch, run, monkeypatch, {'load': True})
    first = module.stay_connected(ctx, dispatch.store)
    assert started == [] and first['retry_due'] > time.time(), 'the first resume waits dispatch_retry_seconds'
    assert module.autostart(ctx)['retry_due'] == first['retry_due'], 'the agent starter says when, with Autostart off'
    due(held)
    resumed = module.stay_connected(ctx, dispatch.store)['connected']
    assert started == [['resume=s1', 'system=true']] and resumed['retry'] == 1, 'in place, never as a worker retry'
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        waited = tx.get('session_attempts', {'work_id': held})['next_at'] - time.time()
    assert 50 < waited <= 60, 'the next waits twice as long'
    due(held)
    module.stay_connected(ctx, dispatch.store)
    due(held)
    assert module.stay_connected(ctx, dispatch.store) == {} and len(started) == 2, 'dispatch_retries is 2'
    [handed] = [one for one in module.read_signals(ctx)['signals'] if one['signal'] == 'handed-over']
    assert handed['work_id'] == held and handed['next'] == 'metaform dispatch system'


@pytest.mark.req('VIEW-045')
def test_a_system_agent_that_cannot_resume_starts_a_new_conversation_and_the_person_is_told_once(
        dispatch, run, monkeypatch):
    module, ctx, held, started = stay_connected(dispatch, run, monkeypatch, {})
    module.stay_connected(ctx, dispatch.store)
    due(held)
    module.stay_connected(ctx, dispatch.store)
    due(held)
    module.stay_connected(ctx, dispatch.store)
    assert started[0] == ['new', 'claude'], 'a new conversation with the default agent, Claude Code'
    told = [one for one in module.read_signals(ctx)['signals'] if one['signal'] == 'new-conversation']
    assert len(told) == 1 and 'can neither resume nor load' in told[0]['reason']


@pytest.mark.req('VIEW-045')
def test_new_on_my_agent_ends_the_running_system_agent_and_starts_a_new_one(dispatch, monkeypatch):
    """/new on My agent is Call with fresh: the running system agent ends as the person's stop ends it and a new one
    starts resuming nothing, whatever the page knew of it; a Call without fresh reuses the running one."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    ctx = context('dispatch', dispatch.folder, project='proj')
    held = module.anchor(ctx, dispatch.store, NODE)
    running = {'session_id': 's1', 'work_id': held, 'agent': 'claude', 'state': 'running'}
    monkeypatch.setattr(module, 'sessions', lambda store, work_id=None: [] if ended else [running])
    ended, started = [], []
    monkeypatch.setattr(module, 'ended_by_person', lambda store, row: ended.append(row['session_id']) or {})
    monkeypatch.setattr(module, 'converse', lambda ctx, store, work_id, agent, extra: started.append(extra)
                        or {'state': 'starting', 'work_id': work_id})
    assert module.system(ctx)['session_id'] == 's1' and ended == [] and started == []
    fresh = context('dispatch', dispatch.folder, project='proj', nouns={'fresh': True})
    assert module.system(fresh)['state'] == 'starting'
    assert ended == ['s1'] and started == [[]]


@pytest.mark.req('VIEW-045')
def test_the_persons_stop_of_their_system_agent_turns_stay_connected_off_and_an_agents_does_not(
        dispatch, run, monkeypatch):
    """Dismiss in the chat dock is the person's stop: it turns dispatch_stay_connected off for the project, so the
    agent does not come straight back; an agent's stop over MCP leaves the person's setting as it is."""
    from metaform.module import context
    module, ctx, held, started = stay_connected(dispatch, run, monkeypatch, {'load': True})
    row = {'work_id': held, 'session_id': 's1'}
    agent = context('dispatch', dispatch.folder, project='proj', surface='mcp')
    assert module.disconnect(agent, dispatch.store, row) is False and ctx.setting('dispatch_stay_connected')
    assert module.disconnect(ctx, dispatch.store, row) is True
    assert context('dispatch', dispatch.folder, project='proj').setting('dispatch_stay_connected') is False
    run('set', '--dispatch-stay-connected', cwd=dispatch.folder)
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('agent_sessions', {'session_id': 's1'}, {'how': 'stopped by the person'})
    run('set', '--dispatch-agent=claude', cwd=dispatch.folder)  # as Call does, the default agent's conversation
    module.stay_connected(ctx, dispatch.store)
    assert started == [['resume=s1', 'system=true']], 'turned on again, it connects at once, resumed in place'
    assert module.stay_connected(ctx, dispatch.store) == {} and len(started) == 1, 'once, while that start runs'


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-045')
def test_a_home_copied_with_its_store_resumes_none_of_the_sessions_the_original_home_started(
        dispatch, run, monkeypatch, tmp_path):
    """A store copied into another home holds sessions that home never started. Its agent starter, run as its web GUI
    starts, resumes none of them, neither the person's system agent whose runner is gone nor a worker that ended on
    its own, and reads them as ended; the home that started them still resumes both, as before."""
    import shutil

    from metaform.data import Store
    from metaform.module import context
    module, _, held, started = stay_connected(dispatch, run, monkeypatch, {'load': True})
    dispatch.store.take_work(dispatch.id, None, 'claude w1')
    with Store('proj', module='dispatch').tables() as tx:  # as on 2026-10-14: a running row whose runner is gone
        tx.update('agent_sessions', {'session_id': 's1'}, {'state': 'running', 'how': None, 'pid': 2 ** 22 + 7, 'port': 9,
                                                     'token': 'x'})
        tx.insert('agent_sessions', {'session_id': 'w1', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'ended',
                               'how': 'the agent ended with exit code 1', 'started': '2026-10-11T00:00:00Z', 'seq': 2,
                               'origin': module.origin()})
        tx.insert('session_lines', {'session_id': 'w1', 'name': 'state', 'work_id': dispatch.id, 'kind': 'state', 'seq': 1,
                            'text': json.dumps({'capabilities': {'load': True}, 'cwd': str(dispatch.folder)})})
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: started.append(['start', ctx.nouns['id']]))
    copy = tmp_path / 'copied-home'
    shutil.copytree(dispatch.home, copy)

    def starts(home):
        monkeypatch.setenv('METAFORM_HOME', str(home))
        for _ in range(2):  # the first pass of each waits dispatch_retry_seconds; the second is due
            module.autostart(context('dispatch', dispatch.folder, project='proj'))
            due(held)
            due(dispatch.id)
        return {row['session_id']: (row['state'], row['how']) for row in module.sessions(Store('proj'))}

    shown = starts(copy)
    assert started == [], 'no runner, no new conversation and no ticket start in the copied home'
    assert shown == {'s1': ('ended', module.FOREIGN), 'w1': ('ended', 'the agent ended with exit code 1')}
    starts(dispatch.home)
    assert started == [['resume=s1', 'system=true'], ['resume=w1', 'retry=true']], 'its own home resumes both'


@pytest.mark.req('VIEW-045')
def test_a_legacy_row_is_resumed_by_the_persons_call_and_never_by_stay_connected(dispatch, run, monkeypatch):
    """A system conversation recorded before sessions kept their origin: stay connected leaves it, telling the person
    once that Call resumes it, and their Call does; one stamped by another home is never resumed by Call."""
    from metaform.data import Store
    module, ctx, _, started = stay_connected(dispatch, run, monkeypatch, {'load': True})
    run('set', '--dispatch-agent=claude', cwd=dispatch.folder)
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('agent_sessions', {'session_id': 's1'}, {'origin': None})
    for _ in range(2):
        assert module.stay_connected(ctx, dispatch.store) == {'legacy': 's1', 'next': 'metaform dispatch system'}
    assert started == [], 'nothing automatic resumes it'
    [told] = [one for one in module.read_signals(ctx)['signals'] if one['signal'] == 'handed-over']
    assert 'Call resumes it' in told['reason'] and told['next'] == 'metaform dispatch system'
    assert module.system(ctx)['conversation'] is True and started == [['resume=s1', 'system=true']]
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('agent_sessions', {'session_id': 's1'}, {'origin': 'elsewhere:/home/other/.metaform'})
    module.system(ctx)
    assert started[1:] == [['new', 'claude']], "another home's conversation is never resumed by Call"


def said(session_id, work_id, text, seq=1):
    """A session's row and one line of its thread, as a runner writes them: in the project's own tables, or, `legacy`,
    beside the map as versions before 16 did."""
    return ({'session_id': session_id, 'work_id': work_id, 'agent': 'claude', 'state': 'ended', 'how': 'ended',
             'started': '2026-10-16T00:00:00Z', 'seq': seq},
            {'session_id': session_id, 'name': 'line:1', 'work_id': work_id, 'kind': 'person', 'text': text,
             'seq': 1})


def threads():
    """Each session the project holds, by its id, with the text of its thread's lines."""
    from metaform.data import Store
    from metaform.modules import dispatch as module
    rows = module.sessions(Store('proj'), verify=False)
    with Store('proj', module='dispatch').tables(write=False) as tx:
        return {row['session_id']: [line['text'] for line in tx.rows('session_lines', {'session_id': row['session_id']},
                                                                     limit=0).results] for row in rows}


@pytest.mark.req('PROJ-025')
@pytest.mark.req('PROJ-026')
@pytest.mark.req('PROJ-030')
def test_a_clear_and_a_restore_keep_every_conversation_and_merge_what_was_said_since_the_backup(dispatch):
    """Rich, 2026-10-16: a clear starts the map again and nothing else. The conversations are the project's: a clear
    keeps them, those a metaform still held from before version 16 carried out first; a restore keeps what was said
    since its backup and merges what the backup's own stores held, never losing a row. The map's own lines, a
    ticket's progress, go with the map."""
    from metaform import home
    from metaform.data import Store
    from metaform.modules import dispatch as module
    with Store('proj', module='dispatch').tables() as tx:
        session, line = said('kept', dispatch.id, 'Said in the project store.')
        tx.insert('agent_sessions', session)
        tx.insert('session_lines', line)
    with Store('proj', module='dispatch').tables() as tx:  # written by a runner before version 16, beside the map
        session, line = said('older', dispatch.id, 'Said beside the map.')
        tx.insert('sessions', session)
        tx.insert('lines', line)
        tx.insert('lines', {'session_id': 'monitor:progress', 'name': dispatch.id, 'work_id': dispatch.id,
                            'kind': 'progress', 'text': '{}', 'seq': 1})
    saved = home.backup_project('proj')  # a backup made by a version before 16: its store still holds `older`
    cleared = home.clear_project('proj')
    assert 'conversations with agents stay' in cleared.said and not home.bases('proj')
    assert threads() == {'kept': ['Said in the project store.'], 'older': ['Said beside the map.']}
    with Store('proj', module='dispatch').tables() as tx:
        session, line = said('since', module.conversation_id(module.SYSTEM_TASK), 'Said after the clear.', seq=2)
        tx.insert('agent_sessions', session)
        tx.insert('session_lines', line)
    assert not home.bases('proj'), 'talking made no map again'
    restored = home.restore_project('proj', saved.name)
    assert 'conversations with agents were kept' in restored.said
    assert threads() == {'kept': ['Said in the project store.'], 'older': ['Said beside the map.'],
                         'since': ['Said after the clear.']}
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.rows('sessions', limit=0).results == ()  # carried out of the restored store, once
        assert [row['session_id'] for row in tx.rows('lines', limit=0).results] == ['monitor:progress']
    assert dispatch.ticket().id == dispatch.id, 'the map is the backup\'s again'


@pytest.mark.req('PROJ-026')
@pytest.mark.req('STORE-045')
def test_carrying_the_conversations_out_of_every_metaform_is_idempotent_and_never_drops_a_row(dispatch):
    """The carry out of each metaform's store: run twice, cut short, or over a row the project holds already, every
    row is there once; the project's row, written since, is kept over the metaform's copy; signals stay with the map."""
    import shutil

    from metaform import home
    from metaform.data import Store
    from metaform.modules import dispatch as module
    other = Store('proj').add_base('other', activate=False)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {**said('both', dispatch.id, '')[0], 'how': 'the project\'s, newer'})
    for base, session_id in ((home.active_base('proj').id, 'main-1'), (other.id, 'other-1')):
        with Store('proj', base=base, module='dispatch').tables() as tx:
            session, line = said(session_id, dispatch.id, f'Said in {session_id}.')
            tx.insert('sessions', session)
            tx.insert('lines', line)
            tx.insert('lines', {**line, 'session_id': 'broadcasts', 'name': f'broadcast:{session_id}'})
            tx.insert('sessions', {**said('both', dispatch.id, '')[0], 'how': 'the metaform\'s, older'})
            tx.insert('lines', {'session_id': f'work:{dispatch.id}', 'name': 'signal:x:', 'work_id': dispatch.id,
                                'kind': 'signal', 'text': '{}', 'seq': 1})
    path = home.store_file('proj', 'other')
    shutil.copyfile(path, path.with_name('copy-of-other.sqlite3'))  # the store as it was, to carry again
    for _ in range(2):
        module.carry_conversations(Store('proj', module='dispatch'))
    assert threads() == {'both': [], 'main-1': ['Said in main-1.'], 'other-1': ['Said in other-1.']}
    shutil.copyfile(path.with_name('copy-of-other.sqlite3'), path)  # carried again from the copy: nothing doubles
    module.carry_conversations(Store('proj', module='dispatch'))
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('agent_sessions', {'session_id': 'both'})['how'] == "the project's, newer"
        assert len(tx.rows('agent_sessions', limit=0).results) == 3
        assert sorted(row['name'] for row in tx.rows('session_lines', {'session_id': 'broadcasts'}, limit=0).results) \
            == ['broadcast:main-1', 'broadcast:other-1']
    for base in home.bases('proj'):
        with Store('proj', base=base.id, module='dispatch').tables(write=False) as tx:
            assert tx.rows('sessions', limit=0).results == ()
            assert [row['kind'] for row in tx.rows('lines', limit=0).results] == ['signal'], 'the map\'s own stays'


@pytest.mark.req('VIEW-045')
def test_the_person_talks_with_their_own_agent_with_no_map_and_no_intake(dispatch, run, monkeypatch):
    """Rich, 2026-10-16: the person can always talk to their own agent. With no element on the map, cleared or never
    made, their system agent hangs on a work id that is no ticket, nothing is written to the map, its runner talks and
    keeps its thread, and an intake is offered, never required first."""
    from metaform import home
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    home.clear_project('proj')
    ctx = context('dispatch', dispatch.folder, project='proj')
    held = module.anchor(ctx, Store('proj'))
    assert held == 'conversation-system' and module.held_ticket(Store('proj'), held) is None
    started = []
    monkeypatch.setattr(module, 'converse', lambda ctx, store, work_id, agent, extra: started.append(work_id)
                        or {'state': 'starting', 'work_id': work_id, 'conversation': True})
    assert module.system(ctx)['work_id'] == held and started == [held], 'Call starts it, with no intake first'
    run('set', '--dispatch-stay-connected', cwd=dispatch.folder)
    assert module.stay_connected(ctx, Store('proj'))['connected']['work_id'] == held, 'kept connected with no map'
    dispatch.id = held
    dispatch.start('hold', 'system=true')
    row = dispatch.session().extra
    assert row['work_id'] == held and row['state'] == 'running'
    eventually(lambda: [line for line in dispatch.items('note') if line.extra['name'] == 'state'])
    found = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)
    assert [one['work_id'] for one in found['sessions']] == [held]
    dispatch.stop()
    eventually(lambda: dispatch.session().extra['state'] == 'ended')
    assert not home.bases('proj'), 'talking with their agent made no map'


@pytest.mark.req('BASE-052')
@pytest.mark.req('PROJ-026')
def test_a_worker_keeps_its_base_when_another_becomes_active_and_stays_listed_counted_and_stoppable(dispatch, run):
    """UX review round 1, 2026-10-17 (fresh-start-intake F2, dispatch-concurrency F1, interrupt-failure-recovery F2,
    web-gui-controls F2): a new base made active while an agent works left the agent invisible, unstoppable and out of
    the slot count, or ended it with 'No work record has the id'. Every runner is pinned to the base it began on: it
    keeps working there, is listed and counted, the switch says so, and the person's stop reaches it."""
    from metaform import home
    from metaform.data import Node, Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    main = home.active_base('proj')
    dispatch.start('hold')
    row = dispatch.session().extra
    assert row['state'] == 'running' and row['base'] == main.id, 'pinned to the base it began on'
    said = run('map', 'add-base', 'fresh', '--confirm', '--json', cwd=dispatch.folder).stdout
    assert home.active_base('proj').name == 'fresh'
    assert 'One agent at work on main stays on it' in said and dispatch.id in said, said
    fresh = Store('proj')
    fresh.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    fresh.add_element('parts', NODE)
    fresh.add_work(Node('element', NODE), 'unbuilt', task='Another ticket')  # a change the runner hears and reads for
    time.sleep(2)
    assert dispatch.process.poll() is None, 'the runner keeps working on main'
    found = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)['sessions']
    assert [(one['work_id'], one['state']) for one in found] == [(dispatch.id, 'running')], found
    ctx = context('dispatch', dispatch.folder, project='proj')
    assert module.slots(ctx, Store('proj', module='dispatch'))['used'] == 1, 'it still takes its slot'
    stopped = json.loads(run('dispatch', 'stop', dispatch.id, '--json', cwd=dispatch.folder).stdout)
    assert stopped.get('stopped') is not False, stopped
    eventually(lambda: dispatch.process.poll() is not None)
    eventually(lambda: dispatch.session().extra['state'] == 'ended')
    assert Store('proj', base=main.id).ticket(dispatch.id).work.taken, 'its ticket stays in main, taken as it was'


@pytest.mark.req('VIEW-045')
@pytest.mark.req('PROJ-026')
def test_the_persons_agent_is_the_same_conversation_after_a_switch_to_an_empty_base(dispatch, run):
    """UX review round 1, 2026-10-17 (agent-identity-handoff F1 and F3, web-gui-controls F3, orchestrator F1): after a
    switch to an empty base, Call said 'Talking with an agent needs a map with one element at least', or started a
    second system agent that knew nothing while the first ran unseen. The same conversation is found and reused."""
    from metaform import home
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    ctx = context('dispatch', dispatch.folder, project='proj')
    held = module.anchor(ctx, Store('proj'), NODE)
    dispatch.id = held
    dispatch.start('hold', 'system=true')
    first = dispatch.session().extra
    eventually(lambda: [line for line in dispatch.items('note') if line.extra['name'] == 'state'])
    run('map', 'add-base', 'empty', '--confirm', cwd=dispatch.folder)
    assert home.active_base('proj').name == 'empty' and not Store('proj').roots(limit=1).entry
    again = module.system(context('dispatch', dispatch.folder, project='proj'))
    assert (again['state'], again['session_id']) == ('running', first['session_id']), again
    found = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)['sessions']
    assert [one['session_id'] for one in found if one['state'] == 'running'] == [first['session_id']]
    dispatch.stop()
    eventually(lambda: dispatch.session().extra['state'] == 'ended')


@pytest.mark.req('PROJ-025')
def test_a_clear_stops_the_agents_at_work_first_and_says_so(dispatch, run):
    """UX review round 1, 2026-10-17 (cross-surface-state F6): a clear while an agent worked left it running, unseen
    and unstoppable, writing a new base into the cleared project. The clear's caution names it, the clear stops it
    through dispatch before the stores go, and its result says so; its conversation stays."""
    from metaform import home
    dispatch.start('hold')
    row = dispatch.session().extra
    caution = run('clear', 'project', cwd=dispatch.folder, ok=False).stderr
    assert 'It stops one agent at work on it first' in caution and dispatch.id in caution, caution
    said = run('clear', 'project', '--confirm', cwd=dispatch.folder).stdout
    assert 'Stopped one agent at work on it first' in said, said
    eventually(lambda: dispatch.process.poll() is not None)
    assert dispatch.session().extra['session_id'] == row['session_id']
    assert dispatch.session().extra['state'] == 'ended', 'stopped before its store went, and its row kept'
    assert not home.bases('proj'), 'nothing made the cleared map again'


@pytest.mark.req('VIEW-045')
def test_a_runner_that_outlived_its_server_is_reused_by_a_summon_and_its_session_never_resumed_twice(
        dispatch, run, monkeypatch):
    """Rich, 2026-10-15: the system agent's runner outlived restarts of the server that started it, its parent now
    pid 1, and a summon resumed its session a second time. A live runner holding the session, or started to resume
    it and not yet in its row, is found whoever its parent is: the summon after a restart reuses it, stay connected
    leaves it, and a second runner refuses before its agent starts."""
    import contextlib
    import socket

    from metaform.data import Store
    from metaform.module import context
    module, ctx, held, started = stay_connected(dispatch, run, monkeypatch, {'load': True})
    run('set', '--dispatch-agent=claude', cwd=dispatch.folder)
    orphan = subprocess.run(  # a runner of s1 whose starter has exited, so it is no child of this process
        [sys.executable, '-c', ('import subprocess, sys; print(subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL, '
                                'stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True).pid)'),
         sys.executable, '-c', 'import time; time.sleep(120)', 'dispatch', 'run', held, 'claude', 'resume=s1',
         'system=true'], capture_output=True, text=True, check=True)
    alive = int(orphan.stdout)
    try:
        monkeypatch.setattr(module, 'spawn', lambda store, work_id, agent, extra, name, **_: started.append(extra)
                            or {'pid': alive, 'log': ''})
        assert module.system(ctx)['state'] == 'starting' and started == [['resume=s1', 'system=true']]
        restarted = context('dispatch', dispatch.folder, project='proj')  # a new server: nothing kept in memory
        again = module.system(restarted)
        assert (again['state'], again['session_id']) == ('running', 's1') and len(started) == 1, 'reused while it starts'
        assert module.stay_connected(restarted, dispatch.store) == {} and len(started) == 1
        closed = socket.socket()
        closed.bind(('127.0.0.1', 0))
        port = closed.getsockname()[1]
        closed.close()
        with Store('proj', module='dispatch').tables() as tx:  # its row written, its control port not answering
            tx.update('agent_sessions', {'session_id': 's1'}, {'state': 'running', 'how': None, 'pid': alive, 'port': port,
                                                         'token': 'x'})
        module.resuming_path('s1').unlink()
        restarted = context('dispatch', dispatch.folder, project='proj')
        # Critic round 7, F2: a runner that holds the session and does not answer is held, with its pid and the stop
        # that ends it, never running, since the person cannot talk to it
        again = module.system(restarted)
        assert (again['state'], again['session_id'], again['pid']) == ('held', 's1', alive) and len(started) == 1
        assert again['next'] == f'metaform dispatch stop {held} session=s1', again
        told = run('dispatch', 'message', held, 'session=s1', 'Hello', cwd=dispatch.folder, ok=False)
        said = told.stdout + told.stderr
        assert told.returncode != 0 and f'held by its runner, process {alive}' in said and 'dispatch stop' in said, said
        # a newer system conversation that ended on its own is not resumed beside the older one's live runner
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('agent_sessions', {'session_id': 's2', 'work_id': held, 'agent': 'claude', 'state': 'ended',
                                         'how': 'the agent ended with exit code 1', 'started': '2026-10-15T00:00:00Z',
                                   'seq': 2, 'origin': module.origin()})
            tx.insert('session_lines', {'session_id': 's2', 'name': 'state', 'work_id': held, 'kind': 'state', 'seq': 1,
                                'text': json.dumps({'capabilities': {'load': True}, 'cwd': str(dispatch.folder),
                                                    'about': 'system'})})
        for _ in range(2):  # the second pass is due
            assert module.stay_connected(restarted, dispatch.store) == {} and len(started) == 1, started
            due(held)
        assert module.system(restarted)['state'] == 'held', 'the older conversation is still held'
        refused = run('dispatch', 'run', held, 'claude', 'resume=s1', 'system=true', cwd=dispatch.folder, ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and f'held by its live runner, process {alive}' in said, said
        # the person's stop ends the held runner's process group, and their next Call starts one runner
        stopped = module.stop(context('dispatch', dispatch.folder, project='proj', nouns={'id': held, 'session': 's1'}))
        assert stopped['stopped'] is True and stopped['pid'] == alive
        eventually(lambda: module.runner_of(alive) is None, 5)
        assert module.system(context('dispatch', dispatch.folder, project='proj'))['state'] == 'starting'
        assert started[1:] == [['resume=s2', 'system=true']], 'one resume, of the latest conversation'
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(alive, signal.SIGTERM)


@pytest.mark.req('VIEW-005')
def test_the_system_agent_is_told_it_speaks_as_the_mascot_and_where_its_persona_and_tools_are(dispatch, run):
    """The mascot binding: one sentence naming the character, where its persona is written, read on demand, and the
    mascot's tools that are on the surface; nothing while no mascot is chosen."""
    from metaform.modules import dispatch as module
    assert module.mascot_line(dispatch.folder) == ''
    run('set', '--web-mascot=owl', cwd=dispatch.folder)
    line = module.mascot_line(dispatch.folder)
    assert 'You speak as owl' in line and 'persona_owl of ' in line
    written = Path(line.split('persona_owl of ')[1].split(' before ')[0])
    assert written.name == 'prompts.xml' and '<persona_owl>' in written.read_text(encoding='utf-8')
    assert 'wise, watchful owl' not in line, 'the persona is read on demand, never pushed'
    from metaform.module import surface
    [web] = [one for one in surface(dispatch.folder) if one.id == 'web']
    offered = {verb.name for verb in web.verbs}
    for verb in module.MASCOT_VERBS:
        assert (f'web_{verb}' in line) == (verb in offered), 'only the tools the agent has'


# ------------------------------------------------------------------ dispatch serve: an editor's ACP agent, BASE-062

class Editor:
    """An editor's side of ACP, as the official SDK's client: it keeps what the agent sends and allows what it asks."""

    def __init__(self):
        self.updates, self.asked = [], []

    async def session_update(self, session_id, update, **kwargs):
        self.updates.append(update.model_dump(mode='json', by_alias=True, exclude_none=True))

    async def request_permission(self, options, session_id, tool_call, **kwargs):
        from acp.schema import AllowedOutcome, RequestPermissionResponse
        self.asked.append(tool_call.title)
        return RequestPermissionResponse(outcome=AllowedOutcome(outcome='selected', option_id=options[0].option_id))

    def on_connect(self, conn):
        pass

    def said(self, kind='agent_message_chunk'):
        return [one['content'].get('text', '') for one in self.updates if one.get('sessionUpdate') == kind]

    def commands(self):
        offered = [one for one in self.updates if one.get('sessionUpdate') == 'available_commands_update']
        return [command['name'] for command in offered[-1]['availableCommands']] if offered else []


async def until(check, limit=LIMIT):
    deadline = time.monotonic() + limit
    while not (found := check()):
        if time.monotonic() > deadline:
            raise AssertionError(f'not within {limit} s')
        await asyncio.sleep(0.05)
    return found


def served(dispatch, words, body, env=None):
    """Run `metaform dispatch serve <words>` in the project folder, driven over stdio by the SDK's ACP client."""
    import acp
    from acp.schema import AuthCapabilities, ClientCapabilities, FileSystemCapabilities, Implementation

    async def session():
        editor = Editor()
        async with acp.spawn_agent_process(editor, sys.executable, '-m', 'metaform', 'dispatch', 'serve', *words,
                                           cwd=dispatch.folder, env=env or dispatch.env('ask'),
                                           transport_kwargs={'stderr': None}) as (conn, _):
            init = await conn.initialize(
                protocol_version=1, client_info=Implementation(name='editor', version='1'),
                client_capabilities=ClientCapabilities(fs=FileSystemCapabilities(read_text_file=True,
                                                                                 write_text_file=True), terminal=True,
                                                       auth=AuthCapabilities(terminal=True)))
            await body(conn, editor, init)
    asyncio.run(session())


@pytest.mark.req('BASE-062')
@pytest.mark.req('BASE-003')
def test_serve_alone_answers_its_commands_lists_and_loads_dispatch_sessions_and_cancels(dispatch):
    import acp

    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'page-1', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'ended',
                               'how': 'the ticket is done', 'started': '2026-10-11T00:00:00Z', 'seq': 1})
        tx.insert('session_lines', {'session_id': 'page-1', 'name': 'line:1', 'work_id': dispatch.id, 'kind': 'person',
                            'text': 'Write it.', 'seq': 1})
        tx.insert('session_lines', {'session_id': 'page-1', 'name': 'flow:1', 'work_id': dispatch.id,
                            'kind': 'agent_message_chunk', 'text': 'Written.', 'seq': 2})

    async def body(conn, editor, init):
        caps = init.agent_capabilities
        assert init.agent_info.name == 'metaform' and caps.load_session and caps.session_capabilities.list is not None
        made = await conn.new_session(cwd=str(dispatch.folder), mcp_servers=[])
        names = await until(editor.commands)
        assert {'map_work', 'dispatch_claims'} <= set(names), 'the verbs, named as their MCP tools'
        assert 'dispatch_serve' not in names and 'mcp_serve' not in names, 'no transport'
        answered = await conn.prompt(session_id=made.session_id, prompt=[acp.text_block('/dispatch_claims')])
        assert answered.stop_reason == 'end_turn' and 'claims' in editor.said()[-1]
        await conn.prompt(session_id=made.session_id, prompt=[acp.text_block('What is the alarm for?')])
        assert 'answers its own commands' in editor.said()[-1], 'free text is told it needs an agent'
        listed = await conn.list_sessions(cwd=str(dispatch.folder))
        assert [(one.session_id, one.title) for one in listed.sessions] == [('page-1', 'claude on Write notes.txt')]
        assert listed.sessions[0].cwd == str(dispatch.folder.resolve()), 'the folder it worked in'
        assert not (await conn.list_sessions(cwd=str(dispatch.folder / 'elsewhere'))).sessions, 'only that folder'
        assert 'page-1' in [one.session_id for one in (await conn.list_sessions()).sessions], 'every project'
        editor.updates.clear()
        await conn.load_session(cwd=str(dispatch.folder), session_id='page-1', mcp_servers=[])
        assert editor.said('user_message_chunk') == ['Write it.'] and editor.said() == ['Written.']
        waiting = asyncio.ensure_future(conn.prompt(session_id=made.session_id, prompt=[
            acp.text_block(f'/dispatch_wait until=done id={dispatch.id}')]))
        await asyncio.sleep(1)
        await conn.cancel(session_id=made.session_id)
        assert (await asyncio.wait_for(waiting, 30)).stop_reason == 'cancelled'
    served(dispatch, ['agent=none'], body)


@pytest.mark.req('BASE-062')
@pytest.mark.req('BASE-052')
def test_serve_passes_an_agent_through_with_metaforms_server_and_records_it_for_the_page(dispatch):
    import acp

    async def body(conn, editor, init):
        assert init.agent_capabilities.session_capabilities.list is not None, 'Metaform lists sessions it can load'
        [login] = [one.model_dump(by_alias=True, exclude_none=True) for one in init.auth_methods]
        assert login['id'] == 'fake-terminal' and not login.get('args'), 'no argument the serve command would refuse'
        assert login['env'] == {'FAKE_LOGIN': 'yes', 'METAFORM_SERVE_LOGIN': '["--login", "now"]'}
        found['login'] = login
        made = await conn.new_session(cwd=str(dispatch.folder), mcp_servers=[])
        answered = await conn.prompt(session_id=made.session_id, prompt=[acp.text_block('Write notes.txt')])
        assert answered.stop_reason == 'end_turn' and editor.asked == ['Write notes.txt'], 'the editor answers'
        row = await until(lambda: next((one.extra for one in dispatch.items('session')
                                         if one.extra['session_id'] == made.session_id), None))
        assert row['agent'] == 'claude' and row['state'] == 'running'
        assert dispatch.store.ticket(row['work_id']).work.task == 'Sessions from editors'
        await asyncio.to_thread(dispatch.run, 'dispatch', 'message', row['work_id'], 'Look again', cwd=dispatch.folder)
        await until(lambda: len(dispatch.received('session/prompt')) == 2)
        await until(lambda: 'Look again' in editor.said('user_message_chunk'))
        listed = await conn.list_sessions(cwd=str(dispatch.folder))
        assert made.session_id in [one.session_id for one in listed.sessions]
    found = {}
    served(dispatch, ['agent=claude'], body, dispatch.env('ask', FAKE_ACP_LOAD='1'))
    # The editor's login terminal: the configured command again, with the method's environment; Metaform becomes the
    # agent's adapter with the agent's own login arguments, ACP's terminal authentication.
    logged_in = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'serve', 'agent=claude'],
                               cwd=dispatch.folder, env={**dispatch.env('ask'), **found['login']['env']},
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=LIMIT, check=False)
    assert logged_in.returncode == 0, logged_in.stderr.decode()
    assert dispatch.logged('login') == [['--login', 'now']] and dispatch.logged('login_env') == ['yes']
    assert dispatch.logged('login_leak') == [None]
    initialize = dispatch.received('initialize')[0]['params']
    assert initialize['clientCapabilities']['fs'] == {'readTextFile': True, 'writeTextFile': True}
    assert initialize['clientCapabilities']['terminal'] is True, "the editor's capabilities, passed through"
    [server] = dispatch.received('session/new')[0]['params']['mcpServers']
    assert server['name'] == 'metaform' and server['args'][1:] == ['metaform', 'mcp', 'serve']
    assert 'METAFORM_SESSION' in {one['name'] for one in server['env']}
    assert eventually(lambda: dispatch.items('session')[-1].extra['state'] == 'ended')


class Lines:
    """An editor that speaks ACP as plain JSON-RPC lines, for what the SDK's client does not carry yet: Session
    Notices, request cancellation and message ids."""

    def __init__(self, dispatch, *words, env=None):
        import queue
        import threading
        self.process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'serve', *words],
                                        cwd=dispatch.folder, env=env or dispatch.env('ask'), stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.heard = queue.Queue()
        self.seen = []
        threading.Thread(target=lambda: [self.heard.put(json.loads(line)) for line in self.process.stdout],
                         daemon=True).start()

    def send(self, message):
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', **message}).encode() + b'\n')
        self.process.stdin.flush()

    def until(self, check):
        deadline = time.monotonic() + LIMIT
        while True:
            found = next((one for one in self.seen if check(one)), None)
            if found is not None:
                return found
            self.seen.append(self.heard.get(timeout=max(0.1, deadline - time.monotonic())))

    def answer(self, ident):
        return self.until(lambda one: one.get('id') == ident and 'method' not in one)

    def updates(self, kind):
        return [one['params']['update'] for one in self.seen if one.get('method') == 'session/update'
                and one['params']['update'].get('sessionUpdate') == kind]

    def close(self):
        self.process.stdin.close()
        self.process.wait(LIMIT)


@pytest.mark.req('BASE-062')
def test_serve_alone_tells_the_editor_by_notice_marks_its_messages_and_cancels_a_request(dispatch, run):
    run('set', '--dispatch-serve-agent', 'gemini', '--dispatch-gemini', 'no-such-adapter-anywhere', cwd=dispatch.folder)
    editor = Lines(dispatch)
    try:
        editor.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1, 'clientCapabilities': {
            'session': {'notices': {}}}}})
        caps = editor.answer(1)['result']['agentCapabilities']
        assert caps['sessionCapabilities'] == {'list': {}, 'close': {}, 'delete': {}}, 'answered, so advertised'
        assert caps['mcpCapabilities'] == {'http': False, 'sse': False}, 'no key of an unpublished draft'
        editor.send({'id': 2, 'method': 'session/new', 'params': {'cwd': str(dispatch.folder), 'mcpServers': []}})
        session = editor.answer(2)['result']['sessionId']
        notice = editor.until(lambda one: one.get('method') == 'session/update'
                              and one['params']['update'].get('sessionUpdate') == 'notice')['params']['update']
        assert notice['severity'] == 'warning' and 'serving alone' in notice['title']
        assert 'no-such-adapter-anywhere' in notice['description']
        editor.send({'id': 3, 'method': 'session/prompt', 'params': {'sessionId': session, 'prompt': [
            {'type': 'text', 'text': 'Hello'}]}})
        assert editor.answer(3)['result']['stopReason'] == 'end_turn'
        [said] = editor.updates('agent_message_chunk')
        assert said['messageId'].startswith('metaform-'), 'a message of its own, never joined to a neighbour'
        editor.send({'id': 4, 'method': 'session/prompt', 'params': {'sessionId': session, 'prompt': [
            {'type': 'text', 'text': f'/dispatch_wait until=done id={dispatch.id}'}]}})
        time.sleep(1)
        editor.send({'method': '$/cancel_request', 'params': {'requestId': 4}})
        assert editor.answer(4)['result']['stopReason'] == 'cancelled'
        editor.send({'id': 5, 'method': 'session/list', 'params': {}})
        editor.send({'id': 6, 'method': 'session/close', 'params': {'sessionId': session}})
        assert editor.answer(6)['result'] == {}
    finally:
        editor.close()


@pytest.mark.req('BASE-062')
@pytest.mark.req('BASE-052')
def test_serve_steers_each_editor_session_by_its_id_in_turn_and_takes_no_agent_slot(dispatch, run, monkeypatch):
    import acp

    from metaform.module import context
    from metaform.modules import dispatch as module
    run('set', '--dispatch-autostart', '--dispatch-agents', '1', cwd=dispatch.folder)
    launched = []
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: launched.append(ctx.nouns['id']) or
                        {'work_id': ctx.nouns['id']})

    def message(work, *words, env=None):
        return dispatch.run('dispatch', 'message', work, *words, cwd=dispatch.folder, env=env)

    async def body(conn, editor, init):
        first = await conn.new_session(cwd=str(dispatch.folder), mcp_servers=[])
        await conn.prompt(session_id=first.session_id, prompt=[acp.text_block('Write notes.txt')])
        second = await conn.new_session(cwd=str(dispatch.folder), mcp_servers=[])
        rows = await until(lambda: [one.extra for one in dispatch.items('session')] if len(
            [one for one in dispatch.items('session') if one.extra['state'] == 'running']) == 2 else None)
        work = rows[0]['work_id']
        assert {row['work_id'] for row in rows} == {work}, 'editor sessions share their held ticket'
        state = await until(lambda: next((json.loads(one.value) for one in dispatch.items('note')
                                          if one.extra['name'] == 'state' and one.extra['session_id'] ==
                                          second.session_id and 'commands' in json.loads(one.value)), None))
        assert state['commands'] == [], "the agent's own commands, as the runner keeps them"
        # the page's message to the first session goes to it, not to the latest
        await asyncio.to_thread(message, work, f'session={first.session_id}', 'For the first')
        prompted = await until(lambda: dispatch.received('session/prompt')[1:])
        assert prompted[0]['params']['sessionId'] == first.session_id
        interrupted = await asyncio.to_thread(dispatch.run, 'dispatch', 'interrupt', work,
                                              f'session={first.session_id}', '--json', cwd=dispatch.folder)
        assert json.loads(interrupted.stdout)['session_id'] == first.session_id
        await until(lambda: dispatch.received('session/cancel'))
        # an editor session is not one of dispatch's agents: the one slot is free for the ticket in To do
        await asyncio.to_thread(module.autostart, context('dispatch', dispatch.folder, project='proj'))
        assert launched == [dispatch.id]
        stopped = await asyncio.to_thread(dispatch.run, 'dispatch', 'stop', work, cwd=dispatch.folder, ok=False)
        assert stopped.returncode != 0 and 'runs in an editor' in stopped.stderr, 'ended in the editor, said so'
        # turns take their turn: the page's held turn, then the editor's prompt, which the editor's cancel ends unsent
        await asyncio.to_thread(message, f'{work}', f'session={second.session_id}', 'Look again',
                                env={'METAFORM_ROLE': 'talk'})
        await until(lambda: len(dispatch.received('session/prompt')) == 3)
        await until(lambda: 'From the talk agent: Look again' in editor.said('user_message_chunk'))
        assert 'Look again' not in editor.said('user_message_chunk')
        waiting = asyncio.ensure_future(conn.prompt(session_id=second.session_id, prompt=[acp.text_block('Next')]))
        await asyncio.sleep(1)
        assert len(dispatch.received('session/prompt')) == 3, 'no second prompt beside the turn in flight'
        await conn.cancel(session_id=second.session_id)
        assert (await asyncio.wait_for(waiting, LIMIT)).stop_reason == 'cancelled'
        assert len(dispatch.received('session/prompt')) == 3
    served(dispatch, ['agent=claude'], body, dispatch.env('ask', FAKE_ACP_HOLD_LATER='1'))


@pytest.mark.req('BASE-062')
def test_serve_keeps_the_agents_order_pages_its_list_deletes_forks_and_reaches_the_live_session(dispatch):
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        for n in range(60):
            tx.insert('agent_sessions', {'session_id': f'seed-{n:02}', 'work_id': dispatch.id, 'agent': 'claude',
                                   'state': 'ended', 'how': 'the ticket is done', 'seq': n,
                                   'started': f'2026-10-11T00:{n:02}:00Z'})
    editor = Lines(dispatch, 'agent=claude', env=dispatch.env('ask', FAKE_ACP_LOAD='1', FAKE_ACP_INFO='1',
                                                                FAKE_ACP_FORK='1', FAKE_ACP_CLOSE='1'))
    folder = str(dispatch.folder)
    try:
        editor.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1, 'clientCapabilities': {}}})
        editor.answer(1)
        # the agent writes its answer and an update of the new session in one write: the editor hears them in order
        editor.send({'id': 2, 'method': 'session/new', 'params': {'cwd': folder, 'mcpServers': []}})
        info = editor.until(lambda one: one.get('method') == 'session/update'
                            and one['params']['update'].get('sessionUpdate') == 'session_info_update')
        made = editor.answer(2)
        assert editor.seen.index(made) < editor.seen.index(info), 'the session id before an update of it'
        session = made['result']['sessionId']
        row = eventually(lambda: next((one.extra for one in dispatch.items('session')
                                       if one.extra['session_id'] == session), None))
        eventually(lambda: any(one.extra['name'] == 'state' and 'Fake title' in one.value
                               for one in dispatch.items('note') if one.extra['session_id'] == session))

        asked = [100]

        def walk():
            pages, cursor = [], None
            while True:
                asked[0] += 1
                editor.send({'id': asked[0], 'method': 'session/list',
                             'params': {'cwd': folder, **({'cursor': cursor} if cursor else {})}})
                page = editor.answer(asked[0])['result']
                pages.append(page)
                cursor = page.get('nextCursor')
                if not cursor:
                    return pages
        pages = walk()
        assert pages[0]['nextCursor'] == 'metaform:50' and len(pages) == 2
        listed = [one['sessionId'] for page in pages for one in page['sessions']]
        assert len(listed) == len(set(listed)) == 61, 'every session once, across the pages'
        first = pages[0]['sessions'][0]
        assert (first['sessionId'], first['title'], first['updatedAt']) == (session, 'Fake title 1',
                                                                          '2030-01-01T00:00:00Z'), 'as the agent named it'
        # a deleted session leaves every later list
        editor.send({'id': 3, 'method': 'session/delete', 'params': {'sessionId': 'seed-05'}})
        assert editor.answer(3)['result'] == {}
        listed = [one['sessionId'] for page in walk() for one in page['sessions']]
        assert 'seed-05' not in listed and len(listed) == 60
        # a fork is a session like a new one: Metaform's server, its commands and its record
        editor.send({'id': 4, 'method': 'session/fork', 'params': {'sessionId': session, 'cwd': folder,
                                                                   'mcpServers': []}})
        forked = editor.answer(4)['result']['sessionId']
        [fork] = dispatch.received('session/fork')
        assert [one['name'] for one in fork['params']['mcpServers']] == ['metaform']
        offered = editor.until(lambda one: one.get('method') == 'session/update' and one['params']['sessionId'] ==
                               forked and one['params']['update'].get('sessionUpdate') == 'available_commands_update')
        assert 'dispatch_claims' in [one['name'] for one in offered['params']['update']['availableCommands']]
        eventually(lambda: any(one.extra['session_id'] == forked for one in dispatch.items('session')))
        # a row a killed process left, the latest on the ticket, is passed over for the live session before it
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('agent_sessions', {'session_id': 'dead-1', 'work_id': row['work_id'], 'agent': 'claude',
                                   'state': 'running', 'pid': 2 ** 22 + 7, 'port': 9, 'token': 'x', 'seq': 10 ** 15,
                                   'started': '2026-10-12T00:00:00Z'})
        dispatch.run('dispatch', 'message', row['work_id'], 'hello', cwd=dispatch.folder)
        assert eventually(lambda: [one for one in dispatch.received('session/prompt')
                                   if one['params']['prompt'][0]['text'] == 'hello'])
    finally:
        editor.close()


@pytest.mark.req('BASE-062')
def test_a_serve_that_answers_late_keeps_its_editor_session_running(dispatch, monkeypatch):
    from metaform.data import Store
    from metaform.modules import dispatch as module
    monkeypatch.setattr(module, 'runner_of', lambda pid: module.SERVED)
    monkeypatch.setattr(module, 'tell', lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
    row = {'session_id': 's', 'work_id': 'held', 'state': 'running', 'pid': 123, 'port': 9, 'token': 't'}
    assert module.session_status(Store('proj', module='dispatch'), row, done=False)['state'] == 'running'


@pytest.mark.req('BASE-062')
def test_serve_as_a_proxy_of_a_conductors_chain_carries_metaforms_mcp_server_over_acp(dispatch):
    """Initialized with the reference conductor's `_proxy/initialize`, serve starts no agent: it reaches its successor
    through `_proxy/successor`, gives the agent that advertises MCP-over-ACP Metaform's server as `type: "acp"`,
    answers the agent's `mcp/message` itself, and passes another provider's on with every id mapped back."""
    editor = Lines(dispatch, 'agent=claude')
    folder = str(dispatch.folder)

    def wrapped(method):
        return editor.until(lambda one: one.get('method') == '_proxy/successor' and one['params']['method'] == method)
    try:
        editor.send({'id': 1, 'method': '_proxy/initialize', 'params': {'protocolVersion': 1, 'clientCapabilities': {}}})
        asked = wrapped('initialize')
        editor.send({'id': asked['id'], 'result': {'protocolVersion': 1, 'agentInfo': {'name': 'chained', 'version': '1'},
                                                   'agentCapabilities': {'mcpCapabilities': {'acp': True}}}})
        assert editor.answer(1)['result']['agentCapabilities']['mcpCapabilities'] == {'acp': True}
        editor.send({'id': 2, 'method': 'session/new', 'params': {'cwd': folder, 'mcpServers': []}})
        made = wrapped('session/new')
        [server] = made['params']['params']['mcpServers']
        assert server['type'] == 'acp' and server['name'] == 'metaform', 'over ACP, as the agent takes it'
        editor.send({'id': made['id'], 'result': {'sessionId': 'chained-1'}})
        assert editor.answer(2)['result'] == {'sessionId': 'chained-1'}
        meta = {'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                'io.modelcontextprotocol/clientCapabilities': {},
                'io.modelcontextprotocol/clientInfo': {'name': 'chained', 'version': '1'}}
        editor.send({'id': 77, 'method': '_proxy/successor', 'params': {'method': 'mcp/message', 'params': {
            'serverId': server['serverId'], 'requestId': 'r-1', 'method': 'tools/list', 'params': {'_meta': meta}}}})
        tools = editor.answer(77)['result']['result']['tools']
        assert any(tool['name'].startswith('map_') for tool in tools), 'answered by Metaform\'s own MCP server'
        editor.send({'id': 78, 'method': '_proxy/successor', 'params': {'method': 'mcp/message', 'params': {
            'serverId': 'another', 'requestId': 'r-2', 'method': 'tools/list'}}})
        passed = editor.until(lambda one: one.get('method') == 'mcp/message')
        assert passed['params']['serverId'] == 'another' and passed['id'] != 78, 'its own id on this hop'
        editor.send({'id': passed['id'], 'result': {'result': {'tools': []}}})
        assert editor.answer(78)['result'] == {'result': {'tools': []}}
        editor.send({'method': '_proxy/successor', 'params': {'method': 'session/update', 'params': {
            'sessionId': 'chained-1', 'update': {'sessionUpdate': 'agent_message_chunk', 'messageId': 'm-1',
                                                 'content': {'type': 'text', 'text': 'from the chain'}}}}})
        assert editor.until(lambda one: one.get('method') == 'session/update' and one['params']['update']
                            .get('messageId') == 'm-1')['params']['sessionId'] == 'chained-1'
        row = eventually(lambda: next((one.extra for one in dispatch.items('session')
                                       if one.extra['session_id'] == 'chained-1'), None))
        assert row['agent'] == 'chained', 'recorded under the name its initialize gave'
        assert dispatch.received('initialize') == [], 'no agent of its own started'
    finally:
        editor.close()


@pytest.mark.req('BASE-062')
def test_serve_alone_names_slash_commands_only_while_it_offers_them(dispatch, run):
    """Settings cleanup 2026-10-15: the commands are always offered where a module gives one; dispatch_serve_commands,
    which could turn them off, is gone."""
    run('set', '--dispatch-serve-agent', 'gemini', '--dispatch-gemini', 'no-such-adapter-anywhere', cwd=dispatch.folder)
    editor = Lines(dispatch)
    try:
        editor.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1, 'clientCapabilities': {
            'session': {'notices': {}}}}})
        editor.answer(1)
        editor.send({'id': 2, 'method': 'session/new', 'params': {'cwd': str(dispatch.folder), 'mcpServers': []}})
        session = editor.answer(2)['result']['sessionId']
        notice = editor.until(lambda one: one.get('method') == 'session/update'
                              and one['params']['update'].get('sessionUpdate') == 'notice')['params']['update']
        editor.send({'id': 3, 'method': 'session/prompt', 'params': {'sessionId': session, 'prompt': [
            {'type': 'text', 'text': 'Hello'}]}})
        editor.answer(3)
        [said] = editor.updates('agent_message_chunk')
        assert 'slash commands work' in notice['description']
        assert 'type / to list them' in said['content']['text']
        assert 'Free text needs an agent behind it.' in notice['description']
    finally:
        editor.close()


@pytest.mark.req('BASE-062')
def test_serve_lists_the_agents_pages_then_its_own_each_session_once(dispatch):
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        for n in range(60):
            tx.insert('agent_sessions', {'session_id': f'seed-{n:02}', 'work_id': dispatch.id, 'agent': 'claude',
                                   'state': 'ended', 'how': 'the ticket is done', 'seq': n,
                                   'started': f'2026-10-11T00:{n:02}:00Z'})
    editor = Lines(dispatch, 'agent=claude', env=dispatch.env('ask', FAKE_ACP_LOAD='1', FAKE_ACP_LIST='1'))
    try:
        editor.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1, 'clientCapabilities': {}}})
        editor.answer(1)
        pages, cursor, asked = [], None, 10
        while True:
            asked += 1
            editor.send({'id': asked, 'method': 'session/list',
                         'params': {'cwd': str(dispatch.folder), **({'cursor': cursor} if cursor else {})}})
            page = editor.answer(asked)['result']
            pages.append(page)
            if not (cursor := page.get('nextCursor')):
                break
        assert [page.get('nextCursor') for page in pages] == ['fake-page-2', 'metaform:50', None]
        listed = [one['sessionId'] for page in pages for one in page['sessions']]
        assert len(listed) == len(set(listed)) == 63, 'the agent\'s four, then the 59 it did not list, each once'
        assert listed[:4] == ['fake-listed-1', 'fake-listed-2', 'fake-listed-3', 'seed-03']
    finally:
        editor.close()


@pytest.mark.req('BASE-062')
def test_serve_speaks_acp_v2_with_an_agent_that_negotiates_it(dispatch):
    """A v2 agent: its capabilities read from `capabilities`, Metaform's server typed stdio, a prompt answered at
    insertion, and the record keyed by message and tool call ids, so a replaced message is one line."""
    editor = Lines(dispatch, 'agent=claude', env=dispatch.env('ask', FAKE_ACP_V2='1'))
    folder = str(dispatch.folder)
    try:
        editor.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 2, 'capabilities': {},
                                                                 'info': {'name': 'editor', 'version': '1'}}})
        assert editor.answer(1)['result']['protocolVersion'] == 2
        editor.send({'id': 2, 'method': 'session/new', 'params': {'cwd': folder, 'mcpServers': []}})
        session = editor.answer(2)['result']['sessionId']
        [server] = dispatch.received('session/new')[0]['params']['mcpServers']
        assert server['type'] == 'stdio' and server['name'] == 'metaform'
        editor.send({'id': 3, 'method': 'session/prompt', 'params': {'sessionId': session, 'prompt': [
            {'type': 'text', 'text': 'hi'}]}})
        assert editor.answer(3)['result'] == {'messageId': 'fake-user-1'}
        lines = eventually(lambda: (found := {one.extra['name']: one.value for one in dispatch.items('note')
                                              if one.extra['session_id'] == session}).get('turn') and found)
        assert lines['message:fake-agent-1'] == 'Hello v2', 'the upsert replaced the streamed text'
        assert lines['message:fake-user-1'] == 'hi', 'the person\'s message once, as the agent reported it'
        assert lines['tool:fake-edit'] == ('Edit config (completed): modify /work/config.json; '
                                           'move /work/a.txt -> /work/b.txt')
        assert lines['turn'] == 'The turn ended: end_turn.'
        editor.send({'id': 4, 'method': 'session/prompt', 'params': {'sessionId': session, 'prompt': [
            {'type': 'text', 'text': '/dispatch_claims'}]}})
        assert editor.answer(4)['result']['messageId'].startswith('metaform-'), 'answered at insertion'
        idle = editor.until(lambda one: one.get('method') == 'session/update' and one['params']['update']
                            .get('state') == 'idle' and one['params']['update'].get('stopReason') == 'end_turn')
        assert idle['params']['sessionId'] == session
    finally:
        editor.close()


@pytest.mark.req('BASE-052')
def test_an_agent_that_answers_another_protocol_version_is_closed_before_any_session(dispatch, run):
    """ACP's initialization: an agent that answers with a version the runner does not speak is not used; the runner
    says which versions, and asks for no session and sends no prompt. Its ticket still reads that it did not start
    and why, from an ended session row the runner leaves."""
    dispatch.start('hold', FAKE_ACP_V2='1')
    said = dispatch.process.communicate(timeout=30)[1].decode('utf-8')
    assert 'did not start' in said and 'protocol version 2' in said and 'speaks version 1' in said
    assert dispatch.received('initialize') and not dispatch.received('session/new')
    assert not dispatch.received('session/prompt')
    read = json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    [row] = read['sessions']
    assert row['state'] == 'ended' and row['how'].startswith('it did not start') and 'protocol version 2' in row['how']
    assert [line['kind'] for line in read['lines'] if line['session_id'] == row['session_id']] == ['failed']


class Conducted(Lines):
    """An editor of the reference conductor (crates.io agent-client-protocol-conductor), which runs serve as a proxy
    before the fake agent; METAFORM_ACP_CONDUCTOR names the conductor's program."""

    def __init__(self, dispatch, conductor, env):
        import queue
        import threading
        serve = f'{sys.executable} -m metaform dispatch serve'
        self.process = subprocess.Popen([conductor, 'agent', serve, f'{sys.executable} {FAKE}'], cwd=dispatch.folder,
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
        self.heard = queue.Queue()
        self.seen = []
        threading.Thread(target=lambda: [self.heard.put(json.loads(line)) for line in self.process.stdout],
                         daemon=True).start()


@pytest.mark.req('BASE-062')
@pytest.mark.skipif(not os.environ.get('METAFORM_ACP_CONDUCTOR'), reason='the reference conductor is not installed')
def test_serve_in_the_reference_conductors_chain_answers_the_agents_mcp_over_acp(dispatch):
    editor = Conducted(dispatch, os.environ['METAFORM_ACP_CONDUCTOR'], dispatch.env('ask', FAKE_ACP_MCP_ACP='1'))
    try:
        editor.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1, 'clientCapabilities': {}}})
        assert editor.answer(1)['result']['agentCapabilities']['mcpCapabilities']['acp'] is True
        editor.send({'id': 2, 'method': 'session/new', 'params': {'cwd': str(dispatch.folder), 'mcpServers': []}})
        session = editor.answer(2)['result']['sessionId']
        [declared] = dispatch.received('session/new')[0]['params']['mcpServers']
        assert declared['type'] == 'acp' and declared['name'] == 'metaform'
        [answer] = eventually(lambda: dispatch.logged('mcp_acp'))
        assert any(tool['name'].startswith('map_') for tool in answer['result']['tools'])
        editor.send({'id': 3, 'method': 'session/prompt', 'params': {'sessionId': session, 'prompt': [
            {'type': 'text', 'text': '/dispatch_claims'}]}})
        assert editor.answer(3)['result']['stopReason'] == 'end_turn', 'Metaform answers its command in the chain'
    finally:
        editor.close()


# ------------------------------------------------------------------ the client's files, terminals and forks, P019, P030

@pytest.mark.req('BASE-052')
def test_the_runner_serves_files_and_terminals_confined_to_the_session_folder(dispatch, run):
    """P019: the runner offers ACP's fs and terminal methods; a file inside the session's folder is written and read
    by line, one outside it is refused and said in the thread, and a terminal runs, exits, gives its output and is
    released, its line kept in the thread."""
    run('dispatch', 'link', 'file=fake-client/note.txt', f'node={NODE}', cwd=dispatch.folder)  # unlocked, #3d
    dispatch.start('ask', FAKE_ACP_CLIENT='1')
    [client] = eventually(lambda: dispatch.logged('client'))
    offered = dispatch.received('initialize')[0]['params']['clientCapabilities']
    assert offered['fs'] == {'readTextFile': True, 'writeTextFile': True} and offered['terminal'] is True
    assert client['read'] == {'content': 'two\n'}
    assert (dispatch.folder / 'fake-client' / 'note.txt').read_text(encoding='utf-8') == 'one\ntwo\nthree\n'
    assert 'error' in client['outside'] and 'outside the session' in json.dumps(client['outside'])
    assert client['exit']['exitCode'] == 0
    assert 'hi from terminal' in client['output']['output'] and client['output']['exitStatus']['exitCode'] == 0
    assert client['output']['truncated'] is False and 'error' in client['gone'], 'a released terminal is gone'
    lines = eventually(lambda: [one for one in dispatch.items('note') if one.extra['kind'] == 'terminal'
                                and json.loads(one.value)['exit']])
    assert 'hi from terminal' in json.loads(lines[0].value)['output']
    assert any(one.extra['kind'] == 'notice' and 'refused' in one.value for one in dispatch.items('note'))
    state = eventually(lambda: next((json.loads(one.value) for one in dispatch.items('note')
                                     if one.extra['name'] == 'state' and json.loads(one.value)['files']), None))
    assert {'path': 'fake-client/note.txt', 'action': 'read'} in state['files']
    dispatch.stop()


def test_a_write_to_an_unlinked_file_is_refused_with_the_link_call_and_goes_through_once_linked(dispatch, run,
                                                                                               tmp_path):
    """code.dispatcher.agent#3d: a file no element's ref names exactly is locked for writing, the refusal naming the
    call that links it; a read of it is not refused; once dispatch link adds its ref the same write goes through and
    the file is placed exactly. A path .metaform/ignore.txt holds stays read-only, linked or not."""
    skip_while_unlocked()
    (dispatch.folder / 'src').mkdir(exist_ok=True)
    (dispatch.folder / 'src' / 'fresh.py').write_text('old\n', encoding='utf-8')
    (dispatch.folder / 'rich').mkdir(exist_ok=True)
    (dispatch.folder / 'rich' / 'notes.md').write_text('mine\n', encoding='utf-8')
    (dispatch.folder / '.metaform').mkdir(exist_ok=True)
    (dispatch.folder / '.metaform' / 'ignore.txt').write_text('rich/\n', encoding='utf-8')
    run('dispatch', 'link', 'file=rich/notes.md', f'node={NODE}', cwd=dispatch.folder)
    gate = tmp_path / 'linked'
    dispatch.start('hold', FAKE_ACP_WRITES='src/fresh.py,rich/notes.md', FAKE_ACP_WRITE_GATE=str(gate))
    [first] = eventually(lambda: dispatch.logged('writes'))
    assert [one.get('content') for one in first['read']] == ['old\n', 'mine\n'], 'reads are never refused'
    unlinked, ignored = (json.dumps(one) for one in first['write'])
    assert 'To unlock access to this file, please first link it to its functionality in the map.' in unlinked
    assert 'dispatch_link file=src/fresh.py node=' in unlinked
    assert 'error' in json.loads(ignored) and 'read-only to agents' in ignored
    assert (dispatch.folder / 'src' / 'fresh.py').read_text(encoding='utf-8') == 'old\n'
    linked = json.loads(run('dispatch', 'link', 'file=src/fresh.py', f'node={NODE}', '--json',
                            cwd=dispatch.folder).stdout)
    assert (linked['file'], linked['linked']) == ('src/fresh.py', True)
    gate.write_text('', encoding='utf-8')
    [again] = eventually(lambda: dispatch.logged('writes_again'))
    assert 'error' not in again[0], again[0]
    assert 'read-only to agents' in json.dumps(again[1]), 'the ignore list holds it whatever its link'
    assert (dispatch.folder / 'src' / 'fresh.py').read_text(encoding='utf-8') == 'written\n'
    assert (dispatch.folder / 'rich' / 'notes.md').read_text(encoding='utf-8') == 'mine\n'
    state = eventually(lambda: next((json.loads(one.value) for one in dispatch.items('note')
                                     if one.extra['name'] == 'state'
                                     and {'path': 'src/fresh.py', 'action': 'edit'} in json.loads(one.value)['files']),
                                    None))
    assert (NODE, 'edit') in [(one['address'], one['action']) for one in state['touched']]
    dispatch.stop()


def test_dispatch_link_adds_the_ref_beside_the_elements_own_and_never_makes_an_element(dispatch, run):
    from metaform.data import Node
    from metaform.modules.dispatch.runner import placed, sources_index
    run('dispatch', 'link', 'file=src/a.py', f'node={NODE}', cwd=dispatch.folder)
    run('dispatch', 'link', 'file=src/b.py', f'node={NODE}', cwd=dispatch.folder)
    again = json.loads(run('dispatch', 'link', 'file=src/b.py', f'node={NODE}', '--json', cwd=dispatch.folder).stdout)
    assert again['linked'] is False
    dispatch.store.layer('base', 'intake', 'The map.', kind='intake', mutable=False, hideable=False)
    refused = run('dispatch', 'link', 'file=docs/new.md', 'node=document.guide.new', '--json', cwd=dispatch.folder,
                  ok=False)
    assert refused.returncode != 0 and 'linking never makes an element' in refused.stdout + refused.stderr
    assert dispatch.store.element('document.guide.new', raw=True) is None
    node = dispatch.store.element(NODE)
    held = dispatch.store.refs(Node('element', node.id))  # each a record of its own, code.graph.knowledge#c
    assert [(ref.key, ref.value, ref.ref) for ref in held] == [('path', 'src/a.py', f'a@{NODE}'),
                                                               ('path', 'src/b.py', f'b@{NODE}')]
    index = sources_index(dispatch.store, str(dispatch.folder))
    assert placed(index, 'src/a.py') == ([{'kind': 'element', 'id': node.id, 'address': NODE}], True)
    assert placed(index, 'src/a.py/inner')[1] is False, 'a folder fallback is not exact'
    assert placed(index, 'docs/new.md')[1] is False, 'a link refused at a missing address places nothing'


@pytest.mark.cli_process
def test_a_burst_of_reads_of_linked_files_reads_the_sources_layer_once(dispatch, run, monkeypatch):
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules.dispatch import runner
    (dispatch.folder / 'src').mkdir(exist_ok=True)
    for name in ('a', 'b', 'c'):
        (dispatch.folder / 'src' / f'{name}.py').write_text(name, encoding='utf-8')
        run('dispatch', 'link', f'file=src/{name}.py', f'node={NODE}', cwd=dispatch.folder)
    reads = []
    real = runner.sources_index
    monkeypatch.setattr(runner, 'sources_index', lambda *given: reads.append(1) or real(*given))
    session = runner.Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                             dispatch.ticket(), 'claude', [])
    session.session_id = 'unit-session'

    async def burst():
        for _ in range(10):
            for name in ('a', 'b', 'c'):
                await session.read_text_file('unit-session', str(dispatch.folder / 'src' / f'{name}.py'))
        assert await session.locked('src/a.py') is None
    asyncio.run(burst())
    assert len(reads) == 1, 'thirty reads, one read of the sources layer'


@pytest.mark.req('BASE-052')
def test_an_edit_permission_for_an_unlinked_file_is_refused_over_approve_all_and_the_agent_is_told(dispatch, run):
    skip_while_unlocked()
    run('set','--dispatch-prompts=approve-all', '--confirm', cwd=dispatch.folder)
    dispatch.start('ask', FAKE_ACP_ASK_PATH=str(dispatch.folder / 'src' / 'fresh.py'))
    [outcome] = eventually(lambda: dispatch.logged('permission'))
    assert outcome == {'outcome': {'outcome': 'selected', 'optionId': 'reject'}}
    told = eventually(lambda: [one for one in dispatch.received('session/prompt')
                               if 'To unlock access to this file' in json.dumps(one)])
    assert 'dispatch_link file=src/fresh.py' in json.dumps(told[0])
    assert not dispatch.questions(), 'the person is not asked'
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_codex_is_kept_asking_and_cannot_write_an_unlinked_or_ignored_file_or_lift_its_sandbox(dispatch, run):
    """code.dispatcher.agent#43, CTX-061 and CTX-062: Codex is set to read-only, the mode in which it asks before every
    file change and its commands cannot write, while the mode it began in, agent, approves its edit of a linked file
    without asking the person. A file change asked by its path alone, of an unlinked file or an ignore-listed one, a
    command outside the sandbox, and write access for the project folder are each refused and the agent told why; an
    MCP tool's approval, which Codex also asks as execute, is not a command and goes through.
    Claude Code is sent a sandbox in which the project folder is read-only to every command."""
    skip_while_unsandboxed()
    (dispatch.folder / 'src').mkdir(exist_ok=True)
    (dispatch.folder / 'rich').mkdir(exist_ok=True)
    (dispatch.folder / '.metaform').mkdir(exist_ok=True)
    (dispatch.folder / '.metaform' / 'ignore.txt').write_text('rich/\n', encoding='utf-8')
    run('dispatch', 'link', 'file=src/kept.py', f'node={NODE}', cwd=dispatch.folder)
    run('dispatch', 'link', 'file=rich/notes.md', f'node={NODE}', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_CODEX='1', FAKE_ACP_STEER='1',
                   FAKE_ACP_CODEX_PATH=str(dispatch.folder / 'src' / 'fresh.py'),
                   FAKE_ACP_CODEX_IGNORED=str(dispatch.folder / 'rich' / 'notes.md'),
                   FAKE_ACP_CODEX_LINKED=str(dispatch.folder / 'src' / 'kept.py'))
    [answers] = eventually(lambda: dispatch.logged('codex'))
    assert dispatch.logged('mode') == ['read-only']
    assert {name: one['outcome']['optionId'] for name, one in answers.items()} == {
        'unlinked': 'cancel', 'escalation': 'cancel', 'grant': 'cancel', 'ignored': 'cancel', 'linked': 'approved',
        'mcp': 'approved'}
    parts = ('dispatch_link file=src/fresh.py', 'rich/notes.md is read-only to agents', 'Commands run in a sandbox')

    def told() -> str | None:
        said = ' '.join(dispatch.logged('steered'))
        return said if all(part in said for part in parts) else None
    eventually(told)
    assert not dispatch.questions(), 'the person is not asked'
    meta = dispatch.received('session/new')[0]['params']['_meta']['claudeCode']['options']['settings']['sandbox']
    denied = meta['filesystem']['denyWrite']
    assert str(dispatch.folder.resolve() / 'rich') in denied and str(dispatch.folder.resolve()) not in denied, \
        'the sandbox denies what the lock denies, never the whole project, #47'
    assert (meta['enabled'], meta['allowUnsandboxedCommands']) == (True, False)
    dispatch.stop()


def test_a_command_in_the_runners_terminal_cannot_write_the_project(dispatch):
    """code.dispatcher.agent#43, CTX-062: the runner's own terminal runs a command with the project folder read-only,
    so a shell write to a file of the project leaves it unchanged; where no sandbox can do that, it runs none."""
    skip_while_unlocked()
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules.dispatch import runner
    (dispatch.folder / 'src').mkdir(exist_ok=True)
    target = dispatch.folder / 'src' / 'fresh.py'
    target.write_text('old\n', encoding='utf-8')
    session = runner.Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                             dispatch.ticket(), 'claude', [])
    session.session_id = 'unit-session'

    async def shell() -> int | None:
        try:
            made = await session.create_terminal('unit-session', sys.executable,
                                                 ['-c', f'open({str(target)!r}, "w").write("new")'])
        except acp.RequestError:
            return None
        held = session.terminals[made.terminal_id]
        code = await held.process.wait()
        if held.reader is not None:
            await held.reader
        return code
    code = asyncio.run(shell())
    assert target.read_text(encoding='utf-8') == 'old\n'
    assert code != 0 if code is not None else runner.confined_command([], 'x', []) is None


def test_commands_may_write_linked_files_and_tool_folders_and_nothing_else_of_the_project(tmp_path):
    """code.dispatcher.agent#47: the command sandbox denies what the lock denies and no more: an unlinked file, a
    folder holding no linked file, whole, and a path the ignore list holds, linked or not; a linked file and the
    tools' own folders stay writable, and the project folder itself is never denied, since Claude Code lets a denied
    folder win over anything allowed inside it."""
    from metaform.modules.dispatch.runner import denied_writes
    for name in ('src/kept.py', 'src/fresh.py', 'docs/a.md', 'rich/notes.md', '.venv/lib/x.py', '.git/index',
                 '.git/hooks/pre-commit', 'src/__pycache__/kept.pyc', 'pyproject.toml'):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text('', encoding='utf-8')
    place = [{'kind': 'element', 'id': 'e', 'address': NODE}]
    denied = denied_writes(str(tmp_path), str(tmp_path), {'src/kept.py': place, 'rich/notes.md': place}, ['rich/'])
    root = tmp_path.resolve()
    assert sorted(denied) == sorted(str(root / name) for name in ('.git/hooks', 'docs', 'pyproject.toml', 'rich',
                                                                  'src/fresh.py'))


def test_the_lock_holds_for_a_session_only_once_its_rule_has_gone_to_it(dispatch, monkeypatch):
    """code.dispatcher.agent#47: a session never told the rule on writing files is refused nothing; once the rule has
    gone with a prompt, the same write is refused with the owner's sentence."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules.dispatch import runner
    monkeypatch.setattr(runner, 'LINK_LOCK', True)
    session = runner.Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                             dispatch.ticket(), 'claude', [])

    async def asked() -> tuple[str | None, str | None]:
        before = await session.locked('src/fresh.py')
        session.ruled = True
        return before, await session.locked('src/fresh.py')
    before, after = asyncio.run(asked())
    assert before is None and after is not None and 'please first link it' in after


def test_a_resumed_session_is_told_the_rule_with_its_next_prompt(dispatch, run, dispatch_runners):
    """code.dispatcher.agent#47, CTX-060: a session resumed in a new runner gets the rule on writing files at the end
    of the next prompt it is sent, never as a turn of its own, so no refusal reaches it before the rule does."""
    skip_while_unlocked()
    from metaform.modules.dispatch import prompt
    rule = prompt('work_link')
    dispatch.start('hold', FAKE_ACP_LOAD='1')
    [first] = eventually(lambda: dispatch.received('session/prompt'))
    assert first['params']['prompt'][0]['text'].endswith(f'\n\n{rule}')
    dispatch.stop()
    assert dispatch.process.wait(30) == 0
    started = json.loads(run('dispatch', 'resume', dispatch.id, '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold', FAKE_ACP_LOAD='1')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    eventually(lambda: dispatch.session().extra['state'] == 'running')
    assert len(dispatch.received('session/prompt')) == 1, 'the rule is no turn of its own'
    run('dispatch', 'message', dispatch.id, 'Carry on', cwd=dispatch.folder)
    resumed = eventually(lambda: dispatch.received('session/prompt')[1:])[0]
    assert resumed['params']['prompt'][0]['text'] == f'Carry on\n\n{rule}'
    run('dispatch', 'stop', dispatch.id, cwd=dispatch.folder)


@pytest.mark.req('BASE-052')
def test_the_client_files_and_terminal_settings_turn_them_off(dispatch, run):
    run('set', '--no-dispatch-client-files', '--no-dispatch-client-terminal', cwd=dispatch.folder)
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    offered = dispatch.received('initialize')[0]['params']['clientCapabilities']
    assert offered['fs'] == {'readTextFile': False, 'writeTextFile': False} and offered['terminal'] is False
    dispatch.stop()


@pytest.mark.req('BASE-052')
def test_a_fork_keeps_the_sessions_identity_and_has_a_thread_of_its_own(dispatch, run):
    """P030: dispatch fork asks the agent for session/fork, giving the fork the same Metaform server with the same
    identity, and its first turn and its end are in a child thread of the session."""
    dispatch.start('hold', FAKE_ACP_FORK='1')
    eventually(lambda: dispatch.logged('grandchild'))
    forked = json.loads(run('dispatch', 'fork', dispatch.id, '--json', '--', 'What else did you consider?',
                            cwd=dispatch.folder).stdout)
    [asked] = dispatch.received('session/fork')
    made = dispatch.received('session/new')[0]['params']
    assert asked['params']['sessionId'] == 'fake-session-1' and asked['params']['cwd'] == made['cwd']
    assert asked['params']['mcpServers'] == made['mcpServers'], 'the same server and identity'
    env = {one['name']: one['value'] for one in asked['params']['mcpServers'][0]['env']}
    assert env['METAFORM_WORK'] == dispatch.id and env['METAFORM_ROLE'] == 'worker'
    assert forked['identity']['METAFORM_SESSION'] == env['METAFORM_SESSION']
    child = forked['fork']
    [line] = [json.loads(one.value) for one in dispatch.items('note') if one.extra['name'] == f'subagent:{child}']
    assert line['fork'] is True, 'the page tells a fork from the agent\'s own subagent'
    assert eventually(lambda: any(one.value == 'The turn ended: end_turn.' for one in dispatch.items('note')
                                  if one.extra['session_id'] == child))
    prompted = [one['params'] for one in dispatch.received('session/prompt') if one['params']['sessionId'] == child]
    assert prompted[0]['prompt'][0]['text'] == 'What else did you consider?'
    dispatch.stop()


@pytest.mark.req('BASE-052')
@pytest.mark.kind('fixture')
def test_a_turns_usage_is_one_invoke_agent_span_with_cached_input_counted(monkeypatch):
    """The OTel export: one client span per turn, its input tokens holding the cached part as the GenAI conventions
    ask, since ACP's inputTokens leaves it out."""
    from types import SimpleNamespace

    from metaform.modules.dispatch import runner
    usage = SimpleNamespace(input_tokens=100, output_tokens=40, cached_read_tokens=1000, cached_write_tokens=5,
                            thought_tokens=None)
    found = runner.usage_attributes('claude', 'Claude Code', '0.89.1', 's-1', usage, 'end_turn', 'opus')
    assert found['gen_ai.usage.input_tokens'] == 1105 and found['gen_ai.usage.output_tokens'] == 40
    assert found['gen_ai.usage.cache_read.input_tokens'] == 1000 and found['gen_ai.provider.name'] == 'anthropic'
    assert found['gen_ai.operation.name'] == 'invoke_agent' and found['gen_ai.conversation.id'] == 's-1'
    spans = []

    class Span:
        def __init__(self, name, **given):
            spans.append((name, given))

        def end(self):
            spans.append('ended')

    from opentelemetry import trace
    monkeypatch.setattr(trace, 'get_tracer', lambda name: SimpleNamespace(start_span=Span))
    runner.traced(found, 7)
    assert spans[0][0] == 'invoke_agent Claude Code' and spans[0][1]['start_time'] == 7 and spans[1] == 'ended'
    assert spans[0][1]['kind'] == trace.SpanKind.CLIENT and spans[0][1]['attributes'] is found


@pytest.mark.req('BASE-052')
def test_a_turn_that_fails_is_traced_with_its_error(dispatch, monkeypatch):
    """Every turn is traced: one whose prompt fails is a span too, its finish reason error and
    its error given, so error.type is set."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from metaform.data import Store
    from metaform.modules.dispatch import runner
    spans = []
    monkeypatch.setattr(runner, 'traced', lambda attributes, started_ns, error=None: spans.append((attributes, error)))

    async def exercise():
        held = runner.Session(SimpleNamespace(nouns={}), Store('proj', module='dispatch'), dispatch.ticket(), 'claude',
                              [])
        held.session_id = 'failing-turn'
        held.prep = True
        held.conn = SimpleNamespace(prompt=AsyncMock(side_effect=RuntimeError('the agent fell over')))
        held.note = AsyncMock()
        held.changed = AsyncMock()
        held.turn('First turn')
        await asyncio.wait_for(asyncio.gather(*tuple(held.tasks)), 5)

    asyncio.run(exercise())
    [(attributes, error)] = spans
    assert error == 'the agent fell over' and attributes['gen_ai.response.finish_reasons'] == ['error']


# ------------------------------------------------------------------ the ACP Registry, P013 and P030

def registry_of(tmp_path, **entry):
    """A private registry of one binary agent, fakeacp 1.2.3, whose archive for this platform holds a script that runs
    the fake agent, with its sha256; the file the dispatch_registry_url setting can name."""
    import hashlib
    import io
    import tarfile

    from metaform.modules.dispatch import registry
    script = f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n'.encode()
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode='w:gz') as archive:
        info = tarfile.TarInfo('fake-acp')
        info.size, info.mode = len(script), 0o644
        archive.addfile(info, io.BytesIO(script))
    archive_path = tmp_path / 'fake-acp-1.2.3.tar.gz'
    archive_path.write_bytes(packed.getvalue())
    target = {'archive': archive_path.as_uri(), 'cmd': './fake-acp', 'args': ['--acp'],
              'sha256': hashlib.sha256(packed.getvalue()).hexdigest(), 'env': {'FAKE_SECRET': 'from-registry'}}
    agent = {'id': 'fakeacp', 'name': 'Fake ACP', 'version': '1.2.3', 'description': 'A fake agent.',
             'license_url': 'https://example.com/license', 'distribution': {'binary': {registry.platform(): target}},
             **entry}
    path = tmp_path / 'registry.json'
    path.write_text(json.dumps({'version': '1.0.0', 'agents': [agent], 'extensions': []}), encoding='utf-8')
    return path


@pytest.mark.req('BASE-052')
@pytest.mark.skipif(os.name == 'nt', reason='the fake archive holds a POSIX shell script')
def test_a_registry_agent_is_pinned_installed_primed_and_started(dispatch, run, tmp_path):
    """P013: an agent of the ACP Registry other than dispatch's own is chosen, its archive checked against its
    sha256 and unpacked at that exact version, its options read by priming, and it works a ticket."""
    path = registry_of(tmp_path)
    run('set', '--dispatch-registry-url', str(path), cwd=dispatch.folder)
    listed = json.loads(run('dispatch', 'registry', '--json', cwd=dispatch.folder).stdout)
    assert [(one['agent'], one['runs_here'], one['pinned']) for one in listed['agents']] == [('fakeacp', 'binary', None)]
    added = json.loads(run('dispatch', 'registry', 'add=fakeacp', '--json', cwd=dispatch.folder).stdout)
    [changed] = added['changed']
    assert (changed['pinned'], changed['kind'], changed['verified']) == ('1.2.3', 'binary', True)
    assert changed['command'].endswith('fake-acp --acp') and '/agents/fakeacp/1.2.3/' in changed['command']
    agents = json.loads(run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout)['agents']
    mine = next(one for one in agents if one['agent'] == 'fakeacp')
    assert (mine['available'], mine['pinned'], mine['label']) == (True, '1.2.3', 'Fake ACP')
    primed = json.loads(run('dispatch', 'options', 'agent=fakeacp', 'prime=true', '--json', cwd=dispatch.folder,
                            env=dispatch.env('hold', **rich(dispatch))).stdout)['agents'][0]
    assert [one['key'] for one in primed['settings']] == ['mode', 'model', 'thought_level']
    ran = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'run', dispatch.id, 'fakeacp'],
                         cwd=dispatch.folder, env=dispatch.env('done'), capture_output=True, text=True, timeout=60,
                         check=False)
    assert ran.returncode == 0, ran.stderr
    assert dispatch.ticket().done
    [row] = [one.extra for one in dispatch.items('session')]
    assert row['agent'] == 'fakeacp'
    assert any(entry.get('secret') == 'from-registry' and entry['argv'][-1] == '--acp' for entry in dispatch.entries())
    # a newer version listed later leaves the pin where it is until the person upgrades
    path.write_text(path.read_text(encoding='utf-8').replace('1.2.3', '1.2.4'), encoding='utf-8')
    refreshed = json.loads(run('dispatch', 'registry', 'refresh=true', '--json', cwd=dispatch.folder).stdout)
    assert refreshed['agents'][0]['version'] == '1.2.4' and refreshed['agents'][0]['pinned'] == '1.2.3'


@pytest.mark.req('BASE-052')
def test_a_registry_archive_whose_checksum_differs_is_not_installed(dispatch, run, tmp_path):
    path = registry_of(tmp_path)
    wrong = json.loads(path.read_text(encoding='utf-8'))
    from metaform.modules.dispatch import registry
    wrong['agents'][0]['distribution']['binary'][registry.platform()]['sha256'] = '0' * 64
    path.write_text(json.dumps(wrong), encoding='utf-8')
    run('set', '--dispatch-registry-url', str(path), cwd=dispatch.folder)
    refused = run('dispatch', 'registry', 'add=fakeacp', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'sha256' in refused.stdout + refused.stderr
    assert run('dispatch', 'agents', '--json', cwd=dispatch.folder).stdout.count('fakeacp') == 0


@pytest.mark.req('BASE-052')
@pytest.mark.kind('fixture')
def test_the_publication_entry_is_checked_against_the_registry_schema(tmp_path):
    from metaform.modules.dispatch import registry
    good = registry.publication(agent_id='metaform', name='Metaform', version='1.0.0', description='Maps.',
                                package='metaform-acp', repository='https://github.com/example/metaform',
                                license_name='MIT', license_url='https://example.com/LICENSE')
    assert good['problems'] == [] and good['entry']['distribution'] == {
        'uvx': {'package': 'metaform-acp==1.0.0', 'args': ['dispatch', 'serve']}}
    calendar = registry.publication(agent_id='metaform', name='Metaform', version='2026.9.30.2', description='Maps.',
                                    package='metaform', repository=None, license_name=None, license_url=None)
    assert any(problem.startswith('version:') for problem in calendar['problems'])
    assert any('license_url' in problem for problem in calendar['problems'])


# ------------------------------------------------------------------ the intake's guards, M04

@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
def test_an_intake_agent_is_withheld_conclusions_and_steered_to_its_first_record(dispatch, run, dispatch_runners):
    """The intake agent's Metaform server is told to leave out memory and the map's reading tools; reading a review
    file or calling a memory tool raises intake-conclusions; with no Metaform call in time it reads as waiting for
    first record and is steered once, and its first record is timed in its state."""
    run('set', '--dispatch-intake-first-record', '3', cwd=dispatch.folder)
    started = json.loads(run('dispatch', 'intake', 'agent=claude', '--json', cwd=dispatch.folder,
                             env=dispatch.env('hold', FAKE_ACP_INTAKE='1', FAKE_ACP_STEER='1')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    work_id = started['work_id']
    waiting = eventually(lambda: next((one for one in read(run, dispatch, work_id)['sessions']
                                       if one.get('phase') == 'waiting for first record'), None))
    assert (waiting['status'], waiting['reason']) == ('running', 'waiting for first record')
    [made] = eventually(lambda: dispatch.received('session/new'))
    env = {one['name']: one['value'] for one in made['params']['mcpServers'][0]['env']}
    assert env['METAFORM_ROLE'] == 'intake' and env['METAFORM_WITHHELD'] == 'memory,map:read'
    def reached():
        found = [one for one in json.loads(run('dispatch', 'signals', f'id={work_id}', '--json',
                                               cwd=dispatch.folder).stdout)['signals']
                 if one['signal'] == 'intake-conclusions']
        return found if len(found) == 2 else None
    signals = eventually(reached)
    assert {one['reason'] for one in signals} == {'a withheld tool', 'a file of earlier conclusions'}
    [steer] = eventually(lambda: dispatch.logged('steered'))
    assert 'without a Metaform call' in steer
    eventually(lambda: dispatch.logged('intake_recorded'))
    state = eventually(lambda: found if (found := next(
        (json.loads(one.value)['intake'] for one in dispatch.items('note')
         if one.extra['session_id'] != f'work:{work_id}' and one.extra['name'] == 'state'), None)) and
        found.get('first_record_s') is not None else None)
    assert state['phase'] == 'recording' and state['steered'] and state['first_call_s'] >= 1
    run('dispatch', 'stop', work_id, cwd=dispatch.folder)


@pytest.mark.req('BASE-039')
@pytest.mark.kind('fixture')
def test_a_server_serving_a_withheld_session_leaves_those_tools_out(monkeypatch, run, project_folder):
    from metaform.module import WITHHELD, surface
    whole = {module.id: [verb.name for verb in module.verbs] for module in surface(project_folder)}
    monkeypatch.setenv(WITHHELD, 'memory,map:read')
    kept = {module.id: [verb.name for verb in module.verbs] for module in surface(project_folder)}
    assert 'memory' in whole and 'memory' not in kept
    assert 'node' in whole['map'] and 'node' not in kept['map'] and 'work' in kept['map'] and 'intake' in kept
    from metaform.harness import child_environment
    assert WITHHELD not in child_environment(), 'no process the server starts is withheld anything'


# ------------------------------------------------------------------ the status vocabulary of work, H02

@pytest.mark.req('BASE-051')
@pytest.mark.req('BASE-052')
def test_a_cancelled_ticket_and_its_session_read_cancelled_in_the_status_vocabulary(dispatch, run):
    """One cancelled ticket reads cancelled, never completed, in its work read, its session's read and a wait."""
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    working = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)['dispatch']
    assert (working['status'], working['sessions'][-1]['status']) == ('running', 'running')
    run('dispatch', 'cancel', dispatch.id, '--', 'No longer needed', cwd=dispatch.folder)
    assert dispatch.process.wait(LIMIT) == 0
    read = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)['dispatch']
    assert read['status'] == 'cancelled' and read['sessions'][-1]['status'] == 'cancelled'
    listed = json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', 'thread=false', '--json',
                            cwd=dispatch.folder).stdout)['sessions']
    assert (listed[-1]['status'], listed[-1]['reason']) == ('cancelled', 'cancelled by the person')
    waited = json.loads(run('dispatch', 'wait', 'until=done', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert waited['woke'][0]['status'] == 'cancelled'


@pytest.mark.req('BASE-052')
@pytest.mark.kind('fixture')
def test_waits_on_the_person_and_a_dead_runner_are_told_apart_from_work():
    from metaform.modules.dispatch import session_work_status
    running = {'session_id': 's', 'state': 'running', 'activity': 'working'}
    assert session_work_status(running) == {'status': 'running', 'reason': None}
    assert session_work_status(running, [{'signal': 'login-needed', 'session_id': 's'}]) == \
        {'status': 'input_required', 'reason': 'login'}
    assert session_work_status({**running, 'waiting_on': 'permission'})['reason'] == 'permission'
    assert session_work_status({**running, 'activity': 'idle'}, [{'signal': 'stopped-open', 'session_id': 's'}]) == \
        {'status': 'input_required', 'reason': 'stopped'}
    assert session_work_status({**running, 'phase': 'waiting for first record'}) == \
        {'status': 'running', 'reason': 'waiting for first record'}
    died = {'session_id': 's', 'state': 'ended', 'how': 'the runner is no longer running'}
    assert session_work_status(died) == {'status': 'failed', 'reason': 'runner died'}
    assert session_work_status({**died, 'how': 'the ticket is done'})['status'] == 'completed'


@pytest.mark.req('BASE-051')
@pytest.mark.req('MAP-050')
def test_a_workflow_answer_reaches_the_worker_that_paused_the_run(dispatch, run):
    """H03: a worker pauses a workflow run on the person; once the person answers it, the runner hears the answer
    and gives the worker the workflow_answered turn, so no message of the person's is needed."""
    from metaform.data import Store
    from metaform.modules.workflow.tests.test_executor import begin
    run('enable', 'workflow')
    dispatch.start('hold', FAKE_ACP_STEER='1')
    eventually(lambda: dispatch.logged('grandchild'))
    word = begin(Store('proj', module='workflow'))
    run('workflow', 'pause', f'run={word}', 'Which', 'timer?', cwd=dispatch.folder,
        env={'METAFORM_WORK': dispatch.id, 'METAFORM_SESSION': 'r1'})
    time.sleep(1)  # the runner hears the pause before the answer, as it would while the person reads the ticket
    run('workflow', 'answer', f'run={word}', 'The', 'oven', cwd=dispatch.folder)
    wanted = f'Run {word} is answered; resume it with metaform workflow resume run={word}'
    assert eventually(lambda: dispatch.logged('steered')) == [wanted], 'into the turn in flight, as it steers'
    dispatch.stop()


# ------------------------------------------------------------------ Jev's hooks in dispatch, H23

def decided(answer, sure=True):
    from metaform.jev import Decision
    return Decision('pick_one', 'title', 'why', 'question', (), answer, 0.9, sure, 'reason', 'jev', 0.0, False)


@pytest.mark.req('MAP-058')
@pytest.mark.req('VIEW-042')
def test_autostart_takes_jevs_sure_agent_and_options_only_where_the_person_chose_none(dispatch, run, monkeypatch):
    """With Jev on, autostart starts a ticket the person gave no agent with the agent Jev is sure of, and passes its
    model and effort on, under the person's own; a ticket whose eligible agents leave Jev's out, or with Jev unsure,
    starts as before."""
    from metaform import jev
    from metaform.jev import Assignments
    from metaform.module import context
    from metaform.modules import dispatch as module
    picked, unsure = glyphed(dispatch, run, ('Picked by Jev', None, False), ('Jev unsure', None, False))
    eligible(dispatch, run, dispatch.id, 'codex')  # Jev's pick is not eligible here, so the eligible agent starts
    run('set', '--dispatch-autostart', '--dispatch-agent', 'codex', cwd=dispatch.folder)
    asked = []
    monkeypatch.setattr(jev, 'config', lambda folder, decision=None: object())
    monkeypatch.setattr(jev, 'choose_agents', lambda folder, tickets, agents, options, **kw: asked.append(
        (sorted(tickets), sorted(agents))) or Assignments({
            dispatch.id: decided({'agent': 'gemini', 'model': None, 'thought_level': None}),
            picked: decided({'agent': 'gemini', 'model': 'large', 'thought_level': 'high'}),
            unsure: decided({'agent': 'gemini', 'model': None, 'thought_level': None}, sure=False)}))
    launched = []
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: launched.append(
        (ctx.nouns['id'], ctx.nouns['agent'], ctx.nouns.get('chosen'))) or {'work_id': ctx.nouns['id']})
    module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert asked == [(sorted([dispatch.id, picked, unsure]), ['claude', 'codex', 'gemini'])]
    assert launched == [(dispatch.id, 'codex', None),
                        (picked, 'gemini', json.dumps({'model': 'large', 'thought_level': 'high'})),
                        (unsure, 'codex', None)]


@pytest.mark.req('MAP-058')
def test_autostart_starts_as_before_when_jev_is_off_or_fails(dispatch, run, monkeypatch):
    from metaform import jev
    from metaform.module import context
    from metaform.modules import dispatch as module
    run('set', '--dispatch-autostart', '--dispatch-agent', 'codex', cwd=dispatch.folder)
    monkeypatch.setattr(jev, 'config', lambda folder, decision=None: object())

    def failing(*args, **kw):
        raise OSError('unreachable')
    monkeypatch.setattr(jev, 'choose_agents', failing)
    launched = []
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: launched.append(
        (ctx.nouns['id'], ctx.nouns['agent'])) or {'work_id': ctx.nouns['id']})
    module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert launched == [(dispatch.id, 'codex')]


@pytest.mark.req('BASE-057')
def test_jevs_drift_check_raises_the_drift_signal_naming_what_drifted(dispatch, monkeypatch):
    """H23: with Jev on, a worker's recent tool calls and filed steps are judged by session_drift; a sure drift
    raises the drift signal at the ticket, naming what drifted, and one judged clean clears it."""
    from metaform import jev
    from metaform.module import context
    from metaform.modules.dispatch import runner
    from metaform.modules.dispatch.signals import rows
    answers = [{'conclusions': False, 'off_task': True, 'repeating': None},
               {'conclusions': False, 'off_task': False, 'repeating': False}]
    judged = []

    def drift(folder, session, calls, task, **kw):
        judged.append((list(calls), task))
        return decided(answers[len(judged) - 1])
    monkeypatch.setattr(jev, 'session_drift', drift)
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.id, 'agent': 'claude'})
    session = runner.Session(ctx, dispatch.store, dispatch.ticket(), 'claude', ['unused'])
    session.calls.extend(['Read report.md {"path": "artifacts/report.md"}', 'Read src/engine.py'])
    asyncio.run(session.drift())
    [raised] = [one for one in rows(dispatch.store, dispatch.id) if one['signal'] == 'drift']
    assert raised['drifted'] == ['off_task'] and judged[0] == (list(session.calls), 'Write notes.txt')
    asyncio.run(session.drift())
    assert not [one for one in rows(dispatch.store, dispatch.id) if one['signal'] == 'drift']


@pytest.mark.req('STORE-029')
def test_a_runner_the_store_outgrew_hands_its_session_and_what_it_was_sent_to_the_code_on_disk(dispatch, monkeypatch):
    """code.dispatcher.agent#48: a store at a layout past the runner's code refuses a line; with the code on disk
    changed, the runner hands the session over at that refusal instead of going on writing nothing, keeping what it is
    sent after; with the code on disk the same, the refusal fails the session. The code on disk ends the old row as
    handed over, keeps the ticket taken, and resumes that very session, besides the old runner still running."""
    from metaform.data import NewerStore, Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import runner

    def refused(tx):
        raise NewerStore('the store has schema version 23; this Metaform supports version 22.', 'install it')

    def session():
        made = runner.Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                              dispatch.ticket(), 'claude', ['unused'])
        made.session_id, made.recorded = 's1', True
        return made
    monkeypatch.setattr(runner, 'LOADED', 'the code this process loaded')
    held = session()
    held.pending.append('a prompt waiting its turn')
    assert asyncio.run(held.table(refused, fatal=False)) is None
    assert held.handing and held.how == module.HANDED and held.ended.is_set() and held.failure is None
    held.turn('sent after the refusal')
    assert [one['text'] for one in held.handed_on] == ['a prompt waiting its turn', 'sent after the refusal']
    monkeypatch.setattr(runner, 'LOADED', runner.code_print())
    same = session()
    asyncio.run(same.table(refused, fatal=False))
    assert not same.handing and isinstance(same.failure, NewerStore), 'no newer code to hand to: it fails'

    dispatch.store.take_work(dispatch.id, None, 'claude s1')
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 's1', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'running',
                               'pid': os.getpid(), 'runner': 'r1', 'started': '2026-10-15T22:05:00Z', 'seq': 1,
                               'origin': module.origin()})
    module.resuming_path('s1').parent.mkdir(parents=True, exist_ok=True)
    module.resuming_path('s1').write_text(str(os.getpid()), encoding='utf-8')  # the old runner was itself a resume
    spawned = []
    monkeypatch.setattr(module, 'runner_of', lambda pid: dispatch.id)
    monkeypatch.setattr(module, 'command_line', lambda pid: ['dispatch', 'run', dispatch.id, 'resume=s1'])
    monkeypatch.setattr(module, 'spawn', lambda store, work_id, agent, extra, name, **_: spawned.append(extra) or {'pid': 7})
    carried = [{'text': 'hello', 'by': None}]
    assert module.hand_over(dispatch.store, dispatch.id, 'claude', 's1', 'r2', os.getpid(), [], carried) == \
        {'state': 'gone'} and not spawned, 'a late hand-over, the row another runner\'s, starts nothing'
    assert module.hand_over(dispatch.store, dispatch.id, 'claude', 's1', 'r1', os.getpid(), ['system=true'],
                            carried)['pid'] == 7
    assert spawned == [['resume=s1', 'system=true']]
    [row] = [one.extra for one in dispatch.items('session')]
    assert (row['state'], row['how']) == ('ended', module.HANDED)
    assert dispatch.ticket().taken_by == 'claude s1', 'the ticket stays the session\'s'
    assert json.loads(module.handed_path('s1').read_text(encoding='utf-8')) == {'carried': carried}


@pytest.mark.req('STORE-029')
def test_the_runner_taking_a_session_over_says_so_once_and_sends_what_the_old_runner_was_sent(dispatch):
    """code.dispatcher.agent#48: the resumed runner writes one restart line, then each carried message's line and
    turn in order; a prompt whose line was written goes as a turn only, and the hand-over file is used once."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import runner
    path = module.handed_path('s1')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'carried': [{'text': 'queued before', 'by': None}, {'text': 'hello', 'by': ''},
                                            {'text': 'from a peer', 'by': 'worker'}]}), encoding='utf-8')
    session = runner.Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                             dispatch.ticket(), 'claude', ['unused'])
    session.session_id = 's1'
    noted, turns = [], []

    async def note(key, kind, text):
        noted.append((kind, text))
    session.note = note
    session.turn = lambda text, *rest: turns.append(text)
    asyncio.run(session.taken_over())
    asyncio.run(session.taken_over())
    assert [kind for kind, _ in noted] == ['notice', 'person', 'message']
    assert noted[0][1].startswith('Restarted on updated code') and noted[2][1] == 'From the worker agent: from a peer'
    assert turns == ['queued before', 'hello', 'from a peer'] and not path.exists()
