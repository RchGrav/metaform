// The body of the Entity panel: the folder of one element, read from the one specification
// (ARCHITECTURE.md section 1), with the controls that edit it. Each edit is a `Change` that the
// store sends when the user confirms it (src/review/store.ts). Every word comes from strings.ts
// and src/review/strings.ts.

import { useState } from "react";
import type { Address, SummarySheet } from "../source";
import type { Change } from "../spec/changes";
import { REVIEW_LAYER, fieldEvidence, layerEvidence, wantEvidence } from "../spec/evidence";
import type { Evidence } from "../spec/evidence";
import { SPECIFICATION_LAYER } from "../spec/markdown";
import { FIELD_NAMES, elementAt, wantedBy } from "../spec/model";
import type { FieldName, Spec, SpecWant, WantPart } from "../spec/model";
import * as strings from "../strings";
import { BlockForm, PartNotes, StatusWord, ValueEditor, blockOf, recordOf, writableLine } from "../review/Editors";
import type { BlockDraft, Choice } from "../review/Editors";
import { keyOf, newChangeId, partKey } from "../review/store";
import type { Review, Writable } from "../review/store";
import { DIRECTIONS, ROLES, edit as words, fieldLabels, partLabels } from "../review/strings";

/** What the page hands the Entity panel about the selected element. */
export interface EntityFolder {
  address: Address;
  sheet: SummarySheet | null;
  /** The addresses directly beneath this one. */
  beneath: Address[];
  /** The records of each layer the element holds, once they are read; null while they load. */
  records: Record<string, unknown[]> | null;
  /** The project's own name for an element, or its last address segment. */
  nameOf: (address: Address) => string;
  opensProject: boolean;
  /** Present when the element is outside the project and its own map can be read (seam gap 4). */
  onOpenMap?: () => void;
  onClose: () => void;
  onFocus: () => void;
  onOpenProject: () => void;
  onSelect: (address: Address) => void;
}

/** The props of `Entity`: the folder, the specification every panel shows, and the store that takes the edits. */
export interface EntityProps extends EntityFolder {
  spec: Spec | null;
  review: Review | null;
}

const READ_ONLY: Writable = { can: false, reason: null };
const STATUS_CHOICES: readonly Choice[] = [{ value: "", label: words.built }, { value: "un_built", label: words.notBuilt }];
const DIRECTION_CHOICES: readonly Choice[] = DIRECTIONS.map((value) => ({ value, label: value }));

/** The status word for a part the user wrote or accepted. A derived status is shown in the Evidence panel only. */
function Authored({ evidence, pending }: { evidence: Evidence | null; pending: boolean }) {
  if (!evidence || (evidence.status !== "user-authored" && evidence.status !== "accepted")) return null;
  return <StatusWord status={evidence.status} recorded={!pending} />;
}

/** One record of a layer, as text a person can read. */
function LayerRecord({ record }: { record: unknown }) {
  if (typeof record === "string") {
    return /^https?:\/\//.test(record) ? <a href={record} target="_blank" rel="noreferrer noopener">{record}</a> : <span>{record}</span>;
  }
  if (record === null || typeof record !== "object") return <span>{String(record)}</span>;
  const fields = record as Record<string, unknown>;
  // A block of prose: a heading at its level, then the text (R-6.25).
  if (typeof fields.text === "string") {
    const level = typeof fields.level === "number" ? fields.level : 0;
    return (
      <div className={`block block-${level}`}>
        {typeof fields.title === "string" && (
          <p className="block-title">
            {fields.title}
            {typeof fields.code === "string" && <code>{fields.code}</code>}
          </p>
        )}
        {fields.text !== "" && <p className="block-text">{fields.text}</p>}
      </div>
    );
  }
  const head = fields.frontmatter && typeof fields.frontmatter === "object" ? (fields.frontmatter as Record<string, unknown>) : fields;
  const name = typeof head.name === "string" ? head.name : null;
  const rest = Object.entries(head).filter(([key, value]) => key !== "name" && (typeof value === "string" || Array.isArray(value)));
  return (
    <div className="block">
      {name !== null && <p className="block-title">{name}</p>}
      {rest.map(([key, value]) => (
        <p className="block-text" key={key}>
          <span className="term">{key}</span> {Array.isArray(value) ? value.map(String).join("; ") : String(value)}
        </p>
      ))}
    </div>
  );
}

/** What every editable part needs: the specification, the store, and the function that sends a change. */
interface Editing {
  spec: Spec;
  review: Review | null;
  writable: Writable;
  send: (change: Change) => void;
  pending: (key: string) => boolean;
}

/** One relationship, in the words of the map: the other element, then why, how and direction, each with its Edit control. */
function Relationship(props: { holder: Address; want: SpecWant; other: Address; nameOf: (address: Address) => string; editing: Editing; onSelect: (address: Address) => void }) {
  const { holder, want, nameOf, editing } = props;
  const key = partKey(holder, `want ${want.to}`);
  const direction = DIRECTIONS.find((d) => d === want.direction);
  const set = (part: WantPart) => (value: string) =>
    editing.send({ id: newChangeId(), kind: "set-want", address: holder, to: want.to, part, value });
  return (
    <li className="relationship">
      <button type="button" className="link relationship-other" onClick={() => props.onSelect(props.other)} title={props.other}>
        {nameOf(props.other)}
      </button>{" "}
      <Authored evidence={wantEvidence(editing.spec, holder, want.to)} pending={editing.pending(key)} />
      <p>
        <span className="term">{strings.intake.op.long}</span>
        <ValueEditor label={partLabels.why} value={want.why} multiline writable={editing.writable} onConfirm={set("why")}>{want.why}</ValueEditor>
      </p>
      <p>
        <span className="term">{strings.intake.ef.long}</span>
        <ValueEditor label={partLabels.how} value={want.how} multiline writable={editing.writable} onConfirm={set("how")}>{want.how}</ValueEditor>
      </p>
      <p className="direction">
        <span className="term">{strings.intake.ifd.long}</span>
        <ValueEditor label={partLabels.direction} value={want.direction} choices={DIRECTION_CHOICES} writable={editing.writable} onConfirm={set("direction")}>
          {direction ? strings.intake.ifdValue(direction, nameOf(holder), nameOf(want.to)) : want.direction}
        </ValueEditor>
      </p>
      {editing.review && <PartNotes review={editing.review} partKey={key} />}
    </li>
  );
}

/** The blocks of the specification layer at one element. A block can be edited, added and removed; each is one change to the layer's list. */
function Blocks({ address, records, editing }: { address: Address; records: unknown[]; editing: Editing }) {
  const [open, setOpen] = useState<number | "new" | null>(null);
  const [removing, setRemoving] = useState<number | null>(null);
  const key = partKey(address, SPECIFICATION_LAYER);
  const send = (next: unknown[]) => {
    setOpen(null);
    setRemoving(null);
    editing.send({ id: newChangeId(), kind: "set-layer", address, layer: SPECIFICATION_LAYER, records: next });
  };
  const replace = (index: number) => (draft: BlockDraft) => send(records.map((record, i) => (i === index ? recordOf(draft, record) : record)));
  const { can } = editing.writable;
  const reason = can ? undefined : writableLine(editing.writable) ?? undefined;
  return (
    <section className="layer">
      <h3>
        {strings.details.layer(SPECIFICATION_LAYER, records.length)}{" "}
        <Authored evidence={layerEvidence(editing.spec, address, SPECIFICATION_LAYER)} pending={editing.pending(key)} />
      </h3>
      {records.length === 0 && <p className="empty">{words.noBlocks}</p>}
      {records.map((record, index) =>
        open === index ? (
          <BlockForm key={index} start={blockOf(record)} first={index === 0} onConfirm={replace(index)} onCancel={() => setOpen(null)} />
        ) : (
          <div key={index} className="block-row">
            <LayerRecord record={record} />
            {removing === index ? (
              <span className="edit-actions" role="group" aria-label={words.removeBlockAsk}>
                <span>{words.removeBlockAsk}</span>
                <button type="button" className="edit-confirm" autoFocus onClick={() => send(records.filter((_, i) => i !== index))}>{words.confirm}</button>
                <button type="button" onClick={() => setRemoving(null)}>{words.cancel}</button>
              </span>
            ) : (
              <span className="edit-actions">
                <button type="button" className="edit-button" disabled={!can} title={reason} aria-label={words.editBlock(index + 1)} onClick={() => setOpen(index)}>{words.edit}</button>
                <button type="button" className="edit-button" disabled={!can} title={reason} aria-label={words.removeBlockWhat(index + 1)} onClick={() => setRemoving(index)}>{words.removeBlock}</button>
              </span>
            )}
          </div>
        ),
      )}
      {open === "new" ? (
        <BlockForm
          start={{ level: records.length === 0 ? 0 : 1, title: "", text: "" }}
          first={records.length === 0}
          onConfirm={(draft) => send([...records, recordOf(draft)])}
          onCancel={() => setOpen(null)}
        />
      ) : (
        <button type="button" className="edit-button" disabled={!can} title={reason} onClick={() => setOpen("new")}>{words.addBlock}</button>
      )}
      {editing.review && <PartNotes review={editing.review} partKey={key} />}
    </section>
  );
}

/**
 * The folder of one element: what it is, who it serves and why, what it relies on and how, and
 * the knowledge kept there, as text. The user can edit the element's fields, each relationship
 * and the blocks of the specification layer.
 */
export function Entity(props: EntityProps) {
  const { address, sheet, spec, review } = props;
  const element = spec ? elementAt(spec, address) : undefined;
  const writable = review?.state.writable ?? READ_ONLY;
  const nameOf = (at: Address): string => {
    const name = spec ? elementAt(spec, at)?.name : undefined;
    return name !== undefined && name.trim() !== "" ? name : props.nameOf(at);
  };
  const editing: Editing | null = spec
    ? {
        spec,
        review,
        writable,
        send: (change) => void review?.store.edit(change),
        pending: (key) => review?.state.pending.some((entry) => keyOf(entry.change) === key) ?? false,
      }
    : null;
  const sheetText = (key: string) => (typeof sheet?.element[key] === "string" ? (sheet.element[key] as string) : undefined);
  const field = (key: FieldName): string => (spec ? element?.[key] : sheetText(key)) ?? "";
  const wants = element?.wants ?? [];
  const held = spec ? wantedBy(spec, address) : [];
  const layers = element ? element.layers : props.records ?? {};
  const others = Object.entries(sheet?.element ?? {}).filter(([key, value]) => !(FIELD_NAMES as readonly string[]).includes(key) && typeof value !== "object");
  // A branch is an address that only groups the elements beneath it.
  const branch = spec !== null && element === undefined && props.beneath.length > 0;
  const name = nameOf(address);
  const line = writableLine(writable);
  const blocks = layers[SPECIFICATION_LAYER] ?? [];
  const blocksDefined = spec?.layerDefinitions.some((definition) => definition.field === SPECIFICATION_LAYER) ?? false;

  const fieldRow = (key: FieldName, choices?: readonly Choice[]) => {
    if (!editing || !element) return null;
    const value = field(key);
    const partId = partKey(address, key);
    const shown = key === "status" ? (value === "un_built" ? words.notBuilt : value === "" ? words.built : value) : value === "" ? (key === "role" ? words.noRole : words.none) : value;
    return (
      <div key={key}>
        <dt>{fieldLabels[key]}</dt>
        <dd>
          <ValueEditor
            label={fieldLabels[key]}
            value={value}
            writable={writable}
            {...(choices ? { choices: choices.some((choice) => choice.value === value) ? choices : [{ value, label: shown }, ...choices] } : {})}
            onConfirm={(next) => editing.send({ id: newChangeId(), kind: "set-field", address, field: key, value: next === "" ? null : next })}
          >
            {key === "uri" && /^https?:\/\//.test(value) ? <a href={value} target="_blank" rel="noreferrer noopener">{value}</a> : <span className={value === "" ? "empty" : undefined}>{shown}</span>}
          </ValueEditor>{" "}
          <Authored evidence={value === "" && key !== "status" ? null : fieldEvidence(editing.spec, address, key)} pending={editing.pending(partId)} />
          {review && <PartNotes review={review} partKey={partId} />}
        </dd>
      </div>
    );
  };

  return (
    <aside className="details" aria-label={address}>
      <header>
        <div>
          <h2>{name}</h2>
          {field("technical_name") !== "" && <p className="kind">{field("technical_name")}</p>}
        </div>
        <button type="button" onClick={props.onClose} aria-label={strings.details.close}>×</button>
      </header>
      <p className="chips">
        {field("role") !== "" && <span className={`chip role-${field("role").toLowerCase()}`}>{field("role")}</span>}
        {field("status") === "un_built" && <span className="chip not-built">{strings.details.notBuilt}</span>}
        <code className="chip address" title={strings.details.address}>{address}</code>
      </p>
      <div className="actions">
        <button type="button" onClick={props.onFocus}>{strings.details.setAsFocus}</button>
        {props.opensProject && <button type="button" onClick={props.onOpenProject}>{strings.details.openProject}</button>}
        {props.onOpenMap && <button type="button" onClick={props.onOpenMap}>{strings.details.openItsMap}</button>}
      </div>
      {editing && element && (
        <section className="edit-fields" aria-label={words.fields}>
          {line !== null && <p className={`writable-line${writable.can ? "" : " writable-off"}`} role="note">{line}</p>}
          <dl className="fields">
            {fieldRow("name")}
            {fieldRow("technical_name")}
            {fieldRow("role", ROLES.map((role) => ({ value: role, label: role })))}
            {fieldRow("status", STATUS_CHOICES)}
            {fieldRow("uri")}
            {others.map(([key, value]) => (
              <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>
            ))}
          </dl>
        </section>
      )}
      {editing && element && (blocks.length > 0 || blocksDefined) && <Blocks address={address} records={blocks} editing={editing} />}
      {Object.entries(layers).filter(([layer]) => layer !== SPECIFICATION_LAYER || !editing).map(([layer, records]) => (
        <section key={layer} className="layer">
          <h3>{strings.details.layer(layer, records.length)}</h3>
          {layer === REVIEW_LAYER ? <p className="empty">{strings.details.reviewLayer}</p> : records.map((record, index) => <LayerRecord key={index} record={record} />)}
        </section>
      ))}
      {sheet?.skills && Object.keys(sheet.skills).length > 0 && (
        <section className="layer">
          <h3>{strings.details.layer("skills", Object.keys(sheet.skills).length)}</h3>
          {Object.values(sheet.skills).map((skill) => <LayerRecord key={skill.name} record={skill} />)}
        </section>
      )}
      {branch || !editing ? (
        props.beneath.length > 0 && (
          <>
            <p className="empty">{strings.details.branch(props.beneath.length)}</p>
            <ul className="beneath">
              {props.beneath.map((child) => (
                <li key={child}>
                  <button type="button" className="link" onClick={() => props.onSelect(child)} title={child}>{nameOf(child)}</button>
                </li>
              ))}
            </ul>
          </>
        )
      ) : (
        <>
          <h3>{strings.details.serves(held.length)}</h3>
          {held.length === 0 ? (
            <p className="empty">{strings.details.notWanted}</p>
          ) : (
            <ul className="wants">
              {held.map(({ holder, want }) => (
                <Relationship key={holder} holder={holder} want={want} other={holder} nameOf={nameOf} editing={editing} onSelect={props.onSelect} />
              ))}
            </ul>
          )}
          <h3>{strings.details.reliesOn(wants.length)}</h3>
          {wants.length === 0 ? (
            <p className="empty">{strings.details.noWants}</p>
          ) : (
            <ul className="wants">
              {wants.map((want) => (
                <Relationship key={want.to} holder={address} want={want} other={want.to} nameOf={nameOf} editing={editing} onSelect={props.onSelect} />
              ))}
            </ul>
          )}
        </>
      )}
    </aside>
  );
}
