"""The Roundtable 2 engine's own stub of OpenRouter and Jev, as its scripts/check.py has it (RchGrav/roundtable at
65359b2), carried here so the module's tests run the shipped engine with nothing paid for and nothing leaving the
machine: chat completions and Jev's decisions on the loopback. Its fake ACP agent is fake_agent.py beside this file.
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def unmarked(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The messages as the seat keeps them: a marked content list back to its plain text."""
    found = []
    for one in messages:
        content = one.get('content')
        if isinstance(content, list) and len(content) == 1 and content[0].get('cache_control'):
            one = {**one, 'content': content[0]['text']}
        found.append(one)
    return found


class Stub:
    """OpenRouter as the roundtable sees it: chat completions and Jev's decisions."""

    def __init__(self) -> None:
        self.chats: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.jev_failed = False
        self.jev_nulled = False
        self.lock = threading.Lock()

    def chat(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        model, messages = body['model'], body['messages']
        last = json.dumps(messages[-1]['content'])
        with self.lock:
            earlier = [one for one in self.chats if one.get('session_id') == body.get('session_id')]
            self.chats.append(body)
        if model == 'stub/broke':
            return 402, {'error': {'message': 'Insufficient credits', 'code': 402}}
        prefix = len(json.dumps(unmarked(earlier[-1]['messages']))) // 4 if earlier else 0
        ids = sorted(set(re.findall(r'\bI(\d+)\b', last)), key=int)
        if 'The roundtable has ended' in last:
            text = f'# Report by {model}\n\nThe stub read the record.'
        elif '# Topic synthesis' in last:
            text = '\n'.join(f'I{at}. Idea {at} of {model}: substance {at}.' for at in range(1, 7))
        elif '# Rank collected ideas' in last:  # each seat its own order, so the derived count has something to add
            turn = sum(map(ord, model)) % len(ids)
            text = ', '.join(f'I{one}' for one in ids[turn:] + ids[:turn])
        elif '# Explain your top three' in last:
            text = f'{model} ranked its top three first for their substance.'
        elif '# Explain your bottom three' in last:
            text = f'{model} ranked its bottom three last for their cost.'
        elif '# Host summary' in last:
            text = f'{model} summarises every seat\'s ranking and reasons.'
        elif model == 'stub/long' and not earlier:  # not the fake agent's 'long ' * 120, or it would be a repeat
            text = 'stub-long ' * 60
        elif model == 'stub/jev402':
            text = 'jev402: Jev is out of credits for this one.'
        elif model == 'stub/jevfail' and not earlier:
            text = 'jevfail: the first judgment of this fails.'
        elif model == 'stub/jevnull' and not earlier:
            text = 'jevnull: Jev answers the first judgment of this with null.'
        else:
            text = f'{model} says point {len(earlier) + 1}.' + (' I only say veto.' if 'VETO-ME' in last else '')
        return 200, {'model': model, 'choices': [{'message': {'role': 'assistant', 'content': text}}],
                     'usage': {'prompt_tokens': len(json.dumps(messages)) // 4, 'cost': 0.001,
                               'prompt_tokens_details': {'cached_tokens': prefix, 'cache_write_tokens': 0}}}

    def decide(self, body: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        text = body['state'].get('contribution', {}).get('text', '')
        with self.lock:
            self.decisions.append(body)
            if 'jev402' in text:
                return 402, {'error': {'message': 'Insufficient credits', 'code': 402}}
            if 'jevfail' in text and not self.jev_failed:
                self.jev_failed = True
                return 400, {'error': {'message': 'stub Jev failed once'}}
            if 'jevnull' in text and not self.jev_nulled:
                self.jev_nulled = True
                return 200, None
        value = 0.3 if 'veto' in text.lower() else 0.92
        return 200, {'model': body['model'], 'answers': {name: {'type': 'noul', 'noul': value}
                                                         for name in body['questions']},
                     'usage': {'cost': 0.0001}}


def serve_stub(stub: Stub) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            code, answer = stub.chat(body) if self.path.endswith('/chat/completions') else stub.decide(body)
            data = json.dumps(answer).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: Any) -> None:
            return

    held = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=held.serve_forever, daemon=True).start()
    return held
