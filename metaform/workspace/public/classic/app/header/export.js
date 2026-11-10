/* The Export menu, from the earlier page's header/admin.js: the map saved as Markdown or as Mermaid, and copied as
 * Mermaid. The earlier page asked its server for each document, which the command `metaform map` wrote. The new server
 * has no such routes, so this page writes both from the map it already holds: the Mermaid text as the earlier writer,
 * `mermaid` in the earlier outline.py, wrote it, and the Markdown text in the new map's own words. The XML export,
 * the builds, the backups and the administration, which admin.js also held, are not part of this page. */
import '/classic/app/selection/menu.js';  // the part before runs first, so the parts run in the page's order
import {$, h} from '/classic/app/core/dom.js';
import {toast} from '/classic/app/core/controls.js';
import {overlay} from '/classic/app/core/overlays.js';
import {S} from '/classic/app/core/reads.js';
import {toggler} from '/classic/app/header/menus.js';
import {rootsOff} from '/classic/app/header/layers.js';
import {M} from '/classic/app/map2d/build.js';
import {labelOf} from '/classic/app/map2d/inside.js';

/* A file the browser saves, made from a text or a blob, under `name`. */
function saveFile(contents, name, type) {
  const link = h('a', {href: URL.createObjectURL(new Blob([contents], {type})), download: name});
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
const projectName = () => S.projects.find(project => project.id === S.project)?.name || S.project || 'project';
/* The export menu saves the map as a document: Markdown or Mermaid. */
function showExport(open) { $('#exportbox').hidden = !open; }
overlay($('#exportbox'), {kind: 'menu'});
toggler($('#exportBtn'), $('#exportbox'));

/* ---------- Mermaid ----------
 * Mermaid's flowchart syntax, https://mermaid.js.org/syntax/flowchart.html: a node id holds letters, digits and `_`;
 * a label in double quotes takes any character but `"`, written as the entity code `#quot;`, and `#`, written `#35;`,
 * so a label is never read as Mermaid's own; `<br>` breaks a line; `<-->` is an arrow at both ends (there is no arrow
 * at the start alone); `classDef` and `class` style nodes. A lowercase `end` breaks the flowchart, so no id is one.
 * The YAML frontmatter carries the title and the layout, ELK by network simplex, as the page lays out its 2D map; the
 * limits Mermaid renders under, maxTextSize and maxEdges, are secure keys frontmatter cannot raise. */
const MAX_TEXT = 50000;  // Mermaid's default maxTextSize: a longer diagram is refused by a renderer that keeps its defaults
const MAX_EDGES = 500;  // Mermaid's default maxEdges
const ROLES = {Definitive: ['definitive', 'stroke-width:2px,stroke-dasharray:6 3']};
const label = text => String(text).replaceAll('#', '#35;').replaceAll('"', '#quot;').replaceAll('<', '#lt;')
  .replaceAll('>', '#gt;');
/* One want, pointing the way its information goes, as the page's 2D map points it: at the element relied on when the
 * holder sends or nothing is recorded, at the holder when it receives, at both when both. */
function edge(receiver, provider, ifd) {
  const link = ifd === 'both' ? '<-->' : '-->';
  return ifd === 'receives' ? `  ${provider} ${link} ${receiver}` : `  ${receiver} ${link} ${provider}`;
}
/* What a Mermaid renderer that keeps its defaults says to a diagram this long: past `MAX_TEXT` characters or
 * `MAX_EDGES` edges it draws nothing. Null when the diagram is within both. */
export function mermaidLimits(text) {
  const edges = text.split('\n').filter(line => /^\s+\w+ (?:<-->|-->)/.test(line)).length;
  const count = number => number.toLocaleString('en');
  const over = [[`${count(text.length)} characters, past ${count(MAX_TEXT)}`, text.length > MAX_TEXT],
    [`${count(edges)} edges, past ${count(MAX_EDGES)}`, edges > MAX_EDGES]].filter(([, past]) => past)
    .map(([words]) => words);
  if (!over.length) return null;
  return `This diagram has ${over.join(' and ')}: Mermaid with its default limits, as GitHub and mermaid.live run `
    + 'it, refuses it. Draw part of the map, or raise maxTextSize and maxEdges where you render it.';
}
/* The 2D map as a Mermaid flowchart, P063: what the page's 2D map draws at its whole depth, the elements less the
 * roots the page leaves out, and an edge for each want, each pointing the way its information goes, as the 2D map's
 * arrowheads do, in the way the 2D map runs. Each element is a node named by its name, else its technical name, over
 * its address; the Definitive element carries its role's class. The frontmatter gives the title and the page's
 * layout, ELK by network simplex. With an address, that element and those one line away. A diagram past what Mermaid
 * renders by default says so in a comment at its top. */
export function mermaidText({address = null} = {}) {
  const direction = M.base && !M.base.vertical ? 'LR' : 'TB', off = rootsOff();
  let elements = new Map([...S.elements.values()].map(({element}) => [element.address, element])
    .filter(([key]) => !off.has(key.split('.')[0])));
  let edges = S.joins.flatMap(join => join.providers.map(provider => [join.receiver, provider, join.ifd]))
    .filter(([receiver, provider]) => elements.has(receiver) && elements.has(provider));
  if (address) {
    if (!elements.has(address)) throw new Error(`No element at ${address} is shown on this map.`);
    edges = edges.filter(([receiver, provider]) => receiver === address || provider === address);
    const near = new Set([address, ...edges.flatMap(([receiver, provider]) => [receiver, provider])]);
    elements = new Map([...elements].filter(([key]) => near.has(key)));
  }
  const ids = new Map(), taken = new Set();
  for (const key of elements.keys()) {
    let made = key.replace(/[^0-9A-Za-z_]+/g, '_').replace(/^_+|_+$/g, '') || 'node';
    if (/^[0-9]/.test(made) || made.toLowerCase() === 'end') made = `n_${made}`;
    while (taken.has(made)) made += '_';
    taken.add(made);
    ids.set(key, made);
  }
  const title = `${projectName()} functional map` + (address ? ` around ${address}` : '');
  const lines = ['---', `title: ${JSON.stringify(title)}`, 'config:', '  layout: elk', '  elk:',
    '    nodePlacementStrategy: NETWORK_SIMPLEX', '---', `flowchart ${direction}`];
  for (const [key, element] of elements) {
    const called = labelOf(element);
    lines.push(`  ${ids.get(key)}["${label(called)}` + (called !== key ? `<br>${label(key)}` : '') + '"]');
  }
  lines.push(...edges.map(([receiver, provider, ifd]) => edge(ids.get(receiver), ids.get(provider), ifd)));
  for (const [role, [name, style]] of Object.entries(ROLES)) {
    const held = [...elements].filter(([, element]) => element.role === role).map(([key]) => ids.get(key));
    if (held.length) lines.push(`  classDef ${name} ${style}`, `  class ${held.join(',')} ${name}`);
  }
  const text = lines.join('\n') + '\n', notice = mermaidLimits(text);
  return notice ? text.replace('flowchart ', `%% ${notice}\nflowchart `) : text;
}
/* A diagram too long for Mermaid's default limits is said, since GitHub or mermaid.live would draw nothing of it. */
function sayLimits(text) {
  const notice = mermaidLimits(text);
  if (notice) setTimeout(() => toast(notice), 1200);  // after the toast saying it was saved or copied
}
function exportMermaid() {
  showExport(false);
  let text;
  try { text = mermaidText(); } catch (error) { return toast(error.message); }
  saveFile(text, `${projectName()}-map.mmd`, 'text/plain');
  sayLimits(text);
}
async function copyMermaid() {
  showExport(false);
  try {
    const text = mermaidText();
    await navigator.clipboard.writeText(text);
    toast('The map is copied as Mermaid.');
    sayLimits(text);
  } catch (error) { toast(error.message || 'The browser did not let the page copy it.'); }
}
$('#exportMermaid').onclick = exportMermaid;
$('#copyMermaid').onclick = copyMermaid;

/* ---------- Markdown ----------
 * The whole map as a Markdown document: one section for each element, the Definitive element first and the rest by
 * address, with its technical name, its role, its address and its source reference, then each thing it relies on as
 * one sentence: `<address> (<name>) requires <other address> (<other name>) in order to <why>, which <how>.` */
/* A why or a how as part of a sentence: its closing full stop taken off. A why reads as what the element is to do,
 * so its first letter is lowered where its first word is a plain word. A how often starts with an identifier, such
 * as `Transport`, which the page cannot tell from a plain word, so a how is kept as written. */
const clause = text => String(text || '').trim().replace(/[.\s]+$/, '');
const lowered = said => /^[A-Z][a-z']*(?![A-Za-z0-9_/.:(])/.test(said) ? said[0].toLowerCase() + said.slice(1) : said;
const called = (address, element) => element ? `${address} (${labelOf(element)})` : address;
function wantSentence(element, to, want) {
  const why = lowered(clause(want?.why)), how = clause(want?.how);
  return `${called(element.address, element)} requires ${called(to, S.elements.get(to)?.element)}`
    + (why ? ` in order to ${why}` : '') + (how ? `, which ${how}` : '') + '.';
}
export function markdownText() {
  const first = element => element.role === 'Definitive' ? 0 : 1;
  const ordered = [...S.elements.values()].map(({element}) => element)
    .sort((one, two) => first(one) - first(two) || one.address.localeCompare(two.address));
  const lines = [`# ${projectName()} functional map`, ''];
  for (const element of ordered) {
    lines.push(`## ${labelOf(element)}`, '',
      ...(element.short_name ? [`- Technical name: ${element.short_name}`] : []),
      `- Role: ${element.role || 'not recorded'}`,
      ...(element.status ? [`- Status: ${element.status === 'un_built' ? 'not built' : element.status}`] : []),
      `- Address: \`${element.address}\``,
      `- Source reference: ${element.uri ? `\`${element.uri}\`` : 'not recorded'}`, '');
    for (const [to, want] of Object.entries(element.wants)) lines.push(wantSentence(element, to, want), '');
  }
  return lines.join('\n').replace(/\n+$/, '') + '\n';
}
function exportMarkdown() {
  showExport(false);
  saveFile(markdownText(), `${projectName()}-map.md`, 'text/markdown');
}
$('#exportMarkdown').onclick = exportMarkdown;
