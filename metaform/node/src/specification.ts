// Port of `metaform-core/src/specification.rs`. Layers defined in the map, and the specification
// layer (R-6.24 to R-6.28).
//
// Every layer works the same way (owner decision, 2026-11-09). A layer is defined by an element
// beneath the `layer` root scope that has an `instruction` field. Its data sits on the receiving
// elements as a field named after the definition's last segment, as a list of records:
// `layer.document.specification` defines the field `specification`.
//
// A definition may declare `format: "markdown_blocks"`. Its records are then blocks of prose,
// `{"level": 1-4, "title": "...", "text": "..."}`, and the first block may be `{"text": "..."}`
// alone, an intro with no heading. The tool refuses only what would break the Markdown round
// trip or put records before the skeleton.
//
// Not ported: `scope_order`, `stored`, `blocks` and `applies`, which serve the specification
// export and import that this form does not offer.

import type { Json, JsonObject } from "./json.ts";
import { get, isArray, isObject, obj } from "./json.ts";
import type { Element, Fields, MapModel } from "./model.ts";
import { ROOT, lastSegment } from "./names.ts";
import { isProjectDefinitive } from "./reads.ts";
import { Code, Refusal } from "./refusal.ts";
import { lines, trim, trimEnd } from "./text.ts";

/**
 * The system layers (R-6.15): defined in code, shared by every project, written by agents at an
 * address without a definition in the map.
 */
export const SYSTEM_LAYERS = ["skills", "memory", "sources"];

/** The root scope that holds layer definitions (R-3.3, R-6.24). */
export const LAYER_SCOPE = "layer";

/** Where the specification layer is defined in each main map. */
export const DEFINITION_ADDRESS = "layer.document.specification";

/** The record format whose records are Markdown blocks with enforced heading levels. */
export const MARKDOWN_BLOCKS = "markdown_blocks";

/**
 * The deepest relative level. Element headings are `##` in the export, so level 4 is `######`,
 * the deepest Markdown heading (R-6.25).
 */
export const MAX_LEVEL = 4;

/**
 * The specification layer's writing guidance: the short form of `TASTE.md` prepared for this
 * layer by the TASTE auditor (metaform-38), used as written.
 */
export const INSTRUCTION = `Write each block in TASTE: Technically Accurate, Simple, Transparent English. A block adds what the map leaves out on purpose; do not repeat what the element's fields and wants already say.
- Start with what the element does or holds. Then give the detail that explains it.
- Name the element, field or command instead of starting with "it", "this" or "they". A block is often read alone.
- Use the project's terms and exact identifiers. Use one term for one thing. Put identifiers in backticks.
- Write one claim per sentence. Aim for 25 words or fewer per sentence and six sentences or fewer per paragraph. Never cut a condition, an exception or a reason to meet a length target.
- Use lowercase must, should, may, can and might with their TASTE meanings. Do not write SHALL or capitalized MUST.
- Say whether something is built, proposed or planned. Do not describe planned behavior as if it exists.
- Replace words such as simple, robust or fast with the behavior or a measurement.
- Define an abbreviation at its first use. Keep noun clusters to three nouns.
- Leave out openings such as "This section describes", repeated points, analogies and promotion.
- Prefer start, use, adjust, perform and end over kick off/launch/begin, utilize/leverage, modify/change/alter, execute/run and terminate/stop/abort, when the meaning stays the same.
- Do not put Markdown heading lines in the text. Set the block's level and title instead.`;

/**
 * How records of the `markdown_blocks` format are written through the tool (R-6.25, R-6.26).
 * `goto` delivers it before the definition's own instruction. `{layer}` is the field name.
 */
const MARKDOWN_FORM = `The {layer} field is a list of blocks: {"level": 1-4, "title": "...", "text": "..."}. A titled block may also carry "code", a key that other text can cite; it is unique in the layer across the map, ignoring case. The first block may be {"text": "..."} alone, as an intro under the element's heading. The first titled block is level 1, and each level is at most one more than the level before it. update replaces every block at the address and is safe to repeat; add appends blocks; if an answer is lost, a retried add appends them twice. Read them with {"<address>": {"{layer}": {}}}. The root's blocks are in the raw dump {".": {}}, because a key that starts with a period is a raw dump. Blocks are accepted at an element that has technical_name, name and role, and at . once the map has a Definitive element.`;

/**
 * The fields of the specification layer's definition element at `DEFINITION_ADDRESS`. The store
 * writes it into each main map, so `goto` always finds the layer (R-6.24).
 */
export function definition(): Fields {
  return obj(
    ["technical_name", "specification document layer"],
    ["name", "Specification"],
    ["role", "Supportive"],
    [
      "description",
      "Prose that the skeleton leaves out on purpose: what each element does, how it behaves and why, as blocks with Markdown heading levels.",
    ],
    ["template", "{title}: {text}"],
    ["format", MARKDOWN_BLOCKS],
    ["instruction", INSTRUCTION],
  );
}

/** One layer definition found in the map. */
export class Definition {
  /** The field name at receiving elements: the definition's last address segment. */
  layer: string;
  /** The definition element's address. */
  address: string;
  /** The record format, such as `markdown_blocks`, if the definition declares one. */
  format: string | null;
  /** The writing guidance for the layer. */
  instruction: string;

  constructor(layer: string, address: string, format: string | null, instruction: string) {
    this.layer = layer;
    this.address = address;
    this.format = format;
    this.instruction = instruction;
  }

  /** The guidance `goto` delivers: the format's rules, then the definition's own instruction. */
  guidance(): string {
    if (this.format === MARKDOWN_BLOCKS) {
      return `${MARKDOWN_FORM.replaceAll("{layer}", () => this.layer)}\n${this.instruction}`;
    }
    return this.instruction;
  }
}

/**
 * Every layer defined in the map, by field name. A write cannot create two definitions with the
 * same last segment; if stored data has them, the definition whose address sorts first wins.
 */
export function definitions(map: MapModel): Definition[] {
  const out: Definition[] = [];
  for (const [address, element] of map.elements()) {
    if (!isBeneathLayerScope(address)) {
      continue;
    }
    const instruction = element.fields.get("instruction");
    if (typeof instruction !== "string") {
      continue;
    }
    const layer = lastSegment(address);
    if (out.some((d) => d.layer === layer)) {
      continue;
    }
    const format = element.fields.get("format");
    out.push(new Definition(layer, address, typeof format === "string" ? format : null, instruction));
  }
  return out;
}

/** The definition of one layer, if the map defines it. */
export function definitionOf(map: MapModel, layer: string): Definition | undefined {
  return definitions(map).find((d) => d.layer === layer);
}

/**
 * Whether an address is the `layer` root scope or beneath it, where layer definitions live,
 * outside the functional skeleton (R-3.20).
 */
export function inLayerScope(address: string): boolean {
  return address === LAYER_SCOPE || isBeneathLayerScope(address);
}

function isBeneathLayerScope(address: string): boolean {
  return address.startsWith(`${LAYER_SCOPE}.`);
}

/** One block of a `markdown_blocks` layer. */
export class Block {
  /** The relative heading level, 1 to `MAX_LEVEL`. `null` only for an intro block. */
  level: number | null;
  /** The heading text. `null` only for an intro block. */
  title: string | null;
  /** Markdown body text, with no heading lines. Stored with LF line ends and trimmed. */
  text: string;
  /**
   * An optional key that other text can cite, unique within the layer across the whole map,
   * ignoring case (owner decision, 2026-11-09). Only a titled block has one.
   */
  code: string | null;

  constructor(level: number | null, title: string | null, text: string, code: string | null = null) {
    this.level = level;
    this.title = title;
    this.text = text;
    this.code = code;
  }

  copy(): Block {
    return new Block(this.level, this.title, this.text, this.code);
  }

  isIntro(): boolean {
    return this.title === null;
  }

  /** The block as the tool stores and returns it. */
  toJson(): Json {
    if (this.level === null || this.title === null) {
      return obj(["text", this.text]);
    }
    const out = obj(["level", this.level]);
    if (this.code !== null) {
      out.set("code", this.code);
    }
    out.set("title", this.title);
    out.set("text", this.text);
    return out;
  }
}

/** The blocks as the tool stores them. */
export function toJson(blocks: Block[]): Json {
  return blocks.map((block) => block.toJson());
}

/**
 * An element is part of the skeleton when intake has given it every mandatory field (R-3.4):
 * `technical_name`, `name` and `role`. Only then may it hold layer records (R-6.26).
 */
export function isSkeleton(element: Element): boolean {
  return ["technical_name", "name", "role"].every((key) => {
    const value = element.fields.get(key);
    return typeof value === "string" && trim(value) !== "";
  });
}

/**
 * Whether layer records may sit at an address: a skeleton element outside the `layer` scope, or
 * the root once the map has a Definitive element (R-6.26). This holds for every defined layer.
 */
export function recordsAllowed(map: MapModel, address: string): boolean {
  if (address === ROOT) {
    for (const [at, element] of map.elements()) {
      if (isProjectDefinitive(at, element.fields.get("role"))) {
        return true;
      }
    }
    return false;
  }
  const element = map.element(address);
  return address !== LAYER_SCOPE && !isBeneathLayerScope(address) && element !== undefined && isSkeleton(element);
}

/** The kind of heading line found in block text. */
const HeadingLine = {
  /** A line such as `## Title`. */
  Atx: "atx",
  /** A line of `=` or `-` directly under a paragraph line, which turns that line into a heading. */
  Setext: "setext",
} as const;
type HeadingKind = (typeof HeadingLine)[keyof typeof HeadingLine];

/** The number of spaces a line starts with. */
function indentOf(line: string): number {
  let indent = 0;
  while (line[indent] === " ") {
    indent += 1;
  }
  return indent;
}

/** Whether every character of the text is `mark`. */
function isAll(text: string, mark: string): boolean {
  for (const c of text) {
    if (c !== mark) {
      return false;
    }
  }
  return true;
}

/**
 * The first Markdown heading line in `text` outside fenced code, as a 0-based line index and its
 * kind. For a setext heading the index is the underline's; the heading text is the line before.
 */
export function headingInText(text: string): [number, HeadingKind] | null {
  let fence: [string, number] | null = null;
  let previous: string | null = null;
  for (const [index, line] of lines(text).entries()) {
    const indent = indentOf(line);
    const body = line.slice(indent);
    const mark = indent <= 3 ? fenceMark(body) : null;
    if (mark !== null) {
      if (fence === null) {
        fence = mark;
      } else if (fence[0] === mark[0] && mark[1] >= fence[1] && isAll(trimEnd(body), mark[0])) {
        fence = null;
      }
      previous = null;
      continue;
    }
    if (fence !== null) {
      continue;
    }
    if (indent <= 3 && isAtx(body)) {
      return [index, HeadingLine.Atx];
    }
    if (indent <= 3 && isUnderline(body) && previous !== null && isParagraphLine(previous)) {
      return [index, HeadingLine.Setext];
    }
    previous = line;
  }
  return null;
}

/** A fence opener or closer: three or more backticks or tildes. */
function fenceMark(body: string): [string, number] | null {
  const mark = body[0];
  if (mark !== "`" && mark !== "~") {
    return null;
  }
  let run = 0;
  while (body[run] === mark) {
    run += 1;
  }
  return run >= 3 ? [mark, run] : null;
}

function isAtx(body: string): boolean {
  let hashes = 0;
  while (body[hashes] === "#") {
    hashes += 1;
  }
  const next = body[hashes];
  return hashes >= 1 && hashes <= 6 && (next === undefined || next === " " || next === "\t");
}

function isUnderline(body: string): boolean {
  const line = trimEnd(body);
  return line !== "" && (isAll(line, "=") || isAll(line, "-"));
}

/**
 * A line that a setext underline would turn into a heading: non-blank, not indented as code, and
 * not a list item, table row or heading.
 */
function isParagraphLine(line: string): boolean {
  const indent = indentOf(line);
  const body = trim(line);
  if (body === "" || indent > 3 || body.startsWith("|") || body.startsWith(">") || isAtx(body)) {
    return false;
  }
  if (body.startsWith("- ") || body.startsWith("* ") || body.startsWith("+ ")) {
    return false;
  }
  const digits = /^[0-9]*/.exec(body)?.[0].length ?? 0;
  return !(digits > 0 && (body.startsWith(". ", digits) || body.startsWith(") ", digits)));
}

/**
 * Whether a title has the form the export reserves for element headings: it ends with an address
 * in backticks inside parentheses, such as "Name (`code.engine`)".
 */
export function isElementHeadingForm(title: string): boolean {
  const trimmed = trimEnd(title);
  return trimmed.endsWith("`)") && trimmed.includes("(`");
}

/** An example of valid blocks, given as the remediation of a malformed block. */
function example(layer: string, address: string): Json {
  return obj([
    "update",
    obj([
      address,
      obj([
        layer,
        [
          obj(["text", "<intro prose, optional>"]),
          obj(["level", 1], ["title", "<heading>"], ["text", "<prose>"]),
          obj(["level", 2], ["title", "<subheading>"], ["text", "<prose>"]),
        ],
      ]),
    ]),
  ]);
}

/**
 * Read and normalize the blocks of a `markdown_blocks` layer value. The value must be a list;
 * each block must have the block shape. Line ends become LF and title and text are trimmed, so
 * the stored form is the form the export writes and the import reads back.
 */
export function blocksOf(layer: string, address: string, value: Json): Block[] {
  const mismatch = (why: string): Refusal =>
    new Refusal(Code.FieldMismatch, `'${address}': ${layer}: ${why}`, example(layer, address));
  if (!isArray(value)) {
    throw mismatch("must be a list of blocks");
  }
  const out: Block[] = [];
  for (const [index, item] of value.entries()) {
    const n = index + 1;
    if (!isObject(item)) {
      throw mismatch(`block ${n} must be an object`);
    }
    for (const key of item.keys()) {
      if (!["level", "title", "text", "code"].includes(key)) {
        throw mismatch(`block ${n} does not take: ${key}`);
      }
    }
    const givenText = item.get("text");
    if (givenText !== undefined && typeof givenText !== "string") {
      throw mismatch(`block ${n}: text must be a string`);
    }
    const text = givenText === undefined ? "" : normalize(givenText);
    const givenTitle = item.get("title");
    if (givenTitle !== undefined && typeof givenTitle !== "string") {
      throw mismatch(`block ${n}: title must be a string`);
    }
    const title = givenTitle === undefined ? null : normalize(givenTitle);
    const givenLevel = item.get("level");
    let level: number | null = null;
    if (givenLevel !== undefined) {
      if (typeof givenLevel !== "number" || !Number.isInteger(givenLevel) || givenLevel < 0) {
        throw mismatch(`block ${n}: level must be a whole number from 1 to ${MAX_LEVEL}`);
      }
      level = givenLevel;
    }
    const givenCode = item.get("code");
    if (givenCode !== undefined && (typeof givenCode !== "string" || !isCode(givenCode))) {
      throw mismatch(
        `block ${n}: code must be one token of 1 to 32 letters, digits, '.', '_' or '-', starting with a letter and ending with a letter or digit, such as R-1.2`,
      );
    }
    const code = givenCode === undefined ? null : (givenCode as string);
    if (code !== null && title === null) {
      throw mismatch(`block ${n}: only a block with a level and title can have a code`);
    }
    if (level === null && title === null) {
      if (index > 0) {
        throw mismatch(`block ${n} has no level and title; only the first block may be an intro`);
      }
      if (text === "") {
        throw mismatch("block 1 is an intro with no text");
      }
      out.push(new Block(null, null, text));
    } else if (level !== null && title !== null) {
      if (title === "" || title.includes("\n")) {
        throw mismatch(`block ${n}: title must be one line of text`);
      }
      if (title.startsWith("`")) {
        throw mismatch(`block ${n}: title must not start with a backtick; the export writes the block's code there`);
      }
      if (title.startsWith("#")) {
        throw mismatch(`block ${n}: title must not start with '#'; the level sets the heading`);
      }
      if (isElementHeadingForm(title)) {
        throw mismatch(
          `block ${n}: title must not end with an address in backticks inside parentheses; the export uses that form for element headings`,
        );
      }
      // The Rust form holds a level in one byte, so a larger number becomes 255.
      out.push(new Block(Math.min(level, 255), title, text, code));
    } else {
      throw mismatch(`block ${n} needs both level and title, or neither for an intro`);
    }
  }
  return out;
}

/**
 * A block code: a letter, then up to 31 letters, digits, `.`, `_` or `-`, ending with a letter or
 * digit. It has no spaces or backticks, so it survives the Markdown export.
 */
export function isCode(code: string): boolean {
  return /^[A-Za-z](?:[A-Za-z0-9._-]{0,30}[A-Za-z0-9])?$/.test(code);
}

/** Rust's `to_ascii_lowercase`: only the letters A to Z are lowered. */
function asciiLower(text: string): string {
  return text.replace(/[A-Z]/g, (letter) => letter.toLowerCase());
}

/**
 * Refuse a code in `blocks` (just written at `address`) that another block of the same layer
 * already holds, anywhere in the map after the write, ignoring case. The remediation is the
 * same update with that block's code removed.
 */
export function checkCodes(map: MapModel, address: string, layer: string, blocks: Block[]): void {
  const held: [string, string, number][] = [];
  for (const [holder, element] of map.elements()) {
    if (holder === address) {
      continue;
    }
    // Read codes from the stored JSON, not parsed blocks, so a holder whose blocks predate
    // the rules still counts.
    const stored = element.fields.get(layer);
    if (!isArray(stored)) {
      continue;
    }
    for (const [index, record] of stored.entries()) {
      const code = get(record, "code");
      if (typeof code === "string") {
        held.push([asciiLower(code), holder, index + 1]);
      }
    }
  }
  for (const [index, block] of blocks.entries()) {
    if (block.code === null) {
      continue;
    }
    const code = block.code;
    const key = asciiLower(code);
    const earlier = blocks.slice(0, index).findIndex((b) => b.code !== null && asciiLower(b.code) === key);
    const elsewhere = held.find(([k]) => k === key);
    const found: [string, number] | null =
      earlier !== -1 ? [address, earlier + 1] : elsewhere ? [elsewhere[1], elsewhere[2]] : null;
    if (found !== null) {
      const [holder, n] = found;
      const fixed = blocks.map((b) => b.copy());
      fixed[index].code = null;
      throw new Refusal(
        Code.CodeNotUnique,
        `'${address}': ${layer} block ${index + 1} has code ${code}, which '${holder}' block ${n} already holds; a code is unique in the ${layer} layer, ignoring case`,
        obj(["update", obj([address, obj([layer, toJson(fixed)])])]),
      );
    }
  }
}

function normalize(text: string): string {
  return trim(text.replaceAll("\r\n", "\n").replaceAll("\r", "\n"));
}

/**
 * The blocks with each level brought into the rules: the first titled block at 1, each next block
 * at most one deeper, and none beyond `MAX_LEVEL`.
 */
function clampLevels(blocks: Block[]): Block[] {
  let previous = 0;
  return blocks.map((given) => {
    const block = given.copy();
    if (block.level !== null) {
      const fixed = Math.min(Math.max(block.level, 1), Math.min(previous + 1, MAX_LEVEL));
      block.level = fixed;
      previous = fixed;
    }
    return block;
  });
}

/** `text` without the run of `mark` at its start. */
function trimStartMatches(text: string, mark: string): string {
  let at = 0;
  while (text[at] === mark) {
    at += 1;
  }
  return text.slice(at);
}

/** `text` without the run of `mark` at its end. */
function trimEndMatches(text: string, mark: string): string {
  let end = text.length;
  while (end > 0 && text[end - 1] === mark) {
    end -= 1;
  }
  return text.slice(0, end);
}

/**
 * The blocks with each heading line in a text moved out into a block of its own, one level
 * deeper than the block it was in. This is the remediation for `HEADING_IN_TEXT`.
 */
function splitHeadings(blocks: Block[]): Block[] {
  const out: Block[] = [];
  for (const block of blocks) {
    let rest = block.copy();
    for (;;) {
      const heading = headingInText(rest.text);
      if (heading === null) {
        out.push(rest);
        break;
      }
      const [index, kind] = heading;
      const all = lines(rest.text);
      const titleLine = kind === HeadingLine.Atx ? index : index - 1;
      const bodyFrom = index + 1;
      const title = trim(trimEndMatches(trim(trimStartMatches(trim(all[titleLine]), "#")), "#"));
      const level = rest.level === null ? 1 : Math.min(rest.level + 1, MAX_LEVEL);
      const before = trim(all.slice(0, titleLine).join("\n"));
      const after = trim(all.slice(bodyFrom).join("\n"));
      rest.text = before;
      if (!(rest.isIntro() && rest.text === "")) {
        out.push(rest);
      }
      rest = new Block(level, title === "" ? "<heading>" : title, after);
    }
  }
  return clampLevels(out);
}

/**
 * The refusal for a layer value that is not a list. The remediation is the same write with the
 * value as the one record of a list.
 */
export function notAList(verb: string, layer: string, address: string, value: Json): Refusal {
  return new Refusal(
    Code.FieldMismatch,
    `'${address}': ${layer}: a layer's value must be a list of records`,
    obj([verb, obj([address, obj([layer, [value]])])]),
  );
}

/** The records of any defined layer: the value must be a list (R-6.24). */
export function records(layer: string, address: string, value: Json): Json[] {
  if (!isArray(value)) {
    throw notAList("update", layer, address, value);
  }
  return value;
}

/**
 * Refuse records of any layer at an address where records are not allowed (R-6.26). `map` is
 * the map after the write.
 */
export function checkAllowed(map: MapModel, address: string, layer: string): void {
  if (recordsAllowed(map, address)) {
    return;
  }
  // No command lets a layer definition hold records, so that refusal has no remediation.
  let remediation: Json;
  let reason: string;
  if (address === ROOT) {
    remediation = obj(["update", obj(["<definitive address>", obj(["role", "Definitive"])])]);
    reason = `'.': ${layer} records at the root need a Definitive element in the map first`;
  } else if (inLayerScope(address)) {
    remediation = null;
    reason = `'${address}': ${layer} records do not go on layer definitions`;
  } else {
    const element = map.element(address);
    const fix: JsonObject = new Map();
    for (const key of ["technical_name", "name", "role"]) {
      const value = element?.fields.get(key);
      if (!(typeof value === "string" && trim(value) !== "")) {
        fix.set(key, `<${key}>`);
      }
    }
    remediation = obj(["update", obj([address, fix])]);
    reason = `'${address}': ${layer} records need an element with technical_name, name and role; intake has not placed it in the skeleton yet`;
  }
  throw new Refusal(Code.ElementNotInSkeleton, reason, remediation);
}

/** Check the blocks of a `markdown_blocks` layer written at an address (R-6.25). */
export function checkBlocks(address: string, layer: string, blocks: Block[]): void {
  let previous = 0;
  for (const [index, block] of blocks.entries()) {
    if (block.level === null) {
      continue;
    }
    const level = block.level;
    const allowed = Math.min(previous + 1, MAX_LEVEL);
    if (level < 1 || level > allowed) {
      let why: string;
      if (level < 1 || level > MAX_LEVEL) {
        why = `level ${level} is outside 1 to ${MAX_LEVEL}`;
      } else if (previous === 0) {
        why = `level ${level}; the first titled block is level 1`;
      } else {
        why = `level ${level} follows level ${previous}; a level is at most one more than the level before it`;
      }
      throw new Refusal(
        Code.HeadingLevelInvalid,
        `'${address}': ${layer} block ${index + 1} ("${block.title ?? ""}"): ${why}`,
        obj(["update", obj([address, obj([layer, toJson(clampLevels(blocks))])])]),
      );
    }
    previous = level;
  }
  for (const [index, block] of blocks.entries()) {
    const heading = headingInText(block.text);
    if (heading !== null) {
      const [line, kind] = heading;
      const what =
        kind === HeadingLine.Atx
          ? "a Markdown heading line"
          : "a line of = or - under a paragraph line, which Markdown reads as a heading";
      throw new Refusal(
        Code.HeadingInText,
        `'${address}': ${layer} block ${index + 1}: text line ${line + 1} is ${what}; set a block's level and title instead`,
        obj(["update", obj([address, obj([layer, toJson(splitHeadings(blocks))])])]),
      );
    }
  }
}
