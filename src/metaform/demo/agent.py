"""The demo's agent, `metaform demo`: an ACP agent over standard input and output, newline-delimited JSON-RPC, the
standard library only and no model, promoted from dispatch's test fake. It calls no network service and spends
nothing.

Started by dispatch on one of the demo map's tickets, its first turn plays that ticket's script from script.json as a
real agent works: it says what it is doing a sentence at a time, which the map shows in its figure's speech bubble;
it reads the sample project's files as tool calls that name them, which the map draws as its requests flowing to the
parts those files belong to; and it records its steps, a memory and the ticket's close with the real metaform command
line. A later turn, such as dispatch's turn to record what it learned once the ticket is done, is answered in a
line, since its script recorded that already. Started as the person's system agent, it is the mascot: once the page has given it a body it greets the person
and waves, and every little while says a line about what is on the map, until it is stopped."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, cast

SCRIPT = Path(__file__).with_name('script.json')
OUT = sys.stdout.buffer
WRITING = threading.Lock()
CANCELLED = threading.Event()
GREETING = threading.Event()  # the mascot's greetings have begun
PLAYED = threading.Event()  # a worker's script has been played; it is played once
SESSION = ['demo-session']
WORD = 0.09  # seconds between the words of a sentence, as a model writes it
CALLS = [0]  # the tool calls made, for each one's id


def send(message: dict[str, Any]) -> None:
    with WRITING:
        OUT.write(json.dumps(message).encode('utf-8') + b'\n')
        OUT.flush()


def update(body: dict[str, Any]) -> None:
    send({'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': SESSION[0], 'update': body}})


def metaform(*words: str) -> subprocess.CompletedProcess[str]:
    """The real metaform command line, run as this agent: its home and its ticket come from dispatch's environment."""
    return subprocess.run([sys.executable, '-m', 'metaform', *words], capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL)


def pause(seconds: float) -> bool:
    """Wait, and say whether the turn goes on: False once it is cancelled."""
    return not CANCELLED.wait(seconds)


def say(text: str) -> bool:
    """A sentence, a word at a time, after a moment's thought, so it is a line of its own in the thread."""
    update({'sessionUpdate': 'agent_thought_chunk', 'content': {'type': 'text', 'text': 'Thinking it over.'}})
    for at, word in enumerate(text.split(' ')):
        update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': (' ' if at else '') + word}})
        if not pause(WORD):
            return False
    return pause(2.5)


def call(title: str, kind: str, body: dict[str, Any], output: str) -> None:
    """One tool call, pending and then completed with what it gave back."""
    CALLS[0] += 1
    ident = f'demo-{CALLS[0]}'
    update({'sessionUpdate': 'tool_call', 'toolCallId': ident, 'title': title, 'kind': kind, 'status': 'in_progress',
            **body})
    update({'sessionUpdate': 'tool_call_update', 'toolCallId': ident, 'status': 'completed', 'rawOutput': output,
            'content': [{'type': 'content', 'content': {'type': 'text', 'text': output}}]})


def read(path: str, line: int | None) -> bool:
    """Read a file of the project, named by its place, so the map draws the request reaching the part it belongs to."""
    full = Path.cwd() / path
    try:
        text = full.read_text(encoding='utf-8')
    except OSError:
        text = f'{path} does not exist yet.'
    call(f'Read {path}', 'read', {'locations': [{'path': str(full), **({'line': line} if line else {})}],
                                  'rawInput': {'path': str(full)}}, text)
    return pause(2.0)


def run(words: list[str]) -> bool:
    """Run a short local command, such as Python checking an expression, and show what it printed."""
    command = [sys.executable if word == 'python' else word for word in words]
    printed = subprocess.run(command, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    call(' '.join(words), 'execute', {'rawInput': {'command': words}}, (printed.stdout + printed.stderr).strip())
    return pause(2.0)


def recorded(title: str, words: list[str]) -> bool:
    """A record on the map through the real command line, shown as the tool call it is."""
    done = metaform(*words)
    call(title, 'other', {'rawInput': {'command': ['metaform', *words]}}, (done.stdout + done.stderr).strip()[:400])
    return pause(1.5)


def act(entry: dict[str, Any], work: str, address: str) -> bool:
    """One entry of a ticket's script; False once the turn is cancelled."""
    if 'say' in entry:
        return say(str(entry['say']))
    if 'read' in entry:
        return read(str(entry['read']), cast(int | None, entry.get('line')))
    if 'run' in entry:
        return run([str(word) for word in cast(list[Any], entry['run'])])
    if 'plan' in entry:
        return recorded('Plan the ticket', ['map', 'work', 'op=plan', f'id={work}', f'steps={entry["plan"]}'])
    if 'step' in entry:
        return recorded('Record a step', ['map', 'work', 'op=step', f'id={work}', f'said={entry["step"]}'])
    if 'remember' in entry:
        memory = cast(dict[str, Any], entry['remember'])
        entity = [{'name': memory['name'], 'entityType': 'fact', 'observations': memory['observations'],
                   'why': 'The next agent here needs it.'}]
        return recorded('Record a memory here', ['memory', 'create_entities', json.dumps(entity),
                                                 f'node=element:{address}'])
    if 'done' in entry:
        closing = cast(dict[str, Any], entry['done'])
        return recorded('Close the ticket', ['map', 'work', 'op=done', f'id={work}',
                                             f'resolution={closing["resolution"]}', f'why={closing["why"]}'])
    return pause(float(entry.get('wait', 1)))


def ticket_of(text: str) -> str:
    """The ticket this agent was started on: its runner names it, else the hand-off does."""
    named = re.search(r'\b([0-9a-f]{32})\b', text)
    return os.environ.get('METAFORM_WORK') or (named.group(1) if named else '')


def worker_turn(prompt_id: int, text: str) -> None:
    """A ticket's script, played from its first entry to its last, or until the turn is cancelled."""
    work = ticket_of(text)
    read_back = metaform('map', 'work', f'id={work}', '--json')
    call('Read the ticket', 'read', {'rawInput': {'id': work}}, read_back.stdout[:400])
    try:
        found = cast(dict[str, Any], json.loads(read_back.stdout))
    except ValueError:
        found = {}
    address = str(found.get('address') or '')
    tickets = cast(list[dict[str, Any]], json.loads(SCRIPT.read_text(encoding='utf-8'))['tickets'])
    script = next((one['script'] for one in tickets if one['address'] == address), [{'say': 'Nothing to do here.'}])
    for entry in cast(list[dict[str, Any]], script):
        if not act(entry, work, address):
            break
    reason = 'cancelled' if CANCELLED.is_set() else 'end_turn'
    send({'jsonrpc': '2.0', 'id': prompt_id, 'result': {'stopReason': reason}})


def mascot() -> None:
    """The person's mascot: once a page shows it with a body it greets the person and waves, then every 40 s, its
    pace, says the next line about the map, until the process is stopped. While no page shows it, it waits for the
    web GUI to say one may: a page of the project opening (map.changed naming kinds pages, with a page count), or a
    page drawing this session, which gives the mascot its body (kinds session, naming it). Nothing tries on a timer."""
    from metaform import events
    held = cast(dict[str, Any], json.loads(SCRIPT.read_text(encoding='utf-8')))
    lines, project = cast(list[str], held['mascot']), str(held['project'])
    session = os.environ.get('METAFORM_SESSION') or ''
    shown = threading.Event()  # a page may show the mascot now

    def heard(payload: dict[str, Any]) -> None:
        if payload.get('project') != project:
            return
        kinds: Any = payload.get('kinds')
        named: Any = payload.get('session_ids')
        kinds = cast(list[Any], kinds) if isinstance(kinds, list) else []
        if 'pages' in kinds and int(payload.get('pages') or 0) > 0 or \
                'session' in kinds and isinstance(named, list) and session in cast(list[Any], named):
            shown.set()
    at = 0
    with events.listen('demo', heard):
        while True:
            shown.clear()  # before the try, so a page that opens during it is heard
            if metaform('web', 'say', lines[at % len(lines)]).returncode == 0:
                if at == 0:
                    metaform('web', 'emote', 'wave')
                at += 1
                threading.Event().wait(40)  # pacing: a line every 40 s
            else:  # no page open yet, or no body given yet
                shown.wait()


def main() -> None:
    system = os.environ.get('METAFORM_TASK_NAME') == 'user_agent'  # the person's own agent, the mascot
    for line in sys.stdin.buffer:
        message = cast(dict[str, Any], json.loads(line))
        method, ident = message.get('method'), message.get('id')
        params = cast(dict[str, Any], message.get('params') or {})
        if method is None:
            continue  # an answer to a request; this agent asks none
        if method == 'initialize':
            send({'jsonrpc': '2.0', 'id': ident, 'result': {
                'protocolVersion': 1, 'authMethods': [], 'agentCapabilities': {'loadSession': False},
                'agentInfo': {'name': 'metaform-demo', 'title': 'Metaform demo agent', 'version': '1'}}})
        elif method == 'session/new':
            SESSION[0] = f'demo-{os.getpid()}'
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': SESSION[0]}})
        elif method == 'session/prompt' and system:  # its first turn starts the mascot; a later one is answered
            if not GREETING.is_set():
                GREETING.set()
                threading.Thread(target=mascot, daemon=True).start()
            update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': (
                "Hello. I'm the demo's mascot, scripted, with no AI behind me. To talk for real, run metaform start in "
                'your own project: it connects Claude Code there.')}})
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn'}})
        elif method == 'session/prompt' and PLAYED.is_set():  # dispatch's turn to record what it learned, once done
            update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': (
                'What I learned is recorded at this node already.')}})
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn'}})
        elif method == 'session/prompt':  # its first turn plays the ticket's script, once
            PLAYED.set()
            CANCELLED.clear()
            text = ' '.join(str(block.get('text', '')) for block in cast(list[dict[str, Any]], params.get('prompt', [])))
            threading.Thread(target=worker_turn, args=(ident, text), daemon=True).start()
        elif method == 'session/cancel':
            CANCELLED.set()
        elif ident is not None:
            send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})


if __name__ == '__main__':
    main()
