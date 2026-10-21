"""Project-wide release of explicit work holds."""
from __future__ import annotations

from typing import Any, cast

from metaform.data import Store, StoreError


def unhold_all_project(store: Store) -> int:
    """Release both hold flags atomically per base, keeping normal change notifications."""
    return sum(Store(store.project_id, base=base.id).unhold_all_work()
               for base in store.bases(limit=0).results)


def held_work_project(store: Store) -> list[dict[str, Any]]:
    """Gather release explanations across project bases only when explicitly requested."""
    found: list[dict[str, Any]] = []
    for base in store.bases(limit=0).results:
        own = Store(store.project_id, base=base.id)
        rows = own.held_work()
        numbers: dict[str, Any] = own.numbers_of('work', [row['id'] for row in rows]) if rows else {}
        for row in rows:
            numbered = numbers.get(row['id'])
            found.append({**row, 'base': base.id, 'base_name': base.name,
                          'title': numbered[1] if numbered else row['task'],
                          'item': numbered[0] if numbered else None})
    return found


def unhold_reviewed_project(store: Store, preview: Any) -> dict[str, int]:
    """Keep concurrently changed holds outside the work the person reviewed."""
    if not isinstance(preview, list) or any(not isinstance(row, dict) for row in cast(list[Any], preview)):
        raise StoreError('A hold preview is a list of reviewed tickets.', 'review held work before releasing it')
    reviewed = cast(list[dict[str, Any]], preview)
    changed = review_changed = 0
    for base in store.bases(limit=0).results:
        expected = [row for row in reviewed if row.get('base') == base.id]
        result = Store(store.project_id, base=base.id).unhold_reviewed_work(expected)
        changed += result['changed']
        review_changed += result['review_changed']
    return {'changed': changed, 'review_changed': review_changed}
