/**
 * Render a project's map as a readable specification (R-1.2). The base map is the skeleton; each
 * layer record is one sentence from its layer's template (R-6.16, R-6.20). The CLI calls this; it is
 * not an MCP command, because MCP is for data manipulation and reads (R-5.14 to R-5.16).
 */
import type { Element, Want } from './store.ts';
import { flatten, isObject, projectIn, type Json } from './tree.ts';

/** A layer definition, as R-6.16 gives it. Only `template` is used here. */
export interface LayerDefinition {
  description?: string;
  template?: string;
  fields?: Json;
  instruction?: string;
  named?: boolean;
}

/** The wants definition's sentence (R-6.17). */
export const WANTS_TEMPLATE = '{this.address} ({this.name}) requires {other.address} ({other.name}) in order to {why}, which {how}.';

/** Fields of the base map. Every other field of an element is a layer. */
const INTAKE_FIELDS = new Set(['technical_name', 'name', 'name_length', 'role', 'uri', 'status', 'wants', 'id', 'project']);

/** The role hierarchy (R-3.13, R-3.20), with the earlier names the stored maps still use. */
const ROLES: [string, string[]][] = [
  ['Definitive', ['definitive', 'de', 'defining']],
  ['Supportive', ['supportive', 'se', 'substantial', 'subtantial']],
  ['Notable', ['notable', 'ne']],
  ['Divergent', ['divergent']],
];

function roleOf(element: Element): string | null {
  const role = typeof element.fields.role === 'string' ? element.fields.role.trim().toLowerCase() : '';
  if (role === '') return null;
  return ROLES.find(([, names]) => names.includes(role))?.[0] ?? 'Unrecognized role';
}

/**
 * A stored goal or function made to fit inside a template sentence: no trailing full stop, and a
 * first capital lowered when the next letter is lower case (so "Receive" becomes "receive", while
 * "Jev" or "ACP" stay as written).
 */
export function fragment(text: string): string {
  const trimmed = text.trim().replace(/[.]+$/, '');
  return /^[A-Z][a-z]/.test(trimmed) ? trimmed[0].toLowerCase() + trimmed.slice(1) : trimmed;
}

/** Fill a template's `{placeholder}` names from `values`. An unknown name is left visible. */
export function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{([a-z_.]+)\}/g, (whole, key: string) => values[key] ?? whole);
}

function wantSentence(holder: Element, want: Want, names: Map<string, string>): string {
  return fill(WANTS_TEMPLATE, {
    'this.address': `\`${holder.address}\``,
    'this.name': names.get(holder.address) ?? holder.address,
    'other.address': `\`${want.provider}\``,
    'other.name': names.get(want.provider) ?? want.provider,
    // The stored fields are still goal and function until the R-3.4 renames (DECISIONS.md term mapping).
    why: fragment(want.why),
    how: fragment(want.how),
  });
}

/** The records of one layer at one element: a list, or a dictionary keyed by record name. */
function records(value: unknown): [string | null, unknown][] {
  if (Array.isArray(value)) return value.map((record) => [null, record]);
  if (isObject(value)) return Object.entries(value);
  return [[null, value]];
}

function recordSentence(element: Element, name: string | null, record: unknown, template: string | undefined, names: Map<string, string>): string {
  const values: Record<string, string> = {
    'this.address': `\`${element.address}\``,
    'this.name': names.get(element.address) ?? element.address,
  };
  if (name !== null) values.name = name;
  if (isObject(record)) {
    for (const [key, value] of Object.entries(record)) values[key] = typeof value === 'string' ? fragment(value) : JSON.stringify(value);
  } else values.value = typeof record === 'string' ? record : JSON.stringify(record);
  if (template !== undefined) return fill(template, values);
  // No template: show the record as written, so nothing is lost from the export.
  const label = name !== null ? `${name}: ` : '';
  return `${label}${typeof record === 'string' ? record : JSON.stringify(record)}`;
}

function elementSection(element: Element, names: Map<string, string>, layers: Record<string, LayerDefinition>): string[] {
  const name = names.get(element.address) ?? element.address;
  const technical = typeof element.fields.technical_name === 'string' ? ` — ${element.fields.technical_name}` : '';
  const lines = [`### ${name} (\`${element.address}\`)${technical}`, ''];
  for (const key of ['status', 'uri']) {
    if (typeof element.fields[key] === 'string') lines.push(`- ${key}: ${element.fields[key] as string}`);
  }
  if (lines.length > 2) lines.push('');
  for (const want of element.wants) lines.push(wantSentence(element, want, names), '');
  for (const [layer, value] of Object.entries(element.fields)) {
    if (INTAKE_FIELDS.has(layer)) continue;
    lines.push(`**${layer}**`, '');
    for (const [recordName, record] of records(value)) {
      lines.push(`- ${recordSentence(element, recordName, record, layers[layer]?.template, names)}`);
    }
    lines.push('');
  }
  return lines;
}

/** The whole specification as Markdown, from an exported document and the project's layer definitions. */
export function renderSpecification(document: Json, layers: Record<string, LayerDefinition> = {}): string {
  const [project, body] = projectIn(document);
  const elements = flatten(body, '');
  const names = new Map(elements.map((element) => [element.address, typeof element.fields.name === 'string' ? element.fields.name : element.address]));
  const root = elements.find((element) => element.address === '');
  const title = typeof root?.fields.name === 'string' ? root.fields.name : project;
  // A trunk that a write created has no fields of its own; every other element is part of the specification.
  const placed = elements.filter((element) => element.address !== '' && (Object.keys(element.fields).length > 0 || element.wants.length > 0));
  const outside = (element: Element) => /^(upstream|downstream)(\.|$)/.test(element.address);
  const byAddress = (a: Element, b: Element) => a.address.localeCompare(b.address);

  const lines = [`# ${title}`, ''];
  const projectWide = root === undefined ? [] : Object.keys(root.fields).filter((key) => !INTAKE_FIELDS.has(key));
  if (root !== undefined && projectWide.length > 0) {
    lines.push('## Project-wide', '');
    for (const layer of projectWide) {
      lines.push(`**${layer}**`, '');
      for (const [recordName, record] of records(root.fields[layer])) {
        lines.push(`- ${recordSentence(root, recordName, record, layers[layer]?.template, names)}`);
      }
      lines.push('');
    }
  }
  const groups: [string, Element[]][] = [
    ...ROLES.map(([role]) => [role, placed.filter((element) => !outside(element) && roleOf(element) === role)] as [string, Element[]]),
    ['Unrecognized role', placed.filter((element) => !outside(element) && roleOf(element) === 'Unrecognized role')],
    ['Without a role', placed.filter((element) => !outside(element) && roleOf(element) === null)],
    ['What the project relies on', placed.filter((element) => element.address.startsWith('upstream'))],
    ['What relies on the project', placed.filter((element) => element.address.startsWith('downstream'))],
  ];
  for (const [heading, members] of groups) {
    if (members.length === 0) continue;
    lines.push(`## ${heading}`, '');
    for (const element of [...members].sort(byAddress)) lines.push(...elementSection(element, names, layers));
  }
  return `${lines.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd()}\n`;
}
