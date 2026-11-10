// The edit controls of the entity panel: a value with an Edit button, the form that replaces it
// while the user edits, and the notes a refused write leaves at the part. Nothing is written
// until the user confirms; Escape or Cancel discards the draft.

import { useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import type { EvidenceStatus } from "../spec/evidence";
import { statusMarks, statusMeanings, statusWords } from "../spec/strings";
import "../spec/spec.css";
import "./review.css";
import { keyOf } from "./store";
import type { Review, Writable } from "./store";
import { edit as words, evidence as evidenceWords } from "./strings";

/** The line that says why the controls are disabled, or where an edit goes. Null when no line is needed. */
export function writableLine(writable: Writable): string | null {
  if (writable.reason === "sample") return words.sample;
  if (writable.reason === "read-only") return words.readOnly;
  if (writable.reason === "unreachable") return words.unreachable;
  return null;
}

/**
 * A status as a mark and a word. The mark is decoration; the word carries the meaning. `recorded`
 * is true when the status comes from the review history and not from a pending change.
 */
export function StatusWord({ status, recorded = false }: { status: EvidenceStatus; recorded?: boolean }) {
  const meaning =
    recorded && status === "user-authored" ? evidenceWords.userAuthoredRecorded
    : recorded && status === "accepted" ? evidenceWords.acceptedRecorded
    : statusMeanings[status];
  return (
    <span className={`spec-status spec-status-${status}`} title={meaning}>
      <span className="spec-status-mark" aria-hidden="true">{statusMarks[status]}</span>
      <span className="spec-status-word">{statusWords[status]}</span>
    </span>
  );
}

/** The notes at one part: a change the server has not confirmed, a refusal with its correction, or a history that was not recorded. */
export function PartNotes({ review, partKey }: { review: Review; partKey: string }) {
  const { store, state } = review;
  const note = state.notes.find((other) => other.key === partKey);
  const pending = state.pending.some((entry) => keyOf(entry.change) === partKey);
  if (!note && !pending) return null;
  return (
    <div className="part-notes">
      {pending && <p className="part-pending" role="status">{words.pending}</p>}
      {note && (
        <div className={`part-note part-note-${note.kind}`} role="alert">
          <p>{note.kind === "refused" ? words.refused(note.message, note.code) : words.historyFailed(note.message)}</p>
          {note.remediation && (
            <p className="part-remedy">
              {words.remedyCommand} <code>{JSON.stringify(note.remediation)}</code>
            </p>
          )}
          <div className="edit-actions">
            {note.remediation && (
              <button type="button" disabled={!state.writable.can} onClick={() => void store.remedy(partKey)}>{words.remedy}</button>
            )}
            <button type="button" onClick={() => store.dismiss(partKey)}>{words.dismiss}</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** One choice a `ValueEditor` offers. */
export interface Choice {
  value: string;
  label: string;
}

/** The props of `ValueEditor`. */
export interface ValueEditorProps {
  /** The name of the part, such as "why". It labels the input and the Edit button. */
  label: string;
  /** The value the specification holds now. An empty string means none. */
  value: string;
  /** What the page shows for the value while the user does not edit it. */
  children: ReactNode;
  /** The choices of a fixed set. Without them the editor is a text input. */
  choices?: readonly Choice[];
  /** True for a text of several lines. */
  multiline?: boolean;
  /** Whether the page can store an edit, with the reason when it cannot. */
  writable: Writable;
  /** Called with the new value when the user confirms a value that differs. */
  onConfirm: (value: string) => void;
}

/**
 * A value with an Edit button. Edit shows an input with Confirm and Cancel. Enter confirms a
 * one-line text; Escape cancels. The draft is dropped on Cancel and is never written before Confirm.
 */
export function ValueEditor({ label, value, children, choices, multiline, writable, onConfirm }: ValueEditorProps) {
  const [draft, setDraft] = useState<string | null>(null);
  if (draft === null) {
    return (
      <span className="editable">
        <span className="editable-value">{children}</span>
        <button
          type="button"
          className="edit-button"
          disabled={!writable.can}
          aria-label={words.editWhat(label)}
          title={writable.can ? words.editWhat(label) : writableLine(writable) ?? undefined}
          onClick={() => setDraft(value)}
        >
          {words.edit}
        </button>
      </span>
    );
  }
  const confirm = () => {
    const next = draft.trim();
    setDraft(null);
    if (next !== value) onConfirm(next);
  };
  const onKey = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      setDraft(null);
    } else if (event.key === "Enter" && !multiline && !choices) {
      event.preventDefault();
      confirm();
    }
  };
  return (
    <span className="edit-form" onKeyDown={onKey}>
      {choices ? (
        <select aria-label={label} autoFocus value={draft} onChange={(event) => setDraft(event.target.value)}>
          {choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
        </select>
      ) : multiline ? (
        <textarea aria-label={label} autoFocus rows={3} value={draft} onChange={(event) => setDraft(event.target.value)} />
      ) : (
        <input aria-label={label} autoFocus type="text" value={draft} onChange={(event) => setDraft(event.target.value)} />
      )}
      <span className="edit-actions">
        <button type="button" className="edit-confirm" onClick={confirm}>{words.confirm}</button>
        <button type="button" onClick={() => setDraft(null)}>{words.cancel}</button>
      </span>
    </span>
  );
}

/** One block of the specification layer, as the editor holds it. Level 0 is an introduction with no heading. */
export interface BlockDraft {
  level: number;
  title: string;
  text: string;
}

/** The block a record of the specification layer holds. A record of another form gives its text as JSON. */
export function blockOf(record: unknown): BlockDraft {
  if (record !== null && typeof record === "object" && !Array.isArray(record)) {
    const held = record as Record<string, unknown>;
    if (typeof held.text === "string") {
      const titled = typeof held.title === "string";
      return { level: titled ? (typeof held.level === "number" ? held.level : 1) : 0, title: titled ? (held.title as string) : "", text: held.text };
    }
  }
  return { level: 0, title: "", text: typeof record === "string" ? record : JSON.stringify(record) };
}

/** The record for an edited block. Fields the editor does not show, such as `code`, are kept from the record it replaces. */
export function recordOf(draft: BlockDraft, replaced?: unknown): Record<string, unknown> {
  const kept = replaced !== null && typeof replaced === "object" && !Array.isArray(replaced) ? { ...(replaced as Record<string, unknown>) } : {};
  delete kept.level;
  delete kept.title;
  if (draft.level === 0) return { text: draft.text.trim() };
  return { ...kept, level: draft.level, title: draft.title.trim(), text: draft.text.trim() };
}

/** The form for one block: its level, its title and its text, with Confirm and Cancel. */
export function BlockForm(props: { start: BlockDraft; first: boolean; onConfirm: (draft: BlockDraft) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState(props.start);
  const levels = props.first ? [0, 1, 2, 3, 4] : [1, 2, 3, 4];
  const onKey = (event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    props.onCancel();
  };
  return (
    <div className="block-form" onKeyDown={onKey}>
      <label>
        <span className="term">{words.level}</span>
        <select autoFocus value={draft.level} onChange={(event) => setDraft({ ...draft, level: Number(event.target.value) })}>
          {levels.map((level) => <option key={level} value={level}>{level === 0 ? words.levelIntro : words.levelN(level)}</option>)}
        </select>
      </label>
      {draft.level > 0 && (
        <label>
          <span className="term">{words.title}</span>
          <input type="text" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
        </label>
      )}
      <label>
        <span className="term">{words.text}</span>
        <textarea rows={4} value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} />
      </label>
      <span className="edit-actions">
        <button type="button" className="edit-confirm" onClick={() => props.onConfirm(draft)}>{words.confirm}</button>
        <button type="button" onClick={props.onCancel}>{words.cancel}</button>
      </span>
    </div>
  );
}
