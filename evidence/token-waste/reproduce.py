"""Read-only duplicate-delivery attribution; no provider calls, original packet remains untouched."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from metaform import home
from metaform.data import Store
from metaform.module import surface

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--project', required=True, help='Project ID in the copied METAFORM_HOME.')
parser.add_argument('--output', type=Path, required=True, help='Write aggregate results here.')
options = parser.parse_args()
project = next(p for p in home.projects() if p.project_id == options.project)
surface(Path(project.path))
store = Store(project.project_id, module='dispatch')
with store.tables(write=False) as tx:
    lines = list(tx.rows('session_lines', limit=0).results)
    sessions = {r['session_id']: r for r in tx.rows('agent_sessions', limit=0).results}

def decode(text):
    try:
        got = json.loads(text)
        return got if isinstance(got, dict) else {}
    except (ValueError, TypeError):
        return {}

# Exclude entire conversations with a recorded compaction, even if the repeated payload precedes it. These are
# candidates conditional on complete compaction telemetry, not independently certified provider token counts.
compacted = {r['session_id'] for r in lines if r['kind'] in ('notice', 'agent_notice') and
             'compact' in r['text'].lower()}
seen = set()
by_tool = defaultdict(Counter)
duplicates = []
for row in sorted(lines, key=lambda r: (r['session_id'], r['seq'])):
    sid = row['session_id']
    if row['kind'] != 'tool_detail' or sessions.get(sid, {}).get('agent') != 'claude' or sid in compacted:
        continue
    detail = decode(row['text'])
    call = detail.get('call') or {}
    result = call.get('result') or {}
    if not isinstance(result, dict) or detail.get('status') != 'completed':
        continue
    blocks = result.get('content') or []
    body = '\n'.join(str(b.get('text') or '') for b in blocks if b.get('type') == 'text')
    if not body or len(body) < 64:
        continue
    tool = str(call.get('tool') or detail.get('title') or '')
    args = json.dumps(call.get('input'), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(body.encode()).hexdigest()
    key = (sid, tool, args, digest)
    if key in seen:
        by_tool[tool].update(copies=1, chars=len(body), utf8_bytes=len(body.encode()))
        duplicates.append({'session': sid, 'seq': row['seq'], 'tool': tool, 'chars': len(body), 'sha256': digest})
    seen.add(key)

with Store(project.project_id, module='agents').tables(write=False) as tx:
    receipts = list(tx.rows('receipts', limit=0).results)
actions = [r for r in receipts if r['name'] == 'orchestration:actions']
action_chars = sum(len((r['component'] or {}).get('text') or '') for r in actions)
peer_receipts = [r for r in receipts if r['name'] == 'dispatch:peer_note' and r['channel'] == 'acp_prompt']
peer_overhead = 0
peer_notes = 0
for receipt in peer_receipts:
    component = receipt['component'] or {}
    note = (component.get('bindings') or {}).get('note')
    if isinstance(note, str) and note in component.get('text', ''):
        peer_overhead += len(component['text']) - len(note)
        peer_notes += 1
duplicates_chars = sum(r['chars'] for r in duplicates)
answer = {'method': 'Exact completed tool result text, identical tool and arguments, same Claude session; exclude '
                   'all sessions with a retained compaction notice; minimum 64 characters. Extra copies only.',
          'caveat': 'A retained UI tool record is not a final provider prompt trace; missing compaction evidence '
                    'and provider-side truncation prevent certifying billed token waste.',
          'excluded_sessions_with_compaction': len(compacted),
          'duplicate_tool_result_candidates': {'copies': len(duplicates), 'chars': duplicates_chars,
                                               'sessions': len({r['session'] for r in duplicates}),
                                               'by_tool': dict(sorted(by_tool.items(), key=lambda p: p[1]['chars'],
                                                                      reverse=True))},
          'delivered_duplicate_schema': {'receipts': len(actions), 'chars': action_chars,
                                        'channels': dict(Counter(r['channel'] for r in actions))},
          'delivered_peer_wrapper': {'receipts': peer_notes, 'chars': peer_overhead},
          'confirmed_redundant_delivered_chars': action_chars + peer_overhead,
          'illustrative_cost': {str(chars_per_token): {
              'assumed_characters_per_token': chars_per_token,
              'estimated_tokens': (action_chars + peer_overhead) / chars_per_token,
              'initial_cache_write_usd_at_6_25_per_million': (action_chars + peer_overhead) / chars_per_token * 6.25 / 1e6,
              'each_complete_reread_usd_at_0_50_per_million': (action_chars + peer_overhead) / chars_per_token * .5 / 1e6,
              'initial_plus_100_rereads_usd': (action_chars + peer_overhead) / chars_per_token * 56.25 / 1e6,
          } for chars_per_token in (3, 4, 5)},
          'duplicates': duplicates}
options.output.write_text(json.dumps({k: v for k, v in answer.items() if k != 'duplicates'}, indent=2) + '\n')
print(f'Wrote {options.output}; no model calls.')
