/* The graph data both maps draw, built from what the server read: elements, joins as their purpose vertex and
 * encounters, the layers' items and the memories shown at nodes; and what a view hosting the page waits on. */
import '/page/app/header/admin.js';  // the part before runs first, so the parts run in the page's order
import {S} from '/page/app/core/reads.js';
import {underHiddenRoot} from '/page/app/header/layers.js';
import {keyOf, labelOf} from '/page/app/map2d/inside.js';
import {memoryLayer, memoryKey} from '/page/app/memory/graph.js';
import {itemText} from '/page/app/panel/object.js';

/* ---------- the graph data ---------- */
/* The graph as the approved prototype draws it: each join uncollapsed as its receiver, a purpose vertex and the
 * encounter, a link on to each element the join holds; the namespace joins each element to
 * its nearest parent element, VIEW-005. */
export function graphData() {
  const graph = {nodes: [], links: []};
  addElements(graph);
  addJoins(graph);
  const drawn = new Set(graph.nodes.map(node => node.id));
  addItems(graph, drawn);
  addMemories(graph, drawn);
  return graph;
}
/* Each element shown, linked to its nearest parent element. */
function addElements({nodes, links}) {
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.id]));
  for (const {element, parent} of S.elements.values()) {
    if (underHiddenRoot(element.address)) continue;  // an edge of the project the viewer turned off
    nodes.push({id: element.id, t: 'el', name: labelOf(element), address: element.address,
      role: element.role, work: element.open_work || [], layer: element.layer});
    if (parent && byAddress.has(parent)) links.push({source: byAddress.get(parent), target: element.id, k: 'tree'});
  }
}
/* Each join whose receiver and some provider are drawn: its purpose vertex, a link from the receiver to it, and an
 * encounter on to each provider drawn. */
function addJoins({nodes, links}) {
  const ids = new Set(nodes.map(node => node.id));
  for (const join of S.joins) {
    const drawnTo = join.providers.filter(id => ids.has(id));
    if (!ids.has(join.receiver) || !drawnTo.length) continue;
    const purpose = 'p:' + join.id, work = join.open_work || [];
    nodes.push({id: purpose, t: 'purpose', join: join.id, layer: join.layer, work});
    links.push({source: join.receiver, target: purpose, k: 'purpose', layer: join.layer, join: join.id, work});
    for (const provider of drawnTo)
      links.push({source: purpose, target: provider, k: 'encounter', layer: join.layer, join: join.id, work});
  }
}
/* Every item and property of the layers turned on is its own node, hung from its node; a link runs on, VIEW-017.
 * The sources layer's refs are shown in the panel and never hung on the map, the map is the design. */
function addItems({nodes, links}, drawn) {
  const at = thing => thing.kind === 'property' ? thing.item.element_id : keyOf(thing.item.target);
  const hung = [...S.items.values()].filter(thing => drawn.has(at(thing)) && thing.layer !== 'sources');
  for (const thing of hung) {
    nodes.push({id: thing.key, t: 'item', layer: thing.layer, text: itemText(thing.value)});
    drawn.add(thing.key);
  }
  for (const thing of hung) {
    links.push({source: at(thing), target: thing.key, k: 'item', layer: thing.layer});
    const to = keyOf(thing.item.link);
    if (to && drawn.has(to)) links.push({source: thing.key, target: to, k: 'relation', layer: thing.layer});
  }
}
/* Every memory shown at a node is its own node, hung from each node it is kept at, and each relation between two
 * memories drawn is a link, LAYER-013 and VIEW-017. */
function addMemories({nodes, links}, drawn) {
  const memory = memoryLayer();
  for (const [key, names] of S.memory.at) {
    if (!drawn.has(key)) continue;
    for (const name of names) {
      if (!drawn.has(memoryKey(name))) {
        nodes.push({id: memoryKey(name), t: 'item', layer: memory, text: name});
        drawn.add(memoryKey(name));
      }
      links.push({source: key, target: memoryKey(name), k: 'item', layer: memory});
    }
  }
  for (const relation of S.memory.relations) {
    const from = memoryKey(relation.from), to = memoryKey(relation.to);
    if (drawn.has(from) && drawn.has(to))
      links.push({source: from, target: to, k: 'relation', layer: memory, relation: relation.relationType});
  }
}
/* A selection is an element's id or a join as 'p:<id>', the same keys the 3D view uses. */
/* A join as the metaform's shape holds it, D115: `providers` are the ids of every element it holds, each a provider;
 * `provider` and `provider_address` name the first, the one that names the join beside its receiver. */
export const withProviders = join => ({...join, providers: (join.elements || []).map(each => each.element_id),
  provider: join.elements?.[0]?.element_id, provider_address: join.elements?.[0]?.address});
export const joinOf = key => S.joins.find(join => 'p:' + join.id === key);
/* The Address a selection stands for: an element's own, or for a join its receiving element's, since what is known
 * about a join is attached to its RE. */
export const addressOf = id => {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return join ? join.receiver_address : S.elements.get(id)?.element.address;
};
/* What a view that hosts the page waits on, MCP Apps among them: `ready`, a promise kept once the first map is drawn,
 * and `selectAddress`, which selects the node at an Address once it is, as `select` selects a node by its id. */
export const READY = {done: null};
READY.promise = new Promise(resolve => { READY.done = () => { READY.done = null; resolve(true); }; });
