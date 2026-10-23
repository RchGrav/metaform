"""A fake ACP agent for the roundtable's checks, cut down from Metaform's dispatch/tests/fake_agent.py: newline-delimited
JSON-RPC over standard input and output, the standard library only, no model. Every message it reads is logged as one
JSON line to FAKE_ACP_LOG, with its pid and whether an API key reached it.

It offers modes (default, acceptEdits, plan, as Claude Code does) and a model option (haiku, sonnet, opus), takes
session/set_mode and session/set_config_option, offers session/load, and answers each prompt with one message: the
model it runs and how long the prompt was, so every seat's reply differs. Its first turn first asks permission to
write a file and logs the answer. FAKE_ACP_LONG=1 makes its first reply run over 512 characters. A prompt that holds
"VETO-ME" is answered with a reply holding "veto", which the stub Jev turns down. A prompt that starts with "The
roundtable has ended" is answered with a Markdown report. A Roundtable 2 ranking is answered with every id it lists,
in an order of the model's own, and a request to explain a top or bottom three with a sentence.

FAKE_ACP_MCP=1 makes it declare MCP over http. Its first turn of a session given MCP servers then calls a tool of the
first, as Codex reports one (a tool call titled `mcp.<server>.<tool>`, then a permission request holding only its id),
and one of a server it was not given, and logs both answers.
FAKE_ACP_MODELS replaces its model choices with a JSON list of {value, name} entries.
"""
import json
import os
import re
import sys
import threading

LOG = os.environ['FAKE_ACP_LOG']
WRITING = threading.Lock()
ANSWERS = {}
RESULTS = {}
STATE = {'session': None, 'model': 'sonnet', 'mode': 'default', 'prompts': 0, 'servers': []}
MODELS = json.loads(os.environ['FAKE_ACP_MODELS']) if os.environ.get('FAKE_ACP_MODELS') else [
    {'value': 'haiku', 'name': 'Haiku 5.5'}, {'value': 'sonnet', 'name': 'Sonnet 5.5'},
    {'value': 'opus', 'name': 'Opus 5.5'}]


def log(entry):
    with WRITING, open(LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps({'pid': os.getpid(), **entry}) + '\n')


def send(message):
    with WRITING:
        sys.stdout.buffer.write(json.dumps(message).encode('utf-8') + b'\n')
        sys.stdout.buffer.flush()


def update(body):
    send({'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': STATE['session'], 'update': body}})


def request(request_id, method, params):
    event = threading.Event()
    ANSWERS[request_id] = event
    send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    event.wait()
    return RESULTS.pop(request_id)


def options():
    return [{'id': 'model', 'name': 'Model', 'type': 'select', 'category': 'model', 'currentValue': STATE['model'],
             'options': MODELS}]


def modes():
    return {'currentModeId': STATE['mode'], 'availableModes': [
        {'id': 'default', 'name': 'Default'}, {'id': 'acceptEdits', 'name': 'Accept edits'},
        {'id': 'plan', 'name': 'Plan'}]}


def call_mcp(request_id, call_id, server):
    """One MCP tool call as Codex makes it: the call reported with its server, then permission asked by its id alone."""
    update({'sessionUpdate': 'tool_call', 'toolCallId': call_id, 'title': f'mcp.{server}.see', 'kind': 'execute',
            'status': 'pending', 'rawInput': {'server': server, 'tool': 'see', 'arguments': {}}})
    return request(request_id, 'session/request_permission', {
        'sessionId': STATE['session'], 'toolCall': {'toolCallId': call_id, 'kind': 'execute'},
        'options': [{'optionId': 'approved', 'name': 'Allow', 'kind': 'allow_once'},
                    {'optionId': 'abort', 'name': 'Deny', 'kind': 'reject_once'}]})


def staged(text):
    """A Roundtable 2 stage's answer, or None for a discussion turn."""
    if '# Topic synthesis' in text:
        return 'I1. Evidence: inspect source.\nI2. Disagreement: preserve alternatives.'
    if '# Host summary' in text:
        return f'{STATE["model"]} summarises the evidence and unresolved disagreement.'
    if '# Shared continuation' in text:
        return 'Keep original instructions. Preserve evidence, decisions, disagreement and open questions.'
    if '# Carry-forward note' in text:
        return f'{STATE["model"]} retains its evidence and disagreement. Question remains open.'
    if '# Rank collected ideas' in text or 'could not be read as every idea' in text:
        ids = sorted(set(re.findall(r'\bI(\d+)\b', text)), key=int)
        turn = len(STATE['model']) % max(len(ids), 1)
        return ', '.join(f'I{one}' for one in ids[turn:] + ids[:turn])
    if '# Explain your top three' in text:
        return f'The fake {STATE["model"]} ranked its top three first for their substance.'
    if '# Explain your bottom three' in text:
        return f'The fake {STATE["model"]} ranked its bottom three last for their cost.'
    return None


def turn(ident, text):
    STATE['prompts'] += 1
    if STATE['prompts'] == 1 and STATE['servers']:
        log({'mcp_permission': call_mcp(901, 'm1', STATE['servers'][0]['name'])})
        log({'mcp_other': call_mcp(902, 'm2', 'elsewhere')})
    if STATE['prompts'] == 1:
        outcome = request(900, 'session/request_permission', {
            'sessionId': STATE['session'],
            'toolCall': {'toolCallId': 'w1', 'title': 'Write notes.txt', 'kind': 'edit', 'status': 'pending'},
            'options': [{'optionId': 'allow', 'name': 'Allow once', 'kind': 'allow_once'},
                        {'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'}]})
        log({'permission': outcome})
        update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Let me look first.'}})
        update({'sessionUpdate': 'tool_call', 'toolCallId': 'r1', 'title': 'Read README', 'kind': 'read',
                'status': 'completed'})
    if text.startswith('The roundtable has ended'):
        reply = f'# Report\n\nThe fake {STATE["model"]} read {text.count(chr(10))} lines of the record.'
    elif staged(text) is not None:
        reply = staged(text)
    elif STATE['prompts'] > int(os.environ.get('FAKE_ACP_PASS_AFTER', '999999')):
        reply = 'PASS'
    elif os.environ.get('FAKE_ACP_LONG') == '1' and STATE['prompts'] == 1:
        reply = 'long ' * 120
    else:
        veto = ' I only say veto.' if 'VETO-ME' in text else ''
        reply = f'{STATE["model"]} on turn {STATE["prompts"]}: the prompt was {len(text)} characters.{veto}'
    for part in (reply[:len(reply) // 2], reply[len(reply) // 2:]):
        update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': part}})
    send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn', 'usage': {
        'totalTokens': len(text) // 4 + 20, 'inputTokens': len(text) // 4, 'outputTokens': 20,
        'cachedReadTokens': max(len(text) // 4 - 50, 0) if STATE['prompts'] > 1 else 0, 'cachedWriteTokens': 0}}})


def main():
    for line in sys.stdin.buffer:
        message = json.loads(line)
        method, ident = message.get('method'), message.get('id')
        log({'message': message, 'api_key': bool(os.environ.get('ANTHROPIC_API_KEY'))})
        if method is None:
            if ident in ANSWERS:
                RESULTS[ident] = message.get('result', {'error': message.get('error')})
                ANSWERS.pop(ident).set()
            continue
        if method == 'initialize':
            send({'jsonrpc': '2.0', 'id': ident, 'result': {
                'protocolVersion': 1, 'agentCapabilities': {
                    'loadSession': True, **({'mcpCapabilities': {'http': True}}
                                            if os.environ.get('FAKE_ACP_MCP') == '1' else {})},
                'agentInfo': {'name': 'fake-agent', 'version': '1.0'}}})
        elif method == 'session/new':
            STATE['session'] = f'fake-{os.getpid()}'
            STATE['servers'] = message['params'].get('mcpServers') or []
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': STATE['session'], 'modes': modes(),
                                                            'configOptions': options()}})
        elif method == 'session/load':
            STATE['session'] = message['params']['sessionId']
            update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': 'Replayed'}})
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'modes': modes(), 'configOptions': options()}})
        elif method == 'session/set_mode':
            STATE['mode'] = message['params']['modeId']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {}})
        elif method == 'session/set_config_option':
            STATE['model'] = message['params']['value']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'configOptions': options()}})
        elif method == 'session/prompt':
            text = ' '.join(block.get('text', '') for block in message['params'].get('prompt', []))
            threading.Thread(target=turn, args=(ident, text), daemon=True).start()
        elif method == 'session/cancel':
            pass
        else:
            send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})


log({'started': True, 'argv': sys.argv})
main()
