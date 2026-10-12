"""A fake ACP agent for dispatch's tests, BASE-052: newline-delimited JSON-RPC over standard input and output, the
standard library only, no model. Every message it reads is logged as one JSON line to FAKE_ACP_LOG, with whether the
line ended in a carriage return.

FAKE_ACP_MODE says what its first turn does after two message chunks and one tool call:
  ask   asks permission for a second tool call, logs the outcome, and ends the turn; with FAKE_ACP_ASK_GATE naming a
        file, it keeps working until that file exists before it asks, and with FAKE_ACP_ASK_HOLD=1 it keeps working
        after the answer until the turn is cancelled
  done  closes the ticket its prompt names, or else FAKE_ACP_WORK, with the real metaform command line, logs the
        ticket, and ends the turn; with FAKE_ACP_RECORD naming a node, it first records a memory there
  hold  starts a grandchild that sleeps, logs its pid, and ends the turn only when the turn is cancelled
  workflow  reads its ticket's Workflow input JSON, starts and redeems the real stored call, returns its result,
        closes the ticket with that result, and ends the turn
  replace  keeps only the latest prompt active and answers it when its numbered file in FAKE_ACP_TURN_GATES exists;
        overlapping prompts abandon the earlier request, reproducing adapters that replace rather than queue
A later prompt is logged and ends at once. Each process's session id counts the sessions made in the log before it,
fake-session-1 for the first, so the agents a runner starts one after another have sessions of their own.

FAKE_ACP_RICH=1 makes it an agent with more than text: it names itself, offers two modes, a model option and an
effort option (category thought_level) at session/new, then its slash commands, takes session/set_mode and
session/set_config_option, and its first turn edits FAKE_ACP_RICH_PATH, a diff at a location, and reports its usage.
FAKE_ACP_LOAD=1 offers session/load, which takes the session id it is given and replays one message of its history
before it answers.

The extensions the real adapters advertise, each on its own switch: FAKE_ACP_STEER=1 advertises `_session/steering`
and takes it into a turn in flight; FAKE_ACP_SUBAGENT=1 starts one subagent session in its first turn, which says a
word and completes; FAKE_ACP_AUTH=1 offers an agent login method, advertises authStatus and pushes a logged-out
status after initialize, and takes authenticate; FAKE_ACP_USAGE=<n> answers every prompt with n tokens used;
FAKE_ACP_STDERR=1 writes two lines to stderr when it starts, one holding a secret-looking key.
FAKE_ACP_ELICIT=form puts one question to the person in its first turn with ACP's elicitation/create, a choice of
Red or Blue, and logs the answer as `elicited`; FAKE_ACP_ELICIT=url asks it to open a page, logs the answer, and sends
elicitation/complete; FAKE_ACP_ELICIT=ask asks as claude-agent-acp's AskUserQuestion does, a choice of Red or Blue
with its optional free-text "Other" companion, nothing required, and logs the answer; FAKE_ACP_ELICIT=withdraw asks
that question and withdraws it with `$/cancel_request` half a second later, and FAKE_ACP_ELICIT=complete asks a page
to be opened and sends elicitation/complete for it half a second later, each logging what its request was answered
with. FAKE_ACP_USED=<a,b,...> sends a usage update with each context size in use and no cost in its first turn, as
the adapters do after each model call. FAKE_ACP_COST=<a,b,...> sends a usage update with each cumulative cost in USD in its first turn;
FAKE_ACP_NOTICE=1 sends a session notice when the client advertises them; FAKE_ACP_CLOSE=1 advertises session/close
and session/delete and takes them; FAKE_ACP_FORK=1 advertises session/fork and answers it with fake-fork-<n>;
FAKE_ACP_INFO=1 writes, in one write with its session/new answer and after it, a session_info_update giving the
session a title and its last activity; FAKE_ACP_SILENT=<seconds> makes a hold turn fall silent that long, say one word,
and fall silent again.
FAKE_ACP_MCP_ACP=1 advertises MCP-over-ACP (`mcpCapabilities.acp`) and, once a session declares a server of
`type: "acp"`, asks it for its tools with `mcp/message` and logs the answer as `mcp_acp`; FAKE_ACP_LIST=1 advertises
session/list and answers it in two pages of its own, the second holding seed-03, a session Metaform records too;
FAKE_ACP_V2=1 negotiates ACP v2: `capabilities` and `info` at initialize, and every prompt answered at insertion with
its messageId, then reported as a user message, an agent message streamed and replaced, a tool call that modifies a
file, and an idle `state_update`.
To a client whose clientCapabilities.auth.terminal is true it offers a terminal login, and started with that
login's --login it logs its arguments and exits 0, speaking no ACP.
"""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

LOG = os.environ['FAKE_ACP_LOG']
MODE = os.environ.get('FAKE_ACP_MODE', 'ask')
SESSION = 'fake-session-1'  # until session/new names it
OUT = sys.stdout.buffer
WRITING = threading.Lock()
ANSWERS: dict[int, threading.Event] = {}
RESULTS: dict[int, object] = {}
CANCELLED = threading.Event()
PROMPTS = [0]
ACTIVE_PROMPT = [None]
PROMPT_LOCK = threading.Lock()
RICH = os.environ.get('FAKE_ACP_RICH') == '1'
MCP_ACP = os.environ.get('FAKE_ACP_MCP_ACP') == '1'
V2 = os.environ.get('FAKE_ACP_V2') == '1'
MODES = {'currentModeId': 'default', 'availableModes': [{'id': 'default', 'name': 'Default'},
                                                         {'id': 'plan', 'name': 'Plan', 'description': 'Plans only'}]}
MODEL = ['small']


EFFORT = ['low']


def options():
    return [{'id': 'model', 'name': 'Model', 'type': 'select', 'category': 'model', 'currentValue': MODEL[0],
             'options': [{'value': 'small', 'name': 'Small'}, {'value': 'large', 'name': 'Large'}]},
            {'id': 'reasoning', 'name': 'Effort', 'type': 'select', 'category': 'thought_level',
             'currentValue': EFFORT[0], 'options': [{'value': 'low', 'name': 'Low'}, {'value': 'high', 'name': 'High'}]}]


def made():
    """What session/new and session/load answer with: the modes and the options of a rich agent."""
    return {'modes': MODES, 'configOptions': options()} if RICH else {}


def log(entry):
    with WRITING, open(LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry) + '\n')


def send(message):
    with WRITING:
        OUT.write(json.dumps(message).encode('utf-8') + b'\n')
        OUT.flush()


def update(body):
    send({'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': SESSION, 'update': body}})


def ask(request_id, params):
    return request(request_id, 'session/request_permission', params)


def request(request_id, method, params):
    """A request to the client, answered before it returns: its result, or its error."""
    event = threading.Event()
    ANSWERS[request_id] = event
    send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    event.wait()
    return RESULTS.pop(request_id)


def later(request_id, method, params, then):
    """A request to the client, and half a second later `then`, sent while it waits; its answer, once given."""
    event = threading.Event()
    ANSWERS[request_id] = event
    send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    if not event.wait(0.5):
        send(then)
    event.wait()
    return RESULTS.pop(request_id)


def tool(ident, title, words):
    """One tool call that runs the real metaform command line, its output what the command printed."""
    command = [sys.executable, '-m', 'metaform', *words]
    update({'sessionUpdate': 'tool_call', 'toolCallId': ident, 'title': title, 'kind': 'execute', 'status': 'pending',
            'rawInput': {'command': command}})
    printed = subprocess.run(command, capture_output=True, text=True, check=False).stdout
    update({'sessionUpdate': 'tool_call_update', 'toolCallId': ident, 'status': 'completed', 'rawOutput': printed,
            'content': [{'type': 'content', 'content': {'type': 'text', 'text': printed}}]})
    return printed


def first_turn(prompt_id, text):
    update({'sessionUpdate': 'agent_thought_chunk', 'content': {'type': 'text', 'text': 'Thinking it over'}})
    update({'sessionUpdate': 'plan', 'entries': [{'content': 'Read', 'priority': 'high', 'status': 'in_progress'}]})
    update({'sessionUpdate': 'plan', 'entries': [{'content': 'Read', 'priority': 'high', 'status': 'completed'},
                                                 {'content': 'Write', 'priority': 'high', 'status': 'pending'}]})
    update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Hello '}})
    update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'from fake'}})
    update({'sessionUpdate': 'tool_call', 'toolCallId': 't1', 'title': 'Read file', 'kind': 'read',
            'status': 'pending'})
    update({'sessionUpdate': 'tool_call_update', 'toolCallId': 't1', 'status': 'completed'})
    if os.environ.get('FAKE_ACP_SUBAGENT') == '1':  # the native subagent session shape of claude-agent-acp
        update({'sessionUpdate': 'subagent_spawned', 'subagentSessionId': 'child-1', 'name': 'Explorer',
                'task': 'Look around', 'capabilities': {}})
        send({'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': 'child-1', 'update': {
            'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Child words'}}}})
        update({'sessionUpdate': 'subagent_state_update', 'subagentSessionId': 'child-1', 'state': 'completed'})
    if RICH:
        path = os.environ['FAKE_ACP_RICH_PATH']
        update({'sessionUpdate': 'tool_call', 'toolCallId': 't-edit', 'title': 'Edit engine', 'kind': 'edit',
                'status': 'in_progress', 'locations': [{'path': path, 'line': 2}],
                'content': [{'type': 'diff', 'path': path, 'oldText': 'one\n', 'newText': 'one\ntwo\n'}]})
        update({'sessionUpdate': 'tool_call_update', 'toolCallId': 't-edit', 'status': 'completed'})
        update({'sessionUpdate': 'usage_update', 'used': 1200, 'size': 200000})
    if os.environ.get('FAKE_ACP_NOTICE') == '1' and NOTICES[0]:
        update({'sessionUpdate': 'notice', 'severity': 'warning', 'title': 'MCP server unavailable',
                'description': 'Continuing without it.'})
    for amount in [one for one in os.environ.get('FAKE_ACP_COST', '').split(',') if one]:
        update({'sessionUpdate': 'usage_update', 'used': 1000, 'size': 200000,
                'cost': {'amount': float(amount), 'currency': 'USD'}})
    for context in [one for one in os.environ.get('FAKE_ACP_USED', '').split(',') if one]:
        update({'sessionUpdate': 'usage_update', 'used': int(context), 'size': 200000})
    elicit = os.environ.get('FAKE_ACP_ELICIT')
    if elicit in ('ask', 'withdraw'):  # claude-agent-acp 0.89.1's askUserQuestionsToCreateRequest, one question
        schema = {'type': 'object', 'properties': {
            'question_0': {'type': 'string', 'title': 'Colour', 'oneOf': [{'const': 'Red', 'title': 'Red'},
                                                                           {'const': 'Blue', 'title': 'Blue'}]},
            'question_0_custom': {'type': 'string', 'title': 'Other', 'description': 'Type your own answer, or add a '
                                  'note to the option you chose above (optional).'}}}
        params = {'sessionId': SESSION, 'toolCallId': 't-ask', 'mode': 'form', 'message': 'Which colour?',
                  'requestedSchema': schema}
        if elicit == 'ask':
            log({'elicited': request(952, 'elicitation/create', params)})
        else:
            log({'elicited': later(953, 'elicitation/create', params,
                                   {'jsonrpc': '2.0', 'method': '$/cancel_request', 'params': {'requestId': 953}})})
    elif elicit == 'complete':
        log({'elicited': later(954, 'elicitation/create', {
            'sessionId': SESSION, 'mode': 'url', 'elicitationId': 'e2', 'message': 'Sign in to the server',
            'url': 'https://auth.example.com/login?state=y'},
            {'jsonrpc': '2.0', 'method': 'elicitation/complete', 'params': {'elicitationId': 'e2'}})})
    if elicit == 'form':
        answer = request(950, 'elicitation/create', {
            'sessionId': SESSION, 'mode': 'form', 'message': 'Which colour?',
            'requestedSchema': {'type': 'object', 'required': ['colour'], 'properties': {'colour': {
                'type': 'string', 'title': 'Colour', 'oneOf': [{'const': 'red', 'title': 'Red'},
                                                               {'const': 'blue', 'title': 'Blue'}]}}}})
        log({'elicited': answer})
    elif elicit == 'url':
        answer = request(951, 'elicitation/create', {'sessionId': SESSION, 'mode': 'url', 'elicitationId': 'e1',
                                                     'message': 'Sign in to the server',
                                                     'url': 'https://auth.example.com/login?state=x'})
        log({'elicited': answer})
        send({'jsonrpc': '2.0', 'method': 'elicitation/complete', 'params': {'elicitationId': 'e1'}})
    if MODE == 'ask':
        gate = os.environ.get('FAKE_ACP_ASK_GATE')
        while gate and not os.path.exists(gate) and not CANCELLED.wait(0.05):
            pass
        if CANCELLED.is_set():
            send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled'}})
            return
        outcome = ask(900, {'sessionId': SESSION,
                            'toolCall': {'toolCallId': 't2', 'title': os.environ.get('FAKE_ACP_ASK_TITLE', 'Write notes.txt'),
                                         'kind': os.environ.get('FAKE_ACP_ASK_KIND', 'edit'),
                                         'status': 'pending'},
                            'options': [{'optionId': 'allow', 'name': 'Allow once', 'kind': 'allow_once'},
                                        {'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'}]})
        log({'permission': outcome})
        if os.environ.get('FAKE_ACP_ASK_HOLD') == '1':
            end_gate = os.environ.get('FAKE_ACP_ASK_END')
            while not (end_gate and os.path.exists(end_gate)) and not CANCELLED.wait(0.05):
                pass
            reason = 'cancelled' if CANCELLED.is_set() else 'end_turn'
            send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': reason}})
            return
    if MODE == 'done':
        if os.environ.get('FAKE_ACP_EDIT'):  # a change in the folder it works in, its worktree when there is one
            with open(os.environ['FAKE_ACP_EDIT'], 'w', encoding='utf-8') as written:
                written.write('changed by the fake agent\n')
        named = re.search(r'\b([0-9a-f]{32})\b', text)
        work = named.group(1) if named else os.environ['FAKE_ACP_WORK']
        if os.environ.get('FAKE_ACP_RECORD'):  # a memory at that node first, written with the runner's identity
            entity = [{'name': 'fake finding', 'entityType': 'fact', 'observations': ['seen by the fake'],
                       'why': 'The next agent here needs it.'}]
            recorded = subprocess.run([sys.executable, '-m', 'metaform', 'memory', 'create_entities',
                                       json.dumps(entity), f'node={os.environ["FAKE_ACP_RECORD"]}'],
                                      capture_output=True, text=True, check=False)
            log({'recorded': recorded.returncode, 'err': recorded.stderr})
        finished = subprocess.run([sys.executable, '-m', 'metaform', 'map', 'work', 'op=done', f'id={work}',
                                   'resolution=fake', 'why=The fake finished it.'], capture_output=True, text=True,
                                  check=False)
        log({'done': finished.returncode, 'err': finished.stderr, 'work': work})
    if MODE == 'workflow':
        named = re.search(r'\b([0-9a-f]{32})\b', text)
        work = named.group(1) if named else os.environ['FAKE_ACP_WORK']
        ticket = json.loads(tool('workflow-ticket', 'Read the workflow ticket',
                                 ['map', 'work', f'id={work}', '--json']))
        given = re.search(r'^Workflow input: (.+)$', ticket['task'], re.MULTILINE)
        inputs = json.loads(given.group(1))
        started = json.loads(tool('workflow-run', 'Start the stored workflow',
                                  ['workflow', 'run', inputs['call'], f'element={inputs["element"]}', '--json']))
        log({'workflow_run': started})
        redeemed = json.loads(tool('workflow-resume', 'Resume the workflow run',
                                   ['workflow', 'resume', f'run={started["run"]}', '--json']))
        log({'workflow_resume': redeemed})
        returned = json.loads(tool('workflow-complete', 'Return the workflow result',
                                   ['workflow', 'complete', f'run={started["run"]}',
                                    'RETURN (TRUE, {target}.address)', '--json']))
        log({'workflow_complete': returned})
        finished = tool('workflow-done', 'Complete the workflow ticket',
                        ['map', 'work', 'op=done', f'id={work}',
                         'resolution=' + json.dumps(returned['value']), 'why=The workflow returned it.', '--json'])
        log({'workflow_done': json.loads(finished), 'work': work})
    if MODE == 'hold':
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])
        log({'grandchild': child.pid})
        silent = float(os.environ.get('FAKE_ACP_SILENT') or 0)
        if silent and not CANCELLED.wait(silent):  # silent, one word, then silent again until cancelled
            update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Still here'}})
            log({'spoke': True})
        CANCELLED.wait()
        send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled', **used()}})
        return
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'end_turn', **used()}})


def used():
    """What a prompt's answer says it used, ACP's end-turn token usage, when FAKE_ACP_USAGE sets it."""
    tokens = int(os.environ.get('FAKE_ACP_USAGE') or 0)
    return {'usage': {'totalTokens': tokens, 'inputTokens': tokens, 'outputTokens': 0}} if tokens else {}


def held_turn(prompt_id):
    CANCELLED.wait()
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled'}})


def replacing_turn(prompt_id, number):
    """Like codex-acp, only the latest prompt receives a reply if prompts overlap. Gates let tests end each turn."""
    gate = Path(os.environ['FAKE_ACP_TURN_GATES']) / str(number)
    while not gate.exists() and not CANCELLED.wait(0.05):
        pass
    with PROMPT_LOCK:
        if ACTIVE_PROMPT[0] == prompt_id:
            reason = 'cancelled' if CANCELLED.is_set() else 'end_turn'
            send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': reason}})
            ACTIVE_PROMPT[0] = None


def main():
    global SESSION
    for line in sys.stdin.buffer:
        message = json.loads(line)
        log({'crlf': line.endswith(b'\r\n'), 'message': message, 'secret': os.environ.get('FAKE_SECRET'),
             'argv': sys.argv, 'filtering': os.environ.get('DISABLE_MCP_CONFIG_FILTERING'),
             'role': os.environ.get('METAFORM_ROLE'), 'runner': os.environ.get('METAFORM_SESSION')})
        method, ident = message.get('method'), message.get('id')
        if method is None:
            if ident in ANSWERS:
                RESULTS[ident] = message.get('result', {'error': message.get('error')})
                ANSWERS.pop(ident).set()
            continue
        if method == 'initialize':
            NOTICES[0] = message['params'].get('clientCapabilities', {}).get('session', {}).get('notices') is not None
            closing = os.environ.get('FAKE_ACP_CLOSE') == '1'
            sessions = {**({'close': {}, 'delete': {}} if closing else {}),
                        **({'fork': {}} if os.environ.get('FAKE_ACP_FORK') == '1' else {})}
            auth = os.environ.get('FAKE_ACP_AUTH') == '1'
            if os.environ.get('FAKE_ACP_LIST') == '1':
                sessions['list'] = {}
            if V2:
                send({'jsonrpc': '2.0', 'id': ident, 'result': {
                    'protocolVersion': 2, 'info': {'name': 'fake-v2', 'version': '2.0'},
                    'capabilities': {'session': {'mcp': {'stdio': {}}}}}})
                continue
            send({'jsonrpc': '2.0', 'id': ident,
                  'result': {'protocolVersion': 1,
                             'authMethods': ([{'id': 'fake-login', 'name': 'Log in', 'type': 'agent'}] if auth else [])
                             + ([TERMINAL_LOGIN] if message['params'].get('clientCapabilities', {}).get('auth', {})
                                .get('terminal') is True else []),
                             'agentCapabilities': {'loadSession': os.environ.get('FAKE_ACP_LOAD') == '1',
                                                   **({'mcpCapabilities': {'acp': True}} if MCP_ACP else {}),
                                                   **({'sessionCapabilities': sessions} if sessions else {}),
                                                   **({'_meta': {'authStatus': {}}} if auth else {})},
                             **({'agentInfo': {'name': 'fake-agent', 'version': '1.0'}} if RICH else {}),
                             **({'_meta': {'steering': {'supported': True}}} if os.environ.get('FAKE_ACP_STEER') == '1'
                                else {})}})
            if auth:
                send({'jsonrpc': '2.0', 'method': '_auth/status_update',
                      'params': {'authStatus': {'kind': 'none', 'label': 'Not logged in'}}})
        elif method == 'authenticate':
            send({'jsonrpc': '2.0', 'id': ident, 'result': {}})
        elif method == '_session/steering':
            outcome = 'injected' if ACTIVE_TURN[0] else 'promptRequired'
            log({'steered': message['params']['prompt'][0]['text'], 'outcome': outcome})
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'outcome': outcome}})
        elif method == 'session/new':
            with WRITING, open(LOG, encoding='utf-8') as handle:
                count = sum(json.loads(line).get('message', {}).get('method') == 'session/new' for line in handle)
            SESSION = f'fake-session-{count}'
            answer = {'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': SESSION, **made()}}
            if os.environ.get('FAKE_ACP_INFO') == '1':  # the answer and an update of its session, in one write
                info = {'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': SESSION, 'update': {
                    'sessionUpdate': 'session_info_update', 'title': f'Fake title {count}',
                    'updatedAt': '2030-01-01T00:00:00Z'}}}
                with WRITING:
                    OUT.write(json.dumps(answer).encode('utf-8') + b'\n' + json.dumps(info).encode('utf-8') + b'\n')
                    OUT.flush()
            else:
                send(answer)
            declared = [one for one in message['params'].get('mcpServers', []) if one.get('type') == 'acp']
            if MCP_ACP and declared:
                threading.Thread(target=over_acp, args=(declared[0]['serverId'],), daemon=True).start()
            if RICH:
                update({'sessionUpdate': 'available_commands_update', 'availableCommands': [
                    {'name': 'review', 'description': 'Review the changes', 'input': {'hint': 'what to review'}}]})
        elif method == 'session/load' and os.environ.get('FAKE_ACP_LOAD') == '1':
            SESSION = message['params']['sessionId']
            update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Replayed history'}})
            send({'jsonrpc': '2.0', 'id': ident, 'result': made()})
        elif method == 'session/set_mode' and RICH:
            MODES['currentModeId'] = message['params']['modeId']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {}})
            update({'sessionUpdate': 'current_mode_update', 'currentModeId': MODES['currentModeId']})
        elif method == 'session/set_config_option' and RICH:
            (MODEL if message['params']['configId'] == 'model' else EFFORT)[0] = message['params']['value']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'configOptions': options()}})
        elif method == 'session/list' and os.environ.get('FAKE_ACP_LIST') == '1':
            second = message['params'].get('cursor') == 'fake-page-2'
            listed = ['fake-listed-3', 'seed-03'] if second else ['fake-listed-1', 'fake-listed-2']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {
                'sessions': [{'sessionId': one, 'cwd': message['params'].get('cwd') or os.getcwd(), 'title': one}
                             for one in listed], **({} if second else {'nextCursor': 'fake-page-2'})}})
        elif method == 'session/prompt' and V2:
            PROMPTS[0] += 1
            v2_turn(ident, message['params'], PROMPTS[0])
        elif method == 'session/prompt':
            CANCELLED.clear()  # each serial turn receives only its own cancellation
            PROMPTS[0] += 1
            if MODE == 'replace':
                with PROMPT_LOCK:
                    if ACTIVE_PROMPT[0] is not None:
                        log({'replaced': ACTIVE_PROMPT[0]})
                    ACTIVE_PROMPT[0] = ident
                threading.Thread(target=replacing_turn, args=(ident, PROMPTS[0]), daemon=True).start()
            elif PROMPTS[0] == 1:
                said = ' '.join(block.get('text', '') for block in message['params'].get('prompt', []))
                threading.Thread(target=turn_of, args=(first_turn, ident, said), daemon=True).start()
            elif os.environ.get('FAKE_ACP_HOLD_LATER') == '1':
                threading.Thread(target=turn_of, args=(held_turn, ident), daemon=True).start()
            else:
                send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn', **used()}})
        elif method == 'session/cancel':
            CANCELLED.set()
        elif method == 'session/fork' and os.environ.get('FAKE_ACP_FORK') == '1':
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': f'fake-fork-{PROMPTS[0]}'}})
        elif method in ('session/close', 'session/delete') and os.environ.get('FAKE_ACP_CLOSE') == '1':
            send({'jsonrpc': '2.0', 'id': ident, 'result': {}})
        else:
            send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})


def over_acp(server_id):
    """Metaform's server, declared over ACP, asked for its tools as an agent of MCP 2026-07-28 asks."""
    answer = request(900, 'mcp/message', {'serverId': server_id, 'requestId': 'fake-mcp-1', 'method': 'tools/list',
                                          'params': {'_meta': {
                                              'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                                              'io.modelcontextprotocol/clientCapabilities': {},
                                              'io.modelcontextprotocol/clientInfo': {'name': 'fake', 'version': '1'}}}})
    log({'mcp_acp': answer})


def v2_turn(ident, params, number):
    """A v2 prompt: answered once inserted, its work reported by updates and ended by an idle state_update."""
    mine, said = f'fake-user-{number}', f'fake-agent-{number}'
    send({'jsonrpc': '2.0', 'id': ident, 'result': {'messageId': mine}})
    for body in ({'sessionUpdate': 'user_message', 'messageId': mine, 'content': params.get('prompt', [])},
                 {'sessionUpdate': 'state_update', 'state': 'running'},
                 {'sessionUpdate': 'agent_message_chunk', 'messageId': said, 'content': {'type': 'text', 'text': 'Hel'}},
                 {'sessionUpdate': 'agent_message_chunk', 'messageId': said, 'content': {'type': 'text', 'text': 'lo'}},
                 {'sessionUpdate': 'agent_message', 'messageId': said, 'content': [{'type': 'text', 'text': 'Hello v2'}]},
                 {'sessionUpdate': 'tool_call_update', 'toolCallId': 'fake-edit', 'title': 'Edit config', 'status':
                  'in_progress'},
                 {'sessionUpdate': 'tool_call_update', 'toolCallId': 'fake-edit', 'status': 'completed', 'content': [
                     {'type': 'diff', 'changes': [{'operation': 'modify', 'path': '/work/config.json'},
                                                  {'operation': 'move', 'oldPath': '/work/a.txt', 'path': '/work/b.txt'}],
                      'patch': None}]},
                 {'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': 'end_turn'}):
        update(body)


def turn_of(work, *args):
    """A turn in flight, as steering sees it, until it answers."""
    ACTIVE_TURN[0] = True
    try:
        work(*args)
    finally:
        ACTIVE_TURN[0] = False


ACTIVE_TURN = [False]
NOTICES = [False]  # the client advertised ACP's session notices
# ACP's terminal login, offered to an editor that can run one: the editor runs this agent again with these arguments
# and this environment, in a terminal; started so, it logs what it was given and exits 0 without speaking ACP.
TERMINAL_LOGIN = {'id': 'fake-terminal', 'name': 'Log in in a terminal', 'type': 'terminal', 'args': ['--login', 'now'],
                  'env': {'FAKE_LOGIN': 'yes'}}
log({'pid': os.getpid()})
if '--login' in sys.argv:
    log({'login': sys.argv[sys.argv.index('--login'):], 'login_env': os.environ.get('FAKE_LOGIN'),
         'login_leak': os.environ.get('METAFORM_SERVE_LOGIN')})
    sys.exit(0)
if os.environ.get('FAKE_ACP_STDERR') == '1':
    sys.stderr.write('fake agent starting\nusing api_key=sk-abcdefghijklmnop0123456789 for the run\n')
    sys.stderr.flush()
main()
if os.environ.get('FAKE_ACP_ORPHAN_HOLD') == '1':
    # Reproduce an adapter that remains alive with descendants after its ACP client's pipes close.
    threading.Event().wait()
