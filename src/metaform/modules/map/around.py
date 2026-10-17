"""What is at an agent's node, told as counts with the calls that read them, once per agent session, MCP-039.

The node is the element the agent works on. Around it stand the elements that rely on it directly, the receivers of
the joins it provides for, and those it relies on directly, the providers of the joins it receives; no further hop.
For each, what the modules hold there is counted, and at the node itself its open work, messages, layer items, earlier
runs and properties too. Nothing they hold is sent: each count names the call that reads it.

The counts are drawn as a small tree the first time a session orients on the node, and recorded as shown to that
session. Later in the session the same counts are not shown again; a count that changed is told in one line.
"""
from __future__ import annotations

from collections.abc import Callable
from importlib import resources
from typing import Any, cast

from metaform import prompt_files
from metaform.data import Where, shown_number
from metaform.module import Context, latest_item, node_counts

from .glossary import at_node

SIDE = 8  # the neighbours drawn on each side before the rest are counted, so a busy node stays a few lines
FOCUS = '▶ '
TITLE = 80  # the characters of the latest item's title the tree gives; the item itself is read with its number


def _prompt(name: str, **fills: str) -> str:
    return prompt_files.text(resources.files(__package__ or 'metaform.modules.map'), name, **fills) or ''


def neighbours(found: Where) -> tuple[list[str], list[str]]:
    """The addresses that rely on the node directly, the receivers of the joins it provides for, and the addresses it
    relies on directly, the providers of the joins it receives, each in the map's order, the node itself left out."""
    me = found.element.address if found.element is not None else None
    above = [join.receiver_address for join in found.provides if join.receiver_address]
    below = [held.address for join in found.receives for held in join.elements]
    return ([one for one in dict.fromkeys(above) if one != me],
            [one for one in dict.fromkeys(below) if one and one != me])


def _plural(count: int, one: str, many: str) -> str:
    return f'{count} {one if count == 1 else many}'


def _own(found: Where) -> list[tuple[str, str, str]]:
    """What the map holds at the node itself: each kind as said with its count, its name, and the command line that
    reads it; a kind with none is left out. The sources are left out of the layer items: the read shows them."""
    address = found.element.address if found.element is not None else ''
    items = sum(len(group.items) for group in found.layers if group.layer != 'sources')
    return [(_plural(count, one, many), many, read) for count, one, many, read in (
        (len(found.work), 'open work', 'open work', f'metaform map work node={address}'),
        (len(found.messages), 'message', 'messages', f'metaform map messages node={address}'),
        (items, 'layer item', 'layer items', f'metaform map node node=element:{address}'),
        (len(found.past_work), 'earlier run', 'earlier runs', f'metaform map work node={address} open=false'),
        (len(found.applying), 'property', 'properties', f'metaform map context address={address}'),
    ) if count]


class Around:
    """The counts at a node and around it, drawn once and compared after."""

    def __init__(self, ctx: Context, found: Where) -> None:
        assert found.element is not None
        self.ctx = ctx
        self.found = found
        self.address = found.element.address
        self.name = found.element.short_name or found.element.name or ''
        self.above, self.below = neighbours(found)
        everyone = (self.address, *self.above, *self.below)
        self.counts = node_counts(ctx.folder, everyone, project=ctx.project, session=ctx.session,
                                  layers=cast(list[str] | None, ctx.switches.get('layers')))
        self.own = _own(found)
        self.latest = self._latest()
        named = at_node(ctx.store, self.address) if ctx.store is not None else []
        self.terms = ctx.calls(_prompt('around_terms', terms=', '.join(named),
                                       read=f'metaform map glossary term="{named[0]}"')) if named else ''

    def _latest(self) -> str:
        """The line under the node naming what is new there, MCP-037: the last number taken at it with its item's
        title, and the numbers the last session other than this one took there, as a range; '' when nothing is
        numbered at the node."""
        try:
            latest = latest_item(self.ctx.folder, self.address, project=self.ctx.project)
            store = self.ctx.store
            last = store.last_session(self.address, besides=self.ctx.session) if store is not None else None
        except Exception:  # noqa: BLE001  the line is a pointer; a fault reading it leaves it out, never the brief
            return ''
        if latest is None:
            return ''
        title = ' '.join(str(latest.get('title') or '').split())
        title = title if len(title) <= TITLE else title[:TITLE - 1].rstrip() + '…'
        session = ''
        if last is not None:
            _, first, end, count = last
            span = shown_number(end) if first == end else f'{shown_number(first)}–{shown_number(end)}'
            whole = count == end - first + 1
            session = _prompt('around_session', range=span,
                              count='' if whole else _prompt('around_session_count', count=str(count)))
        return _prompt('around_latest', item=str(latest['item']), title=f'  {title}' if title else '',
                       session=session)

    def parts(self, address: str) -> list[str]:
        """The counts at one address, the modules' first: `3 memories · 1 new`; a zero part is never said."""
        said: list[str] = []
        for count in self.counts.values():
            total, new, _ = count.at.get(address, (0, 0, 0))
            if total:
                said.append(count.said(total) + (f' · {new} new' if new else ''))
        if address == self.address:
            said += [word for word, _, _ in self.own]
        return said

    def held(self, address: str) -> int:
        return sum(count.at.get(address, (0, 0, 0))[0] for count in self.counts.values())

    def state(self) -> dict[str, dict[str, int]]:
        """What a later read compares: at each address, each module's count without this session's own writes, which
        are never news to it, and the messages at the node."""
        found: dict[str, dict[str, int]] = {}
        for address in (self.address, *self.above, *self.below):
            for module, count in self.counts.items():
                total, _, mine = count.at.get(address, (0, 0, 0))
                if total - mine:
                    found.setdefault(address, {})[module] = total - mine
        if self.found.messages:
            found.setdefault(self.address, {})['messages'] = len(self.found.messages)
        return found

    def _side(self, heading: str, addresses: list[str], read: str, side: int) -> list[tuple[str, list[str]]]:
        """One side of the tree: its heading and a line per neighbour, those holding most first, at most `side`, and
        then how many more and the call that lists them all."""
        if not heading or not addresses:
            return []
        ordered = sorted(addresses, key=lambda one: (-self.held(one), addresses.index(one)))
        shown = ordered[:side]
        rest = len(ordered) - len(shown)
        more = _prompt('around_more', count=str(rest), read=read) if rest else ''
        lines: list[tuple[str, list[str]]] = [(heading, [])]
        for index, address in enumerate(shown):
            last = index == len(shown) - 1 and not more
            lines.append((f'  {"└" if last else "├"} {address}', self.parts(address)))
        if more:
            lines.append((f'  └ {more}', []))
        return lines

    def tree(self, side: int = SIDE) -> str:
        """The tree: what relies on the node, the node with its counts, what it relies on, at most `side` neighbours
        each way, then the line that says how to read each kind counted, its counts aligned in one column."""
        under: list[tuple[str, list[str]]] = [(f'  {line}', []) for line in (self.latest, self.terms) if line]
        rows = [*self._side(_prompt('around_above'), self.above,
                            f'metaform map joins element={self.address} as=provider', side),
                (f'{FOCUS}{self.address}' + (f'  {self.name}' if self.name else ''), self.parts(self.address)),
                *under,
                *self._side(_prompt('around_below'), self.below, f'metaform map joins element={self.address}', side)]
        width = max((len(label) for label, parts in rows if parts), default=0)
        digits = max((len(parts[0].split(' ', 1)[0]) for _, parts in rows if parts), default=0)
        lines: list[str] = []
        for label, parts in rows:
            if not parts:
                lines.append(label)
                continue
            number, _, rest = parts[0].partition(' ')
            lines.append(f'{label.ljust(width)}  {number.rjust(digits)} {rest}' +
                         ''.join(f' · {part}' for part in parts[1:]))
        everyone = (self.address, *self.above, *self.below)
        legends = [legend(count.legend, [one for one in everyone if count.at.get(one, (0, 0, 0))[1]] or
                          [one for one in everyone if count.at.get(one, (0, 0, 0))[0]])
                   for count in self.counts.values()
                   if count.legend and any(count.at.get(one, (0, 0, 0))[0] for one in everyone)]
        reads = ' · '.join(f'{name}: {read}' for _, name, read in self.own)
        closing = _prompt('around_read', reads=reads) if reads else ''
        return self.ctx.calls('\n'.join([*lines, *legends, *([closing] if closing else [])]))

    def changed(self, before: dict[str, dict[str, int]]) -> list[str]:
        """A line per count that changed since the session was last shown it: how many more, or how many now."""
        now = self.state()
        said: list[str] = []
        for address in dict.fromkeys([*before, *now]):
            was, held = before.get(address, {}), now.get(address, {})
            for kind in dict.fromkeys([*was, *held]):
                old, new = was.get(kind, 0), held.get(kind, 0)
                if old == new:
                    continue
                count = self.counts.get(kind)
                words = (count.one, count.many) if count is not None else ('message', 'messages')
                if new > old:
                    line = _prompt('around_new', count=str(new - old),
                                   what=words[0] if new - old == 1 else words[1], address=address)
                else:
                    line = _prompt('around_fewer', what=words[1], address=address, count=str(new))
                if line:
                    said.append(line)
        return said


def legend(said: str, held: list[str]) -> str:
    """A count's legend with its <address> filled in, so the call reads as it is made and no placeholder is sent:
    `held` is the addresses that hold what it counts, those with new records first chosen by the caller. With several,
    the call, from the last `: ` before the placeholder, is given once per address, joined by ` · `."""
    at = said.find('<address>')
    if at < 0 or not held:
        return said
    start = said.rfind(': ', 0, at)
    start = 0 if start < 0 else start + 2
    return said[:start] + ' · '.join(said[start:].replace('<address>', one) for one in held)


def told(ctx: Context, found: Where, fits: Callable[[dict[str, Any]], bool] | None = None) -> dict[str, Any]:
    """What an agent is told of the counts at its node in this read: the tree the first time its session reads the
    node, `around`; the counts that changed since, `changed`; or nothing when nothing changed, MCP-039. With no agent
    session every read draws the tree. While `fits` says the tree leaves the read too big, it is drawn again with one
    neighbour fewer each way, down to one, so a busy node keeps the summary its budget allows."""
    if found.element is None:
        return {}
    around = Around(ctx, found)
    before = ctx.seen(f'around:{ctx.project}:{around.address}', around.state())
    if before is None:
        side = SIDE
        said = {'around': around.tree(side)}
        while fits is not None and side > 1 and not fits(said):
            side -= 1
            said = {'around': around.tree(side)}
        return said
    changed = around.changed(cast(dict[str, dict[str, int]], before))
    return {'changed': changed} if changed else {}
