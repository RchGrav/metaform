"""Retire the previous Google agent's stored choices without changing other settings."""
from __future__ import annotations

import json
from typing import Any

from metaform import home

LEGACY = 'gemini'  # Stored identity only. No retired adapter is registered or started.
MARKER = 'migrated-antigravity-agent'


def migrate_settings(command: str) -> list[str]:
    """Migrate each settings database in one transaction, once per home. New choices win collisions.

    Commands the person supplied survive under the new setting. The retired shipped command becomes the pinned
    official adapter. Historical session records and transcripts retain their original identities.
    """
    marker = home.home() / MARKER
    if marker.exists() or not home.chassis_path().is_file():
        return []
    seen: set[str] = set()
    said: list[str] = []
    for source in ['global', *(home.path_key(record.path) for record in home.projects())]:
        with home.settings_db(source) as db:
            path = str(db.execute('PRAGMA database_list').fetchone()[2])
        if path in seen:
            continue
        seen.add(path)
        touched: set[tuple[str, str]] = set()
        with home.settings_db(source, write=True) as db:
            rows = db.execute('SELECT scope, owner, key, position, value FROM settings').fetchall()
            glues = db.execute('SELECT scope, owner, key FROM glue').fetchall()
            existing = {(scope, owner, key) for scope, owner, key, _, _ in rows}
            existing_glues = set(glues)
            for scope, owner, key, position, raw in rows:
                new_key = key.replace(f'dispatch_{LEGACY}', 'dispatch_antigravity', 1) \
                    if owner == 'dispatch' and (key == f'dispatch_{LEGACY}' or
                                               key.startswith(f'dispatch_{LEGACY}_')) else key
                if owner == 'chassis' and key == f'{LEGACY}_reminder':
                    db.execute('DELETE FROM settings WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
                    db.execute('DELETE FROM glue WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
                    touched.add((scope, owner))
                    continue
                value: Any = json.loads(raw)
                updated = value
                if new_key != key and key == f'dispatch_{LEGACY}' and isinstance(value, str):
                    if value == f'npx -y @google/{LEGACY}-cli@0.63.0 --acp':
                        updated = command
                elif owner == 'dispatch' and key in ('dispatch_agent', 'dispatch_system_agent',
                                                      'dispatch_healing_agent', 'dispatch_serve_agent'):
                    updated = 'antigravity' if value == LEGACY else value
                elif owner == 'dispatch' and key == 'dispatch_agent_options' and isinstance(value, str):
                    updated = 'antigravity' + value[len(LEGACY):] if value.startswith(LEGACY + '.') else value
                elif owner == 'roundtables' and key in ('roundtables_seats', 'roundtables_host',
                                                       'roundtables_synthesizer') and isinstance(value, str):
                    for prefix in ('', 'acp:'):
                        if value.startswith(prefix + LEGACY + '/'):
                            updated = prefix + 'antigravity' + value[len(prefix + LEGACY):]
                            break
                if new_key == key and updated == value:
                    continue
                if new_key != key:
                    if (scope, owner, new_key) not in existing:
                        db.execute('INSERT OR IGNORE INTO settings VALUES (?, ?, ?, ?, ?)',
                                   (scope, owner, new_key, position, json.dumps(updated)))
                    db.execute('DELETE FROM settings WHERE scope=? AND owner=? AND key=? AND position=?',
                               (scope, owner, key, position))
                    db.execute('DELETE FROM glue WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
                else:
                    db.execute('UPDATE settings SET value=? WHERE scope=? AND owner=? AND key=? AND position=?',
                               (json.dumps(updated), scope, owner, key, position))
                touched.add((scope, owner))
                said.append(f'{scope}: {new_key}')
            for scope, owner, key in glues:
                if owner == 'chassis' and key == f'{LEGACY}_reminder':
                    db.execute('DELETE FROM glue WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
                    touched.add((scope, owner))
                elif owner == 'dispatch' and (key == f'dispatch_{LEGACY}' or key.startswith(f'dispatch_{LEGACY}_')):
                    new_key = key.replace(f'dispatch_{LEGACY}', 'dispatch_antigravity', 1)
                    if (scope, owner, new_key) not in existing and (scope, owner, new_key) not in existing_glues:
                        db.execute('INSERT OR IGNORE INTO glue VALUES (?, ?, ?)', (scope, owner, new_key))
                    db.execute('DELETE FROM glue WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
                    touched.add((scope, owner))
                    said.append(f'{scope}: {new_key} glue')
        for scope, owner in sorted(touched):
            home.settings_changed(scope, owner)
    home.write_private(marker, '\n'.join(said))
    return said
