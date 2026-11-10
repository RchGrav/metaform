// The plate that shows the why and the how of one want while the pointer is on its line.

import { intake } from "../strings";
import type { Point } from "./layout";
import { el } from "./svg";

/** A line of a plate is cut to this many characters and continued on the next line. */
const DETAIL_CHARS = 48;

/**
 * The why and how of one want, on a plate beside the line's middle. The plate keeps its size on
 * screen at any zoom (`--mf-unzoom`), so the text can always be read, and long text is wrapped,
 * not cut.
 */
export function drawDetail(parent: SVGGElement, at: Point, why: string | null, how: string | null): SVGGElement {
  const wrap = (text: string): string[] => {
    const lines: string[] = [];
    let line = "";
    for (const word of text.split(/\s+/)) {
      if (line !== "" && (line + " " + word).length > DETAIL_CHARS) {
        lines.push(line);
        line = "   " + word;
      } else line = line === "" ? word : `${line} ${word}`;
    }
    if (line !== "") lines.push(line);
    return lines;
  };
  const lines = [...(why ? wrap(intake.opLine(why)) : []), ...(how ? wrap(intake.efLine(how)) : [])];
  const width = Math.max(...lines.map((l) => l.length)) * 6.6 + 16;
  const height = lines.length * 16 + 10;
  const box = { x: at.x + 14, y: at.y + 10, width, height };
  const g = el("g", { class: "mf-want-detail", transform: `translate(${box.x},${box.y})` }, parent);
  const inner = el("g", { class: "mf-want-inner" }, g);
  el("rect", { class: "mf-want-plate", width, height, rx: 5 }, inner);
  lines.forEach((line, i) => {
    el("text", { class: "mf-want-line", x: 8, y: 18 + i * 16, "xml:space": "preserve" }, inner).textContent = line;
  });
  return g;
}
