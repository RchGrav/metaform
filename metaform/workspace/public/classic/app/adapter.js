/* The one part that reads the new Metaform server. It gives the map code of the earlier page the shapes that code
 * was written for, so the earlier parts stay as they were.
 *
 * The new server holds one tree of elements by dotted address, read whole with the `project-map` command `{".": {}}`.
 * Each element may hold `wants`: the elements it relies on, each with `why`, `how` and `direction`. The earlier page
 * held elements with ids and "joins". The mapping:
 *   - an element's id is its address; `name` is its name, `short_name` its `technical_name`; `role`, `status` and
 *     `uri` are kept as the server gives them; `layer` is 'map' for every element.
 *   - `status: "un_built"` becomes the earlier `open_work: ['unbuilt']`, which the map marks.
 *   - one want is one join: its `receiver` is the element that holds the want, and it holds one element, the one
 *     relied on. `purpose` is the want's `why`, `ef` its `how`. `ifd`, the way the information goes as the holder has
 *     it, is `receives` for `inbound`, `sends` for `outbound` and `both` for `two-way`. The earlier names stay inside
 *     the code only; `direction` keeps the new word for the screen.
 *   - an element's `parent` is the nearest element above it by address.
 *   - a field of an element that holds a list is that element's records of a layer of that name. They are kept on the
 *     element as `records` and shown in the side column; the map does not draw them.
 * What has no equivalent: a join that holds several elements (each want names one); memories, tickets and open work
 * other than `un_built`; links from one node's layer record to another node; the server's own search. The brief
 * of an element is the host's answer to `goto`, `readBrief`. */
import '/classic/app/core/reads.js';  // the part before runs first, so the parts run in the page's order
import {S} from '/classic/app/core/reads.js';
import {withProviders} from '/classic/app/graph/data.js';
import {layerOn} from '/classic/app/header/layers.js';

const IFD = {inbound: 'receives', outbound: 'sends', 'two-way': 'both'};
const OWN_FIELDS = new Set(['technical_name', 'name', 'role', 'status', 'uri', 'wants']);
const LAYER_SCOPE = 'layer';
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const isElement = node => ['technical_name', 'name', 'role'].some(key => typeof node[key] === 'string');
const projectPath = project => `/api/projects/${encodeURIComponent(project)}`;

/* One read of the host: its JSON, or an error that says what the host answered. */
async function answer(response) {
  const body = await response.json().catch(() => undefined);
  if (!response.ok || body === undefined) {
    const said = isObject(body) ? body.message || body.error || JSON.stringify(body) : `status ${response.status}`;
    throw new Error(`The Metaform host did not give the map: ${said}`);
  }
  return body;
}
export async function listProjects() {
  return answer(await fetch('/api/projects'));
}
/* The whole map of a project in the earlier page's shapes: `elements`, id to {element, parent}; `joins`; `layers`. */
export async function readMap(project) {
  const dump = await answer(await fetch(`${projectPath(project)}/call`, {method: 'POST',
    headers: {'content-type': 'application/json'}, body: JSON.stringify({'.': {}})}));
  return fromDump(dump);
}
export function fromDump(dump) {
  const tree = isObject(dump?.['.']) ? dump['.'] : {};
  const elements = new Map(), layerNames = new Set(), defined = new Map();
  const walk = (node, address, inLayers, parent) => {
    let here = parent;
    if (inLayers) {
      if (typeof node.instruction === 'string') defined.set(address.split('.').at(-1), node);
    } else if (isElement(node)) {
      const records = {};
      for (const [key, value] of Object.entries(node)) {
        if (Array.isArray(value) && value.length) { records[key] = value; layerNames.add(key); }
      }
      const element = {id: address, address, name: node.name || '', short_name: node.technical_name || '',
        role: node.role || '', status: node.status || '', uri: node.uri || '', layer: 'map',
        open_work: node.status === 'un_built' ? ['unbuilt'] : [], wants: isObject(node.wants) ? node.wants : {},
        records};
      elements.set(address, {element, parent});
      here = address;
    }
    for (const [key, value] of Object.entries(node)) {
      if (!OWN_FIELDS.has(key) && isObject(value)) walk(value, `${address}.${key}`, inLayers, here);
    }
  };
  for (const [key, value] of Object.entries(tree)) if (isObject(value)) walk(value, key, key === LAYER_SCOPE, null);
  const joins = [];
  for (const {element} of elements.values()) {
    for (const [to, want] of Object.entries(element.wants)) {
      if (!elements.has(to) || to === element.address) continue;  // one the map does not hold is said in the side column
      joins.push(withProviders({id: `${element.address}>${to}`, receiver: element.address,
        receiver_address: element.address, elements: [{element_id: to, address: to}], purpose: want?.why || '',
        ef: want?.how || '', ifd: IFD[want?.direction] || 'sends', direction: want?.direction || '', layer: 'map',
        open_work: []}));
    }
  }
  const layers = [{name: 'map', kind: 'base', on: true}, ...[...new Set([...defined.keys(), ...layerNames])].sort()
    .map(name => ({name, kind: 'knowledge', on: true, title: defined.get(name)?.name || name}))];
  return {elements, joins, layers};
}
/* A want's direction in the new map's word, for the screen. */
export const directionWord = join => join?.direction || '';
/* A layer record as text: a block of the specification, which has a title and a text, reads as those two; any other
 * record is left as it is for `itemText` and `itemView`. */
export function recordValue(record) {
  if (isObject(record) && typeof record.text === 'string') {
    return [record.title, record.text].filter(Boolean).join('\n\n');
  }
  return record;
}
/* An element's records, layer by layer, in the layers the Layers checklist leaves on, header/layers.js. */
export const recordsShown = element => Object.entries(element.records).filter(([layer]) => layerOn(layer));
/* An element as an agent is handed it: the host's answer to the `project-map` command `{"goto": "<address>"}`, as
 * the text the host sent and as the object it holds. A refusal is an error that carries what the host said. */
export async function readBrief(project, address) {
  const response = await fetch(`${projectPath(project)}/call`, {method: 'POST',
    headers: {'content-type': 'application/json'}, body: JSON.stringify({goto: address})});
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { body = undefined; }
  if (!response.ok || !isObject(body) || body.status === 'error') {
    throw new Error(isObject(body) ? body.message || body.error || text : `The Metaform host answered ${response.status}.`);
  }
  return {text, body};
}
/* What the layers hold at a node, in the shape the earlier page's read of a node gave: one group for each layer. */
export function nodeView(key) {
  const element = S.elements.get(key)?.element;
  if (!element) return {layers: []};
  return {layers: recordsShown(element).map(([layer, records]) => ({layer, kind: 'knowledge',
    items: records.map((record, index) => ({id: `${element.address}#${layer}#${index}`, value: recordValue(record)}))}))};
}
/* The layers' records that hold every word of `query`, the first `limit`, each with the element it is at, in the shape
 * the earlier page's search of the store gave. */
export function searchRecords(query, limit) {
  const words = String(query).toLowerCase().split(/\s+/).filter(Boolean), found = [];
  if (!words.length) return found;
  for (const {element} of S.elements.values()) {
    for (const [layer, records] of recordsShown(element)) {
      records.forEach((record, index) => {
        const text = typeof record === 'string' ? record : JSON.stringify(record);
        if (found.length < limit && words.every(word => text.toLowerCase().includes(word))) {
          found.push({id: `${element.address}#${layer}#${index}`, layer, value: recordValue(record),
            target: {kind: 'element', id: element.id}});
        }
      });
    }
  }
  return found;
}
/* The map's changes on the server, as the earlier page followed `map.changed`: `changed` runs a moment after the
 * host says the map changed, once for a burst. Gives back what ends the following. */
export function follow(project, changed) {
  const stream = new EventSource(`${projectPath(project)}/events`);
  let timer = 0;
  const heard = () => { clearTimeout(timer); timer = setTimeout(changed, 250); };
  stream.addEventListener('map-changed', heard);
  return () => { clearTimeout(timer); stream.removeEventListener('map-changed', heard); stream.close(); };
}
