"""A fake ACP agent for the roundtable's checks, cut down from Metaform's dispatch/tests/fake_agent.py: newline-delimited
JSON-RPC over standard input and output, the standard library only, no model. Every message it reads is logged as one
JSON line to FAKE_ACP_LOG, with its pid and whether an API key reached it.

It negotiates ACP v2 or v1, offers mode and model configuration, and supports session/resume. V2 prompts
acknowledge insertion and complete through idle states. V1 prompts complete through their response. FAKE_ACP_PERMISSION=1 makes
its first turn ask permission to write a file and log the answer. FAKE_ACP_LONG=1 makes its first reply exceed 512
characters. A prompt that holds
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
STATE = {'session': None, 'model': 'sonnet', 'mode': 'default', 'prompts': 0, 'servers': [],
         'protocol': 2, 'prompt_id': None, 'cancelled': False, 'blocked': None}
MODELS = json.loads(os.environ['FAKE_ACP_MODELS']) if os.environ.get('FAKE_ACP_MODELS') else [
    {'value': 'haiku', 'name': 'Haiku 5.5'}, {'value': 'sonnet', 'name': 'Sonnet 5.5'},
    {'value': 'opus', 'name': 'Opus 5.5'}]
MODES = json.loads(os.environ['FAKE_ACP_MODES']) if os.environ.get('FAKE_ACP_MODES') else [
    {'value': 'default', 'name': 'Default'}, {'value': 'plan', 'name': 'Plan'}]


def log(entry):
    with WRITING, open(LOG, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps({'pid': os.getpid(), **entry}) + '\n')


def send(message):
    with WRITING:
        sys.stdout.buffer.write(json.dumps(message).encode('utf-8') + b'\n')
        sys.stdout.buffer.flush()


def update(body):
    if STATE['protocol'] == 1 and body.get('sessionUpdate') in ('state_update', 'user_message'):
        return
    send({'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': STATE['session'], 'update': body}})


def request(request_id, method, params):
    event = threading.Event()
    ANSWERS[request_id] = event
    send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    event.wait()
    return RESULTS.pop(request_id, {'outcome': {'outcome': 'cancelled'}})


def options():
    key = 'configId' if STATE['protocol'] == 2 else 'id'
    found = [{key: 'model', 'name': 'Model', 'type': 'select', 'category': 'model',
              'currentValue': STATE['model'], 'options': MODELS}]
    if not (STATE['protocol'] == 1 and os.environ.get('FAKE_ACP_LEGACY_MODES') == '1'):
        found.append({key: 'mode', 'name': 'Mode', 'type': 'select', 'category': 'mode',
                      'currentValue': STATE['mode'], 'options': MODES})
    return found


def modes():
    return {'currentModeId': STATE['mode'], 'availableModes': [
        {'id': one['value'], 'name': one['name']} for one in MODES]}


def configured():
    response = {'configOptions': options()}
    if STATE['protocol'] == 1 and os.environ.get('FAKE_ACP_LEGACY_MODES') == '1':
        response['modes'] = modes()
    return response


def call_mcp(request_id, call_id, server):
    """One MCP tool call as Codex makes it: the call reported with its server, then permission asked by its id alone."""
    update({'sessionUpdate': 'tool_call_update' if STATE['protocol'] == 2 else 'tool_call', 'toolCallId': call_id, 'title': f'mcp.{server}.see', 'kind': 'execute',
            'status': 'pending', 'rawInput': {'server': server, 'tool': 'see', 'arguments': {}}})
    update({'sessionUpdate': 'state_update', 'state': 'requires_action'})
    params = {'sessionId': STATE['session'],
              'options': [{'optionId': 'approved', 'name': 'Allow', 'kind': 'allow_once'},
                          {'optionId': 'abort', 'name': 'Deny', 'kind': 'reject_once'}]}
    if STATE['protocol'] == 2:
        params.update(title=f'Call {server}', subject={'type': 'tool_call', 'toolCall': {'toolCallId': call_id}})
    else:
        params['toolCall'] = {'toolCallId': call_id, 'title': f'Call {server}', 'kind': 'execute'}
    answer = request(request_id, 'session/request_permission', params)
    update({'sessionUpdate': 'state_update', 'state': 'running'})
    return answer


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
    STATE['prompt_id'], STATE['cancelled'] = ident, False
    user_id = f'user-{STATE["prompts"]}'
    update({'sessionUpdate': 'user_message', 'messageId': user_id,
            'content': [{'type': 'text', 'text': text}]})
    if STATE['protocol'] == 2:
        send({'jsonrpc': '2.0', 'id': ident, 'result': {'messageId': user_id}})
    update({'sessionUpdate': 'state_update', 'state': 'running'})
    if STATE['prompts'] == 1 and STATE['servers']:
        log({'mcp_permission': call_mcp(901, 'm1', STATE['servers'][0]['name'])})
        log({'mcp_other': call_mcp(902, 'm2', 'elsewhere')})
    if STATE['prompts'] == 1 and os.environ.get('FAKE_ACP_PERMISSION') == '1':
        update({'sessionUpdate': 'tool_call_update' if STATE['protocol'] == 2 else 'tool_call',
                'toolCallId': 'w1', 'title': 'Write notes.txt',
                'kind': os.environ.get('FAKE_ACP_PERMISSION_KIND', 'edit'), 'status': 'pending'})
        update({'sessionUpdate': 'state_update', 'state': 'requires_action'})
        params = {'sessionId': STATE['session'],
                  'options': [{'optionId': 'allow', 'name': 'Allow once', 'kind': 'allow_once'},
                              {'optionId': 'reject', 'name': 'Reject', 'kind': 'reject_once'}]}
        if STATE['protocol'] == 2:
            params.update(title='Write notes.txt', subject={'type': 'tool_call', 'toolCall': {'toolCallId': 'w1'}})
        else:
            params['toolCall'] = {'toolCallId': 'w1', 'title': 'Write notes.txt'}
        outcome = request(900, 'session/request_permission', params)
        log({'permission': outcome})
        update({'sessionUpdate': 'state_update', 'state': 'running'})
        update({'sessionUpdate': 'agent_message_chunk', 'messageId': f'pre-{STATE["prompts"]}',
                'content': {'type': 'text', 'text': 'Let me look first.'}})
        update({'sessionUpdate': 'tool_call_update', 'toolCallId': 'r1', 'title': 'Read README', 'kind': 'read',
                'status': 'completed'})
    if os.environ.get('FAKE_ACP_BLOCK') == '1':
        STATE['blocked'] = threading.Event()
        update({'sessionUpdate': 'tool_call_update' if STATE['protocol'] == 2 else 'tool_call',
                'toolCallId': 'blocked', 'title': 'Long task', 'kind': 'execute', 'status': 'in_progress'})
        STATE['blocked'].wait()
    if STATE['cancelled']:
        return
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
        update({'sessionUpdate': 'agent_message_chunk', 'messageId': f'reply-{STATE["prompts"]}',
                'content': {'type': 'text', 'text': part}})
    usage = {'totalTokens': len(text) // 4 + 20, 'inputTokens': len(text) // 4, 'outputTokens': 20,
             'cachedReadTokens': max(len(text) // 4 - 50, 0) if STATE['prompts'] > 1 else 0, 'cachedWriteTokens': 0}
    if STATE['protocol'] == 2:
        update({'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': 'end_turn', 'usage': usage})
    else:
        send({'jsonrpc': '2.0', 'id': ident, 'result': {'stopReason': 'end_turn', 'usage': usage}})
    STATE['prompt_id'] = None



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
            requested = message['params']['protocolVersion']
            if os.environ.get('FAKE_ACP_INIT_ERROR') == '1':
                send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32000, 'message': 'Authentication required'}})
                continue
            if requested == 2 and os.environ.get('FAKE_ACP_UNSUPPORTED_V2') == '1':
                send({'jsonrpc': '2.0', 'id': ident, 'error': {
                    'code': -32022, 'message': 'Unsupported protocol version', 'data': {'requested': 2, 'supported': [1]}}})
                continue
            selected = min(requested, int(os.environ.get('FAKE_ACP_PROTOCOL', '2')))
            if os.environ.get('FAKE_ACP_PROTOCOL') == '3':
                selected = 3
            if requested == 1:
                selected = 1
            STATE['protocol'] = selected
            if selected == 1 or os.environ.get('FAKE_ACP_LEGACY_INITIALIZE') == '1':
                initialized = {'protocolVersion': selected, 'agentInfo': {'name': 'fake-agent', 'version': '1.0'},
                               'agentCapabilities': {'loadSession': True,
                                   'sessionCapabilities': {'resume': {}, 'close': {}},
                                   'mcpCapabilities': {'http': os.environ.get('FAKE_ACP_MCP') == '1'}}}
            else:
                initialized = {'protocolVersion': selected, 'capabilities': {'session': {
                    **({'mcp': {'http': {}}} if os.environ.get('FAKE_ACP_MCP') == '1' else {})}},
                    'info': {'name': 'fake-agent', 'version': '2.0'}}
            send({'jsonrpc': '2.0', 'id': ident, 'result': initialized})
        elif method == 'session/new':
            if os.environ.get('FAKE_ACP_SESSION_ERROR') == '1':
                send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32000, 'message': 'Authentication required'}})
                continue
            STATE['session'] = f'fake-{os.getpid()}'
            STATE['servers'] = message['params'].get('mcpServers') or []
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': STATE['session'], **configured()}})
        elif method == 'session/resume':
            STATE['session'] = message['params']['sessionId']
            update({'sessionUpdate': 'state_update', 'state': 'idle'})
            send({'jsonrpc': '2.0', 'id': ident, 'result': configured()})
        elif method == 'session/set_config_option':
            STATE[message['params']['configId']] = message['params']['value']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'configOptions': options()}})
        elif method == 'session/set_mode':
            STATE['mode'] = message['params']['modeId']
            send({'jsonrpc': '2.0', 'id': ident, 'result': {}})
        elif method == 'session/prompt':
            text = ' '.join(block.get('text', '') for block in message['params'].get('prompt', []))
            threading.Thread(target=turn, args=(ident, text), daemon=True).start()
        elif method == 'session/cancel':
            STATE['cancelled'] = True
            if STATE['blocked'] is not None:
                STATE['blocked'].set()
            if STATE['protocol'] == 1 and STATE['prompt_id'] is not None:
                send({'jsonrpc': '2.0', 'id': STATE['prompt_id'], 'result': {'stopReason': 'cancelled'}})
                STATE['prompt_id'] = None
            for event in list(ANSWERS.values()):
                event.set()
            update({'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': 'cancelled'})
        elif method == 'session/close':
            update({'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': 'cancelled'})
            send({'jsonrpc': '2.0', 'id': ident, 'result': {}})
        elif method == 'session/list':
            send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessions': []}})
        else:
            send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})


log({'started': True, 'argv': sys.argv})
main()
