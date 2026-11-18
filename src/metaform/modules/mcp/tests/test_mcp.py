"""The mcp module: surfaced tools, calls and project selection."""
from __future__ import annotations

import ast
import asyncio
import contextlib
import functools
import importlib
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import typing

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform.data import Store


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"
CHASSIS_TOOLS = {'metaform_set', 'metaform_feedback', 'metaform_list_reports', 'metaform_read_report',
                 'metaform_instructions', 'metaform_register'}
REGISTERED_TOOLS = CHASSIS_TOOLS - {'metaform_register'}  # registering is listed until the folder has a project


def session(home, folder, fn, heard=None, env=None):
    """A real MCP client on `metaform mcp serve` in the folder, with `env` added to its environment, such as a
    dispatched agent's role; the methods of the notifications it hears go in `heard`."""
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home), **(env or {})})

    async def hear(message):
        method = getattr(message, 'method', None)
        if heard is not None and method:
            heard.append(method)

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write, message_handler=hear) as client:
            init = await client.initialize()
            return await fn(client, init)
    return asyncio.run(go())


# Explicit pre-use guidance is checked in its own tests. Ignore any guidance headings and the provisioning notice
# when reading an operation's substantive result, MCP-028.
GUIDED = re.compile(r"^(How to use \S+:|The \S+ module's rules[, :])|^Results are trimmed to the "
                    r"fields most next steps need|^Notice: Read metaform help provision")


def text(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None
            and not GUIDED.match(item.text)]


class Command:
    """One command of a tool, with what it takes."""

    def __init__(self, description, input_schema):
        self.description, self.input_schema = description, input_schema


async def listed(client):
    """Discover each declaring module on demand, retaining directory text like a real client."""
    found = {tool.name: tool for tool in (await client.list_tools()).tools}
    directory = await client.read_resource('metaform://modules')
    names = re.findall(r'^- ([\w.-]+):', '\n'.join(one.text for one in directory.contents), re.MULTILINE)
    if names:
        client._module_names = names
    for module in getattr(client, '_module_names', []):
        await client.call_tool('metaform_catalog', {'module': module})
        found.update({tool.name: tool for tool in (await client.list_tools()).tools})
    return dict(sorted(found.items()))


async def first_listed(client):
    """The tools the session is listed as it starts, before it opens any category."""
    return {tool.name: tool for tool in (await client.list_tools()).tools}


async def tool_names(client):
    """Every command the server offers, by its tool's name, `<module>_<command>` or `metaform_<command>`, with the
    description and input schema it is listed with, MCP-003."""
    return {name: Command(tool.description, tool.input_schema) for name, tool in (await listed(client)).items()}


async def called(client, name, arguments):
    """A simulated informed agent follows one exact instruction challenge, then retries once.

    Prerequisite tests deliberately use raw call_tool instead, so this client behavior never hides enforcement.
    """
    handle = getattr(client, '_usage_handle', None)
    result = await client.call_tool(name, arguments, meta={'io.metaform/session': handle} if handle else None)
    required = result.structured_content or {}
    if result.is_error and required.get('error') == 'instructions_required':
        alias = required['read_tool']
        guide = await client.call_tool(alias['tool'], alias['arguments'])
        assert not guide.is_error, blocks(guide)
        reads = getattr(client, '_instruction_reads', [])
        reads.append((name, blocks(guide)))
        client._instruction_reads = reads
        client._usage_handle = required.get('session_handle', handle)
        handle = client._usage_handle
        result = await client.call_tool(name, arguments, meta={'io.metaform/session': handle} if handle else None)
    return result


async def whole(client, name, arguments):
    """A module tool's whole result as data, as an agent asks for it with view=full; a chassis tool's, which is given
    whole, as it comes."""
    given = arguments if name.startswith('metaform_') else {**arguments, 'view': 'full'}
    return json.loads(text(await called(client, name, given))[-1])


@pytest.fixture
def mapped(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                            provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE', name='audible alarm')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
    return folder


@pytest.mark.req('MCP-001')
def test_mcp_is_a_module_and_off_means_no_server(run, module_row, tmp_path):
    assert module_row('mcp')[1] == 'on'
    run('disable', 'mcp')
    refused = run('mcp', 'serve', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform enable mcp'
    run('list', 'projects')


HISTORY_TOOLS = {'metaform_add_origin', 'metaform_list_origins', 'metaform_add_variant', 'metaform_list_variants',
                 'metaform_extract'}


LOOPBACK = ('127.0.0.1', 'localhost', '::1')
# web's calls to its own page server, at the address its run record holds: Metaform's own process, not the open world
OWN_SERVER = ('answering', 'held_open', 'ask_page')
# home functions that open a write transaction for bookkeeping: the first base made on first use, the chassis meta
HOME_BOOKKEEPING = ('ensure_base', 'set_meta')
# functions whose module-table writes are bookkeeping: memory carries the old memory layer into its graph once
TABLE_BOOKKEEPING = ('_carry',)
# files written as bookkeeping: a store made 0600 before SQLite opens it, a module's resources copied, the page token
FILE_BOOKKEEPING = ('metaform.sqlite.private', 'metaform.loader._copy_resources', 'metaform_module_system_web.token')
# read verbs that write only on a surface the MCP server is not: the note is written from the web page alone
WEB_ONLY_WRITES = {'memory_note': 'writes only from the web page; a call from any other surface with text is refused'}
# These reads save only the screenshot the caller requests, rather than changing the map or the viewed page.
SCREENSHOT_ONLY_WRITES = {
    'web_look': 'reads the page through Playwright and saves only an explicitly requested screenshot',
    'web_capture': 'reads a frame of the page and saves the requested screenshot',
}


class Reach:
    """What a verb reaches, read from the source of each function it can call: names through the function's globals,
    closure and the imports inside it; `ctx.`, `store.` and `self.` methods through their classes; a published topic
    through its subscribers; a `metaform <module> <verb>` process it starts through that verb. A sink is `network`, a
    connection that is not to this machine; `write`, a Store method that writes the map, or a change to the settings;
    `send`, project text sent to a third party through `metaform.jev`, which spends the person's credit. Bookkeeping
    is no write: a module's tables made or upgraded on first use, a cache, what a session was shown. Three more kinds
    say a verb does something without making it a write of the map: `local`, a request to Metaform's own process on
    this machine; `process`, a process started; `file`, a file written outside the stores. Calls on any other object,
    a module's table rows among them, are not followed, so a reach found is certain and one missed is possible."""

    def __init__(self, modules):
        import http.client
        import shutil
        import socket
        import urllib.request

        from metaform import home, jev
        from metaform.module import Context
        self.modules = modules
        self.subscribers = {}
        for module in modules:
            for subscription in module.subscriptions:
                self.subscribers.setdefault(subscription.topic, []).append(subscription.handler)
        self.typed = {'ctx': Context, 'store': Store}
        self.network = {urllib.request.urlopen, http.client.HTTPConnection, http.client.HTTPSConnection,
                        socket.create_connection}
        self.writes = {*(method for name, method in vars(Store).items()
                         if inspect.isfunction(method) and not name.startswith('_')
                         and 'self._write()' in inspect.getsource(method)),
                       *(function for name, function in vars(home).items()
                         if inspect.isfunction(function) and function.__module__ == home.__name__
                         and not name.startswith('_') and name not in HOME_BOOKKEEPING
                         and 'write=True)' in inspect.getsource(function))}
        # a module's data operations, which Store runs by name: a write operation is a write of the map
        self.operations = {name: declared for module in modules if module.data is not None
                           for name, declared in module.data.operations.items()}
        self.writes |= {declared.run for declared in self.operations.values() if declared.write}
        # an edit of a prompt in the home's prompt store changes what agents are sent; `shipped`, the version of what a
        # module serves, is bookkeeping of what was served, as a table made on first use is
        from metaform.data import prompts
        self.writes |= {prompts.add_prompt, prompts.add_prompt_version, prompts.save_prompt}
        self.send = jev.post
        self.processes = {subprocess.run, subprocess.call, subprocess.check_call, subprocess.check_output}
        self.files = {os.replace, os.rename, os.remove, os.unlink, shutil.copy, shutil.copy2, shutil.copyfile,
                      shutil.copytree, shutil.move, shutil.rmtree}
        self.read = {}

    def verb(self, module_id, name):
        return next((verb.run for module in self.modules if module.id == module_id
                     for verb in module.verbs if verb.name == name), None)

    def sinks(self, start):
        """Each sink the function reaches, with the calls that lead to it."""
        found, seen, queue = {}, set(), [(start, [])]
        while queue:
            fn, path = queue.pop(0)
            if fn in seen:
                continue
            seen.add(fn)
            here = [*path, f'{fn.__module__}.{fn.__qualname__}']
            callees, sinks = self.parsed(fn)
            for kind, what in sinks:
                found.setdefault(kind, [*here, what])
            queue += [(callee, here) for callee in callees]
        return found

    def parsed(self, fn):
        if fn not in self.read:
            self.read[fn] = self._parse(fn)
        return self.read[fn]

    def _parse(self, fn):
        fn = inspect.unwrap(fn)
        fn = getattr(fn.func if isinstance(fn, functools.partial) else fn, '__func__', fn)
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            scope = {**fn.__globals__, **inspect.getclosurevars(fn).nonlocals, **self.imported(tree, fn)}
        except (OSError, TypeError, SyntaxError, ValueError, AttributeError):
            return [], []
        owner = scope.get(fn.__qualname__.split('.')[0]) if '.' in fn.__qualname__ else None
        local = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)} | {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        scope = {name: value for name, value in scope.items() if name not in local}
        assigned = {target.id: node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name)}
        callees, sinks = [], []
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            targets = [self.resolved(call.func, scope, owner)]
            targets += [self.resolved(arg, scope, owner) for arg in [*call.args, *(k.value for k in call.keywords)]
                        if isinstance(arg, (ast.Name, ast.Attribute))]  # a function handed on, to a thread or a hook
            if isinstance(call.func, ast.Attribute) and call.func.attr in ('publish', 'publish_async') and call.args \
                    and isinstance(call.args[0], ast.Constant):
                callees += self.subscribers.get(call.args[0].value, [])
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'tables' \
                    and fn.__name__ not in TABLE_BOOKKEEPING and not any(
                    k.arg == 'write' and isinstance(k.value, ast.Constant) and k.value.value is False
                    for k in call.keywords):
                sinks.append(('write', f'{ast.unparse(call.func)}()'))  # a module's tables, written
            if f'{fn.__module__}.{fn.__qualname__}' not in FILE_BOOKKEEPING and self.writes_file(call, targets[0]):
                sinks.append(('file', ast.unparse(call.func)))
            for target in filter(None, targets):
                if target in self.network:
                    said = [ast.unparse(arg) for arg in call.args[:1]]
                    said += [ast.unparse(assigned[arg.id]) for arg in call.args[:1]
                             if isinstance(arg, ast.Name) and arg.id in assigned]
                    if fn.__name__ not in OWN_SERVER and not any(host in one for one in said for host in LOOPBACK):
                        sinks.append(('network', target.__qualname__))
                    else:
                        sinks.append(('local', target.__qualname__))
                elif target in self.processes:
                    sinks.append(('process', target.__qualname__))
                elif target in self.writes:
                    sinks.append(('write', target.__qualname__))
                elif target is self.send:
                    sinks += [('send', 'jev.post'), ('network', 'jev.post')]
                elif target is subprocess.Popen and call.args:
                    sinks.append(('process', 'Popen'))
                    command = assigned.get(call.args[0].id) if isinstance(call.args[0], ast.Name) else call.args[0]
                    words = [one.value for one in getattr(command, 'elts', []) if isinstance(one, ast.Constant)]
                    at = words.index('metaform') if 'metaform' in words else -1
                    run = self.verb(*words[at + 1:at + 3]) if 0 <= at < len(words) - 2 else None
                    callees += [run] if run else []
                elif inspect.isfunction(target) and target.__module__.startswith('metaform') and not any(
                        k.arg in ('create', 'write') and isinstance(k.value, ast.Constant) and k.value.value is False
                        for k in call.keywords):  # create=False and write=False are this code's reads
                    callees.append(target)
        return callees, sinks

    def writes_file(self, call, target):
        """Whether the call writes a file: a Path's write_text or write_bytes, open or os.open for writing, or a copy,
        move or removal through os and shutil."""
        if isinstance(call.func, ast.Attribute) and call.func.attr in ('write_text', 'write_bytes'):
            return True
        if isinstance(call.func, ast.Name) and call.func.id == 'open':
            mode = [*call.args[1:2], *(k.value for k in call.keywords if k.arg == 'mode')]
            return any(isinstance(one, ast.Constant) and set(str(one.value)) & set('wax+') for one in mode)
        if target is os.open:
            return any(flag in ast.unparse(call) for flag in ('O_WRONLY', 'O_RDWR', 'O_CREAT'))
        return target in self.files

    def resolved(self, node, scope, owner):
        """The function a call's target names, or None."""
        names = []
        while isinstance(node, ast.Attribute):
            names.insert(0, node.attr)
            node = node.value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'require_store':
            found = Store
        elif isinstance(node, ast.Call) and self.returns(self.resolved(node.func, scope, owner)) is Store:
            found = Store  # `_other_project(ctx).add_base(...)`, a call that gives a Store
        elif isinstance(node, ast.Name) and node.id == 'self' and isinstance(owner, type):
            found = owner
        elif isinstance(node, ast.Name):
            found = self.typed.get(node.id, scope.get(node.id))
        else:
            return None
        for name in names:
            operation = self.operations.get(name) if found is Store and not hasattr(Store, name) else None
            found = operation.run if operation else getattr(found, name, None)
        found = inspect.unwrap(found) if callable(found) else found
        found = getattr(found.func if isinstance(found, functools.partial) else found, '__func__', found)
        return found if inspect.isroutine(found) or isinstance(found, type) else None

    @staticmethod
    def returns(fn):
        """What the function's return annotation names, or None."""
        try:
            return typing.get_type_hints(fn).get('return') if inspect.isfunction(fn) else None
        except (NameError, TypeError):  # an annotation that names what the module does not import at run time
            return None

    @staticmethod
    def imported(tree, fn):
        """The names the function imports inside its body, as `from . import jev`."""
        package = fn.__module__ if hasattr(sys.modules.get(fn.__module__), '__path__') else fn.__module__.rpartition('.')[0]
        names = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            source = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level \
                else node.module or ''
            try:
                held = importlib.import_module(source)
            except ImportError:
                continue
            for alias in node.names:
                one = getattr(held, alias.name, None)
                if one is None:
                    with contextlib.suppress(ImportError):
                        one = importlib.import_module(f'{source}.{alias.name}')
                names[alias.asname or alias.name] = one
        return names


# Write/remove verbs without write, send or file evidence, even when the walk sees network, local or process sinks.
# Keep the set exact so losing a declaration or a previously visible write cannot silently pass.
UNSEEN = {
    'cloud_logout': 'revokes at the broker through an httpx client and forgets the sign-in through the login module',
    'dispatch_permit': 'answers an agent permission or question through the local runner control socket',
    'dispatch_configure': 'changes a live agent setting through the local runner control socket',
    'dispatch_message': 'queues a new agent turn through the local runner control socket',
    'dispatch_fork': 'forks or prompts an agent session through the local runner control socket',
    'dispatch_timer': 'sets or cancels a runner-held timer which queues a future agent turn',
    'dispatch_interrupt': 'cancels the current agent turn through the local runner control socket',
    'dispatch_login': 'starts and authenticates an agent through an ACP Session object',
    'dispatch_options': 'prime=true starts each agent once through a runner object to read the options it offers',
    'dispatch_serve': 'serves ACP and forwards requests through stateful frontend and agent objects',
    'node_invite': 'creates an account and invitation through the auth store object, locally or through SSH',
    'node_revoke': 'disables an account through the auth store object, locally or through SSH',
    'node_signout': 'bumps an account generation through the auth store object, invalidating sessions and tokens',
    'node_rotate-key': 'writes signing keys through the Keys object, locally or through SSH',
    'node_relay-enrol': "writes the relay's enrolments file through an Enrolments object",
    'node_relay-gate': 'starts the relay gate server, uvicorn, in the foreground',
    'twilio_call': 'places a paid call through the local bridge, whose Phone object sends it to Twilio',
    'twilio_text': 'sends a paid text through the local bridge or a Twilio Client object',
    'web_stop': 'asks the local page server to shut down through its control endpoint',
    'hello_follow': 'waits for the next map change and shows it; it writes nothing',
    'packet_check': 'reads a packet and says whether it is as sealed; it writes nothing',
}


def unseen_writes(declared, sinks):
    return {tool for tool, verb in declared.items()
            if verb.effect in ('write', 'remove') and not {'write', 'send', 'file'} & sinks[tool].keys()}


# These verbs reach beyond the home and map through objects, callbacks or local runners rather than a direct
# network sink the walk recognizes. This is evidence of open-world behavior, not an exemption from declaring it.
UNSEEN_OPEN_WORLD = {
    'cloud_login': 'signs in through an httpx Client object',
    'cloud_connect': 'connects to the broker through a Connection object and its nested async entry point',
    'cloud_logout': 'revokes the sign-in through an httpx Client object',
    'dispatch_recover': 'signals verified agent process groups through platform process handles',
    'dispatch_permit': 'answers the agent through the local runner, which resolves the ACP permission or question',
    'dispatch_configure': 'the local runner applies a setting through ACP session mode or config methods',
    'dispatch_message': 'the local runner sends a new ACP prompt to the agent',
    'dispatch_broadcast': 'each running session\'s local runner sends a new ACP prompt to its agent',
    'dispatch_fork': 'the local runner forks or prompts an ACP agent session',
    'dispatch_timer': 'the local runner queues a new agent turn when the timer expires',
    'dispatch_interrupt': 'the local runner cancels the ACP agent turn',
    'dispatch_stop': 'the local runner cancels the agent and ends its process group',
    'dispatch_stop-all': 'each running session\'s local runner cancels its agent and ends its process group',
    'dispatch_options': 'prime=true starts an ACP agent through a Session object',
    'dispatch_tune': 'the local runner applies model and effort to the live ACP agent',
    'dispatch_cancel': 'the local runner cancels and ends the ACP agent session',
    'dispatch_login': 'opens an ACP agent Session and invokes its authentication method',
    'dispatch_serve': 'forwards editor requests to agents through stateful ACP frontend and adapter objects',
    'fork_wheel': 'selects dispatch.run dynamically from the loaded module to start a review agent',
    'fork_upkeep': 'selects dispatch.run dynamically from the loaded module to start upkeep agents',
    'mcp_a2a_send': 'sends to the remote agent through a factory-built A2A Client object',
    'mcp_a2a_exchanges': 'polls remote agents through factory-built A2A Client objects',
    'mcp_a2a_cancel': 'cancels remote work through a factory-built A2A Client object',
    'node_logs': 'reads logs on the remote host through an SSH subprocess',
    'node_relay': 'builds the relay wheel through plan callbacks and subprocesses that resolve external dependencies',
    'paperclip_status': 'reads the external Paperclip service through a Client object and injected opener',
    'paperclip_brief': 'reads the external Paperclip service through a Client object and injected opener',
    'paperclip_link': 'reads the external issue before linking it through a Client object and injected opener',
    'paperclip_sync': 'synchronizes external issues through a Client object and injected opener',
    'paperclip_watch': 'runs sync on a timer, synchronizing external issues through a Client object and injected opener',
    'twilio_serve': 'serves phone callbacks whose Phone object reaches Twilio and the selected voice engine',
    'twilio_call': 'the local bridge places the outbound call through a Phone object',
    'twilio_text': 'the local bridge or a Client object sends the outbound text to Twilio',
    'voice_speak': 'selects a module-provided engine callback, which can use an external speech service',
}


def unseen_open_world(declared, sinks):
    return {tool for tool, verb in declared.items() if verb.open_world and 'network' not in sinks[tool]}


def every_module():
    from metaform import loader
    for found in loader.discover():
        loader.set_enabled(found.id, True)
    return loader.enabled()


def undeclared(reach, modules, changed=None):
    """Each verb whose declaration hides what it reaches, with the calls that lead there; `changed` swaps in a verb's
    declaration by tool name, as a wrong one would be written."""
    wrong = []
    for module in modules:
        for verb in module.verbs:
            tool = f'{module.id}_{verb.name}'
            verb = (changed or {}).get(tool, verb)
            sinks = reach.sinks(verb.run)
            if 'network' in sinks and not verb.open_world:
                wrong.append(f'{tool} reaches the network, open_world False: ' + ' > '.join(sinks['network']))
            if tool in UNSEEN_OPEN_WORLD and not verb.open_world:
                wrong.append(f'{tool} reaches outside the home and map, open_world False: ' + UNSEEN_OPEN_WORLD[tool])
            for kind in ('write', 'send', 'file'):
                exempt = (kind == 'write' and tool in WEB_ONLY_WRITES) or (
                    kind == 'file' and tool in SCREENSHOT_ONLY_WRITES)
                if kind in sinks and verb.effect == 'read' and not exempt:
                    wrong.append(f'{tool} declared read, {kind}s: ' + ' > '.join(sinks[kind]))
    return wrong


def help_agents(run, folder):
    return run('help', 'agents', cwd=folder).stdout


def over_mcp(folder):
    """The connect message the MCP server sends the person's own session, MCP-007: the directive line and a link per
    line to each instruction block that applies to it now."""
    from metaform.modules.mcp.server import connect_instructions
    return connect_instructions(folder)


class Served:
    """`metaform mcp serve --http`'s app for the folder, on 127.0.0.1 in a thread of its own."""

    def __init__(self, folder):
        import socket
        import threading

        import uvicorn
        from metaform.modules.mcp.server import http_app
        with socket.socket() as held:
            held.bind(('127.0.0.1', 0))
            port = held.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}/mcp'
        self.server = uvicorn.Server(uvicorn.Config(http_app(folder), host='127.0.0.1', port=port,
                                                    log_level='warning'))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert self.server.started

    def stop(self):
        self.server.should_exit = True
        self.thread.join(10)


def test_paperclip_brief_resolves_explicit_issue_then_call_identity_then_environment(run, mapped, monkeypatch):
    from metaform.module import context
    from metaform.modules import paperclip

    run('enable', 'paperclip', cwd=mapped)
    store = context('paperclip', mapped).require_store()
    for issue, address in [('explicit', 'code.timer.kitchen'), ('header', 'code.alarm.audible'),
                           ('environment', 'code.timer.kitchen')]:
        paperclip._keep(store, {'issue_id': issue, 'address': address, 'work_id': issue, 'works': 'paperclip'})
    monkeypatch.setenv('PAPERCLIP_TASK_ID', 'environment')
    monkeypatch.setattr(paperclip, 'node_brief', lambda folder, address: address)
    ctx = context('paperclip', mapped, surface='mcp')
    ctx.identity = {'issue_id': 'header'}
    assert paperclip.brief(ctx) == 'code.alarm.audible\n'
    ctx.nouns['issue'] = 'explicit'
    assert paperclip.brief(ctx) == 'code.timer.kitchen\n'
    ctx.nouns.clear()
    ctx.identity.clear()
    assert paperclip.brief(ctx) == 'code.timer.kitchen\n'


async def heard_until(heard, method, count, limit=5):
    """Wait for `count` of `method` in `heard`, written by the client's GET stream task, or the limit."""
    deadline = time.monotonic() + limit
    while heard.count(method) < count and time.monotonic() < deadline:
        await asyncio.sleep(0.05)


SHIPPED = ('dispatch', 'fork', 'hello', 'intake', 'map', 'mcp', 'memory', 'packet', 'template', 'web')


def a2a(folder, calls):
    """The A2A routes on an app of their own, as metaform mcp serve --http attaches them to MCP's, driven in-process
    over httpx; `calls` gets the client and the bearer token."""
    import httpx
    from starlette.applications import Starlette

    from metaform.modules.mcp import a2a as served

    app = Starlette()
    served.attach(app, folder, 7434)

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:7434') as client:
            return await calls(client, served.token())
    return asyncio.run(go())


@pytest.fixture
def in_project_store(home, mapped):
    """The mapped project with a map in the project store too, which is what says a project has had its intake; the
    home's service is stopped when the test ends."""
    from metaform import home as metaform_home
    from metaform import project
    from metaform.project import service
    assert project.run({'add': {'proj.code.timer.kitchen': {
        'technical_name': 'kitchen timer', 'name': 'timer', 'role': 'Defining Element', 'ref': './timer.py'}}}) == {
            'status': 'ok'}
    yield mapped
    service.stop(metaform_home.home())


def rpc(method, params, number=1):
    return {'jsonrpc': '2.0', 'id': number, 'method': method, 'params': params}


@pytest.mark.req('MCP-002')
def test_a2a_card_is_public_and_names_no_project_and_everything_else_needs_its_own_token(run, home, mapped):
    async def calls(client, token):
        card = await client.get('/.well-known/agent-card.json')
        bare = await client.post('/a2a', json=rpc('GetExtendedAgentCard', {}), headers={'A2A-Version': '1.0'})
        wrong = await client.post('/a2a', json=rpc('GetExtendedAgentCard', {}),
                                  headers={'A2A-Version': '1.0', 'Authorization': 'Bearer not-it'})
        extended = await client.post('/a2a', json=rpc('GetExtendedAgentCard', {}),
                                     headers={'A2A-Version': '1.0', 'Authorization': f'Bearer {token}'})
        rebound = await client.get('/.well-known/agent-card.json', headers={'Host': 'evil.example'})
        return card, bare, wrong, extended, rebound
    card, bare, wrong, extended, rebound = a2a(mapped, calls)
    assert card.status_code == 200 and '"proj"' not in card.text and 'tenant' not in card.text  # no project, P005
    shown = card.json()
    assert shown['capabilities']['extendedAgentCard'] is True and not shown['capabilities'].get('pushNotifications')
    assert [skill['id'] for skill in shown['skills']] == ['ticket']  # the one thing A2A does here; no tool catalogue
    assert '30 seconds' in shown['skills'][0]['description']  # the cap on a waiting send, stated where clients read
    assert not shown['capabilities']['extensions'][0].get('required')  # works without it: Metaform asks
    assert bare.status_code == 401 and bare.headers['www-authenticate'] == 'Bearer realm="metaform-a2a"'
    assert wrong.status_code == 401 and 'invalid_token' in wrong.headers['www-authenticate']
    assert rebound.status_code == 421  # the MCP endpoint's DNS-rebinding guard, on the card too
    interfaces = extended.json()['result']['supportedInterfaces']
    assert {(one['protocolBinding'], one.get('tenant', '')) for one in interfaces} >= {('JSONRPC', 'proj'),
                                                                                       ('HTTP+JSON', 'proj')}


@pytest.mark.req('MCP-002')
def test_an_a2a_message_opens_one_numbered_ticket_at_its_address_and_the_task_follows_the_ticket(run, home, mapped):
    message = {'messageId': 'm-1', 'role': 'ROLE_USER', 'contextId': 'code.alarm.audible',
               'parts': [{'text': 'Make the alarm louder\nThe cook misses it over the fan.'}]}
    sent = {'message': message, 'configuration': {'returnImmediately': True}}

    async def calls(client, token):
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}', 'User-Agent': 'peer/1'}
        first = (await client.post('/a2a', json=rpc('SendMessage', sent), headers=headers)).json()
        again = (await client.post('/a2a', json=rpc('SendMessage', sent), headers=headers)).json()
        nowhere = (await client.post('/a2a', json=rpc('SendMessage', {
            'message': {**message, 'messageId': 'm-2', 'contextId': 'code.no.such'}}), headers=headers)).json()
        unaddressed = (await client.post('/a2a', json=rpc('SendMessage', {
            'message': {**message, 'messageId': 'm-3', 'contextId': ''}}), headers=headers)).json()
        task_id = first['result']['task']['id']
        run('map', 'work', 'op=take', f'id={task_id}', 'steps=2', cwd=mapped)
        working = (await client.post('/a2a', json=rpc('GetTask', {'id': task_id}), headers=headers)).json()
        run('map', 'work', 'op=done', f'id={task_id}', 'resolution=Louder now', 'why=The cook hears it', cwd=mapped)
        done = (await client.get(f'/a2a/rest/tasks/{task_id}', headers=headers)).json()
        cancel = (await client.post('/a2a', json=rpc('CancelTask', {'id': task_id}), headers=headers)).json()
        tenant = await client.get(f'/a2a/rest/proj/tasks/{task_id}', headers=headers)
        stranger = await client.get(f'/a2a/rest/nosuch/tasks/{task_id}', headers=headers)
        return first, again, nowhere, unaddressed, working, done, cancel, tenant, stranger
    first, again, nowhere, unaddressed, working, done, cancel, tenant, stranger = a2a(mapped, calls)
    assert tenant.json()['id'] == first['result']['task']['id'] and stranger.status_code == 400  # a project by its id
    task = first['result']['task']
    assert task['contextId'] == 'code.alarm.audible' and task['status']['state'] == 'TASK_STATE_SUBMITTED'
    detail = task['metadata']['https://metaform.ing/a2a/address-context/v1']
    assert detail['item'] == 'code.alarm.audible#1' and detail['title'] == 'Make the alarm louder'
    assert again['result']['task']['id'] == task['id']  # a retried message opens no second ticket
    assert nowhere['error']['code'] == -32602 and 'code.no.such' in nowhere['error']['message']
    assert unaddressed['result']['task']['status']['state'] == 'TASK_STATE_INPUT_REQUIRED'  # asked for an Address
    stored = Store('proj').ticket(task['id']).work
    assert stored.address == 'code.alarm.audible' and 'peer/1' in (stored.note or '')  # who sent it, on the ticket
    assert working['result']['status']['state'] == 'TASK_STATE_WORKING'
    assert '0 of 2 steps done' in working['result']['status']['message']['parts'][0]['text']
    assert done['status']['state'] == 'TASK_STATE_COMPLETED'
    assert done['artifacts'][0]['parts'][0]['text'] == 'Louder now'
    assert done['artifacts'][0]['metadata'] == {'why': 'The cook hears it'}
    assert cancel['error']['code'] == -32002  # TaskNotCancelableError: a done ticket cannot be cancelled


@pytest.mark.req('MCP-002')
def test_a2a_on_a_project_in_the_project_store_opens_and_follows_its_tickets_overlay(run, home, in_project_store):
    """Kickoff 2026-11-17, t-legacy-keep: for a project held in the project store, an Address is an element of that
    map, the ticket is a record of its tickets overlay, and the task follows that record to done; the old store gets
    no ticket, and a change there is a change a follower hears."""
    from metaform import project
    from metaform.modules.mcp import a2a as served
    mapped = in_project_store
    message = {'messageId': 'm-1', 'role': 'ROLE_USER', 'contextId': 'code.timer.kitchen',
               'parts': [{'text': 'Make the timer louder\nThe cook misses it over the fan.'}]}

    async def calls(client, token):
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}', 'User-Agent': 'peer/1'}
        first = (await client.post('/a2a', json=rpc('SendMessage', {'message': message}), headers=headers)).json()
        old_only = (await client.post('/a2a', json=rpc('SendMessage', {
            'message': {**message, 'messageId': 'm-2', 'contextId': 'code.alarm.audible'}}), headers=headers)).json()
        asked = (await client.post('/a2a', json=rpc('SendMessage', {
            'message': {**message, 'messageId': 'm-3', 'contextId': '',
                        'parts': [{'text': 'The kitchen timer rings too quietly'}]}}), headers=headers)).json()
        task_id = first['result']['task']['id']
        run('map', 'work', 'op=take', f'id={task_id}', 'by=claude', cwd=mapped)
        working = (await client.post('/a2a', json=rpc('GetTask', {'id': task_id}), headers=headers)).json()
        run('map', 'work', 'op=done', f'id={task_id}', 'resolution=Louder now', 'why=The cook hears it', cwd=mapped)
        done = (await client.get(f'/a2a/rest/tasks/{task_id}', headers=headers)).json()
        listed = (await client.post('/a2a', json=rpc('ListTasks', {}), headers=headers)).json()
        # archived on the board, its record completed: the task still resolves, as completed (review of 2026-11-18, F4)
        one = project.overlay_record('proj', 'tickets', 'id', task_id) or {}
        assert project.run({'update': {str(one['element']): {'tickets': [
            {'position': one['position'], 'record': one['record'], 'completed': True}]}}}) == {'status': 'ok'}
        archived = (await client.get(f'/a2a/rest/tasks/{task_id}', headers=headers)).json()
        return first, old_only, asked, working, done, listed, archived
    first, old_only, asked, working, done, listed, archived = a2a(mapped, calls)
    assert archived['status']['state'] == 'TASK_STATE_COMPLETED', archived
    task = first['result']['task']
    assert task['contextId'] == 'code.timer.kitchen' and task['status']['state'] == 'TASK_STATE_SUBMITTED'
    detail = task['metadata']['https://metaform.ing/a2a/address-context/v1']
    assert detail['item'] == task['id'] and detail['title'] == 'Make the timer louder'  # no item numbers there
    record = project.overlay_record('proj', 'tickets', 'id', task['id']) or {}
    assert record['element'] == 'proj.code.timer.kitchen' and 'peer/1' in str(record['note'])
    assert not old_work('proj')  # the old store gets no ticket
    assert old_only['error']['code'] == -32602  # an Address only the old store holds is no Address of this map
    assert asked['result']['task']['status']['state'] == 'TASK_STATE_INPUT_REQUIRED'
    offered = asked['result']['task']['metadata']['https://metaform.ing/a2a/address-context/v1']['candidates']
    assert offered[0] == 'code.timer.kitchen'  # offered from the project store's map
    assert working['result']['status']['state'] == 'TASK_STATE_WORKING'
    assert done['status']['state'] == 'TASK_STATE_COMPLETED'
    assert done['artifacts'][0]['parts'][0]['text'] == 'Louder now'
    assert done['artifacts'][0]['metadata'] == {'why': 'The cook hears it'}
    assert {one['id'] for one in listed['result']['tasks']} >= {task['id']}
    assert served.concerns({'project': 'proj', 'tables': ['project.map'], 'kinds': ['map']}, 'proj', task['id'])
    assert not served.concerns({'project': 'proj', 'tables': ['project.memory'], 'kinds': ['memory']}, 'proj',
                               task['id'])


@pytest.mark.req('MCP-041')
def test_what_a_peer_says_on_a_project_in_the_project_store_is_its_questions_overlay(run, home, in_project_store):
    """An artifact is a message and an input-required status an open question, records of the questions overlay at the
    exchange's Address; the answer given there is the one sent back. No peer is reached."""
    from a2a.types import Artifact, Message, Part, Role, TaskState, TaskStatus

    from metaform import project
    from metaform.modules.mcp import a2a_out
    from metaform.modules.mcp import a2a_records as records
    mapped = in_project_store
    made = records.send('proj', records.Exchange('x-1', 'peer', 'code.timer.kitchen', 'Check the bell'))
    status = TaskStatus(state=TaskState.TASK_STATE_INPUT_REQUIRED, message=Message(
        message_id='s-1', role=Role.ROLE_AGENT, parts=[Part(text='Which bell?')]))
    artifact = Artifact(artifact_id='a-1', name='report', parts=[Part(text='The bell is fine.')])
    now = a2a_out.heard('proj', made.exchange_id, status, (artifact,), 'peer-task')
    again = a2a_out.heard('proj', made.exchange_id, status, (artifact,), 'peer-task')
    kept = project.overlay_records('proj', 'questions') or []
    assert sorted((one['kind'], one['text'], one['by']) for one in kept) == [
        ('message', 'The bell is fine.', 'a2a peer'), ('question', 'Which bell?', 'a2a peer')]  # each once
    assert {one['element'] for one in kept} == {'proj.code.timer.kitchen'}
    assert now is not None and again is not None and now.asked == next(one['id'] for one in kept
                                                                      if one['kind'] == 'question')
    assert a2a_out._answer('proj', now) == (False, None)
    run('map', 'reply', f'id={now.asked}', 'answer=The kitchen one', cwd=mapped)
    assert a2a_out._answer('proj', now) == (True, 'The kitchen one')
    # completed before its answer was sent, the question still gives its answer (review of 2026-11-18, F4)
    asked = project.overlay_record('proj', 'questions', 'id', now.asked) or {}
    assert project.run({'update': {str(asked['element']): {'questions': [
        {'position': asked['position'], 'record': asked['record'], 'completed': True}]}}}) == {'status': 'ok'}
    assert a2a_out._answer('proj', now) == (True, 'The kitchen one')



@pytest.mark.req('MCP-041')
def test_a_peers_artifact_whose_write_fails_is_written_once_when_heard_again(home, in_project_store, monkeypatch):
    """Review of 2026-11-18, F7: the artifact's key was marked seen before it was written, so a write that failed left
    it seen and a replay skipped it for good. A claim is now pending until written, and given back on a failure."""
    from a2a.types import Artifact, Part

    from metaform import project
    from metaform.modules.mcp import a2a_out
    from metaform.modules.mcp import a2a_records as records
    made = records.send('proj', records.Exchange('x-2', 'peer', 'code.timer.kitchen', 'Check the bell'))
    artifact = Artifact(artifact_id='a-1', name='report', parts=[Part(text='The bell is fine.')])
    real, calls = a2a_out._tell, []

    def once(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise OSError('the disk is full')
        return real(*args, **kwargs)
    monkeypatch.setattr(a2a_out, '_tell', once)
    with pytest.raises(OSError):
        a2a_out.heard('proj', made.exchange_id, None, (artifact,), 'peer-task')
    a2a_out.heard('proj', made.exchange_id, None, (artifact,), 'peer-task')
    a2a_out.heard('proj', made.exchange_id, None, (artifact,), 'peer-task')
    kept = [one['text'] for one in project.overlay_records('proj', 'questions') or []]
    assert kept == ['The bell is fine.'] and len(calls) == 2
    assert (records.exchange('proj', made.exchange_id) or made).seen == ['artifact:a-1']

@pytest.mark.req('MCP-002')
def test_a2a_push_webhooks_are_only_those_the_person_allows(run, home, mapped):
    from metaform.modules.mcp.a2a import allowed
    run('set', '--mcp-a2a-webhooks', 'https://agent.example/hooks/', cwd=mapped)
    assert allowed('https://agent.example/hooks/a2a', mapped)
    assert allowed('https://AGENT.example/hooks/', mapped)
    assert not allowed('https://agent.example.evil/hooks/a2a', mapped)  # compared parsed, never as a prefix
    assert not allowed('https://agent.example:8443/hooks/a2a', mapped)
    assert not allowed('http://agent.example/hooks/a2a', mapped)
    assert not allowed('https://agent.example/hooksmith', mapped)
    assert not allowed('file:///etc/passwd', mapped)


@pytest.mark.req('MCP-002')
def test_a2a_push_resume_sends_where_an_ended_task_stands_and_drops_its_configuration(run, home, mapped, monkeypatch):
    """A task that ended while the server was down was never pushed, and its configuration was kept for ever. A task
    whose ticket is gone is told as failed; a watched task that ends while the server runs drops its configuration."""
    import anyio
    import httpx
    from starlette.applications import Starlette

    from metaform.modules.mcp import a2a as served
    from metaform.modules.mcp import a2a_records as records
    run('set', '--mcp-a2a-webhooks', 'https://agent.example/hooks/', cwd=mapped)
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'task=Make it louder.', 'title=Louder', cwd=mapped)
    work_id = next(one.id for one in Store('proj').work(limit=0).results if one.task == 'Make it louder.')
    records.record('proj', work_id, 'm-1', 'code.alarm.audible', None)
    records.set_push('proj', records.Push(work_id, 'c-1', 'https://agent.example/hooks/a2a', None, None, None, None))
    run('map', 'work', 'op=take', f'id={work_id}', cwd=mapped)
    run('map', 'work', 'op=done', f'id={work_id}', 'resolution=Louder now', 'why=The cook hears it', cwd=mapped)
    records.record('proj', 'w-gone', 'm-2', 'code.alarm.audible', None)  # its ticket no longer exists
    records.set_push('proj', records.Push('w-gone', 'c-2', 'https://agent.example/hooks/a2a', None, None, None, None))
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'task=Make it flash.', 'title=Flash', cwd=mapped)
    watched = next(one.id for one in Store('proj').work(limit=0).results if one.task == 'Make it flash.')
    records.record('proj', watched, 'm-3', 'code.alarm.audible', None)
    records.set_push('proj', records.Push(watched, 'c-3', 'https://agent.example/hooks/a2a', None, None, None, None))
    posted = []

    async def post(self, url, json=None, headers=None):
        posted.append(json)
        return httpx.Response(200, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    app = Starlette()
    served.attach(app, mapped, 7434)

    async def go():
        async with app.router.lifespan_context(app):
            # done from another process, as a person or agent does it, heard through the home's change relay
            await anyio.to_thread.run_sync(lambda: run('map', 'work', 'op=done', f'id={watched}', 'resolution=Flashing',
                                                       'why=The cook sees it', cwd=mapped, isolated=True))
            with anyio.fail_after(15):
                while records.pushes('proj', watched):
                    await anyio.sleep(0.05)
    asyncio.run(go())

    def told(task_id):
        return [one['statusUpdate']['status']['state'] for one in posted
                if one.get('statusUpdate', {}).get('taskId') == task_id]
    assert [one['artifactUpdate']['artifact']['parts'][0]['text'] for one in posted
            if one.get('artifactUpdate', {}).get('taskId') == work_id] == ['Louder now']
    assert told(work_id) == ['TASK_STATE_COMPLETED']
    assert records.pushes('proj', work_id) == []
    assert told('w-gone') == ['TASK_STATE_FAILED'] and records.pushes('proj', 'w-gone') == []
    assert told(watched)[-1] == 'TASK_STATE_COMPLETED' and records.pushes('proj', watched) == []


def july_wire(home, folder, **extra_env):
    """A client on the 2026-07-28 wire, whose requests declare the capabilities a check gives them."""
    from metaform.probe import Session
    return Session([sys.executable, '-m', 'metaform', 'mcp', 'serve'], cwd=folder,
                   env={**os.environ, 'METAFORM_HOME': str(home), **extra_env})


def declaring(wire, method, params, capabilities, limit=30):
    """A July client follows exact instruction challenges without changing the operation or capabilities."""
    handle = getattr(wire, '_usage_handle', None)
    meta = {'io.modelcontextprotocol/clientCapabilities': capabilities,
            **({'io.metaform/session': handle} if handle else {})}
    result = wire.request(method, {**params, '_meta': meta}, deadline=time.monotonic() + limit)
    required = result.get('structuredContent') or {}
    if method == 'tools/call' and result.get('isError') and required.get('error') == 'instructions_required':
        alias = required['read_tool']
        guide = wire.request('tools/call', {'name': alias['tool'], 'arguments': alias['arguments'], '_meta': meta},
                             deadline=time.monotonic() + limit)
        assert not guide.get('isError'), guide
        wire._usage_handle = required.get('session_handle', handle)
        if wire._usage_handle:
            meta['io.metaform/session'] = wire._usage_handle
        result = wire.request(method, {**params, '_meta': meta}, deadline=time.monotonic() + limit)
    return result


def opened(wire, category, capabilities):
    """The tools a July client is listed once it opens `category` with metaform_catalog, MCP-003, by name."""
    declaring(wire, 'tools/call', {'name': 'metaform_catalog', 'arguments': {'module': category}}, capabilities)
    return {tool['name']: tool for tool in declaring(wire, 'tools/list', {}, capabilities)['tools']}


def every_listed(wire, capabilities):
    """Every tool a July client is listed, each category opened in turn, by name."""
    found = {tool['name']: tool for tool in declaring(wire, 'tools/list', {}, capabilities)['tools']}
    directory = declaring(wire, 'resources/read', {'uri': 'metaform://modules'}, capabilities)
    names = re.findall(r'^- ([\w.-]+):', '\n'.join(one['text'] for one in directory['contents']), re.MULTILINE)
    for module in names:
        found.update(opened(wire, module, capabilities))
    return found


FORMS = {'elicitation': {'form': {}}}


# Changes that concern no task, no followed ticket t1 and no exchange of the project 'proj': another project's, an
# agent's thread lines and signals, another ticket's, its sessions'.
UNRELATED = (
    {'project': 'other', 'tables': ['work', 'mcp.tool_tasks'], 'work_ids': ['t1'], 'kinds': ['task']},
    {'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines'], 'work_ids': ['t2'],
     'session_ids': ['s2'], 'kinds': ['line']},
    {'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.signals'], 'work_ids': ['t2'],
     'session_ids': ['s2'], 'kinds': ['signal']},
    {'project': 'proj', 'tables': ['work', 'work_steps'], 'work_ids': ['t2'], 'session_ids': [], 'kinds': ['ticket']},
    {'project': 'proj', 'tables': ['dispatch.sessions'], 'work_ids': ['t2'], 'session_ids': ['s2'], 'kinds': ['session']},
)


@pytest.mark.req('MCP-043')
def test_a_followed_a2a_task_and_the_exchange_followers_read_only_for_changes_that_concern_them(monkeypatch, tmp_path):
    """An A2A task followed for its client is read again only for a change naming its ticket, and the exchange
    followers read open exchanges only for a change to the exchanges; a burst of other changes reads nothing, and
    nothing is read on a clock."""
    import threading

    import anyio
    from a2a.types import Task

    from metaform.modules.mcp import a2a, a2a_out
    monkeypatch.setattr(a2a, 'refresh_modules', lambda: None)
    first = a2a.Read(Task(id='t1', context_id='code.alarm'), 'running', '')
    first.work_id = 't1'
    tasks_read: list[str] = []
    exchanges_read: list[set[str] | None] = []
    task_was_read, exchanges_were_read = threading.Semaphore(0), threading.Semaphore(0)

    def read(project, folder, task_id, length=None):
        tasks_read.append(task_id)
        task_was_read.release()
        return first

    def open_exchanges(projects=None):
        exchanges_read.append(projects)
        exchanges_were_read.release()
        return []
    monkeypatch.setattr(a2a, 'read', read)
    monkeypatch.setattr(a2a_out, '_open_exchanges', open_exchanges)

    async def reads() -> None:  # one more of each, signalled by the reads themselves
        for signal in (task_was_read, exchanges_were_read):
            assert await anyio.to_thread.run_sync(signal.acquire, True, 10)

    async def main() -> None:
        changes, wakes = a2a.Changes(), a2a_out.Wakes()
        changes.bind()
        followers = a2a_out.Followers(tmp_path, wakes)

        async def follow() -> None:
            async for _ in a2a.follow(changes, 'proj', tmp_path, first):
                pass
        async with anyio.create_task_group() as group:
            group.start_soon(follow)
            group.start_soon(followers.run)
            await reads()  # the reads at the start
            await anyio.wait_all_tasks_blocked()
            for _ in range(20):
                for payload in UNRELATED:
                    changes.heard(payload)
                    wakes.heard(payload)
            await anyio.wait_all_tasks_blocked()
            assert (len(tasks_read), len(exchanges_read)) == (1, 1)
            changes.heard({'project': 'proj', 'tables': ['work'], 'work_ids': ['t1'], 'kinds': ['ticket']})
            wakes.heard({'project': 'proj', 'tables': ['mcp.a2a_exchanges']})
            await reads()
            await anyio.wait_all_tasks_blocked()
            group.cancel_scope.cancel()
    anyio.run(main)
    assert tasks_read == ['t1', 't1'] and exchanges_read[1:] == [{'proj'}]


@pytest.fixture
def chromium():
    """Headless Chromium through Playwright, a dev dependency, for the views in a frame."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        launched = driver.chromium.launch(executable_path=os.environ.get('METAFORM_CHROMIUM') or None)
        yield launched
        launched.close()


# A host page as the MCP Apps specification describes one, written for this check: the view in a sandboxed frame
# under the specification's restrictive default content policy, the view's requests checked against the official
# SDK's own schemas, its tool calls carried to the real server, and a light conversation with style variables.
HOST = '''<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">
<iframe id="frame" sandbox="allow-scripts" style="width:900px;height:700px;border:0"></iframe>
<script>SDK</script>
<script>
window.told = []; window.refused = []; window.initialized = false;
const frame = document.getElementById('frame');
const send = message => frame.contentWindow.postMessage({jsonrpc: '2.0', ...message}, '*');
window.open_view = (html, args, result) => {
  const policy = "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data:; media-src 'self' data:; connect-src 'none'";
  addEventListener('message', async event => {
    if (event.source !== frame.contentWindow) return;
    const m = event.data;
    if (m.method === 'ui/initialize') {
      const checked = McpApps.McpUiInitializeRequestSchema.safeParse({method: m.method, params: m.params});
      if (!checked.success) window.refused.push(JSON.stringify(checked.error.issues));
      window.initialize = m.params;
      return send({id: m.id, result: {protocolVersion: '2026-01-26', hostInfo: {name: 'check-host', version: '1'},
        hostCapabilities: {serverTools: {}, updateModelContext: {text: {}}},
        hostContext: {theme: 'light', displayMode: 'inline',
                      styles: {variables: {'--color-background-primary': 'rgb(250, 250, 250)'}}}}});
    }
    if (m.method === 'ui/notifications/initialized') {
      window.initialized = true;
      send({method: 'ui/notifications/tool-input', params: {arguments: args}});
      return send({method: 'ui/notifications/tool-result', params: result});
    }
    if (m.method === 'ui/update-model-context') {
      const checked = McpApps.McpUiUpdateModelContextRequestSchema.safeParse({method: m.method, params: m.params});
      if (!checked.success) window.refused.push(JSON.stringify(checked.error.issues));
      window.told.push(m.params.content[0].text);
      return send({id: m.id, result: {}});
    }
    if (m.method === 'tools/call') return send({id: m.id, result: JSON.parse(await window.rpc(JSON.stringify(m.params)))});
    if (m.id !== undefined && m.method !== undefined) send({id: m.id, error: {code: -32601, message: 'not here'}});
  });
  frame.srcdoc = html.replace('<head>', `<head><meta http-equiv="Content-Security-Policy" content="${policy}">`);
};
</script></body></html>'''


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_node_view_connects_through_the_official_sdk_and_tells_the_agent_what_the_person_selects(
        run, home, mapped, chromium):
    """The node view, served to a client that renders MCP Apps, makes the handshake the specification asks for, as
    the official SDK's own schema checks it (appInfo, appCapabilities, protocolVersion), only then hears the call's
    input and result, paints the result it was handed, reads the rest through metaform_view, wears the host's light
    theme and style variables, and tells the agent in one line which item the person selected."""
    from metaform import prompt_files
    from metaform.modules.mcp import views
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'finding', 'why': 'The cook misses it.',
                                                   'observations': ['The tone is too quiet.']}]),
        'node=code.alarm.audible', cwd=mapped)
    apps = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/node'}, apps)['contents'][0]['text']
        args = {'item': 'code.alarm.audible#1'}
        result = declaring(wire, 'tools/call', {'name': 'map_item', 'arguments': args}, apps)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page()
        page.set_default_timeout(10_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), apps)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>'))
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        assert page.evaluate('window.refused') == []
        assert page.evaluate('window.initialize.appInfo')['name'] == 'metaform-node'
        view = page.frame_locator('#frame')
        view.locator('.row').first.wait_for()
        assert 'The tone is too quiet.' in view.locator('#item').inner_text()  # the call's own result, painted first
        assert view.locator('#reliedOnList').inner_text().startswith('code.timer.kitchen')
        root = view.locator('html')
        assert root.get_attribute('data-theme') == 'light'
        assert root.evaluate('el => getComputedStyle(document.body).backgroundColor') == 'rgb(250, 250, 250)'
        assert page.evaluate('window.told') == []  # nothing is told until the person selects
        view.locator('.row').first.click()
        page.wait_for_function('window.told.length === 1')
        line = prompt_files.module('mcp', 'view_selected', address='code.alarm.audible#1')
        assert page.evaluate('window.told') == [line] and page.evaluate('window.refused') == []
    finally:
        wire.close()


@pytest.mark.req('MCP-002')
def test_an_a2a_message_naming_no_address_is_asked_for_one_and_a_refused_webhook_opens_nothing(run, home, mapped):
    run('set', '--mcp-a2a-webhooks', 'https://agent.example/hooks/', cwd=mapped)
    asking = {'messageId': 'q-1', 'role': 'ROLE_USER', 'parts': [{'text': 'The alarm is too quiet for the cook'}]}

    async def calls(client, token):
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}'}

        async def send(message, **configuration):
            params = {'message': message, 'configuration': {'returnImmediately': True, **configuration}}
            return (await client.post('/a2a', json=rpc('SendMessage', params), headers=headers)).json()
        asked = (await send(asking))['result']['task']
        reply = {'messageId': 'r-1', 'role': 'ROLE_USER', 'taskId': asked['id'], 'contextId': asked['contextId'],
                 'parts': [{'text': 'code.alarm.audible'}]}
        elsewhere = await send({**reply, 'contextId': 'a2a-other'})
        nowhere = await send({**reply, 'parts': [{'text': 'code.no.such'}]})
        opened = await send(reply)
        again = await send(reply)
        hooked = await send({'messageId': 'p-1', 'role': 'ROLE_USER', 'contextId': 'code.alarm.audible',
                             'parts': [{'text': 'Another'}]},
                            taskPushNotificationConfig={'url': 'https://agent.example.evil/hooks/x'})
        unkind = await send({'messageId': 'k-1', 'role': 'ROLE_USER', 'contextId': 'code.alarm.audible',
                             'parts': [{'text': 'Another'}], 'metadata': {
                                 'https://metaform.ing/a2a/address-context/v1': {'kind': 'urgent', 'agent': 'x'}}})
        withdrawn = (await send({**asking, 'messageId': 'q-2'}))['result']['task']
        cancelled = (await client.post('/a2a', json=rpc('CancelTask', {'id': withdrawn['id']}), headers=headers)).json()
        return asked, elsewhere, nowhere, opened, again, hooked, unkind, cancelled
    asked, elsewhere, nowhere, opened, again, hooked, unkind, cancelled = a2a(mapped, calls)
    assert asked['status']['state'] == 'TASK_STATE_INPUT_REQUIRED' and asked['contextId'].startswith('a2a-')
    offered = asked['metadata']['https://metaform.ing/a2a/address-context/v1']['candidates']
    assert offered[0] == 'code.alarm.audible' and 'code.alarm.audible' in asked['status']['message']['parts'][0]['text']
    assert elsewhere['error']['code'] == -32602 and asked['contextId'] in elsewhere['error']['message']
    assert nowhere['error']['code'] == -32602 and 'code.alarm.audible' in nowhere['error']['message']
    task = opened['result']['task']
    assert (task['id'], task['contextId']) == (asked['id'], asked['contextId'])  # the same task, now its ticket
    assert task['status']['state'] == 'TASK_STATE_SUBMITTED'
    assert task['metadata']['https://metaform.ing/a2a/address-context/v1']['item'] == 'code.alarm.audible#1'
    assert again['result']['task']['id'] == asked['id']  # a retried reply opens no second ticket
    tickets = [one for one in Store('proj').work(limit=0).results if (one.task or '').strip()]
    assert [one.task for one in tickets] == ['The alarm is too quiet for the cook']  # nothing from the refusals
    assert hooked['error']['code'] == -32602 and 'mcp_a2a_webhooks' in hooked['error']['message']
    assert unkind['error']['code'] == -32602 and 'enhancement' in unkind['error']['message']
    assert cancelled['result']['status']['state'] == 'TASK_STATE_CANCELED'


@pytest.mark.req('MCP-002')
def test_a2a_reaches_only_its_own_tickets_reads_a_cancel_as_canceled_and_a_wait_on_the_person_as_working(run, home,
                                                                                                         mapped):
    from metaform.modules.dispatch.signals import record
    run('enable', 'dispatch')
    run('map', 'work', 'op=add', 'node=code.timer.kitchen', 'task=The person\'s own.', 'title=Mine', cwd=mapped)
    own = next(one.id for one in Store('proj').work(limit=0).results if one.task == "The person's own.")
    extension = 'https://metaform.ing/a2a/address-context/v1'

    async def calls(client, token):
        import anyio
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}'}

        async def send(text, number, **message):
            params = {'message': {'messageId': f'w-{number}', 'role': 'ROLE_USER', 'parts': [{'text': text}],
                                  **message}, 'configuration': {'returnImmediately': True}}
            return (await client.post('/a2a', json=rpc('SendMessage', params), headers=headers)).json()
        followed = (await send('Make it louder', 1, contextId='code.alarm.audible'))['result']['task']['id']
        waiting = (await send('Make it flash', 2, contextId='code.alarm.audible'))['result']['task']['id']
        streamed = {}

        async def subscribe():
            streamed['response'] = await client.post('/a2a', json=rpc('SubscribeToTask', {'id': followed}),
                                                     headers=headers)
        with anyio.fail_after(10):  # well inside the slow read: the stream wakes on the cancel's announcement
            async with anyio.create_task_group() as group:
                group.start_soon(subscribe)
                await anyio.sleep(0.5)
                cancel = (await client.post('/a2a', json=rpc('CancelTask', {'id': followed}), headers=headers)).json()
            asking = await client.post('/a2a', headers=headers, json=rpc('SendStreamingMessage', {'message': {
                'messageId': 'w-3', 'role': 'ROLE_USER', 'parts': [{'text': 'The alarm is too quiet'}]}}))
        listed = (await client.post('/a2a', json=rpc('ListTasks', {'status': 'TASK_STATE_CANCELED'}),
                                    headers=headers)).json()
        every = (await client.post('/a2a', json=rpc('ListTasks', {}), headers=headers)).json()
        record(Store('proj'), 'login-needed', work_id=waiting, key='login')
        login = (await client.post('/a2a', json=rpc('GetTask', {'id': waiting}), headers=headers)).json()
        theirs = [(await client.post('/a2a', json=rpc(method, {'id': one}), headers=headers)).json()
                  for method in ('GetTask', 'CancelTask') for one in (own,)]
        # a ticket whose runner died holding it, one the person holds, and one taken with no session yet
        died, held, taken = [(await send(f'Make it {how}', number, contextId='code.alarm.audible'))['result']['task']['id']
                             for number, how in ((4, 'ring'), (5, 'buzz'), (6, 'chime'))]
        run('map', 'work', 'op=take', f'id={died}', cwd=mapped)
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('agent_sessions', {'session_id': 's-died', 'work_id': died, 'agent': 'claude', 'state': 'ended',
                                   'how': 'the runner is no longer running', 'started': '2026-10-11T00:00:00Z',
                                   'seq': 1})
        run('map', 'work', 'op=edit', f'id={held}', 'held=true', 'hold_reason=Wait for the fixture decision.', cwd=mapped)
        run('map', 'work', 'op=take', f'id={taken}', cwd=mapped)
        read = {one: (await client.post('/a2a', json=rpc('GetTask', {'id': one}), headers=headers)).json()['result']
                for one in (died, held, taken)}
        return streamed['response'].text, cancel, asking.text, listed, every, login, theirs, [read[died], read[held],
                                                                                              read[taken]]
    stream, cancel, asking, listed, every, login, theirs, (died, held, taken) = a2a(mapped, calls)
    told = [json.loads(line[5:])['result'] for line in stream.splitlines() if line.startswith('data:')]
    assert told[-1]['statusUpdate']['status']['state'] == 'TASK_STATE_CANCELED'  # and then the stream closed
    ended = cancel['result']
    assert ended['status']['state'] == 'TASK_STATE_CANCELED' and not ended.get('artifacts')  # never a resolution
    assert Store('proj').ticket(ended['id']).work.outcome == 'cancelled'
    asked = [json.loads(line[5:])['result'] for line in asking.splitlines() if line.startswith('data:')]
    assert [one['task']['status']['state'] for one in asked] == ['TASK_STATE_INPUT_REQUIRED']  # it closed there
    assert [one['id'] for one in listed['result']['tasks']] == [ended['id']]
    assert own not in {one['id'] for one in every['result']['tasks']}
    shown = login['result']
    assert shown['status']['state'] == 'TASK_STATE_WORKING'  # the client cannot log Metaform's agent in
    assert shown['metadata'][extension]['waitingOn'] == 'person' and shown['metadata'][extension]['reason'] == 'login'
    assert 'log it in' in shown['status']['message']['parts'][0]['text']
    assert [one['error']['code'] for one in theirs] == [-32001] * 2  # TaskNotFoundError: the person's, not A2A's
    assert Store('proj').ticket(own).work.done is None
    # dispatch's own reason for the ticket, not one worked out again from its last session
    assert died['status']['state'] == 'TASK_STATE_WORKING'
    assert died['metadata'][extension]['reason'] == 'runner died' and died['metadata'][extension]['waitingOn'] == 'person'
    assert held['status']['state'] == 'TASK_STATE_SUBMITTED' and taken['status']['state'] == 'TASK_STATE_WORKING'
    assert 'waitingOn' not in held['metadata'][extension] and 'waitingOn' not in taken['metadata'][extension]
    from metaform.modules.dispatch import ticket_work_status
    from metaform.modules.mcp.a2a import ticket_state
    work = Store('proj').ticket(taken['id']).work
    idle = ticket_work_status(work, [{'session_id': 's-idle', 'state': 'running', 'activity': 'idle'}], [])
    assert ticket_state(work, {'dispatch': idle}) == ('running', None, 'a2a_working')  # idle between turns
    # dispatch's own status for a ticket it keeps nothing on yet: taken and starting, or held, wait on no one
    starting = ticket_work_status(work, [], [])
    assert starting == {'status': 'running', 'reason': 'starting'}
    assert ticket_state(work, {'dispatch': starting}) == ('running', None, 'a2a_working')
    kept = Store('proj').ticket(held['id']).work
    holding = ticket_work_status(kept, [], [])
    assert holding == {'status': 'submitted', 'reason': 'held'}
    assert ticket_state(kept, {'dispatch': holding}) == ('submitted', None, 'a2a_held')


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_map_view_in_an_ai_tool_draws_the_brief_and_its_items_as_the_web_gui_does(run, home, mapped, chromium):
    """The map view's Brief tab reads metaform_view's `brief`, the answer the web GUI's /api/brief gives, so it lists
    the items numbered at the node; the agent view and the Mermaid copy, which are the web GUI's, are not drawn."""
    from metaform.modules.mcp import views
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'finding', 'why': 'The cook misses it.',
                                                   'observations': ['The tone is too quiet.']}]),
        'node=code.alarm.audible', cwd=mapped)
    apps = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}
    # a view older than the page is not served and the node view, which has no Brief tab, stands in, `views.built`
    assert views.built(), 'the map view is older than the page: node scripts/build_map_view.mjs, as CI runs first'
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/map'}, apps)['contents'][0]['text']
        args = {'address': 'code.alarm.audible'}
        result = declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': args}, apps)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page(viewport={'width': 1280, 'height': 800})
        page.set_default_timeout(30_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), apps)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>')
                         .replace('width:900px;height:700px', 'width:1260px;height:760px'))
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        view = page.frame_locator('#frame')
        view.locator('#t-brief').click()
        row = view.locator('#p-brief ul.items .itemrow')
        row.first.wait_for()
        assert 'The tone is too quiet.' in row.first.inner_text() and 'The cook misses it.' in row.first.inner_text()
        assert view.locator('#p-brief .seeall').count() == 0 and view.locator('#p-brief .acts').count() == 0
        row.first.locator('.itemhead').click()                              # opened through metaform_view's item
        view.locator('#p-brief .itemopen pre.itemtext').wait_for()
        assert 'tone (finding)' in view.locator('#p-brief .itemopen pre.itemtext').inner_text()
        assert page.evaluate('window.refused') == []
    finally:
        wire.close()


APPS = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}


def seed_thread(work_id, lines, first=1):
    """A recorded agent thread for a ticket, written into dispatch's own tables as its runner writes them, and
    announced as its runner announces them; no agent is started."""
    import threading
    from pathlib import Path

    from metaform import events, home
    store = Store('proj', module='dispatch')
    with store.tables() as tx:
        if not tx.rows('agent_sessions', {'session_id': 's-1'}, limit=1).results:
            tx.insert('agent_sessions', {'session_id': 's-1', 'work_id': work_id, 'agent': 'claude', 'state': 'ended',
                                   'started': '2026-10-12T06:30:00Z', 'seq': 1})
        for seq, (kind, text) in enumerate(lines, start=first):
            tx.insert('session_lines', {'session_id': 's-1', 'name': f'line:{seq}', 'work_id': work_id, 'kind': kind,
                                'text': text, 'seq': seq})
    project = home.project('proj')
    assert project is not None
    # from a thread of its own: a browser check calls this inside Playwright's event loop
    announcing = threading.Thread(target=events.announce, args=(Path(project.path), 'cli'))
    announcing.start()
    announcing.join()


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_node_view_turns_to_the_address_the_agent_names_and_its_own_tool_turns_it_without_telling_the_agent(
        run, home, mapped, chromium):
    """The shared picture, agent to person: an open node view turns to the Address a later Metaform call names, read
    through `focus`; a host that calls a view's own tools (App-Provided Tools) lists metaform_view_show and
    metaform_view_state and turns the view with the first. Neither turn is told to the agent as the person's; the
    person's own selection still is, as one line with the Address as structured content."""
    from metaform import prompt_files
    from metaform.modules.mcp import views
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/node'}, APPS)['contents'][0]['text']
        args = {'address': 'code.alarm.audible'}
        result = declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': args}, APPS)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page()
        page.set_default_timeout(15_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), APPS)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>'))
        page.evaluate('''() => {  // the view's answers to the host's own requests, and every context update whole
          window.answers = {}; window.contexts = [];
          addEventListener('message', event => {
            const m = event.data;
            if (m && m.id !== undefined && m.method === undefined) window.answers[m.id] = m;
            if (m && m.method === 'ui/update-model-context') window.contexts.push(m.params);
          });
          window.ask = (id, method, params) => send({id, method, params});
        }''')
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        assert page.evaluate('window.initialize.appCapabilities.tools') == {'listChanged': False}
        view = page.frame_locator('#frame')
        view.locator('#address', has_text='code.alarm.audible').wait_for()
        view.locator('#reliedOnList', has_text='code.timer.kitchen').wait_for()

        declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': {'address': 'code.timer.kitchen'}}, APPS)
        view.locator('#address', has_text='code.timer.kitchen').wait_for()  # the agent named it: the view turned

        page.evaluate("window.ask(901, 'tools/list', {})")
        page.wait_for_function('window.answers[901]')
        assert [tool['name'] for tool in page.evaluate('window.answers[901].result.tools')] == [
            'metaform_view_show', 'metaform_view_state']
        page.evaluate("window.ask(902, 'tools/call', {name: 'metaform_view_show', arguments: {address: "
                      "'code.alarm.audible'}})")
        page.wait_for_function('window.answers[902]')
        shown = page.evaluate('window.answers[902].result')
        assert shown['content'][0]['text'] == prompt_files.module('mcp', 'view_shown', address='code.alarm.audible')
        view.locator('#address', has_text='code.alarm.audible').wait_for()
        assert page.evaluate('window.contexts') == []  # neither turn was the person's

        view.locator('#node').click()
        page.wait_for_function('window.contexts.length === 1')
        assert page.evaluate('window.contexts') == [{'content': [{'type': 'text', 'text': prompt_files.module(
            'mcp', 'view_selected', address='code.alarm.audible')}], 'structuredContent': {'address': 'code.alarm.audible'}}]
        page.evaluate("window.ask(903, 'tools/call', {name: 'metaform_view_state', arguments: {}})")
        page.wait_for_function('window.answers[903]')
        assert page.evaluate('window.answers[903].result.structuredContent') == {
            'view': 'node', 'shows': 'code.alarm.audible', 'selected': 'code.alarm.audible'}
        assert page.evaluate('window.refused') == []
    finally:
        wire.close()


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_trace_view_follows_a_tickets_thread_as_lines_are_added(run, home, mapped, chromium):
    """The trace view, opened by dispatch_sessions for a ticket, shows its title, its node and the agent's thread,
    and draws a line the agent adds while it is open, read again through the views' tool."""
    from metaform.modules.mcp import views
    run('enable', 'dispatch')
    ticket = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'title=Make the alarm louder',
                 'task=Make the alarm louder', cwd=mapped)
    work_id = next(line.split(': ', 1)[1] for line in ticket.stdout.splitlines() if line.startswith('id: '))
    seed_thread(work_id, [('agent_message_chunk', 'I will raise the tone.')])
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/trace'}, APPS)['contents'][0]['text']
        args = {'id': work_id}
        result = declaring(wire, 'tools/call', {'name': 'dispatch_sessions', 'arguments': args}, APPS)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page()
        page.set_default_timeout(15_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), APPS)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>'))
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        view = page.frame_locator('#frame')
        view.locator('#thread .line', has_text='I will raise the tone.').wait_for()
        assert view.locator('#title').inner_text() == 'Make the alarm louder'
        assert view.locator('#address').inner_text() == 'code.alarm.audible'
        seed_thread(work_id, [('tool_call', 'Edit src/alarm.py (completed)')], first=2)
        view.locator('#thread .line', has_text='Edit src/alarm.py (completed)').wait_for()
        assert page.evaluate('window.refused') == []
    finally:
        wire.close()



@pytest.mark.req('MCP-040')
def test_a2a_peers_are_records_the_person_adds_and_removes_one_at_a_time(run, home, mapped):
    """Settings cleanup 2026-10-15: the peers are records, not the list setting mcp_a2a_peers, so adding one keeps
    the others; a stored list carries over once as mcp starts; add and remove are refused in an agent's session."""
    from metaform import home as homes
    from metaform import settings
    from metaform.modules.mcp import a2a_peers
    homes.save('global', 'mcp', 'mcp_a2a_peers', ['old=http://127.0.0.1:7440/.well-known/agent-card.json OLD_TOKEN',
                                                  'not a peer'])
    with homes.chassis(write=True) as db:  # the test home's own start carried nothing and marked it; undo the mark
        db.execute("DELETE FROM meta WHERE key='carried:mcp-a2a-peers'")
    settings._carried.clear()
    assert a2a_peers.carry() == ['peer old', "'not a peer' cannot be read as a peer and was left out"]
    assert a2a_peers.carry() == [], 'once per home'
    listed = lambda: {one['name']: one for one in json.loads(run('mcp', 'a2a_peers', '--json', cwd=mapped).stdout)['peers']}
    assert listed()['old']['token_env'] == 'OLD_TOKEN' and len(listed()) == 1  # carried; the malformed one left out
    assert homes.stored('global', 'mcp', 'mcp_a2a_peers') is None
    run('mcp', 'a2a_peer_add', 'other', 'http://127.0.0.1:7441/.well-known/agent-card.json', cwd=mapped)
    assert set(listed()) == {'old', 'other'}, 'adding one keeps the others'
    run('mcp', 'a2a_peer_remove', 'old', cwd=mapped)
    assert set(listed()) == {'other'}


# What each agent is given, since 2026-10-17: tools found by purpose, results trimmed, each piece at its moment.

def blocks(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None]


def ticket(run, folder, node='code.timer.kitchen', title='Ring louder'):
    """A ticket written on the command line, by its work id."""
    made = run('map', 'work', 'op=add', f'node={node}', f'title={title}', f'task={title}.', '--json', cwd=folder)
    return json.loads(made.stdout)['id']


# A worker explicitly held back by the person's configuration keeps its ticket-oriented schema and guides.
NOT_FOR_A_RESTRICTED_WORKER = ('distribute', 'glyph', 'gitignore', 'YIELD', 'upon loading', 'legacy migration',
                    'The person writes', 'memory prompt', '<address>', "full worker's brief")




@pytest.mark.req('MCP-007')
@pytest.mark.parametrize('task', [None, 'intake', 'project_agent', 'user_agent'])
def test_every_agent_connects_to_the_directive_and_the_links_that_apply_and_each_reads_back_its_block_whole(
        run, home, mapped, monkeypatch, task, in_project_store):
    """Every agent, the person's own session and a session on each task, on stdio and on the July 2026 wire over HTTP:
    its connect message is the directive line and one link per line to the instruction blocks that apply to it, far
    within what any host keeps, and each link reads back its block exactly as its prompt holds it: the rules, the
    glossary, the memory prompt, the task block where one applies, the person's own and the intake's, and the project's
    terms. A task whose text is its first turn gets no task block."""

    from metaform import prompt_files
    from metaform.modules.mcp.opening import task_text
    run('enable', 'memory', cwd=mapped)
    block = 'metaform://task/person' if task is None else 'metaform://task/intake' if task == 'intake' else None
    links = ['metaform://rules', *([block] if block else [])]  # the rules and the task: nothing else is linked
    if task == 'intake':  # a procedure is run with the procedure and nothing beside it: its task alone
        links = [block]
    directive = prompt_files.module('mcp', 'connect_directive') or ''
    assert directive and 'metaform://' not in directive
    identity = {} if task is None else {'METAFORM_TASK_NAME': task, 'METAFORM_SESSION': f'links-{task}'}
    for name, value in identity.items():
        monkeypatch.setenv(name, value)

    def blocks_for(client, session, keyed):
        every = {'metaform://rules': prompt_files.module('mcp', 'connect_rules'),
                 **({block: task_text(mapped)} if block else {})}
        return {uri: every[uri] for uri in links}

    async def over_stdio(client, init):
        return init.instructions, {uri: (await client.read_resource(uri)).contents[0].text for uri in links}
    connect, read = session(home, mapped, over_stdio, env=identity)
    assert connect.splitlines() == [directive, *links] and len(connect) <= 512, connect
    assert read == blocks_for('mcp', f'links-{task}' if task else 'process:stdio', True)


def test_nothing_points_to_a_part_of_the_glossary():
    """metaform://metaform/terms is gone: no resource, prompt, code or reference document names it, so no agent is
    routed to a part of the glossary."""
    from pathlib import Path

    import metaform
    root = Path(metaform.__file__).parent
    named = [str(path) for path in (*root.rglob('*.py'), *root.rglob('*.xml'), *root.rglob('*.md'),
                                    *(root.parent.parent / 'docs').rglob('*.md'))
             if 'tests' not in path.parts and 'metaform://metaform/terms' in path.read_text(encoding='utf-8')]
    assert named == []


def test_find_names_the_addresses_that_hold_the_words(run, home, mapped):
    """map find: an element by its name and a join by its purpose, each by its Address, the most words first."""
    found = Store('proj').find('audible alarm')
    assert found[0] == {'address': 'code.alarm.audible', 'kind': 'element', 'what': 'audible alarm'}
    assert {'address': 'code.timer.kitchen', 'kind': 'join', 'what': 'Get attention. EF: Plays a tone.'} in \
        Store('proj').find('attention')


@pytest.fixture
def usage_tool(run, mapped, user_module):
    user_module('usage', r'''
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        from metaform.module import Module, Noun, Verb
        def write(ctx):
            path = ctx.folder / 'usage-effects.txt'
            path.write_text((path.read_text() if path.exists() else '') + 'effect\n')
            return {'written': True}
        def plain(ctx):
            return {'plain': True}
        MODULE = Module(id='usage', summary='Instruction prerequisite fixture.', purpose='Prove pre-use delivery.',
                        verbs=(Verb('write', write, 'Write one effect.', effect='write', needs_project=False,
                                    nouns=(Noun('value', 'One input.', kind='int', required=False),),
                                    details='Keep the exact selected usage instruction before writing an effect.'),
                               Verb('plain', plain, 'Read a plain value.', effect='read', needs_project=False),
                               Verb('switch', write, 'Apply one operation.', effect='write', nouns=(
                                   Noun('op', 'The operation.', schema={'type': 'string', 'enum': ['one', 'two']}),
                                   Noun('first', 'one: Keep the first operation exact. Read these instructions before '
                                        'using the first operation and preserve the selected first value.', required=False),
                                   Noun('second', 'two: Keep the second operation exact. Read these instructions before '
                                        'using the second operation and preserve the selected second value.', required=False)))))
    ''')
    run('enable', 'usage', cwd=mapped)
    return mapped / 'usage-effects.txt'


def test_the_project_server_lists_one_tool_and_passes_its_arguments_as_the_command(monkeypatch):
    import httpx

    from metaform.modules.mcp import project_tool

    sent = []

    def answered(command, home=None, caller=''):
        sent.append(command)
        return {'status': 'ok'} if 'add' in command else {**command, 'status': 'error', 'code': 'NOT_FOUND',
                                                          'message': 'm', 'remediation': None}
    monkeypatch.setattr(project_tool.commands, 'run', answered)
    app = project_tool.http_app()
    headers = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-06-18'}

    async def go():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:7434') as client:
                async def ask(method, params):  # no initialize and no session id: each request stands alone
                    return (await client.post('/mcp', json=rpc(method, params), headers=headers)).json()['result']
                return (await ask('tools/list', {}),
                        await ask('tools/call', {'name': 'project', 'arguments': {'add': {'p.code.a': {}}}}),
                        await ask('tools/call', {'name': 'project', 'arguments': {'p.code.b': '{}'}}))  # as text
    listed, wrote, refused = asyncio.run(go())
    assert [tool['name'] for tool in listed['tools']] == ['project']
    assert sent == [{'add': {'p.code.a': {}}}, {'p.code.b': {}}]
    assert json.loads(wrote['content'][0]['text']) == {'status': 'ok'} and not wrote.get('isError')
    assert refused['isError'] and json.loads(refused['content'][0]['text'])['code'] == 'NOT_FOUND'


def test_an_agent_is_linked_its_rules_and_its_task_and_an_intake_agent_its_task_alone(tmp_path, monkeypatch):
    from metaform.modules.mcp import opening
    monkeypatch.setattr(opening, 'first_run_text', lambda folder: None)
    person, worker, intake = (opening.Agent(tmp_path, None, True), opening.Agent(tmp_path, 'project_agent', False),
                              opening.Agent(tmp_path, 'intake', False))
    assert opening.links(person) == ['metaform://rules', 'metaform://task/person']
    assert opening.links(worker) == ['metaform://rules']  # its task is its first turn
    assert opening.links(intake) == ['metaform://task/intake']  # a procedure is run with nothing beside it
    monkeypatch.setattr(opening, 'first_run_text', lambda folder: 'first run')
    assert opening.links(person) == ['metaform://rules', 'metaform://firstrun', 'metaform://task/person']
    assert opening.links(worker) == ['metaform://rules']  # never said to an agent a runner started
    assert opening.opening(intake).splitlines()[1:] == ['metaform://task/intake']


def old_work(project):
    """The old store's work rows: none is read or made for a project held in the project store (review of
    2026-11-18, F3); `Store.work` reads the project store's tickets for it."""
    from metaform.data.session import Session
    with Session(project).read() as tx:
        return tx.execute('SELECT count(*) FROM work').fetchone()[0]
