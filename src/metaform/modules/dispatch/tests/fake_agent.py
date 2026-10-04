"""A fake ACP agent for dispatch's tests, BASE-052: newline-delimited JSON-RPC over standard input and output, the
standard library only, no model. Every message it reads is logged as one JSON line to FAKE_ACP_LOG, with whether the
line ended in a carriage return.

FAKE_ACP_MODE says what its first turn does after two message chunks and one tool call:
  ask   asks permission for a second tool call, logs the outcome, and ends the turn
  done  closes the ticket its prompt names, or else FAKE_ACP_WORK, with the real metaform command line, logs the
        ticket, and ends the turn
  hold  starts a grandchild that sleeps, logs its pid, and ends the turn only when the turn is cancelled
  question  asks a question at FAKE_ACP_ASK_AT with the real metaform command line, as a tool call whose output is
        what the command printed, logs what it printed, and ends the turn; its second prompt lists the questions the
        same way, logs the list and ends
A later prompt is logged and ends at once. Each process's session id counts the sessions made in the log before it,
fake-session-1 for the first, so the agents a runner starts one after another have sessions of their own.
"""
import json
import os
import re
import subprocess
import sys
import threading

LOG = os.environ['FAKE_ACP_LOG']
MODE = os.environ.get('FAKE_ACP_MODE', 'ask')
SESSION = 'fake-session-1'  # until session/new names it
OUT = sys.stdout.buffer
WRITING = threading.Lock()
ANSWERS: dict[int, threading.Event] = {}
RESULTS: dict[int, object] = {}
CANCELLED = threading.Event()
PROMPTS = [0]


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
    event = threading.Event()
    ANSWERS[request_id] = event
    send({'jsonrpc': '2.0', 'id': request_id, 'method': 'session/request_permission', 'params': params})
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
    if MODE == 'ask':
        outcome = ask(900, {'sessionId': SESSION,
                            'toolCall': {'toolCallId': 't2', 'title': os.environ.get('FAKE_ACP_ASK_TITLE', 'Write notes.txt'),
                                         'kind': os.environ.get('FAKE_ACP_ASK_KIND', 'edit'),
                                         'status': 'pending'},
                            'options': [{'optionId': 'allow', 'name': 'Allow once', 'kind': 'allow_once'},
                                        {'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'}]})
        log({'permission': outcome})
    if MODE == 'done':
        named = re.search(r'map work id=([0-9a-f]{32})', text)
        work = named.group(1) if named else os.environ['FAKE_ACP_WORK']
        finished = subprocess.run([sys.executable, '-m', 'metaform', 'map', 'work', 'op=done', f'id={work}',
                                   'resolution=fake'], capture_output=True, text=True, check=False)
        log({'done': finished.returncode, 'err': finished.stderr, 'work': work})
    if MODE == 'question':
        log({'asked': tool('t3', 'Ask a question', ['map', 'ask', os.environ['FAKE_ACP_ASK_AT'], 'Is the store kept?',
                                                    'by=fake agent'])})
        if os.environ.get('FAKE_ACP_QUESTION_HOLD') == '1':
            CANCELLED.wait()
            send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled'}})
            return
    if MODE == 'hold':
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])
        log({'grandchild': child.pid})
        CANCELLED.wait()
        send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled'}})
        return
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'end_turn'}})


def listing_turn(prompt_id):
    log({'listed': tool('t4', 'List the questions', ['map', 'messages', 'kind=question'])})
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'end_turn'}})


def held_turn(prompt_id):
    CANCELLED.wait()
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled'}})


def main():
    global SESSION
    for line in sys.stdin.buffer:
        message = json.loads(line)
        log({'crlf': line.endswith(b'\r\n'), 'message': message, 'secret': os.environ.get('FAKE_SECRET'),
             'argv': sys.argv})
        method, ident = message.get('method'), message.get('id')
        if method is None:
            if ident in ANSWERS:
                RESULTS[ident] = message.get('result')
                ANSWERS.pop(ident).set()
            continue
        if method == 'initialize':
            send({'jsonrpc': '2.0', 'id': ident,
                  'result': {'protocolVersion': 1, 'agentCapabilities': {'loadSession': False}, 'authMethods': []}})
        elif method == 'session/new':
            with WRITING, open(LOG, encoding='utf-8') as handle:
                made = sum(json.loads(line).get('message', {}).get('method') == 'session/new' for line in handle)
            SESSION = f'fake-session-{made}'
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': SESSION}})
        elif method == 'session/prompt':
            PROMPTS[0] += 1
            if PROMPTS[0] == 1:
                said = ' '.join(block.get('text', '') for block in message['params'].get('prompt', []))
                threading.Thread(target=first_turn, args=(ident, said), daemon=True).start()
            elif PROMPTS[0] == 2 and MODE == 'question':
                threading.Thread(target=listing_turn, args=(ident,), daemon=True).start()
            elif os.environ.get('FAKE_ACP_HOLD_LATER') == '1':
                threading.Thread(target=held_turn, args=(ident,), daemon=True).start()
            else:
                send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn'}})
        elif method == 'session/cancel':
            CANCELLED.set()
        else:
            send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})


log({'pid': os.getpid()})
main()
