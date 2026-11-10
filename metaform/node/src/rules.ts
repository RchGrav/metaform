// Port of `metaform-core/src/rules.rs`. Rules on an element's intake fields that need the map
// (R-3.11 to R-3.13), and the rule that a layer's value is a list (R-6.24). `commands` applies
// them to every element a write touched. The grammar of a want's `why` and `how` (R-3.17,
// R-6.17) is checked here too, for the parts a write sets.

import type { Json, JsonObject } from "./json.ts";
import { equal, isArray, isObject, obj } from "./json.ts";
import type { Element, MapModel } from "./model.ts";
import { ROOT, join } from "./names.ts";
import { Code, Refusal } from "./refusal.ts";
import * as specification from "./specification.ts";
import type { Sorted } from "./text.ts";
import { isSpace, trim, words } from "./text.ts";

/** The four roles (R-3.13), spelled as a write must spell them. */
export const ROLES = ["Definitive", "Supportive", "Notable", "Divergent"];

/**
 * Check one touched element: `technical_name` (R-3.11), then `role` (R-3.13). `before` is the
 * map before the write.
 *
 * R-3.12 (`name` must not equal `technical_name`) is not checked. The intake procedure lets
 * `name` be the standard term when the project has no name of its own for the element. The
 * conflict between R-3.12 and the procedure is the owner's to settle (`SPEC.md` D-19).
 */
export function check(before: MapModel, address: string, element: Element): void {
  checkTechnicalName(before, address, element);
  checkRole(before, address, element);
  checkSystemLayers(before, address, element);
}

/**
 * A system layer (`skills`, `memory`, `sources`) holds a list of records (R-6.15). A value this
 * write set that is not a list is refused, with the value as one record in the remediation.
 */
function checkSystemLayers(before: MapModel, address: string, element: Element): void {
  for (const layer of specification.SYSTEM_LAYERS) {
    const value = element.fields.get(layer);
    if (value === undefined) {
      continue;
    }
    const stored = before.element(address)?.fields.get(layer);
    if (!isArray(value) && (stored === undefined || !equal(stored, value))) {
      throw specification.notAList("update", layer, address, value);
    }
  }
}

/**
 * The command that corrects one field. An element this write created is added again with the
 * field corrected, because the refused write stored nothing; an existing one is updated.
 */
function correction(before: MapModel, address: string, element: Element, field: string, value: string): Json {
  if (before.element(address) !== undefined) {
    return obj(["update", obj([address, obj([field, value])])]);
  }
  const view = element.view();
  view.set(field, value);
  return obj(["add", obj([address, view])]);
}

/**
 * `technical_name` is the same number of leading words of the reversed, space-separated address
 * (R-3.11). The root is the project: it has no address words and no `technical_name`.
 */
function checkTechnicalName(before: MapModel, address: string, element: Element): void {
  const technical = element.fields.get("technical_name");
  if (typeof technical !== "string") {
    return;
  }
  if (address === ROOT) {
    throw new Refusal(
      Code.TechnicalNameAlignmentFailure,
      "'.': the root is the project and has no technical_name",
      obj(["update", obj([ROOT, obj(["technical_name", null])])]),
    );
  }
  const segments = address.split(".");
  const reversed = segments.toReversed().flatMap((segment) => segment.split("_"));
  const given = words(technical);
  if (given.length > 0 && given.length <= reversed.length && given.every((word, at) => word === reversed[at])) {
    return;
  }
  // The suggestion is the reversed address without its root scope words: `code.cache.response`
  // gives "response cache".
  const rootWords = segments[0].split("_").length;
  const keep = Math.max(reversed.length - rootWords, 1);
  const suggested = reversed.slice(0, Math.min(keep, reversed.length)).join(" ");
  throw new Refusal(
    Code.TechnicalNameAlignmentFailure,
    `'${address}': technical_name "${technical}" is not the leading words of "${reversed.join(" ")}"`,
    correction(before, address, element, "technical_name", suggested),
  );
}

/**
 * A write that sets or adjusts `role` must set one of the four roles (R-3.13). A role the write
 * did not adjust is not checked, so a stored map with older role names (`DE`, `SE`, `NE`, `CQU`)
 * still accepts unrelated writes.
 */
function checkRole(before: MapModel, address: string, element: Element): void {
  const role = element.fields.get("role");
  if (typeof role !== "string") {
    return;
  }
  const stored = before.element(address)?.fields.get("role");
  if (stored === role || ROLES.includes(role)) {
    return;
  }
  throw new Refusal(
    Code.RoleTaxonomyFailure,
    `'${address}': role "${role}" is not one of: ${ROLES.join(", ")}`,
    correction(before, address, element, "role", "<Definitive, Supportive, Notable or Divergent>"),
  );
}

/**
 * Refuse an object written where an element holds a layer's records (R-6.24). An object there
 * would become an element beneath, which cannot share its name with the layer's field; the
 * records stay, and the remediation gives the object as one record. `verb` is `add` or `update`,
 * `address` the element the command names, `fields` what the command supplies for it, and
 * `map` the map before the write.
 */
export function checkLayerValues(map: MapModel, verb: string, address: string, fields: JsonObject): void {
  const defined = specification.definitions(map);
  const isLayer = (name: string): boolean =>
    specification.SYSTEM_LAYERS.includes(name) || defined.some((d) => d.layer === name);
  layerValues(map, isLayer, verb, address, fields);
}

function layerValues(
  map: MapModel,
  isLayer: (name: string) => boolean,
  verb: string,
  address: string,
  fields: JsonObject,
): void {
  for (const [key, value] of fields) {
    if (!isObject(value)) {
      continue;
    }
    const holdsRecords = isArray(map.element(address)?.fields.get(key));
    if (holdsRecords && isLayer(key)) {
      throw specification.notAList(verb, key, address, value);
    }
    layerValues(map, isLayer, verb, join(address, key), value);
  }
}

/**
 * The rule text that ends the message of every grammar refusal. The message is the only place
 * an agent learns the rule, so it states the whole rule and is the same in every form of
 * Metaform. The faults of the refused want come before it (`grammarFault`).
 */
export const GRAMMAR_RULE =
  "why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values. Detail belongs in a knowledge layer.";

/** The text an agent must replace in the remediation of a grammar refusal. */
const WHY_PLACEHOLDER = "<base verb phrase, as: drain raw frames from the network interface card>";
const HOW_PLACEHOLDER =
  "<verb phrase ending in -s, as: holds descriptor pointers across contiguous memory segments>";

/**
 * Base verbs that end in `ing`. A `why` may start with one; any other first word that ends in
 * `ing` is taken as an `-ing` verb form.
 */
const ING_BASE_VERBS = [
  "bring", "cling", "ding", "fling", "ping", "ring", "sing", "sling", "spring", "sting", "string", "swing",
  "wring", "zing",
];

/** First words that make the text a clause with a subject, not a verb phrase. */
const SUBJECT_WORDS = ["the", "a", "an", "this", "that", "these", "those", "it", "its", "we", "they", "each", "every"];

/**
 * The first word of the text: the characters before the first white space, with A to Z lowered
 * and any trailing `.,;:!?` removed.
 */
function firstWord(text: string): string {
  const word = words(text)[0] ?? "";
  return word.replace(/[A-Z]/g, (letter) => letter.toLowerCase()).replace(/[.,;:!?]+$/, "");
}

/**
 * Whether the text holds more than one fragment: `.`, `!`, `?` or `;` followed by white space
 * and then more text. One trailing full stop is not a second fragment.
 */
function hasManyFragments(text: string): boolean {
  const trimmed = trim(text);
  for (let at = 0; at + 1 < trimmed.length; at += 1) {
    if (".!?;".includes(trimmed[at]) && isSpace(trimmed[at + 1])) {
      return true;
    }
  }
  return false;
}

function isDigit(character: string | undefined): boolean {
  return character !== undefined && character >= "0" && character <= "9";
}

/**
 * A letter, for the number rule: A to Z in either case, or any character outside ASCII. The
 * three forms of Metaform use this one definition, so they decide the same.
 */
function isLetter(character: string | undefined): boolean {
  return character !== undefined && (/[A-Za-z]/.test(character) || character.charCodeAt(0) > 127);
}

/**
 * Whether the text holds a number that stands alone: a run of digits 0 to 9, with an optional
 * decimal part, that is not part of a word. The run is part of a word when a letter follows it
 * directly, or when a letter directly precedes it or precedes the digits, `/`, `-` and `_` that
 * join it to the word. `S256`, `OAuth2`, `utf-8`, `HTTP/2` and `x86-64` are words; `5` and `3.9`
 * stand alone. A want states what happens without tunable values (R-3.17).
 */
function hasLoneNumber(text: string): boolean {
  let at = 0;
  while (at < text.length) {
    if (!isDigit(text[at])) {
      at += 1;
      continue;
    }
    const start = at;
    while (isDigit(text[at])) {
      at += 1;
    }
    if (text[at] === "." && isDigit(text[at + 1])) {
      at += 1;
      while (isDigit(text[at])) {
        at += 1;
      }
    }
    const letterAfter = isLetter(text[at]);
    let wordStart = start;
    while (wordStart > 0 && (isDigit(text[wordStart - 1]) || "/-_".includes(text[wordStart - 1]))) {
      wordStart -= 1;
    }
    const letterBefore = wordStart > 0 && isLetter(text[wordStart - 1]);
    if (!letterAfter && !letterBefore) {
      return true;
    }
  }
  return false;
}

/**
 * The first fault of a `why` or a `how` against the grammar of its field (R-3.17, R-6.17), in
 * the words of the refusal message, or `undefined` when the text follows the rule. `field` is
 * `why` or `how`. The checks have a fixed order, the same in every form of Metaform. For a `how`
 * the subject check comes before the `-s` check, so `The router stores` is reported as a
 * subject. The case of the first letter, one trailing full stop, length, and words ending in
 * `-ing` after the first word are not checked (`SPEC.md` D-14).
 */
export function grammarFault(field: string, text: string): string | undefined {
  const first = firstWord(text);
  const subject = SUBJECT_WORDS.includes(first);
  if (field === "why") {
    if (first === "to") {
      return "starts with 'to'";
    }
    if (first.endsWith("ing") && !ING_BASE_VERBS.includes(first)) {
      return "starts with an '-ing' verb";
    }
    if (subject) {
      return "starts with a subject";
    }
  } else {
    if (subject) {
      return "starts with a subject";
    }
    if (!first.endsWith("s")) {
      return "does not start with a verb ending in -s";
    }
  }
  if (hasManyFragments(text)) {
    return "holds more than one fragment";
  }
  if (hasLoneNumber(text)) {
    return "holds a value";
  }
  return undefined;
}

/**
 * Check the `why` and `how` that a command wrote in one want. `written` names the parts the
 * command wrote; a part it did not write is not checked, so a stored want with older text still
 * accepts an unrelated write. `elements` is the map as the command would leave it.
 *
 * The refusal follows the documentation set, module 6.4. The message names each part that
 * broke the rule and its first fault, `why` before `how`, and then states the rule. The tested
 * sentence is the wants sentence of R-6.17 with the texts as written, without their trailing
 * full stop. The remediation updates the want with a placeholder in each part that broke the rule. For a want
 * that `before` holds, it has only those parts. For a want this command made, it has the whole
 * want, because the refused command stored nothing and a want needs all of its fields (R-5.6).
 */
export function checkWantGrammar(
  before: MapModel,
  elements: Sorted<Element>,
  holder: string,
  other: string,
  written: string[],
): void {
  const record = elements.get(holder)?.wants.get(other);
  if (record === undefined) {
    return;
  }
  const text = (key: string): string => {
    const value = record.get(key);
    return typeof value === "string" ? value : "";
  };
  const broken = obj();
  const faults: string[] = [];
  for (const [key, placeholder] of [["why", WHY_PLACEHOLDER], ["how", HOW_PLACEHOLDER]]) {
    if (!written.includes(key) || trim(text(key)) === "") {
      continue;
    }
    const fault = grammarFault(key, text(key));
    if (fault !== undefined) {
      broken.set(key, placeholder);
      faults.push(`${key} ${fault}`);
    }
  }
  if (broken.size === 0) {
    return;
  }
  const stored = before.element(holder)?.wants.has(other) ?? false;
  const parts: JsonObject = stored ? broken : new Map([...record, ...broken]);
  const named = (address: string): string => {
    const name = elements.get(address)?.fields.get("name");
    return typeof name === "string" && trim(name) !== "" ? `${address} (${name})` : address;
  };
  const part = (key: string): string => trim(text(key)).replace(/\.+$/, "");
  const refusal = new Refusal(
    Code.GrammarConstraintViolation,
    `${faults.join("; ")}. ${GRAMMAR_RULE}`,
    obj(["update", obj([holder, obj(["wants", obj([other, parts])])])]),
  );
  refusal.sentence = `${named(holder)} requires ${named(other)} in order to ${part("why")}, which ${part("how")}.`;
  throw refusal;
}
