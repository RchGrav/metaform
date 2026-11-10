// The body of the Evidence panel: for the selected element, its status, its source paths, and the
// status of each field, each relationship and each layer it holds. Every status is a word with a
// mark (ARCHITECTURE.md section 2). The view holds no copy of the specification.

import type { ReactNode } from "react";
import type { Address } from "../source";
import { REVIEW_LAYER, SOURCES_LAYER, elementEvidence, fieldEvidence, layerEvidence, sourcePaths, wantEvidence } from "../spec/evidence";
import type { Evidence as PartEvidence } from "../spec/evidence";
import { FIELD_NAMES, elementAt, labelAt, labelOf } from "../spec/model";
import type { Spec } from "../spec/model";
import { statusValue } from "../spec/strings";
import { StatusWord } from "../review/Editors";
import { evidence as words, fieldLabels } from "../review/strings";

/** The props of `Evidence`. */
export interface EvidenceProps {
  /** The specification the page shows now. */
  spec: Spec;
  /** The address of the selected element. */
  address: Address;
  /** Called with an element's address when the user chooses a relationship's other element. */
  onSelect: (address: Address) => void;
}

function Path({ path }: { path: string }) {
  return /^https?:\/\//.test(path) ? <a href={path} target="_blank" rel="noreferrer noopener">{path}</a> : <code>{path}</code>;
}

/** The Evidence panel's body for one element. */
export function Evidence({ spec, address, onSelect }: EvidenceProps) {
  const element = elementAt(spec, address);
  if (!element) return <p className="panel-note">{words.noElement(address)}</p>;
  const whole = elementEvidence(element);
  const paths = sourcePaths(element);
  // A status from a pending change has a mark in the specification; any other comes from the map.
  const marked = (part: { field?: string; want?: string; layer?: string }) =>
    spec.marks.some((mark) => mark.address === address && mark.field === part.field && mark.want === part.want && mark.layer === part.layer);
  const row = (key: string, label: ReactNode, value: ReactNode, evidence: PartEvidence | null, pending: boolean) => (
    <tr key={key}>
      <th scope="row">{label}</th>
      <td>{value}</td>
      <td>{evidence && <StatusWord status={evidence.status} recorded={!pending} />}</td>
    </tr>
  );
  const layers = Object.entries(element.layers).filter(([layer]) => layer !== REVIEW_LAYER && layer !== SOURCES_LAYER);
  return (
    <section className="evidence" aria-label={words.label}>
      <p className="evidence-element">
        <strong>{labelOf(element)}</strong> <code>{address}</code> <StatusWord status={whole.status} />
      </p>
      <p className="panel-hint">{words.derived}</p>
      <h3>{words.sourcePaths}</h3>
      {paths.length === 0 ? (
        <p className="empty">{words.noPaths}</p>
      ) : (
        <ul className="evidence-paths">
          {paths.map((path) => (
            <li key={path}>
              <Path path={path} /> <span className="term">{path === element.uri ? words.sourceReference : words.sourcesLayer}</span>
            </li>
          ))}
        </ul>
      )}
      <h3>{words.fields}</h3>
      <table className="evidence-table">
        <tbody>
          {FIELD_NAMES.map((field) => {
            const value = element[field];
            const shown = field === "status" ? statusValue(value ?? "built") : value;
            const evidence = value === undefined && field !== "status" ? null : fieldEvidence(spec, address, field);
            return row(field, fieldLabels[field], shown ?? <span className="empty">{words.notSet}</span>, evidence, marked({ field }));
          })}
        </tbody>
      </table>
      <h3>{words.relationships}</h3>
      {element.wants.length === 0 ? (
        <p className="empty">{words.noRelationships}</p>
      ) : (
        <table className="evidence-table">
          <tbody>
            {element.wants.map((want) =>
              row(
                want.to,
                <button type="button" className="link" title={want.to} onClick={() => onSelect(want.to)}>{words.reliesOn(labelAt(spec, want.to))}</button>,
                want.why,
                wantEvidence(spec, address, want.to),
                marked({ want: want.to }),
              ),
            )}
          </tbody>
        </table>
      )}
      {layers.length > 0 && (
        <>
          <h3>{words.layers}</h3>
          <table className="evidence-table">
            <tbody>
              {layers.map(([layer, records]) =>
                row(layer, layer, words.records(records.length), layerEvidence(spec, address, layer) ?? { status: "inferred", paths: [] }, marked({ layer })),
              )}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
