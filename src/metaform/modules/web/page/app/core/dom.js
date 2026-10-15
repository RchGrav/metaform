/* The page's DOM helpers: $ and css, a node built from a tag, its properties and children with text never set as
 * markup, and lists filled in place so what is typed and focused survives a redraw. */

export const $ = selector => document.querySelector(selector);
/* A theme token, a CSS variable of the page's root, read from the browser once and kept until the root changes: the 3D
 * map reads its colours for every node on every frame, and each read of the computed style cost the frame. A theme,
 * a text size or a class set on <html> is a change to its attributes, seen at the next read even within the same
 * task, `takeRecords`; a resize may cross a media query. An empty value, read before the page's styles apply, is not
 * kept. */
const TOKENS = new Map();
const ROOT_SEEN = new MutationObserver(() => TOKENS.clear());
ROOT_SEEN.observe(document.documentElement, {attributes: true});
addEventListener('resize', () => TOKENS.clear());
export const css = name => {
  if (ROOT_SEEN.takeRecords().length) TOKENS.clear();
  let value = TOKENS.get(name);
  if (value === undefined) {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    if (value) TOKENS.set(name, value);
  }
  return value;
};
// asked once; the list answers for the person's setting as it is now, whenever it changes
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');
export const reduced = () => REDUCED.matches;
export const SVG = 'http://www.w3.org/2000/svg';

/* A DOM node from a tag, its properties and its children; strings become text nodes, never markup. */
export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) setProp(node, key, value);
  return put(node, children, false);
}
/* One property of `h`: a class, a style map, an event handler by its `on` name, or an attribute; an absent value
 * (undefined, null or false) sets nothing, and true sets the attribute empty. */
function setProp(node, key, value) {
  if (value === undefined || value === null || value === false) return;
  if (key === 'class') node.className = value;
  else if (key === 'style') for (const [name, v] of Object.entries(value)) node.style.setProperty(name, v);
  else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
  else node.setAttribute(key, value === true ? '' : value);
}
const present = child => child !== null && child !== undefined && child !== false;
/* Fill a node with children: nested lists are flattened, empty ones dropped, strings kept as text. */
function put(node, children, replace = true) {
  const kids = [children].flat(Infinity).filter(present).map(child => child instanceof Node ? child : String(child));
  if (replace) node.replaceChildren(...kids); else node.append(...kids);
  return node;
}
export const fill = (node, ...children) => put(node, children);
/* Fill a node with these children, leaving in place each one already there in its place, so a text being typed into
 * keeps its text, its cursor and the focus. */
export function keepFill(node, kids) {
  for (const child of [...node.childNodes]) if (!kids.includes(child)) child.remove();
  kids.forEach((kid, index) => {
    if (node.childNodes[index] !== kid) node.insertBefore(kid, node.childNodes[index] || null);
  });
}
/* Fill a list from rows {key, text, make}: a row whose key and text are unchanged keeps its node, a changed one is made
 * again, a new one is added, so a thread that grows only appends and never flashes. Says whether anything changed. */
export function keyedFill(node, rows) {
  const before = node.keyed || new Map(), now = new Map();
  let changed = rows.length !== before.size;
  for (const row of rows) {
    const had = before.get(row.key);
    if (had && had.text === row.text) now.set(row.key, had);
    else { changed = true; now.set(row.key, {text: row.text, node: row.make()}); }
  }
  node.keyed = now;
  keepFill(node, [...now.values()].map(one => one.node));
  return changed;
}
