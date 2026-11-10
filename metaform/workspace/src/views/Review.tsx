// The body of the Review panel: the request for proposals, the proposals that wait for review,
// and the review history from the records of the `review` layer across the map, newest first.
// A proposal is shown beside the specification and is never part of it before the user accepts it.

import { useState } from "react";
import type { KeyboardEvent } from "react";
import type { ProposalScope } from "../source/agent";
import type { Address } from "../source";
import type { Change, Proposal } from "../spec/changes";
import { reviewRecords, whatOf } from "../spec/evidence";
import type { ReviewRecord } from "../spec/evidence";
import { elementAt, labelAt } from "../spec/model";
import type { Spec } from "../spec/model";
import { statusMarks, statusValue, statusWords } from "../spec/strings";
import { PartNotes, StatusWord, writableLine } from "../review/Editors";
import { keyOf } from "../review/store";
import type { Review as ReviewHandle } from "../review/store";
import { ROLES, edit as editWords, fieldLabels, partLabels, review as words } from "../review/strings";

/** The props of `Review`. */
export interface ReviewProps {
  /** The specification the page shows now. */
  spec: Spec;
  review: ReviewHandle;
  /** The address of the selected element, or null. */
  selection: Address | null;
  /** Called with an element's address when the user chooses a proposal's element or a history line. */
  onSelect: (address: Address) => void;
}

/** The functional area of an address: the address above it, or the address itself at the top level. */
export function areaOf(address: Address): Address {
  const cut = address.lastIndexOf(".");
  return cut < 0 ? address : address.slice(0, cut);
}

/** What a change concerns, and its value before and after, as text. */
export function describe(spec: Spec, change: Change): { what: string; before: string; after: string } {
  const element = elementAt(spec, change.address);
  const name = labelAt(spec, change.address);
  const want = "to" in change ? element?.wants.find((other) => other.to === change.to) : undefined;
  const wantText = (held: { why: string; how: string; direction: string }) =>
    `${partLabels.why}: ${held.why}\n${partLabels.how}: ${held.how}\n${partLabels.direction}: ${held.direction}`;
  switch (change.kind) {
    case "set-field": {
      const shown = (value: string | null | undefined) =>
        change.field === "status" ? statusValue(value ?? editWords.built) : value ?? null;
      return {
        what: words.fieldOf(fieldLabels[change.field], name),
        before: shown(element?.[change.field]) ?? words.empty,
        after: shown(change.value) ?? words.removed,
      };
    }
    case "set-want":
      return {
        what: words.wantOf(partLabels[change.part], name, labelAt(spec, change.to)),
        before: want?.[change.part] || words.empty,
        after: change.value,
      };
    case "add-want":
      return { what: words.addWant(name, labelAt(spec, change.to)), before: words.empty, after: wantText(change) };
    case "remove-want":
      return { what: words.removeWant(name, labelAt(spec, change.to)), before: want ? wantText(want) : words.empty, after: words.removed };
    case "set-layer":
      return {
        what: words.layerOf(change.layer, name),
        before: words.records(element?.layers[change.layer]?.length ?? 0),
        after: words.records(change.records.length),
      };
  }
}

/** The change with another value, for a proposal the user edits. Null when the change has no single text value. */
function withValue(change: Change, value: string): Change | null {
  if (change.kind === "set-want") return { ...change, value };
  if (change.kind === "set-field" && change.field !== "status") return { ...change, value: value === "" ? null : value };
  return null;
}

function SimulatedMark() {
  return <span className="badge simulated" title={words.simulatedNote}>{words.simulated}</span>;
}

/** One proposal that waits: what would change, the rationale, the evidence, and the three review actions. */
function ProposalCard({ spec, proposal, review, onSelect }: { spec: Spec; proposal: Proposal; review: ReviewHandle; onSelect: (address: Address) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const { store, state } = review;
  const { change } = proposal;
  const { what, before, after } = describe(spec, change);
  const can = state.writable.can;
  const reason = can ? undefined : writableLine(state.writable) ?? undefined;
  const editable = withValue(change, "") !== null;
  const start = change.kind === "set-want" ? change.value : change.kind === "set-field" ? change.value ?? "" : "";
  const acceptEdited = () => {
    const edited = draft === null ? null : withValue(change, draft.trim());
    setDraft(null);
    if (edited) void store.accept(change.id, edited);
  };
  const onKey = (event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    setDraft(null);
  };
  return (
    <li className="proposal">
      <p className="proposal-head">
        <button type="button" className="link proposal-what" title={change.address} onClick={() => onSelect(change.address)}>{what}</button>{" "}
        {proposal.simulated && <SimulatedMark />} <StatusWord status="agent-proposed" />
      </p>
      <p className="proposal-by">{words.proposedBy(proposal.proposedBy)}</p>
      <dl className="proposal-change">
        <div><dt>{words.before}</dt><dd className="proposal-before">{before}</dd></div>
        <div>
          <dt>{words.after}</dt>
          <dd className="proposal-after">
            {draft === null ? after : change.kind === "set-field" && change.field === "role" ? (
              <select aria-label={words.editedValue} autoFocus value={draft} onKeyDown={onKey} onChange={(event) => setDraft(event.target.value)}>
                {ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
            ) : (
              <textarea aria-label={words.editedValue} autoFocus rows={3} value={draft} onKeyDown={onKey} onChange={(event) => setDraft(event.target.value)} />
            )}
          </dd>
        </div>
        <div><dt>{words.rationale}</dt><dd>{proposal.rationale}</dd></div>
        <div>
          <dt>{words.evidence}</dt>
          <dd><ul className="proposal-evidence">{proposal.evidence.map((line, index) => <li key={index}>{line}</li>)}</ul></dd>
        </div>
      </dl>
      {draft === null ? (
        <div className="edit-actions">
          <button type="button" className="edit-confirm" disabled={!can} title={reason} onClick={() => void store.accept(change.id)}>{words.accept}</button>
          <button type="button" disabled={!can} title={reason} onClick={() => void store.reject(change.id)}>{words.reject}</button>
          {editable && <button type="button" disabled={!can} title={reason} onClick={() => setDraft(start)}>{words.editFirst}</button>}
        </div>
      ) : (
        <div className="edit-actions">
          <button type="button" className="edit-confirm" onClick={acceptEdited}>{words.acceptEdited}</button>
          <button type="button" onClick={() => setDraft(null)}>{editWords.cancel}</button>
        </div>
      )}
      <PartNotes review={review} partKey={keyOf(change)} />
    </li>
  );
}

/** One line of the review history: a record of the `review` layer with the element that holds it. */
export interface HistoryLine {
  address: Address;
  record: ReviewRecord;
}

/** Every review record in the map, newest first. Records of the same time keep the map's order. */
export function historyOf(spec: Spec): HistoryLine[] {
  const lines = spec.elements.flatMap((element) => reviewRecords(element).map((record) => ({ address: element.address, record })));
  return lines.sort((a, b) => (a.record.at < b.record.at ? 1 : a.record.at > b.record.at ? -1 : 0));
}

function timeOf(at: string): string {
  const time = new Date(at);
  return Number.isNaN(time.getTime()) ? at : time.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

/** The Review panel's body. */
export function Review({ spec, review, selection, onSelect }: ReviewProps) {
  const { store, state } = review;
  const waiting = state.proposals.filter((proposal) => proposal.state === "proposed");
  const history = historyOf(spec);
  // A rejection the map recorded is in the history. The others are listed apart, with the reason.
  const recorded = new Set(history.filter(({ record }) => record.state === "rejected").map(({ address, record }) => `${address}|${record.what}`));
  const rejected = state.proposals.filter((proposal) => proposal.state === "rejected" && !recorded.has(`${proposal.change.address}|${whatOf(proposal.change)}`));
  const line = writableLine(state.writable);
  const ask = (scope: ProposalScope) => void store.ask(scope);
  return (
    <section className="review" aria-label={words.label}>
      <div className="review-ask" role="group" aria-label={words.ask}>
        <span className="term">{words.ask}</span>
        <button type="button" disabled={state.asking} onClick={() => ask({ kind: "project" })}>{words.askProject}</button>
        {selection !== null && (
          <>
            <button type="button" disabled={state.asking} onClick={() => ask({ kind: "area", prefix: areaOf(selection) })}>{words.askArea(areaOf(selection))}</button>
            <button type="button" disabled={state.asking} onClick={() => ask({ kind: "element", address: selection })}>{words.askElement(selection)}</button>
          </>
        )}
        <SimulatedMark />
      </div>
      <p className="panel-hint">{words.simulatedNote}</p>
      <p className="review-asked" role="status">
        {state.asking ? words.asking : state.asked === null ? "" : state.asked.failed !== null ? words.askFailed(state.asked.failed) : words.asked(state.asked.added)}
      </p>
      {line !== null && <p className={`writable-line${state.writable.can ? "" : " writable-off"}`} role="note">{line}</p>}
      <h3>{words.waiting(waiting.length)}</h3>
      {waiting.length === 0 ? (
        <p className="empty">{words.noneWaiting}</p>
      ) : (
        <>
          <p className="panel-hint">{words.notInSpec}</p>
          <ul className="proposals">
            {waiting.map((proposal) => <ProposalCard key={proposal.change.id} spec={spec} proposal={proposal} review={review} onSelect={onSelect} />)}
          </ul>
        </>
      )}
      <h3>{words.history(history.length)}</h3>
      <p className="panel-hint">{words.historyNote}</p>
      {history.length === 0 ? (
        <p className="empty">{words.noHistory}</p>
      ) : (
        <ol className="review-history">
          {history.map(({ address, record }, index) => (
            <li key={`${address}|${record.at}|${index}`}>
              <button type="button" className="history-line" aria-current={address === selection ? "true" : undefined} title={address} onClick={() => onSelect(address)}>
                <span className="history-what">{labelAt(spec, address)}: {record.what}</span>
                <span className={`spec-status spec-status-${record.state}`}>
                  <span className="spec-status-mark" aria-hidden="true">{statusMarks[record.state]}</span>
                  <span className="spec-status-word">{statusWords[record.state]}</span>
                </span>
                <span className="history-who">{record.by === "user" ? words.byUser : words.byAgent}</span>
                <time dateTime={record.at}>{timeOf(record.at)}</time>
                {record.simulated && <SimulatedMark />}
                {record.rationale !== "" && <span className="history-rationale">{record.rationale}</span>}
              </button>
            </li>
          ))}
        </ol>
      )}
      {rejected.length > 0 && (
        <>
          <h3>{words.rejected(rejected.length)}</h3>
          <p className="panel-hint">{words.rejectedNote}</p>
          <ol className="review-history">
            {rejected.map((proposal) => (
              <li key={proposal.change.id}>
                <button type="button" className="history-line" aria-current={proposal.change.address === selection ? "true" : undefined} title={proposal.change.address} onClick={() => onSelect(proposal.change.address)}>
                  <span className="history-what">{describe(spec, proposal.change).what}</span>
                  <span className="spec-status spec-status-rejected">
                    <span className="spec-status-mark" aria-hidden="true">{statusMarks.rejected}</span>
                    <span className="spec-status-word">{statusWords.rejected}</span>
                  </span>
                  <span className="history-who">{proposal.proposedBy}</span>
                  {proposal.simulated && <SimulatedMark />}
                  <span className="history-rationale">{proposal.rationale}</span>
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
