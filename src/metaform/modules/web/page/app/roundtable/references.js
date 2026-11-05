/* References open the existing document reader. Search commands are data for the server's bounded lookup,
 * never browser or shell commands. This module has no page state, so a saved note keeps its own project/table. */
const MESSAGE = /^#?R[1-9]\d*-[1-9]\d*$/;
const SEARCH = /^(?:rg|grep)(?:\s|:)/;
const FILE = /^(?:\/?|\.{1,2}\/)(?:[^/?#:\\<>\n]+\/)*[^/?#:\\<>\n]+\.[a-z\d]{1,12}(?::[1-9]\d*(?::[1-9]\d*)?|#L[1-9]\d*(?:-L?[1-9]\d*)?)?$/i;
const TOKENS = /\[([^\]\n]+)\]\((<[^>\n]+>|[^)\n]+)\)|`((?:rg|grep)\s+[^`\n]+)`|https?:\/\/[^\s<>`]+|\bR[1-9]\d*-[1-9]\d*\b|(?<![\w.-])(?:\/?|\.{1,2}\/)(?:[\w.-]+\/)*[\w.-]+\.[a-z\d]{1,12}(?::[1-9]\d*(?::[1-9]\d*)?|#L[1-9]\d*(?:-L?[1-9]\d*)?)?/gi;

function directory(path) {
  const file = String(path || '').replace(/(?::\d+(?::\d+)?|#L\d+(?:-L?\d+)?)$/, '');
  return file.includes('/') ? file.slice(0, file.lastIndexOf('/') + 1) : '';
}

export function referenceHref(value, {project, table, note = '', reference = ''}, relative = false) {
  let text = String(value || '').trim().replace(/^<(.+)>$/, '$1');
  if (/^https?:\/\//i.test(text)) {
    try { return new URL(text).href; } catch { return null; }
  }
  try { text = decodeURIComponent(text); } catch { return null; }
  const message = MESSAGE.test(text), search = SEARCH.test(text), file = FILE.test(text);
  if (!message && !search && !file) return null;
  const query = new URLSearchParams({project, table});
  if (file && relative && note && !text.startsWith('/')) query.set('note', directory(note) + text);
  else query.set('reference', message ? text.replace(/^#/, '')
    : file && relative && FILE.test(reference) && !text.startsWith('/') ? directory(reference) + text : text);
  return `/page/roundtable-note.html?${query}`;
}

export function referenceParts(value, context) {
  const text = String(value ?? ''), parts = [];
  if (SEARCH.test(text) && !text.includes('\n')) return [{text, href: referenceHref(text, context)}];
  let at = 0;
  for (const found of text.matchAll(TOKENS)) {
    if (found.index > at) parts.push({text: text.slice(at, found.index), href: null});
    const markdown = found[1] !== undefined;
    const target = markdown ? found[2] : found[3] || found[0];
    const href = referenceHref(target, context, markdown);
    parts.push({text: href ? markdown ? found[1] : found[3] || found[0] : found[0], href});
    at = found.index + found[0].length;
  }
  if (at < text.length || !parts.length) parts.push({text: text.slice(at), href: null});
  return parts;
}
