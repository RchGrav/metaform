// Port of `metaform-core/src/rules.rs`. Rules on an element's intake fields that need the map
// (R-3.11 to R-3.13), and the rule that a layer's value is a list (R-6.24). `commands` applies
// them to every element a write touched.

import type { Json, JsonObject } from "./json.ts";
import { equal, isArray, isObject, obj } from "./json.ts";
import type { Element, MapModel } from "./model.ts";
import { ROOT, join } from "./names.ts";
import { Code, Refusal } from "./refusal.ts";
import * as specification from "./specification.ts";
import { words } from "./text.ts";

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
