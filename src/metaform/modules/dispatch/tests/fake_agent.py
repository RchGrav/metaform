"""A fake ACP agent for dispatch's tests, BASE-052: newline-delimited JSON-RPC over standard input and output, the
standard library only, no model. Every message it reads is logged as one JSON line to FAKE_ACP_LOG, with whether the
line ended in a carriage return.

FAKE_ACP_MODE says what its first turn does after two message chunks and one tool call:
  ask   asks permission for a second tool call, logs the outcome, and ends the turn; with FAKE_ACP_ASK_GATE naming a
        file, it keeps working until that file exists before it asks, and with FAKE_ACP_ASK_HOLD=1 it keeps working
        after the answer until the turn is cancelled; with FAKE_ACP_ASK_AGAIN naming a file, it asks again for a
        third tool call, Write more.txt, once that file exists, and logs that outcome as `permission_again`
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
before it answers. FAKE_ACP_APP=<address> makes its first turn call mcp__metaform__map_where on that address, a tool
with an MCP App view, its result what the real metaform map where prints. FAKE_ACP_SAY=<text> makes its first turn call
mcp__metaform__web_say with that text, running the real metaform web say, and then say the same text as a message, as
agents that speak through the mascot do; FAKE_ACP_SAY_STREAM=<seconds> sends that message a word at a time, that many
seconds apart, as a model writes it, and with FAKE_ACP_SAY_GATE naming a file it starts the message once that file
exists.

The extensions the real adapters advertise, each on its own switch: FAKE_ACP_STEER=1 advertises `_session/steering`
and takes it into a turn in flight; FAKE_ACP_SUBAGENT=1 starts one subagent session in its first turn, which says a
word and completes; FAKE_ACP_AUTH=1 offers an agent login method, advertises authStatus and pushes a logged-out
status after initialize, and takes authenticate; FAKE_ACP_USAGE=<n> answers every prompt with n tokens used;
FAKE_ACP_STDERR=1 writes two lines to stderr when it starts, one holding a secret-looking key.
FAKE_ACP_AUDIO=1 declares promptCapabilities.audio, so a person's spoken message may carry its recording;
FAKE_ACP_IMAGE=1 declares promptCapabilities.image, so a person's message may carry a frame of their shared screen.
FAKE_ACP_ELICIT=form puts one question to the person in its first turn with ACP's elicitation/create, a choice of
Red or Blue, and logs the answer as `elicited`; FAKE_ACP_ELICIT=url asks it to open a page, logs the answer, and sends
elicitation/complete; FAKE_ACP_ELICIT=ask asks as claude-agent-acp's AskUserQuestion does, a choice of Red or Blue
with its optional free-text "Other" companion, nothing required, and logs the answer; FAKE_ACP_ELICIT=withdraw asks
that question and withdraws it with `$/cancel_request` half a second later, and FAKE_ACP_ELICIT=complete asks a page
to be opened and sends elicitation/complete for it half a second later, and FAKE_ACP_ELICIT=complete-first sends
elicitation/complete before it asks, each logging what its request was answered with; FAKE_ACP_ELICIT=setup asks a
page to be opened while it makes its session, scoped to session/new's request, answers session/new half a second
later, and logs what the question was answered with. FAKE_ACP_USED=<a,b,...> sends a usage update with each context size in use and no cost in its first turn, as
the adapters do after each model call. FAKE_ACP_COST=<a,b,...> sends a usage update with each cumulative cost in USD in its first turn;
FAKE_ACP_NOTICE=1 sends a session notice when the client advertises them; FAKE_ACP_COMPACT=<status,...> sends
ACP's compaction_update with each status in turn as the first turn ends, when the client advertises session compaction; FAKE_ACP_CLOSE=1 advertises session/close
and session/delete and takes them; FAKE_ACP_FORK=1 advertises session/fork and answers it with fake-fork-<n>;
FAKE_ACP_CLIENT=1 makes its first turn use the client's own files and terminals, ACP's fs/* and terminal/*: it writes and
reads fake-client/note.txt in its folder, reads a file outside it, runs one command in a terminal, waits for it, reads
its output and releases it, and logs every answer as `client`. FAKE_ACP_WRITES=<a,b,...> makes its first turn read and
then write each of those files, from its folder, through fs/*, logging the answers as `writes`.
FAKE_ACP_INTAKE=1 makes its first turn read a review file and call a memory tool, wait up to 30 s for a steer, then
call intake_element and log `intake_recorded`.
FAKE_ACP_INFO=1 writes, in one write with its session/new answer and after it, a session_info_update giving the
session a title and its last activity; FAKE_ACP_SILENT=<seconds> makes a hold turn fall silent that long, say one word,
and fall silent again.
FAKE_ACP_MCP_ACP=1 advertises MCP-over-ACP (`mcpCapabilities.acp`) and, once a session declares a server of
`type: "acp"`, asks it for its tools with `mcp/message` and logs the answer as `mcp_acp`; FAKE_ACP_LIST=1 advertises
session/list and answers it in two pages of its own, the second holding seed-03, a session Metaform records too;
FAKE_ACP_V2=1 negotiates ACP v2: `capabilities` and `info` at initialize, and every prompt answered at insertion with
its messageId, then reported as a user message, an agent message streamed and replaced, a tool call that modifies a
file, and an idle `state_update`.
FAKE_ACP_MASCOT=1 makes it a system agent that drives the person's mascot: each prompt after the first runs the real
metaform web say, web go (to FAKE_ACP_MASCOT_GO, when set, then web see and web look there) and web emote wave, then
answers in one message; with FAKE_ACP_MASCOT_SCRIPT naming a file, it first runs each metaform command of its lines, a JSON
list of words each, or waits the seconds a line gives alone.
To a client whose clientCapabilities.auth.terminal is true it offers a terminal login, and started with that
login's --login it logs its arguments and exits 0, speaking no ACP.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
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


def confirm_context(params):
    text = '\n'.join(block.get('text', '') for block in params.get('prompt', []))
    checkpoint = re.search(r'Startup context checkpoint: ([0-9a-f]+)', text)
    if checkpoint:
        key = re.search(r'Retain this context key: ([0-9a-f]+)', text)
        words = ['agents', 'confirm', f'checkpoint={checkpoint[1]}', '--json']
        if key:
            words.append(f'key={key[1]}')
        # This fixture has no retained model context on process restart, so it truthfully omits a lost key.
        subprocess.run([sys.executable, '-m', 'metaform', *words], capture_output=True, check=True)


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
    if os.environ.get('FAKE_ACP_CLIENT') == '1':  # the client's files and terminals, ACP fs/* and terminal/*
        inside = os.path.join(os.getcwd(), 'fake-client', 'note.txt')
        done = {'write': request(800, 'fs/write_text_file', {'sessionId': SESSION, 'path': inside,
                                                              'content': 'one\ntwo\nthree\n'}),
                'read': request(801, 'fs/read_text_file', {'sessionId': SESSION, 'path': inside, 'line': 2,
                                                            'limit': 1}),
                'outside': request(802, 'fs/read_text_file', {'sessionId': SESSION, 'path': os.path.join(
                    os.path.dirname(os.getcwd()), 'outside.txt')})}
        made = request(803, 'terminal/create', {'sessionId': SESSION, 'command': sys.executable,
                                                 'args': ['-c', 'print("hi from terminal")'], 'outputByteLimit': 1000})
        own = {'sessionId': SESSION, 'terminalId': made.get('terminalId')}
        done.update(create=made, exit=request(804, 'terminal/wait_for_exit', own),
                    output=request(805, 'terminal/output', own), release=request(806, 'terminal/release', own),
                    gone=request(807, 'terminal/output', own))
        log({'client': done})
    writes = [one for one in os.environ.get('FAKE_ACP_WRITES', '').split(',') if one]
    if writes:  # each file read then written through the client
        paths = [os.path.join(os.getcwd(), one) for one in writes]
        log({'writes': {'read': [request(810 + at, 'fs/read_text_file', {'sessionId': SESSION, 'path': path})
                                 for at, path in enumerate(paths)],
                        'write': [request(820 + at, 'fs/write_text_file', {'sessionId': SESSION, 'path': path,
                                                                            'content': 'written\n'})
                                  for at, path in enumerate(paths)]}})
    if os.environ.get('FAKE_ACP_INTAKE') == '1':  # an intake that reaches for earlier conclusions, then is steered
        for ident, title, raw in (('i1', 'Read artifacts/review-notes.md', {'path': 'artifacts/review-notes.md'}),
                                  ('i2', 'mcp__metaform__memory_read_graph', {})):
            update({'sessionUpdate': 'tool_call', 'toolCallId': ident, 'title': title, 'kind': 'read',
                    'status': 'pending', 'rawInput': raw})
            update({'sessionUpdate': 'tool_call_update', 'toolCallId': ident, 'status': 'completed'})
        STEERED.wait(30)
        update({'sessionUpdate': 'tool_call', 'toolCallId': 'i3', 'title': 'mcp__metaform__intake_element',
                'kind': 'other', 'status': 'pending', 'rawInput': {'address': 'code.engine'}})
        update({'sessionUpdate': 'tool_call_update', 'toolCallId': 'i3', 'status': 'completed'})
        log({'intake_recorded': True})
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
    if os.environ.get('FAKE_ACP_APP'):  # a Metaform tool with a view, called as an MCP tool, its result the real one
        address = os.environ['FAKE_ACP_APP']
        update({'sessionUpdate': 'tool_call', 'toolCallId': 't-app', 'title': 'mcp__metaform__map_where',
                'kind': 'other', 'status': 'in_progress', 'rawInput': {'address': address}})
        printed = subprocess.run([sys.executable, '-m', 'metaform', 'map', 'where', address], capture_output=True,
                                 text=True, check=False).stdout
        update({'sessionUpdate': 'tool_call_update', 'toolCallId': 't-app', 'status': 'completed',
                'rawOutput': {'content': [{'type': 'text', 'text': printed}], 'isError': False},
                'content': [{'type': 'content', 'content': {'type': 'text', 'text': printed}}]})
    if os.environ.get('FAKE_ACP_SAY'):  # a line said in the bubble as an MCP tool, and the same line as a message
        line = os.environ['FAKE_ACP_SAY']
        update({'sessionUpdate': 'tool_call', 'toolCallId': 't-say', 'title': 'mcp__metaform__web_say',
                'kind': 'other', 'status': 'in_progress', 'rawInput': {'text': line}})
        printed = subprocess.run([sys.executable, '-m', 'metaform', 'web', 'say', line, '--json'], capture_output=True,
                                 text=True, check=False).stdout
        update({'sessionUpdate': 'tool_call_update', 'toolCallId': 't-say', 'status': 'completed',
                'rawOutput': {'content': [{'type': 'text', 'text': printed}], 'isError': False},
                'content': [{'type': 'content', 'content': {'type': 'text', 'text': printed}}]})
        gate = os.environ.get('FAKE_ACP_SAY_GATE')
        while gate and not os.path.exists(gate) and not CANCELLED.wait(0.05):
            pass
        pause = float(os.environ.get('FAKE_ACP_SAY_STREAM') or 0)
        pieces = [(' ' if at else '') + word for at, word in enumerate(line.split(' '))] if pause else [line]
        for piece in pieces:  # sent whole, or a word at a time as a model writes it
            update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': piece}})
            time.sleep(pause)
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
    elif elicit == 'complete-first':  # the page done with before its question is asked, as a sign-in done at once
        send({'jsonrpc': '2.0', 'method': 'elicitation/complete', 'params': {'elicitationId': 'e3'}})
        log({'elicited': request(955, 'elicitation/create', {
            'sessionId': SESSION, 'mode': 'url', 'elicitationId': 'e3', 'message': 'Sign in to the server',
            'url': 'https://auth.example.com/login?state=z'})})
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
        again = os.environ.get('FAKE_ACP_ASK_AGAIN')
        while again and not os.path.exists(again) and not CANCELLED.wait(0.05):
            pass
        if again and not CANCELLED.is_set():  # a later request of the same session, once its file exists
            log({'permission_again': ask(901, {'sessionId': SESSION,
                                               'toolCall': {'toolCallId': 't3', 'title': 'Write more.txt',
                                                            'kind': 'edit', 'status': 'pending'},
                                               'options': [{'optionId': 'allow', 'name': 'Allow once',
                                                            'kind': 'allow_once'},
                                                           {'optionId': 'reject', 'name': 'Reject',
                                                            'kind': 'reject_once'}]})})
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


def mascot_turn(prompt_id, text):
    """The person's message, answered as their mascot: the bubble, a walk and a wave through the web module's verbs."""
    asked = ' '.join(text.split())[:60]
    log({'mascot_say': tool('m-say', 'Say it in the bubble', ['web', 'say', f'On it: {asked}'])})
    if os.environ.get('FAKE_ACP_MASCOT_GO'):
        log({'mascot_go': tool('m-go', 'Walk the mascot there', ['web', 'go', os.environ['FAKE_ACP_MASCOT_GO']])})
    log({'mascot_emote': tool('m-emote', 'Wave', ['web', 'emote', 'wave'])})
    if os.environ.get('FAKE_ACP_MASCOT_GO'):  # and what it sees there, and a picture from its eyes
        log({'mascot_see': tool('m-see', 'See', ['web', 'see', '--json'])[:2000]})
        log({'mascot_look': tool('m-look', 'Look', ['web', 'look', '--json'])[:2000]})
    script = Path(os.environ.get('FAKE_ACP_MASCOT_SCRIPT') or '')
    if script.is_file():  # each line a metaform command to run, its words as a JSON list, a pause in seconds alone
        for at, line in enumerate(script.read_text(encoding='utf-8').splitlines()):
            words = json.loads(line) if line.strip() else []
            if isinstance(words, (int, float)):
                CANCELLED.wait(words)
            elif words:
                log({'mascot_script': words, 'printed': tool(f'm-script-{at}', ' '.join(words), [*words, '--json'])[:400]})
    update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': f'The fake answers: {asked}'}})
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
    if number == 1 and COMPACTION[0]:  # the agent compacts its context as its first turn ends, ACP's RFD
        for status in [one for one in os.environ.get('FAKE_ACP_COMPACT', '').split(',') if one]:
            update({'sessionUpdate': 'compaction_update', 'status': status})
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
            COMPACTION[0] = message['params'].get('clientCapabilities', {}).get('session', {}).get('compaction') \
                is not None
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
                                                   **({'promptCapabilities': {
                                                       kind: True for kind in ('audio', 'image')
                                                       if os.environ.get(f'FAKE_ACP_{kind.upper()}') == '1'}}
                                                      if os.environ.get('FAKE_ACP_AUDIO') == '1'
                                                      or os.environ.get('FAKE_ACP_IMAGE') == '1' else {}),
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
            STEERED.set()
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'outcome': outcome}})
        elif method == 'session/new':
            if os.environ.get('FAKE_ACP_START_FAIL') == '1':
                send({'jsonrpc': '2.0', 'id': ident, 'error': {
                    'code': -32603, 'message': 'fixture startup failure'}})
                continue
            with WRITING, open(LOG, encoding='utf-8') as handle:
                count = sum(json.loads(line).get('message', {}).get('method') == 'session/new' for line in handle)
            SESSION = f'fake-session-{count}'
            answer = {'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': SESSION, **made()}}
            if os.environ.get('FAKE_ACP_ELICIT') == 'setup':  # a sign-in asked before the session is made
                threading.Thread(target=setup, args=(ident, answer), daemon=True).start()
            elif os.environ.get('FAKE_ACP_INFO') == '1':  # the answer and an update of its session, in one write
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
            if RICH or os.environ.get('FAKE_ACP_CLEAR') == '1':  # FAKE_ACP_CLEAR=1: a /clear of its own
                update({'sessionUpdate': 'available_commands_update', 'availableCommands': [
                    *([{'name': 'review', 'description': 'Review the changes', 'input': {'hint': 'what to review'}}]
                      if RICH else []),
                    *([{'name': 'clear', 'description': "The agent's own clear"}]
                      if os.environ.get('FAKE_ACP_CLEAR') == '1' else [])]})
        elif method == 'session/load' and os.environ.get('FAKE_ACP_LOAD') == '1':
            SESSION = message['params']['sessionId']
            if os.environ.get('FAKE_ACP_MISSING_ROLLOUT') == '1':
                send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32603, 'message': 'Internal error',
                      'data': {'details': f'no rollout found for thread id {SESSION}'}}})
                continue
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
            confirm_context(message['params'])
            PROMPTS[0] += 1
            v2_turn(ident, message['params'], PROMPTS[0])
        elif method == 'session/prompt':
            confirm_context(message['params'])
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
            elif os.environ.get('FAKE_ACP_MASCOT') == '1':
                said = ' '.join(block.get('text', '') for block in message['params'].get('prompt', []))
                threading.Thread(target=turn_of, args=(mascot_turn, ident, said), daemon=True).start()
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


def setup(ident, answer):
    """A question scoped to session/new's request, asked before it is answered: session/new is answered half a second
    later whether or not the question was, and the question's answer logged once it comes."""
    event = threading.Event()
    ANSWERS[956] = event
    send({'jsonrpc': '2.0', 'id': 956, 'method': 'elicitation/create', 'params': {
        'requestId': ident, 'mode': 'url', 'elicitationId': 'e-setup', 'message': 'Sign in to the server',
        'url': 'https://auth.example.com/login?state=s'}})
    event.wait(0.5)
    send(answer)
    event.wait()
    log({'elicited': RESULTS.pop(956)})


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
STEERED = threading.Event()  # a steer reached the turn, FAKE_ACP_INTAKE waits for it
NOTICES = [False]  # the client advertised ACP's session notices
COMPACTION = [False]  # the client advertised ACP's session compaction
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
