"""The data access object: the only code that opens a store or issues SQL, STORE-023.

`Store(project)` reads and writes the active metaform of one registered
project. Writes are STORE-024, reads are STORE-025. Every write is one
transaction; every read is one read transaction and goes through an index,
STORE-005. Selection, masking, hiding and the transitive rules of properties
are applied inside every read, so no caller computes or bypasses them,
STORE-019.

`Store` is the one public door. Each method opens its transaction and calls one
operation of the internal modules, which each take that `Tx`: `writes` for the
map's objects, `layering` for layers and refining the metaform, `reads` for
native reads, and module declarations for feature operations. No write is refused
for its content, BASE-044 and STORE-026: what does not fit is stored as given and named
in the result's `notices`.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Generator, Iterable, Sequence
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar, cast

from .. import changes, home, loader
from ..errors import StoreError
from . import history, layering, log, numbers, operations, promotion, reads, recorder, rows, tables, views, writes
from . import refs as ref_records
from .paging import LIMIT, sliced
from .records import (
    Citation,
    ContextView,
    Element,
    GraphPage,
    Item,
    Join,
    Layer,
    Node,
    NodeView,
    Notice,
    Outcome,
    Page,
    Property,
    Provenance,
    Record,
    Recording,
    Ref,
    Roots,
    Selection,
    SourceRef,
    Version,
    Where,
)
from .selection import Resolver
from .session import Session, Tx
from .tables import Place, Tables, TableTx

RecordT = TypeVar('RecordT', bound=Record)


class Store:
    """Reads and writes one project's active metaform.

    `module` names the module the store works for; a layer this store makes for a write sent without one records it
    as its owner, LAYER-001. `write_layer` names the layer a write sent without one goes to instead, the folder's
    `write_layer` setting, BASE-060.
    """

    def __init__(self, project: str, *, toggled: Sequence[str] | None = None, base: str | None = None,
                 module: str | None = None, write_layer: str | None = None) -> None:
        record = home.project(project)
        if record is None:
            raise StoreError(f'No project {project} is registered.', 'metaform list projects')
        self._record = record
        self._session = Session(record.project_id, base)
        self.toggled: tuple[str, ...] = tuple(toggled or ())
        self.module = module
        self.write_layer = write_layer

    # ------------------------------------------------------------------ plumbing

    def _follow_enabled(self) -> None:
        if not self._session.in_atomic and not loader.request_followed():
            loader.follow_enabled()

    def __getattr__(self, name: str) -> Any:
        """An enabled module's operation, run by the DAO in one transaction."""
        self._follow_enabled()
        found = operations.operation(name)
        if found is None:
            raise AttributeError(name)
        def run(*args: Any, **kwargs: Any) -> Any:
            with (self._write() if found.write else self._read(required=operations.preparation(name))) as tx:
                return operations.invoke(tx, name, *args, **kwargs)
        return run

    @property
    def project_id(self) -> str:
        return self._record.project_id

    @property
    def in_atomic(self) -> bool:
        """Whether this store's writes join an `atomic()` block open now, so a write of another store made here would
        take that store's lock while this one's is held, STORE-024."""
        return self._session.in_atomic

    @contextmanager
    def atomic(self) -> Generator[None, None, None]:
        """Every write inside the block commits together, or none does, STORE-024."""
        self._follow_enabled()
        with self._session.atomic():
            yield

    @contextmanager
    def _write(self) -> Generator[Tx, None, None]:
        self._follow_enabled()
        try:
            with self._session.write() as tx:
                tx.toggled = self.toggled
                yield tx
        except sqlite3.IntegrityError as error:
            raise StoreError(f'The write does not fit the store: {error}.', 'metaform help map knowledge') from None

    @contextmanager
    def _read(self, *, required: tuple[str, Tables] | None = None) -> Generator[Tx, None, None]:
        self._follow_enabled()
        with self._session.read(required=required) as tx:
            tx.toggled = self.toggled
            yield tx

    def _resolver(self, tx: Tx, selection: Sequence[str] | None) -> Resolver:
        return reads.resolver(tx, selection, self.toggled)

    def _named(self, tx: Tx, layer: str | None) -> tuple[str, Notice | None]:
        """The layer a write goes to: the one named, else the store's write layer, BASE-060, else a new building layer
        `unnamed-<UTC timestamp>`, LAYER-001."""
        if layer:
            return layer, None
        if self.write_layer:
            if tx.base.layer_by_name(self.write_layer) is None:
                raise StoreError(f"No layer {self.write_layer}, which this folder's write_layer setting names.",
                                 'metaform unset --write-layer, or name the layer with layer=<name>')
            return self.write_layer, None
        stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
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

    def complete(self, layer: str, provenance: dict[str, Any], result_id: str | None = None) -> Outcome:
        """Fill in what a layer still being built lacks of its provenance and its result id, LAYER-010."""
        with self._write() as tx:
            return layering.complete(tx, layer, provenance, result_id)

    def finish(self, layer: str) -> Layer | Outcome:
        """Mark a layer ready, STORE-024."""
        with self._write() as tx:
            done = layering.finish(tx, layer)
        if isinstance(done, Layer):
            recorder.let_go(self.project_id, done.id)  # a finished intake is no longer being recorded
        return done

    def discard(self, layer: str) -> Outcome:
        """Delete a knowledge layer's content and the layer, or an intake layer still building, which is not the map
        yet; identity and type rows stay, STORE-032."""
        with self._write() as tx:
            gone = rows.layer(tx, layer).id
            done = layering.discard(tx, layer)
        if not any(one.id == gone for one in self.layers(limit=0).results):
            recorder.let_go(self.project_id, gone)
        return done

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

    def rename_layer(self, layer: str, name: str, module: str) -> Outcome:
        """Rename a layer and its owning module in place, for a module whose id changed."""
        with self._write() as tx:
            return layering.rename(tx, layer, name, module)

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

    def add_element(self, layer: str | None, address: Any, *, name_length: Any = None, role: Any = None,
                    name: Any = None) -> Element | Outcome:
        """Write an element, its address, name_length, name and role, or return the one already at the
        address, STORE-009."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_element(tx, named, address, name_length=name_length, role=role, name=name),
                               notice)

    def add_join(self, layer: str | None, receiver: Any, elements: Any, *, purpose: Any = None, ef: Any = None,
                 ifd: Any = None, type: Any = 'purpose') -> Join | Outcome:
        """Write one join: held by its receiver, holding the elements that serve its purpose, with its
        type, purpose, ef and ifd, STORE-010."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_join(tx, named, receiver, elements, purpose=purpose, ef=ef, ifd=ifd,
                                               type=type), notice)

    def promote_join(self, join: str, address: Any, *, name: Any = None, name_length: Any = None,
                     role: Any = None, reason: Any = 'Promote the join to an element.') -> Join | Outcome:
        """Associate a join with an ordinary element by address, keeping its ends and attachments, MAP-054.

        Element creation and association share one transaction. Intake joins retain
        earlier versions. Repeating the same association adds no join version.
        """
        with self._write() as tx:
            return promotion.promote(tx, join, address, name=name, name_length=name_length, role=role, reason=reason)

    def add_ref(self, owner: str, key: str, value: str) -> Ref | Outcome:
        """Add one ref to a thing's current version in a knowledge or mutable layer, STORE-012."""
        with self._write() as tx:
            return writes.add_ref(tx, owner, key, value)

    def link_ref(self, key: Any, value: Any, node: Node, *, name: str | None = None,
                 details: Iterable[tuple[str, str]] = (), by: str | None = None,
                 why: str | None = None) -> SourceRef | Outcome:
        """Link a ref at a node, a record of the sources layer with an id that lasts, STORE-012: a new one, named
        `name` or from what it names, or the ref already naming this key and value at this node linked again. A ref
        never moves: linked at another node, the same key and value is a second ref there."""
        with self._write() as tx:
            return ref_records.link(tx, key, value, node, name=name, details=details, by=by, why=why)

    def place_refs(self, node: Node, refs: Iterable[Any], *, by: str | None = None,
                   why: str | None = None) -> list[Notice]:
        """The refs given for a node, linked there, replacing the refs linked at it, MAP-021."""
        with self._write() as tx:
            return ref_records.place(tx, node, refs, by=by, why=why)

    def unlink_ref(self, ref: str, *, by: str | None = None, why: str | None = None) -> Outcome:
        """Remove a ref, by its id or its name, as a version its history keeps."""
        with self._write() as tx:
            found = ref_records.read(tx, ref)
            if found is None:
                raise StoreError(f'No ref is named {ref}.', 'metaform map node node=element:<address>')
            return ref_records.unlink(tx, found.id, by=by, why=why)

    def ref(self, name: str) -> SourceRef | None:
        """A ref by its id, its ref_id or its name `{ref_id}@{address}:{join}`, with where it is linked now."""
        with self._read() as tx:
            return ref_records.read(tx, name)

    def refs(self, node: Node | None = None) -> tuple[SourceRef, ...]:
        """Every current ref of the sources layer, or those linked at one node, MAP-021."""
        with self._read() as tx:
            return ref_records.current(tx, node)

    def add_item(self, layer: str | None, target: Node, value: Any, *, link: Node | None = None,
                 refs: Iterable[Any] = (), extra: Any = None, read_first: Any = False, always_show: Any = False,
                 task: Any = False, condition: Any = None) -> Item | Outcome:
        """Attach one value of the layer's variable at one node, with an optional link to another, STORE-015; an
        item flagged task adds a ticket at its node instead of storing the flag, LAYER-021."""
        with self._write() as tx:
            named, notice = self._named(tx, layer)
            return self._noted(writes.add_item(tx, named, target, value, link=link, refs=refs, extra=extra,
                                               read_first=read_first, always_show=always_show, task=task,
                                               condition=condition), notice)

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
        """Change a thing of a knowledge layer, or of a building intake, in place, STORE-032. A
        join's receiver, provider and parent move it, MAP-003; an element's address never changes, MAP-015."""
        with self._write() as tx:
            return writes.edit(tx, thing, changes)


    def remove(self, thing: str | int) -> Outcome:
        """Delete a row a knowledge layer or a building intake wrote, with its refs, STORE-032."""
        with self._write() as tx:
            return writes.remove(tx, thing)

    # ------------------------------------------------------------ refining

    def refine(self, thing: str, changes: dict[str, Any] | None = None, *, remove: bool = False, reason: Any,
               evidence: Any = None) -> Version | Outcome:
        """Write a change or removal of a thing of the metaform as its newest version in the metaform's own layer,
        keeping every earlier version, LAYER-025."""
        with self._write() as tx:
            return layering.refine(tx, thing, changes, remove=remove, reason=reason, evidence=evidence)


    # ------------------------------------------------------- item numbers

    def number(self, address: str) -> int:
        """The next number at an address, for an item written there: one counter per address in the project's own
        database, counting up from 1 and never reused, `numbers.py`."""
        return numbers.take(numbers.project_folder(self.project_id), address)

    def latest_number(self, address: str) -> int:
        """The last number taken at an address, 0 when none has been."""
        return numbers.latest(numbers.project_folder(self.project_id), address)

    def last_session(self, address: str, *, besides: str | None = None) -> tuple[str, int, int, int] | None:
        """What the last agent session other than `besides` numbered at an address: its session, the first and last
        number it took there and how many, `numbers.last_session`; None when no session is known to have taken one."""
        return numbers.last_session(numbers.project_folder(self.project_id), address, besides=besides)

    # ------------------------------------------------------- a module's own tables

    @contextmanager
    def tables(self, *, write: bool = True) -> Generator[TableTx, None, None]:
        """One transaction on the tables the store's module declares, STORE-045: on the store of the first table it
        touches, the metaform's or the project's, created or upgraded to the module's version when first reached.
        Inside `atomic()` a metaform-level table joins the map's transaction."""
        self._follow_enabled()
        declared = tables.declared(self.module)
        module = cast(str, self.module)
        with ExitStack() as stack:
            held: list[TableTx] = []  # the transaction, whose `about` the write's change carries

            def opener(place: Place) -> tuple[sqlite3.Connection, Path, bool]:
                if place == 'metaform':
                    return self._metaform_tables(stack, module, declared, write, held)
                return self._project_tables(stack, module, declared, write, held)
            given = TableTx(module, declared, write=write, opener=opener)
            held.append(given)
            yield given

    def _metaform_tables(self, stack: ExitStack, module: str, declared: Tables, write: bool,
                         held: Sequence[TableTx] = ()) -> tuple[sqlite3.Connection, Path, bool]:
        if write:
            tx = stack.enter_context(self._write())
            if held:  # before the write commits and notes its change: what the module's writes said they concern
                stack.callback(lambda: [tx.about.setdefault(key, set()).update(value)
                                        for key, value in held[0].about.items()])
            tables.ensure(tx.db, tx.path, module, declared, 'metaform')
            return tx.db, tx.path, True
        reading = ExitStack()
        try:
            tx = reading.enter_context(self._read())
            found = tables.state(tx.db, module, declared, 'metaform')
            if found in ('older', 'update'):  # an upgrade or an addition is a write, made before the read begins
                reading.close()
                with self._write() as upgrading:
                    tables.ensure(upgrading.db, upgrading.path, module, declared, 'metaform')
                tx = reading.enter_context(self._read())
                found = tables.state(tx.db, module, declared, 'metaform')
        except BaseException:
            reading.close()
            raise
        stack.enter_context(reading)
        return tx.db, tx.path, found == 'ready'

    @contextmanager
    def _project_write(self, path: Path, held: Sequence[TableTx] = ()) -> Generator[sqlite3.Connection, None, None]:
        """A write transaction on a project-level module store, noted after its commit when it changed rows, as a
        metaform store's write is, so the chassis announces it when the command ends, VIEW-018. The project's map
        presents what a module keeps for the project, such as the memories at its nodes, so the change is noted for
        the active metaform, or for the project's metaforms when it has none."""
        with tables.project_transaction(path, write=True) as db:
            written = changes.watch(db)
            yield db
            changed = db.total_changes
        if changed:
            active = home.active_base(self.project_id)
            changes.note(self.project_id, active.id if active is not None else None, written,
                         about=held[0].about or None if held else None)

    def _project_tables(self, stack: ExitStack, module: str, declared: Tables, write: bool,
                        held: Sequence[TableTx] = ()) -> tuple[sqlite3.Connection, Path, bool]:
        path = tables.project_store(self.project_id, module)
        if write:
            db = stack.enter_context(self._project_write(path, held))
            tables.ensure(db, path, module, declared, 'project')
            return db, path, True
        reading = ExitStack()
        try:
            db = reading.enter_context(tables.project_transaction(path, write=False))
            found = tables.state(db, module, declared, 'project')
            if found in ('older', 'update'):
                reading.close()
                with tables.project_transaction(path, write=True) as upgrading:
                    tables.ensure(upgrading, path, module, declared, 'project')
                db = reading.enter_context(tables.project_transaction(path, write=False))
                found = tables.state(db, module, declared, 'project')
        except BaseException:
            reading.close()
            raise
        stack.enter_context(reading)
        return db, path, found == 'ready'

    # ================================================================== reads

    def element(self, ref: str, *, selection: Sequence[str] | None = None, raw: bool = False) -> Element | None:
        """One element by address or id: its address, name_length, name, role and short name."""
        with self._read() as tx:
            return reads.element(tx, None if raw else self._resolver(tx, selection), ref)

    def joins(self, element: str, as_: str = 'receiver', *, selection: Sequence[str] | None = None,
              raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Join]:
        """The joins an element receives, or those that hold it, as provider, each with its layer."""
        with self._read() as tx:
            return reads.joins(tx, None if raw else self._resolver(tx, selection), element, as_, limit, after)

    def identity(self, element: str, *, selection: Sequence[str] | None = None, raw: bool = False,
                 limit: int = LIMIT, after: str | None = None) -> Page[Join]:
        """Every current join the element provides for: who receives it, why, and how, STORE-010."""
        return self.joins(element, 'provider', selection=selection, raw=raw, limit=limit, after=after)

    def join_ends(self, join: str) -> tuple[str, str] | None:
        """One join's receiver and the first element it holds, by address, read from every stored layer as a work
        record reads them, STORE-010. None for no current join."""
        with self._read() as tx:
            return reads.join_ends(tx, join)

    def purpose(self, receiver: Any, provider: Any, address: Any = None) -> Node:
        """The node an agent names by address, MAP-005: the join of `receiver` that holds `provider`, or with `address`
        the element at that address it holds, read from every stored layer as refine reads them. It stops when the map
        holds none, or several that their addresses cannot tell apart, naming their purposes."""
        said = f'the purpose of {receiver} served by {provider}'
        if receiver is None or provider is None:
            raise StoreError(f'{said}: a purpose is named by its receiver and its provider together.',
                             'metaform map where <receiver>')
        owner = self.element(str(receiver), raw=True)
        if owner is None:
            raise StoreError(f'{receiver} is not an element of the map here.', f'metaform map where {receiver}')
        found = [held for held in self.joins(owner.id, raw=True, limit=0).results
                 if any(each.address == provider for each in held.elements)]
        if not found:
            raise StoreError(f'{receiver} has no purpose served by {provider}.', f'metaform map where {receiver}')
        if len(found) > 1:
            purposes = '; '.join(repr(held.purpose) for held in found)
            raise StoreError(f'{receiver} has {len(found)} purposes served by {provider}, which their addresses '
                             f'cannot tell apart, with the purposes {purposes}.', f'metaform map where {receiver}')
        if address is None:
            return Node('join', found[0].id)
        parts = [each for each in found[0].elements if each.address == address]
        if not parts:
            raise StoreError(f'{address} is not held by {said}.', f'metaform map where {receiver}')
        return Node('element', parts[0].element_id)

    def where(self, address: str, *, selection: Sequence[str] | None = None, raw: bool = False,
              full: bool = False) -> Where | None:
        """One read of an address: the element, the joins that hold it, the joins it receives, each with the elements
        it holds, its open work records and the layers in context at it, STORE-025; `full` keeps ids and empty fields
        in its plain data."""
        with self._read() as tx:
            return reads.where(tx, self._resolver(tx, selection), raw, address, full)

    def children(self, address: str, *, limit: int = LIMIT, after: str | None = None) -> Page[str]:
        """The next types toward the leaves."""
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
        """The properties that apply at an address, and those attached toward the leaves from it that are visible
        there, STORE-035."""
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
        """Every version of a thing in the order it was written: the row that added it, then each refinement."""
        with self._read() as tx:
            return reads.history(tx, thing, limit, after)

    def layers(self, tag: str | None = None, kind: str | None = None, module: str | None = None, *,
               limit: int = LIMIT, after: str | None = None) -> Page[Layer]:
        """The layers with their declaration, tags, state, hidden and toggled flags, LAYER-019."""
        with self._read() as tx:
            return reads.layers(tx, self._resolver(tx, None), tag, kind, module, limit, after)

    # ------------------------------------------------------------------ history, PROJ-010 to PROJ-024

    def add_origin(self) -> history.Origin:
        """Establish an origin from the project's current state, or report the one of the same content, PROJ-014."""
        return history.add_origin(self.project_id)

    def origins(self) -> tuple[history.Origin, ...]:
        return history.origins(self.project_id)

    def add_variant(self, folder: Path, origin: str | None = None, *, remove: bool = False,
                    provenance: dict[str, object] | None = None) -> history.Variant:
        """Collect a folder as a variant of an origin, the selected one unless named, PROJ-017."""
        return history.add_variant(self.project_id, folder, origin, remove=remove, provenance=provenance)

    def variants(self, origin: str | None = None) -> tuple[history.Variant, ...]:
        return history.variants(self.project_id, origin)

    def extract(self, ids: Sequence[str], folder: Path, origin: str | None = None) -> list[Path]:
        """Reconstruct variants into folders with Python alone, PROJ-018."""
        return history.extract(self.project_id, ids, folder, origin)

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
        """The map's entry: the CQU and DE with the joins they receive, and every root element, one page, STORE-025."""
        with self._read() as tx:
            return reads.roots(tx, None if raw else self._resolver(tx, selection), limit, after)

    def graph(self, *, selection: Sequence[str] | None = None, raw: bool = False, limit: int = LIMIT,
              after: str | None = None) -> GraphPage:
        """A page of the map in address order, with parents and joins, each with the elements it holds, VIEW-010."""
        with self._read() as tx:
            return reads.graph(tx, None if raw else self._resolver(tx, selection), limit, after)

    def layer_graph(self, layer: str) -> GraphPage:
        """One layer's own elements and joins, building or finished; not a context read, BASE-039."""
        with self._read() as tx:
            return reads.layer_graph(tx, layer)

    def cypher(self, query: str, layers: Sequence[str] | None = None) -> Any:
        """A Cypher query over the base's graph in memory, STORE-046, seeing what the layers in view show: the layers
        named, or else the ones turned on."""
        with self._read() as tx:
            return reads.cypher(tx, query, layers)

    def ops(self, after: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        """The ops of the log past a sequence, as a page applies them, STORE-046 and VIEW-018."""
        with self._read() as tx:
            return log.read_ops(tx.db, after, limit)

    def sequence(self) -> int:
        """The sequence of the last op of the base, STORE-046."""
        with self._read() as tx:
            return tx.base.seq


    # -------------------------------------------------------------- metaforms

    def layer_ref(self, layer: str) -> Layer:
        """One layer by name or id, with its declaration."""
        with self._read() as tx:
            return views.layer(tx, rows.layer(tx, layer))

    def has_intake(self) -> bool:
        with self._read() as tx:
            return reads.has_intake(tx)

    def intake_bases(self) -> tuple[str, ...]:
        """The names of the project's metaforms that hold a finished intake, in creation order, whichever is active:
        whether the project has been mapped is the project's, not the active metaform's, which a new base or a clear
        may leave empty, MCP-009 as amended 2026-10-17. A metaform that cannot be read is left out."""
        found: list[str] = []
        for base in home.bases(self.project_id):
            try:
                if Store(self.project_id, base=base.id).has_intake():
                    found.append(base.name)
            except StoreError:
                continue
        return tuple(found)

    def bases(self, *, limit: int = LIMIT, after: str | None = None) -> Page[home.Base]:
        return sliced(home.bases(self.project_id), limit, after)

    def intake_building(self) -> Page[Recording]:
        """Every intake building for this project, in whichever of its metaforms, BASE-039: a page of none or one,
        and of every one when more than one was opened, so none is hidden. Each says whether an agent records it now,
        how many parts it holds and when it last recorded anything; one no agent records was left unfinished. While an
        intake agent Metaform started lives, its runner holding `intake.agent`, the intake its records go into, the
        first, is being recorded, whatever surface it records through: its MCP server, or the command line."""
        found: list[Recording] = []
        now = recorder.held(self.project_id)
        agent = recorder.agent_held(self.project_id) is not None
        for metaform in home.bases(self.project_id):
            building = Store(self.project_id, base=metaform.id)
            for layer in building.layers(kind='base', limit=0).results:
                if layer.ready is None:
                    with building._read() as tx:
                        parts = len(reads.layer_graph(tx, layer.id).elements)
                        last = tx.db.execute('SELECT max(at) FROM ops WHERE layer_id=?', (layer.id,)).fetchone()[0]
                    found.append(Recording(metaform.id, metaform.name, metaform.active, layer,
                                           layer.id == now or agent and not found, parts, last))
        return Page(tuple(found), None)

    def intake_agent(self) -> dict[str, Any] | None:
        """The intake agent Metaform started that lives now for this project, held by its runner for as long as it
        lives: its launch record (work, agent, pid, since, map), or None, BASE-039."""
        return recorder.agent_held(self.project_id)

    def intake_launch(self) -> dict[str, Any] | None:
        """The intake launch last noted for this project, live or not: the caller checks its runner."""
        return recorder.launch_noted(self.project_id)

    def note_intake_launch(self, record: dict[str, Any]) -> None:
        """Note an intake agent launched now, under the intake lock, before its runner holds `intake.agent`."""
        recorder.note_launch(self.project_id, record)

    def forget_intake_launch(self, work_id: str) -> None:
        """Forget this work's intake launch, stopped before its runner held `intake.agent`."""
        recorder.forget_launch(self.project_id, work_id)

    def hold_intake_agent(self, work_id: str) -> dict[str, Any] | None:
        """Hold `intake.agent` for this process, the intake agent's runner, while it lives: None once held, or the
        launch record of the live runner that holds it already."""
        return recorder.hold_agent(self.project_id, work_id)

    def intake_recording(self) -> Page[Recording]:
        """The intake an agent records now for this project, BASE-039: building, with the process of the agent
        recording it alive. An intake building that no agent records was left unfinished; `intake_building` has it."""
        return Page(tuple(one for one in self.intake_building().results if one.recording), None)

    def hold_intake(self, layer: str) -> None:
        """Say that this process's agent records the intake into this building layer of the bound base now, for as
        long as the process lives; only a process serving one agent's conversation says so, BASE-039."""
        bound = self.bound_base()
        if bound is not None:
            recorder.hold(self.project_id, bound.id, self.layer_ref(layer).id)

    def active_base(self) -> home.Base | None:
        return home.active_base(self.project_id)

    def bound_base(self) -> home.Base | None:
        """The metaform this DAO reads, explicitly bound or currently active."""
        bound = self._session.base_id
        return home.base_by_id(self.project_id, bound) if bound is not None else self.active_base()

    def add_base(self, name: str, *, activate: bool = True) -> home.Base:
        """A new, empty metaform; a name already used gets `-2` or the next free number, with a notice, STORE-041."""
        made = home.add_base(self.project_id, name, activate=activate)
        if made.name == name:
            return made
        notice = Notice('name', f'{self.project_id} already has a metaform named {name}; this one was named '
                                f'{made.name}.')
        return dataclasses.replace(made, notices=(notice,))

    def collapse(self, name: str) -> home.Base:
        """The current functional map written as a new metaform of one intake layer and made active, LAYER-026.

        Element and join ids carry over; the old metaform is kept whole with its history. A taken name gets `-2`
        with a notice, as `add_base` does. Knowledge, memory and tickets stay with the old metaform until D111
        2 and 3 of 3 are answered, and a notice says so.
        """
        from .exchange import collapsed, export_document, import_document
        old = self.bound_base()
        if old is None:
            raise StoreError(f'{self.project_id} has no base to collapse.', 'metaform map bases')
        document = export_document([self.project_id], metaform=old.name)
        made = self.add_base(name, activate=False)
        try:
            import_document(collapsed(document, made.name, workflow='collapse', role='collapse',
                                      base_id=made.id, created=made.created), self.project_id)
            home.activate_base(self.project_id, made.name)
        except BaseException:
            self.withdraw_base(made.id)
            raise
        kept = Notice('kept', f'Knowledge and memory layers, sources and tickets stay with {old.name}; to switch '
                              f'back: metaform map activate {old.name}')
        return dataclasses.replace(made, active=True, notices=(*made.notices, kept))

    def withdraw_base(self, base_id: str) -> None:
        """Undo a metaform made by this operation whose first write failed, so a failed write leaves nothing."""
        home.withdraw_base(self.project_id, base_id)

    def activate_base(self, name: str) -> home.Base:
        return home.activate_base(self.project_id, name)

    def project(self) -> home.Project:
        record = home.project(self.project_id)
        if record is None:
            raise StoreError(f'Project {self.project_id} is no longer registered.', 'metaform list projects')
        return record
