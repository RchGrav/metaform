// The one typed model of a project's functional specification (ARCHITECTURE.md section 1).
// The graph, the outline, the entity panel and the Markdown are views of a `Spec`.
// `fromDump` builds a `Spec` from the server's raw dump. Every function here is pure.

import type { Address, RawDump, Role } from "../source/types";

/** Where an element lies: in the project, among those the project serves, or among what it relies on. */
export type Band = "project" | "downstream" | "upstream";

/** The element fields a change may set. They are the element's own scalar fields. */
export const FIELD_NAMES = ["name", "technical_name", "role", "status", "uri"] as const;

/** One of the element fields a change may set. */
export type FieldName = (typeof FIELD_NAMES)[number];

/** The three parts of a want that hold text. */
export const WANT_PARTS = ["why", "how", "direction"] as const;

/** One of the three parts of a want. */
export type WantPart = (typeof WANT_PARTS)[number];

/** One want: the holder relies on the element at `to`. A part the map does not hold is an empty string. */
export interface SpecWant {
  to: Address;
  why: string;
  how: string;
  direction: string;
}

/** One element of the specification, with its wants and the records of each layer it carries. */
export interface SpecElement {
  address: Address;
  band: Band;
  name?: string;
  technical_name?: string;
  /** The map's role word. A value the page does not know is kept as the map holds it. */
  role?: Role | string;
  status?: string;
  /** The source reference: the entry point of the element's functionality. */
  uri?: string;
  /** Ordered by the wanted address. */
  wants: SpecWant[];
  /** Records by layer name. A layer with no records has no entry. */
  layers: Record<string, unknown[]>;
}

/** A layer's definition, from the `layer` scope of the map. It describes the map, not the project. */
export interface LayerDefinition {
  /** The definition's address, such as "layer.document.specification". */
  address: Address;
  /** The field that holds the layer's records at an element: the last segment of the address. */
  field: string;
  name?: string;
  description?: string;
}

/** Who made a change that the server has not confirmed: the user, or an agent whose proposal the user accepted. */
export type Origin = "user" | "agent";

/**
 * A mark on one part of the specification that a change set and the server has not confirmed.
 * Exactly one of `field`, `want` and `layer` is present. A `Spec` built from a dump has no marks.
 */
export interface Mark {
  /** The `id` of the change that set this part. */
  id: string;
  address: Address;
  origin: Origin;
  field?: FieldName;
  /** The wanted address of the want that changed. */
  want?: Address;
  layer?: string;
}

/** The canonical specification of one project. */
export interface Spec {
  /** The project's name, as the host lists it. */
  project: string;
  /** Every element in the three bands, ordered by address. Layer definitions are not here. */
  elements: SpecElement[];
  /** The layer definitions, ordered by address. */
  layerDefinitions: LayerDefinition[];
  /** Layer records the map holds at the project's root, by layer name. */
  rootLayers: Record<string, unknown[]>;
  /** Parts that a change set and the server has not confirmed. */
  marks: Mark[];
}

const LAYER_SCOPE = "layer";

/** Compares two strings by code unit, so the order does not depend on the browser's locale. */
export function byText(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** The band an address lies in, from its first segment. */
export function bandOf(address: Address): Band {
  const first = address.split(".")[0];
  return first === "upstream" || first === "downstream" ? first : "project";
}

/** The first segment of an address, such as "code" in "code.engine.game". */
export function firstSegment(address: Address): string {
  const cut = address.indexOf(".");
  return cut < 0 ? address : address.slice(0, cut);
}

/** True when `address` is `scope` or lies beneath it. A null scope holds every address. */
export function inScope(address: Address, scope: Address | null): boolean {
  return scope === null || address === scope || address.startsWith(`${scope}.`);
}

/** The element at an address, or undefined when the specification has none there. */
export function elementAt(spec: Spec, address: Address): SpecElement | undefined {
  return spec.elements.find((element) => element.address === address);
}

/** The name to show for an element: its project name, else its technical name, else its address. */
export function labelOf(element: SpecElement): string {
  return element.name ?? element.technical_name ?? element.address;
}

/** The name to show for an address: the label of the element there, or the address when there is none. */
export function labelAt(spec: Spec, address: Address): string {
  const element = elementAt(spec, address);
  return element ? labelOf(element) : address;
}

/** The one Definitive element inside the project, or undefined when the map has none. */
export function definitiveOf(spec: Spec): SpecElement | undefined {
  return spec.elements.find((element) => element.band === "project" && element.role === "Definitive");
}

/** A want together with the element that holds it. */
export interface HeldWant {
  holder: Address;
  want: SpecWant;
}

/** Every want that names `address`: the elements that rely on it. Ordered by the holder's address. */
export function wantedBy(spec: Spec, address: Address): HeldWant[] {
  const out: HeldWant[] = [];
  for (const element of spec.elements) {
    for (const want of element.wants) if (want.to === address) out.push({ holder: element.address, want });
  }
  return out;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value !== "" ? value : undefined;
}

function wantsOf(node: Record<string, unknown>): SpecWant[] {
  const held = node.wants;
  if (!isObject(held)) return [];
  const wants: SpecWant[] = [];
  for (const [to, record] of Object.entries(held)) {
    if (!isObject(record)) continue;
    wants.push({
      to,
      why: text(record.why) ?? "",
      how: text(record.how) ?? "",
      direction: text(record.direction) ?? "",
    });
  }
  return wants.sort((a, b) => byText(a.to, b.to));
}

function layersOf(node: Record<string, unknown>): Record<string, unknown[]> {
  const layers: Record<string, unknown[]> = {};
  for (const key of Object.keys(node).sort(byText)) {
    const value = node[key];
    if (Array.isArray(value) && value.length > 0) layers[key] = value;
  }
  return layers;
}

function isElement(node: Record<string, unknown>): boolean {
  return text(node.technical_name) !== undefined || text(node.name) !== undefined || text(node.role) !== undefined;
}

function elementOf(address: Address, node: Record<string, unknown>): SpecElement {
  const element: SpecElement = { address, band: bandOf(address), wants: wantsOf(node), layers: layersOf(node) };
  for (const field of FIELD_NAMES) {
    const value = text(node[field]);
    if (value !== undefined) element[field] = value;
  }
  return element;
}

function definitionOf(address: Address, node: Record<string, unknown>): LayerDefinition {
  const definition: LayerDefinition = { address, field: address.slice(address.lastIndexOf(".") + 1) };
  const name = text(node.name);
  const description = text(node.description);
  if (name !== undefined) definition.name = name;
  if (description !== undefined) definition.description = description;
  return definition;
}

/**
 * Builds the specification from the server's raw dump, `{".": <the stored tree>}`.
 * An element is an address that has at least one of `technical_name`, `name` and `role`.
 * An address beneath `layer` with an `instruction` is a layer definition and is kept apart.
 * An address that is neither is a path to the elements beneath it and is not recorded.
 */
export function fromDump(projectName: string, rawDump: RawDump): Spec {
  const tree = isObject(rawDump["."]) ? rawDump["."] : {};
  const elements: SpecElement[] = [];
  const layerDefinitions: LayerDefinition[] = [];

  const walk = (node: Record<string, unknown>, address: Address, inLayers: boolean): void => {
    if (inLayers) {
      if (typeof node.instruction === "string" && address !== LAYER_SCOPE) {
        layerDefinitions.push(definitionOf(address, node));
      }
    } else if (isElement(node)) {
      elements.push(elementOf(address, node));
    }
    for (const [key, value] of Object.entries(node)) {
      if (key !== "wants" && isObject(value)) walk(value, `${address}.${key}`, inLayers);
    }
  };

  for (const [key, value] of Object.entries(tree)) {
    if (isObject(value)) walk(value, key, key === LAYER_SCOPE);
  }
  elements.sort((a, b) => byText(a.address, b.address));
  layerDefinitions.sort((a, b) => byText(a.address, b.address));
  return { project: projectName, elements, layerDefinitions, rootLayers: layersOf(tree), marks: [] };
}
