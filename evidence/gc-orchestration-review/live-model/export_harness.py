"""Export only the known live-smoke threads through Codex's own thread/read API."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

ROOT = Path('/tmp/metaform-review-live')
CODEX = '/tmp/metaform-review-live-adapter/node_modules/.bin/codex'


async def main() -> None:
    latest = sorted((ROOT / 'snapshots').iterdir())[-1]
    sessions = json.loads((latest / 'sessions.json').read_text())['sessions']
    ids = [s['session_id'] for s in sessions if s['agent'] == 'codex']
    output = ROOT / 'harness'
    output.mkdir(exist_ok=True)
    with (output / 'export.stderr').open('wb') as stderr:
        process = await asyncio.create_subprocess_exec(
            CODEX, 'app-server', '--stdio', cwd=ROOT / 'project',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr,
            limit=64 * 1024 * 1024)
        assert process.stdin is not None and process.stdout is not None
        sequence = 0

        async def request(method: str, params: dict) -> dict:
            nonlocal sequence
            sequence += 1
            ident = sequence
            process.stdin.write((json.dumps({'id': ident,
                                            'method': method, 'params': params}) + '\n').encode())
            await process.stdin.drain()
            while True:
                raw = await asyncio.wait_for(process.stdout.readline(), 25)
                if not raw:
                    raise RuntimeError('Codex app-server ended before its read response.')
                message = json.loads(raw)
                if message.get('id') == ident:
                    if 'error' in message:
                        raise RuntimeError(json.dumps(message['error']))
                    return message['result']
                if 'id' in message and 'method' in message:
                    raise RuntimeError(f'Unexpected app-server request: {message["method"]}')

        try:
            await request('initialize', {'clientInfo': {'name': 'metaform-review-evidence',
                'version': '1'}, 'capabilities': {'experimentalApi': True, 'requestAttestation': False}})
            reports = []
            for thread_id in ids:
                result = await request('thread/read', {'threadId': thread_id, 'includeTurns': True})
                thread = result['thread']
                excluded = 0
                for turn in thread.get('turns', []):
                    prior = turn.get('items', [])
                    turn['items'] = [item for item in prior if item.get('type') != 'reasoning']
                    excluded += len(prior) - len(turn['items'])
                (output / f'{thread_id}.json').write_text(json.dumps(result, indent=2) + '\n')
                reports.append({'thread_id': thread_id, 'turns': len(thread.get('turns', [])),
                    'item_types': sorted({item['type'] for turn in thread.get('turns', [])
                                          for item in turn.get('items', [])}),
                    'reasoning_items_omitted': excluded})
            (output / 'manifest.json').write_text(json.dumps({
                'method': 'thread/read', 'includeTurns': True,
                'scope': 'Only Codex thread IDs recorded by the isolated Metaform live-smoke sessions.',
                'threads': reports}, indent=2) + '\n')
            print(json.dumps(reports, indent=2))
        finally:
            process.stdin.close()
            try:
                await asyncio.wait_for(process.communicate(), 5)
            except TimeoutError:
                process.kill()
                await process.communicate()


if __name__ == '__main__':
    asyncio.run(main())
