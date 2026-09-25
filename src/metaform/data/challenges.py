"""Blind-spot challenge states and plans, kept beside the critic's layer, never as edits to it, STORE-040.

`answer` is an agent's write and never refused for its content, BASE-044: an
answer outside a blind-spot layer, a C without its link, or an answer to an
approved challenge is stored as given with a notice. A plan comes only from
`approve`, the one place a person acts, LAYER-015, so an answer of `plan`
writes nothing and says so. `approve` keeps its check: it acts only on B.
"""
from __future__ import annotations

from typing import Any, cast

from .. import home
from ..errors import StoreError
from . import rows
from .records import Answer, ChallengeState, Node, Notice, Outcome, Plan
from .session import Tx

ANSWERS = ('A', 'B', 'C')


def answer(tx: Tx, item_id: str, state: Any, link: Node | None = None) -> ChallengeState | Outcome:
    """Record a challenge's answer beside the critic's layer, STORE-040."""
    if state == 'plan':
        return Outcome((Notice('answer', 'plan comes only from metaform map approve, which a person runs; nothing '
                                         'was written. Answer A, B or C.'),))
    if state not in ANSWERS:
        raise StoreError(f'{state!r} is not an answer: use A, B or C.', f'metaform map answer {item_id} A')
    if rows.kind_of(tx, item_id) != 'item':
        raise StoreError(f'{item_id} is not a challenge.', 'metaform map layers')
    _, found = rows.own_row(tx, 'item', item_id)
    notices: list[Notice] = []
    if found.kind != 'layer':
        notices.append(Notice('challenge', f'{item_id} is in {found.name}, which is not a blind-spot layer; the '
                                           'answer was stored as given.'))
    existing = tx.db.execute('SELECT state FROM challenge_states WHERE item_id=?', (item_id,)).fetchone()
    if existing is not None and existing[0] == 'plan':
        notices.append(Notice('challenge', f'Challenge {item_id} was already approved as a plan; this answer was '
                                           'stored as given.'))
    link_kind: str | None = None
    link_id: str | None = None
    if state == 'C':
        if link is None:
            notices.append(Notice('link', 'A C answer names the element or join that already handles the challenge; '
                                          'give it with link=element:<address>. The answer was stored without it.'))
        else:
            link_kind, link_id = rows.node_at(tx, link, found, 'link', notices)
    stamp = home.now()
    tx.db.execute('INSERT INTO challenge_states(item_id, state, link_kind, link_id, answered) VALUES (?, ?, ?, ?, ?) '
                  'ON CONFLICT(item_id) DO UPDATE SET state=excluded.state, link_kind=excluded.link_kind, '
                  'link_id=excluded.link_id, answered=excluded.answered', (item_id, state, link_kind, link_id, stamp))
    # `state` is one of ANSWERS, checked above.
    return ChallengeState(item_id, cast(Answer, state), Node.of(link_kind, link_id) if link_kind and link_id else None,
                          stamp, None, tuple(notices))


def approve(tx: Tx, item_id: str) -> ChallengeState:
    """A person approves a B answer; it becomes a plan with the element and join it carries, STORE-040."""
    existing = tx.db.execute('SELECT state, answered FROM challenge_states WHERE item_id=?', (item_id,)).fetchone()
    if existing is None or existing[0] != 'B':
        state = 'open' if existing is None else existing[0]
        raise StoreError(f'Challenge {item_id} is {state}; only a challenge answered B is approved.',
                         f'metaform map answer {item_id} B')
    item, found = rows.own_row(tx, 'item', item_id)
    stamp = home.now()
    tx.db.execute("UPDATE challenge_states SET state='plan', approved=? WHERE item_id=?", (stamp, item_id))
    if item['target_kind'] == 'element':
        element_id = str(item['target_id'])
        added = tx.db.execute("SELECT 1 FROM elements WHERE element_id=? AND layer_id=? AND op='add'",
                              (element_id, found.layer_id)).fetchone()
        if added is not None:
            tx.db.execute('INSERT OR IGNORE INTO plans(element_id, join_id, layer_id, source, item_id) '
                          'VALUES (?, ?, ?, ?, ?)',
                          (element_id, _join_in_layer(tx, element_id, found.layer_id), found.layer_id, 'approved',
                           item_id))
    return ChallengeState(item_id, 'plan', None, str(existing[1]), stamp)


def _join_in_layer(tx: Tx, element_id: str, layer_id: str) -> str | None:
    for column in ('provider', 'receiver'):
        row = tx.db.execute(f'SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                            f'WHERE c.{column}=? AND j.layer_id=? ORDER BY c.row LIMIT 1',
                            (element_id, layer_id)).fetchone()
        if row is not None:
            return str(row[0])
    return None


def add_plan(tx: Tx, layer: str, element: Any, join: str | None) -> Plan:
    """An agent adds a plan directly; it needs no approval, STORE-040."""
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    element_id = rows.element_at(tx, element, found, 'element', notices)
    join_id: str | None = None
    if join:
        kind, join_id = rows.node_at(tx, Node('join', join), found, 'join', notices)
        if not rows.target_current(tx, kind, join_id) and not tx.db.execute(
                'SELECT 1 FROM join_ids WHERE join_id=?', (join_id,)).fetchone():
            join_id = None
    tx.db.execute('INSERT INTO plans(element_id, join_id, layer_id, source, item_id) VALUES (?, ?, ?, ?, NULL) '
                  'ON CONFLICT(element_id) DO UPDATE SET join_id=excluded.join_id, layer_id=excluded.layer_id, '
                  "source='direct', item_id=NULL", (element_id, join_id, found.layer_id, 'direct'))
    return Plan(element_id, join_id, found.layer_id, found.name, 'direct', None, tuple(notices))
