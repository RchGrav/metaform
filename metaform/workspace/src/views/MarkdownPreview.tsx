// The specification as Markdown: the choices of scope and sections, the generated text, and the
// copy and download actions. The view holds no copy of the specification. One `toMarkdown` call
// per render gives the text that the preview shows, the copy sends and the download saves.

import { useEffect, useMemo, useState } from "react";
import type { Proposal } from "../spec/changes";
import { DEFAULT_SECTIONS, fileName, toMarkdown } from "../spec/markdown";
import type { Spec } from "../spec/model";
import { preview as words, SECTION_KEYS, sectionTitles } from "../spec/strings";
import type { SectionKey } from "../spec/strings";
import "../spec/spec.css";

/** The props of `MarkdownPreview`. */
export interface MarkdownPreviewProps {
  /** The specification the page shows now. */
  spec: Spec;
  /** Every proposal. The Markdown shows those that are not accepted only when the user includes that section. */
  proposals: Proposal[];
  /** The address the preview starts scoped to, or null for the whole project. */
  scope: string | null;
}

/** The result of the last copy or download, shown until the Markdown changes. */
interface Outcome {
  failed: boolean;
  text: string;
}

function reasonOf(error: unknown): string {
  return error instanceof Error && error.message !== "" ? error.message : words.unknownReason;
}

/** Hands the text to the browser as a file download. Throws when the browser refuses. */
function download(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * The Markdown preview. The user chooses the scope and the sections, reads the generated
 * Markdown, and copies it or downloads it. Each action reports its success or its failure.
 */
export function MarkdownPreview({ spec, proposals, scope }: MarkdownPreviewProps) {
  const [sections, setSections] = useState<Record<SectionKey, boolean>>(DEFAULT_SECTIONS);
  const [wholeProject, setWholeProject] = useState(scope === null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  const usedScope = wholeProject ? null : scope;
  const text = useMemo(
    () => toMarkdown(spec, { scope: usedScope, sections, proposals }),
    [spec, usedScope, sections, proposals],
  );
  const name = fileName(spec, usedScope);

  // A report of an earlier copy or download does not describe a text that has changed since.
  useEffect(() => setOutcome(null), [text]);

  const copy = async () => {
    try {
      if (!navigator.clipboard) throw new Error(words.noClipboard);
      await navigator.clipboard.writeText(text);
      setOutcome({ failed: false, text: words.copied });
    } catch (error) {
      setOutcome({ failed: true, text: words.copyFailed(reasonOf(error)) });
    }
  };

  const save = () => {
    try {
      download(name, text);
      setOutcome({ failed: false, text: words.downloaded(name) });
    } catch (error) {
      setOutcome({ failed: true, text: words.downloadFailed(reasonOf(error)) });
    }
  };

  return (
    <section className="spec-preview" aria-label={words.label}>
      <div className="spec-choices">
        {scope !== null && (
          <fieldset>
            <legend>{words.scopeLegend}</legend>
            <label>
              <input type="radio" name="spec-scope" checked={!wholeProject} onChange={() => setWholeProject(false)} />
              {words.scopeElement(scope)}
            </label>
            <label>
              <input type="radio" name="spec-scope" checked={wholeProject} onChange={() => setWholeProject(true)} />
              {words.scopeWhole}
            </label>
          </fieldset>
        )}
        <fieldset>
          <legend>{words.sectionsLegend}</legend>
          {SECTION_KEYS.map((key) => (
            <label key={key} title={key === "proposals" ? words.proposalsHint : undefined}>
              <input
                type="checkbox"
                checked={sections[key]}
                onChange={(event) => setSections({ ...sections, [key]: event.target.checked })}
              />
              {sectionTitles[key]}
            </label>
          ))}
        </fieldset>
      </div>
      <div className="spec-actions">
        <button type="button" onClick={() => void copy()}>
          {words.copy}
        </button>
        <button type="button" onClick={save}>
          {words.download}
        </button>
        <span className="spec-summary">{words.summary(text.split("\n").length - 1, text.length)}</span>
      </div>
      <p className="spec-note">{words.downloadNote}</p>
      <p className="spec-note">{words.sameState}</p>
      <p className={outcome?.failed ? "spec-outcome spec-outcome-failed" : "spec-outcome"} role={outcome?.failed ? "alert" : "status"}>
        {outcome?.text ?? ""}
      </p>
      <pre className="spec-text" tabIndex={0} aria-label={words.textLabel}>
        {text}
      </pre>
    </section>
  );
}
