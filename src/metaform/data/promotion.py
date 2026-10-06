"""Associate a join with an ordinary element without rerouting it, MAP-054."""
from __future__ import annotations

import dataclasses
from typing import Any

from . import layering, rows, views, writes
from .records import Join, Notice, Outcome
from .selection import all_layers
from .session import Tx
from .versions import METAFORM_KINDS


def promote(tx: Tx, join_id: str, address: Any, *, name: Any = None, name_length: Any = None,
            role: Any = None, reason: Any = 'Promote the join to an element.') -> Join | Outcome:
    """Create or reuse an element and record its address on the same join in this transaction.

    Intake joins gain a version under LAYER-025. Knowledge joins follow their
    existing edit rules. A retry retains the association, and a different target
    returns a notice before writing anything.
    """
    if rows.kind_of(tx, join_id) != 'join':
        return Outcome((Notice('join', f'{join_id} is not a join; nothing was written.'),))
    base = rows.current_join(tx, join_id)
    if base is None:
        return Outcome((Notice('join', f'{join_id} has no current join; nothing was written.'),))
    found = rows.layer(tx, str(base['layer_id']))
    if found.kind not in METAFORM_KINDS:
        stop = writes.unchangeable(tx, found, join_id)
        if stop is not None:
            return Outcome((stop,))
    associated = base['element']
    if associated is not None and associated != address:
        return Outcome((Notice('element', f'The join already names {associated}; promotion to {address} was not '
                                          'applied. Nothing was written.'),))
    element = writes.add_element(tx, found.name, address, name=name, name_length=name_length, role=role)
    if isinstance(element, Outcome):
        return element
    notices = list(element.notices)
    if associated is None:
        change = {'element': element.address}
        if found.kind in METAFORM_KINDS:
            result = layering.refine(tx, join_id, change, reason=reason)
        else:
            result = writes.edit(tx, join_id, change)
        notices.extend(result.notices)
    current = rows.current_join(tx, join_id)
    assert current is not None
    return dataclasses.replace(views.join(tx, current, all_layers(tx.db)), notices=tuple(notices))
