"""The data access object: the only code that opens a store or issues SQL, STORE-023.

`Store(project)` reads and writes the active metaform of one registered
project. Writes are STORE-024, reads are STORE-025. Every write is one
transaction; every read is one read transaction and goes through an index,
STORE-005. Selection, masking, hiding and the transitive rules of properties
are applied inside every read, so no caller computes or bypasses them,
STORE-019.

`Store` is the one public door. Each method opens its transaction and calls one
operation of the internal modules, which each take that `Tx`: `writes` for the
map's objects, `layering` for layers and the correction stack, `challenges` for
challenge states and plans, `reads` for every read. No write is refused for its
content, BASE-044 and STORE-026: what does not fit is stored as given and named
in the result's `notices`.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Generator, Iterable, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, TypeVar, cast

from .. import home
from ..errors import StoreError
from . import challenges, layering, reads, rows, views, writes
from .paging import LIMIT, sliced
from .records import (ChallengeState, Citation, ContextView, Element, Finding, Item, Join, Layer, Node, NodeView,
                      Notice, Outcome, Page, PeelPreview, Plan, Property, Provenance, Record, Ref, Report, Roots,
                      Selection, Subtype, Version, Where)
from .selection import Resolver
from .session import Session, Tx

REPORT_KINDS = ('report', 'feedback', 'shape')

RecordT = TypeVar('RecordT', bound=Record)


class Store:
    """Reads and writes one project's active metaform.

    `module` names the module the store works for; a layer this store makes for a write sent without one records it
    as its owner, LAYER-001.
    """

    def __init__(self, project: str, *, toggled: Sequence[str] | None = None, metaform: str | None = None,
                 module: str | None = None) -> None:
        record = home.project(project)
        if record is None:
            raise StoreError(f'No project {project} is registered.', 'metaform list projects')
        self._record = record
        self._session = Session(record.project_id, metaform)
        self.toggled: tuple[str, ...] = tuple(toggled or ())
        self.module = module

    # ------------------------------------------------------------------ plumbing

    @property
    def project_id(self) -> str:
        return self._record.project_id

    @contextmanager
    def atomic(self) -> Generator[None, None, None]:
        """Every write inside the block commits together, or none does, STORE-024."""
        with self._session.atomic():
            yield

    @contextmanager
    def _write(self) -> Generator[Tx, None, None]:
        try:
            with self._session.write() as tx:
                yield tx
        except sqlite3.IntegrityError as error:
            raise StoreError(f'The write does not fit the store: {error}.', 'metaform help map knowledge') from None

    @contextmanager
    def _read(self) -> Generator[Tx, None, None]:
        with self._session.read() as tx:
            yield tx

    def _resolver(self, tx: Tx, selection: Sequence[str] | None) -> Resolver:
        return reads.resolver(tx, selection, self.toggled)

    def _named(self, tx: Tx, layer: str | None) -> tuple[str, Notice | None]:
        """The layer a write goes to: the one named, or a new building layer `unnamed-<UTC timestamp>`, LAYER-001."""
        if layer:
            return layer, None
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        made = layering.create(tx, f'unnamed-{stamp}', self.module or '', '', mutable=True, hideable=True)
        return made.name, Notice('layer', f'No layer was named; this was stored in a new building layer {made.name}, '
                                          'which has no variable and no provenance.')

    @staticmethod
    def _noted(result: RecordT, notice: Notice | None) -> RecordT:
        """The result with the notice of the layer it was written to, first."""
        if notice is None:
            return result
        noted: RecordT = dataclasses.replace(cast(Any, result), notices=(notice, *getattr(result, 'notices', ())))
        return noted

    # ------------------------------------------------------------------ layers

    def layer(self, name: str, module: str, variable: Any, *, kind: str = 'layer', mutable: bool, hideable: bool,
              fields: Sequence[str] = (), tags: Sequence[Any] = (), provenance: dict[str, Any] | None = None,
              result_id: str | None = None, sources: Sequence[Any] = (), ready: bool = False) -> Layer:
        """Create a layer, or return the one with this name and the same declaration, STORE-024."""
        with self._write() as tx:
            return layering.create(tx, name, module, variable, kind=kind, mutable=mutable, hideable=hideable,
                                   fields=fields, tags=tags, provenance=provenance, result_id=result_id,
                                   sources=sources, ready=ready)

    def finish(self, layer: str) -> Layer | Outcome:
        """Mark a layer ready; a correction layer is also applied on top of the stack, STORE-017."""
        with self._write() as tx:
            return layering.finish(tx, layer)

    def discard(self, layer: str) -> Outcome:
        """Delete a knowledge layer's content and the layer; identity and type rows stay, STORE-032."""
        with self._write() as tx:
            return layering.discard(tx, layer)

    def hide(self, layer: str) -> Outcome:
        with self._write() as tx:
            return layering.hide(tx, layer, True)

    def unhide(self, layer: str) -> Outcome:
        with self._write() as tx:
            return layering.hide(tx, layer, False)

    def tag(self, layer: str, tag: Any) -> Outcome:
        with self._write() as tx:
            return layering.tag(tx, layer, tag)

    def untag(self, layer: str, tag: str) -> Outcome:
        with self._write() as tx:
            return layering.untag(tx, layer, tag)

    def reexamined(self, layer: str) -> Outcome:
        with self._write() as tx:
            return layering.reexamined(tx, layer)

    def select(self, address: str, layer: str) -> Outcome:
        with self._write() as tx:
            return layering.selection(tx, address, layer, 'select')

    def mask(self, address: str, layer: str) -> Outcome:
        with self._write() as tx:
            return layering.selection(tx, address, layer, 'mask')

    def clear(self, address: str, layer: str, kind: str) -> Outcome:
        with self._write() as tx:
            return layering.clear(tx, address, layer, kind)

    # ---------------------------------------------------------------- the map

    def add_element(self, layer: str | None, address: Any, *, name: Any = None, name_length: Any = None,
                    role: Any = None, refs: Iterable[Any] = (), extra: Any = None, flag: Any = None,
                    flag_note: Any = None) -> Element | Outcome:
        """Write an element, or return the one already at the address, STORE-009."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_element(tx, named, address, name=name, name_length=name_length, role=role,
                                                  refs=refs, extra=extra, flag=flag, flag_note=flag_note), notice)

    def add_join(self, layer: str | None, receiver: Any, provider: Any, *, purpose: Any = None, function: Any = None,
                 relation: Any = None, observation: Any = None, non_goal: Any = None, type: Any = 'purpose',
                 refs: Iterable[Any] = (), extra: Any = None, flag: Any = None,
                 flag_note: Any = None) -> Join | Outcome:
        """Write one join, owned by its receiver and served by its provider, STORE-010."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_join(tx, named, receiver, provider, purpose=purpose, function=function,
                                               relation=relation, observation=observation, non_goal=non_goal,
                                               type=type, refs=refs, extra=extra, flag=flag, flag_note=flag_note),
                               notice)

    def add_subtype(self, layer: str | None, join: Any, address: Any, *, function: Any = None, relation: Any = None,
                    observation: Any = None, name: Any = None, name_length: Any = None, role: Any = None,
                    refs: Iterable[Any] = (), extra: Any = None, purpose: Any = None, flag: Any = None,
                    flag_note: Any = None) -> Subtype | Outcome:
        """Write a subtype inside the one join it shares with its parent; it has no purpose, STORE-011."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_subtype(tx, named, join, address, function=function, relation=relation,
                                                  observation=observation, name=name, name_length=name_length,
                                                  role=role, refs=refs, extra=extra, purpose=purpose, flag=flag,
                                                  flag_note=flag_note), notice)

    def add_ref(self, owner: str, key: str, value: str) -> Ref | Outcome:
        """Add one ref to a thing's current version in a knowledge or mutable layer, STORE-012."""
        with self._write() as tx:
            return writes.add_ref(tx, owner, key, value)

    def add_item(self, layer: str | None, target: Node, value: Any, *, link: Node | None = None,
                 refs: Iterable[Any] = (), extra: Any = None) -> Item | Outcome:
        """Attach one value of the layer's variable at one node, with an optional link to another, STORE-015."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_item(tx, named, target, value, link=link, refs=refs, extra=extra), notice)

    def add_property(self, layer: str | None, element: Any, value: Any, *, refs: Iterable[Any] = (),
                     extra: Any = None) -> Property | Outcome:
        """Attach a property to an element; it travels the namespace and has no join, STORE-039."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_property(tx, named, element, value, refs=refs, extra=extra), notice)

    def update_item(self, item: str, value: Any) -> Item | Outcome:
        """Change a memory in place, with no history, STORE-018."""
        with self._write() as tx:
            return writes.update_item(tx, item, value)

    def delete_item(self, item: str) -> Outcome:
        with self._write() as tx:
            return writes.delete_item(tx, item)

    def edit(self, thing: str, changes: Any) -> Version | Outcome:
        """Change a thing of a knowledge layer, or of a building correction layer, in place, STORE-032."""
        with self._write() as tx:
            return writes.edit(tx, thing, changes)

    def remove(self, thing: str | int) -> Outcome:
        """Delete a row a knowledge layer or a building correction layer wrote, with its refs, STORE-032."""
        with self._write() as tx:
            return writes.remove(tx, thing)

    # ------------------------------------------------------------ corrections

    def correct(self, layer: str, thing: str, changes: dict[str, Any] | None = None, *, remove: bool = False,
                reason: Any, evidence: Any = None) -> Version | Outcome:
        """Write a change or removal of a thing of the metaform into a building correction layer, STORE-017."""
        with self._write() as tx:
            return layering.correct(tx, layer, thing, changes, remove=remove, reason=reason, evidence=evidence)

    def peel(self, layer: str) -> Layer | Outcome:
        """Take the top correction layer off the stack and return it to building, STORE-017."""
        with self._write() as tx:
            return layering.peel(tx, layer)

    # ------------------------------------------------------------- challenges

    def answer(self, item_id: str, state: Any, link: Node | None = None) -> ChallengeState | Outcome:
        """Record a challenge's answer beside the critic's layer, STORE-040."""
        with self._write() as tx:
            return challenges.answer(tx, item_id, state, link)

    def approve(self, item_id: str) -> ChallengeState:
        """A person approves a B answer; it becomes a plan, STORE-040."""
        with self._write() as tx:
            return challenges.approve(tx, item_id)

    def add_plan(self, layer: str, element: Any, join: str | None) -> Plan:
        """An agent adds a plan directly; it needs no approval, STORE-040."""
        with self._write() as tx:
            return challenges.add_plan(tx, layer, element, join)

    # ================================================================== reads

    def element(self, ref: str, *, selection: Sequence[str] | None = None, raw: bool = False) -> Element | None:
        """One element by address or id, with its descriptors and refs."""
        with self._read() as tx:
            return reads.element(tx, None if raw else self._resolver(tx, selection), ref)

    def joins(self, element: str, as_: str = 'receiver', *, selection: Sequence[str] | None = None,
              raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Join]:
        """The joins an element owns, or those it provides for, each with its layer."""
        with self._read() as tx:
            return reads.joins(tx, None if raw else self._resolver(tx, selection), element, as_, limit, after)

    def identity(self, element: str, *, selection: Sequence[str] | None = None, raw: bool = False,
                 limit: int = LIMIT, after: str | None = None) -> Page[Join]:
        """Every current join the element provides for: who receives it, why, and how, STORE-010."""
        return self.joins(element, 'provider', selection=selection, raw=raw, limit=limit, after=after)

    def subtypes(self, join: str, *, selection: Sequence[str] | None = None, raw: bool = False,
                 limit: int = LIMIT, after: str | None = None) -> Page[Subtype]:
        with self._read() as tx:
            return reads.subtypes(tx, None if raw else self._resolver(tx, selection), join, limit, after)

    def where(self, address: str, *, selection: Sequence[str] | None = None, raw: bool = False) -> Where | None:
        """The element at an address, or the subtype there with the join that holds it."""
        with self._read() as tx:
            return reads.where(tx, None if raw else self._resolver(tx, selection), address)

    def children(self, address: str, *, limit: int = LIMIT, after: str | None = None) -> Page[str]:
        """The next types up the tree, toward the leaves."""
        with self._read() as tx:
            return reads.children(tx, address, limit, after)

    def layer_items(self, layer: str, target: Node | None = None, *, in_context: bool = False, limit: int = LIMIT,
                    after: str | None = None) -> Page[Item | Property]:
        """A whole layer in row order, or a layer at one node: its items, then its properties.

        Named by the caller, the layer is read directly, hidden or masked, LAYER-008. With `in_context=True`, as an
        agent's context read, only what the layer reaches at its node's address is returned, STORE-019.
        """
        with self._read() as tx:
            return reads.layer_items(tx, self._resolver(tx, None) if in_context else None, layer, target, limit,
                                     after)

    def node(self, target: Node, *, selection: Sequence[str] | None = None, raw: bool = False) -> NodeView | None:
        """Every layer's items at one node, grouped by layer; in context, only the layers that reach it."""
        with self._read() as tx:
            return reads.node(tx, self._resolver(tx, selection), target, raw)

    def context(self, address: str, *, selection: Sequence[str] | None = None, limit: int = LIMIT,
                after: str | None = None) -> ContextView:
        """The properties that apply at an address, and those visible there from above, STORE-035."""
        with self._read() as tx:
            return reads.context(tx, self._resolver(tx, selection), address, limit, after)

    def links_to(self, target: Node, layer: str | None = None, *, selection: Sequence[str] | None = None,
                 raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Item]:
        """Items that link to a node; a named layer narrows the read and never widens it, STORE-019."""
        with self._read() as tx:
            return reads.links_to(tx, self._resolver(tx, selection), target, layer, raw, limit, after)

    def citing(self, key: str, value: str, *, limit: int = LIMIT, after: str | None = None) -> Page[Citation]:
        """Every current thing whose refs hold this key and value, MAP-021."""
        with self._read() as tx:
            return reads.citing(tx, key, value, limit, after)

    def history(self, thing: str, *, limit: int = LIMIT, after: str | None = None) -> Page[Version]:
        """Every version of a thing: the row that added it, then each stacked correction's row, in order."""
        with self._read() as tx:
            return reads.history(tx, thing, limit, after)

    def stack(self, *, limit: int = LIMIT, after: str | None = None) -> Page[Layer]:
        """The correction layers in the order they were applied, each with its provenance."""
        with self._read() as tx:
            return reads.stack(tx, limit, after)

    def layers(self, tag: str | None = None, kind: str | None = None, module: str | None = None, *,
               limit: int = LIMIT, after: str | None = None) -> Page[Layer]:
        """The layers with their declaration, tags, state, hidden and toggled flags, LAYER-019."""
        with self._read() as tx:
            return reads.layers(tx, self._resolver(tx, None), tag, kind, module, limit, after)

    def peel_preview(self, layer: str) -> PeelPreview:
        """What removing a correction layer would change, and whether it is on top, writing nothing, VIEW-014."""
        with self._read() as tx:
            return reads.peel_preview(tx, layer)

    def provenance(self, layer: str) -> Provenance | None:
        with self._read() as tx:
            return reads.provenance(tx, layer)

    def effective_selection(self, address: str, root: Sequence[str] | None = None) -> Selection:
        """The layers that reach an address, and any select or mask rows that cannot apply, STORE-035."""
        with self._read() as tx:
            return reads.effective_selection(tx, self._resolver(tx, root), address)

    def search(self, text: str, layer: str | None = None, *, selection: Sequence[str] | None = None,
               raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Item]:
        """Items whose value holds every word of the text, STORE-020; in context unless `raw`."""
        with self._read() as tx:
            return reads.search(tx, self._resolver(tx, selection), text, layer, raw, limit, after)

    def roots(self, *, selection: Sequence[str] | None = None, raw: bool = False, limit: int = LIMIT,
              after: str | None = None) -> Roots:
        """The map's entry: the VE and DE with the joins they receive, and every root element, one page, STORE-025."""
        with self._read() as tx:
            return reads.roots(tx, None if raw else self._resolver(tx, selection), limit, after)

    def findings(self, flag: str | None = None, layer: str | None = None, *, selection: Sequence[str] | None = None,
                 raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Finding]:
        """Flagged objects, by flag, each with its address or its join's ends, STORE-042."""
        with self._read() as tx:
            return reads.findings(tx, None if raw else self._resolver(tx, selection), flag, layer, limit, after)

    # --------------------------------------------------------------- reports

    def save_report(self, name: str, run_id: str, kind: str, size: int, layer: str | None = None) -> Report:
        """Record one report, feedback or shape file, or its new size after an append, STORE-043."""
        if kind not in REPORT_KINDS:
            raise StoreError(f'{kind!r} is not report, feedback or shape.', 'metaform help feedback')
        with self._write() as tx:
            return reads.save_report(tx, name, run_id, kind, size, layer)

    def reports(self, kind: str | None = None, layer: str | None = None, *, limit: int = LIMIT,
                after: str | None = None) -> Page[Report]:
        """The report, feedback and shape files of this metaform, oldest first, STORE-043."""
        with self._read() as tx:
            return reads.reports(tx, kind, layer, limit, after)

    def report(self, name: str) -> Report | None:
        with self._read() as tx:
            return reads.report(tx, name)

    # -------------------------------------------------------------- metaforms

    def layer_ref(self, layer: str) -> Layer:
        """One layer by name or id, with its declaration."""
        with self._read() as tx:
            return views.layer(tx, rows.layer(tx, layer))

    def has_intake(self) -> bool:
        with self._read() as tx:
            return reads.has_intake(tx)

    def metaforms(self, *, limit: int = LIMIT, after: str | None = None) -> Page[home.Metaform]:
        return sliced(home.metaforms(self.project_id), limit, after)

    def active_metaform(self) -> home.Metaform | None:
        return home.active_metaform(self.project_id)

    def add_metaform(self, name: str, *, activate: bool = True) -> home.Metaform:
        """A new, empty metaform; a name already used gets `-2` or the next free number, with a notice, STORE-041."""
        made = home.add_metaform(self.project_id, name, activate=activate)
        if made.name == name:
            return made
        notice = Notice('name', f'{self.project_id} already has a metaform named {name}; this one was named '
                                f'{made.name}.')
        return dataclasses.replace(made, notices=(notice,))

    def withdraw_metaform(self, metaform_id: str) -> None:
        """Undo a metaform made by this operation whose first write failed, so a failed write leaves nothing."""
        home.withdraw_metaform(self.project_id, metaform_id)

    def activate_metaform(self, name: str) -> home.Metaform:
        return home.activate_metaform(self.project_id, name)

    def project(self) -> home.Project:
        record = home.project(self.project_id)
        if record is None:
            raise StoreError(f'Project {self.project_id} is no longer registered.', 'metaform list projects')
        return record
