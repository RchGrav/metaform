"""A fake ACP agent for dispatch's tests, BASE-052: newline-delimited JSON-RPC over standard input and output, the
standard library only, no model. Every message it reads is logged as one JSON line to FAKE_ACP_LOG, with whether the
line ended in a carriage return.

FAKE_ACP_MODE says what its first turn does after two message chunks and one tool call:
  ask   asks permission for a second tool call, logs the outcome, and ends the turn
  done  closes its ticket, FAKE_ACP_WORK, with the real metaform command line, and ends the turn
  hold  starts a grandchild that sleeps, logs its pid, and ends the turn only when the turn is cancelled
A later prompt is logged and ends at once.
"""
import json
import os
import subprocess
import sys
import threading

LOG = os.environ['FAKE_ACP_LOG']
MODE = os.environ.get('FAKE_ACP_MODE', 'ask')
SESSION = 'fake-session-1'
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


def first_turn(prompt_id):
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
                            'toolCall': {'toolCallId': 't2', 'title': 'Write notes.txt', 'kind': 'edit',
                                         'status': 'pending'},
                            'options': [{'optionId': 'allow', 'name': 'Allow once', 'kind': 'allow_once'},
                                        {'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'}]})
        log({'permission': outcome})
    if MODE == 'done':
        finished = subprocess.run([sys.executable, '-m', 'metaform', 'map', 'work', 'op=done',
                                   f'id={os.environ["FAKE_ACP_WORK"]}', 'resolution=fake'],
                                  capture_output=True, text=True, check=False)
        log({'done': finished.returncode, 'err': finished.stderr})
    if MODE == 'hold':
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])
        log({'grandchild': child.pid})
        CANCELLED.wait()
        send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'cancelled'}})
        return
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': 'end_turn'}})


def main():
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
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': SESSION}})
        elif method == 'session/prompt':
            PROMPTS[0] += 1
            if PROMPTS[0] == 1:
                threading.Thread(target=first_turn, args=(ident,), daemon=True).start()
            else:
                send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn'}})
        elif method == 'session/cancel':
            CANCELLED.set()
        else:
            send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})


main()
