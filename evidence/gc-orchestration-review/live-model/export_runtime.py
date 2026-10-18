"""Read the isolated completed runtime with Metaform's Store/table API."""
from pathlib import Path
import json
from metaform.data import Store
from metaform.module import surface

ROOT = Path('/tmp/metaform-review-live')
surface(ROOT / 'project')
TABLES = {
    'agents': ('contexts', 'receipts', 'definition_history'),
    'orchestration': ('assignments', 'sessions', 'transitions', 'role_requests', 'changes'),
    'dispatch': ('agent_sessions', 'session_lines', 'session_attempts'),
    'memory': ('entities', 'observations', 'relations', 'joins'),
}

def sanitize(value):
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, dict):
        # Retain runtime behavior; omit authentication account identity from state metadata.
        return {k: ({ak: sanitize(av) for ak, av in v.items() if ak != 'account'}
                    if k == 'auth' and isinstance(v, dict) else sanitize(v))
                for k, v in value.items()}
    return value

out = {'source': 'Read-only Store.tables(write=False) of isolated review_live project',
       'filters': ['auth.account omitted from adapter state metadata']}
for module, tables in TABLES.items():
    out[module] = {}
    with Store('review_live', module=module).tables(write=False) as tx:
        for table in tables:
            out[module][table] = sanitize([dict(r) for r in tx.rows(table, limit=0).results])
(ROOT / 'runtime-records.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({m: {t: len(v) for t,v in out[m].items()} for m in TABLES}, indent=2))
print('PM update receipts:', sum(r['name'].startswith('dispatch:user-update:') for r in out['agents']['receipts']))
