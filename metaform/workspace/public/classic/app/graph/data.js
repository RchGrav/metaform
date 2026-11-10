/* The graph data both maps draw, from the earlier page's graph/data.js: elements, and joins as encounters. The
 * layers' items and the memories that file also hung on the 3D map are not part of this page: the new map's layer
 * records are read in the side column. */
import '/classic/app/header/menus.js';  // the part before runs first, so the parts run in the page's order
import {S} from '/classic/app/core/reads.js';
import {underHiddenRoot} from '/classic/app/header/layers.js';
import {labelOf} from '/classic/app/map2d/inside.js';
import {depthView} from '/classic/app/keys/walk.js';

/* ---------- the graph data ---------- */
/* The graph as the approved prototype draws it: each join uncollapsed as its receiver, a purpose vertex and the
 * encounter, a link on to each element the join holds; the namespace joins each element to
 * its nearest parent element, VIEW-005. */
export function graphData() {
  const graph = {nodes: [], links: []};
  addElements(graph);
  addJoins(graph);
  return graph;
}
/* Each element shown, linked to its nearest parent element; one deeper than the depth stays inside the node that
 * holds it, which says how many it holds, VIEW-051. */
function addElements({nodes, links}) {
  const byAddress = new Map([...S.elements.values()].map(entry => [entry.element.address, entry.element.id]));
  const {shown, held} = depthView(), work = workShown();
  for (const {element, parent} of S.elements.values()) {
    if (underHiddenRoot(element.address)) continue;  // an edge of the project the viewer turned off
    if (shown && !shown.has(element.id)) continue;
    nodes.push({id: element.id, t: 'el', name: heldName(labelOf(element), held.get(element.id)),
      address: element.address, role: element.role, work: work.get(element.id) || [], layer: element.layer,
      held: held.get(element.id) || 0});
    const above = parent && byAddress.get(parent);  // a parent held deeper than the depth is not drawn to
    if (above && (!shown || shown.has(above))) links.push({source: above, target: element.id, k: 'tree'});
  }
}
/* Each join whose receiver and some provider are drawn is drawn as edges alone, one from its receiver to each provider
 * drawn, with no node of its own: nothing attaches to a join, everything to its receiving element (the Join rule,
 * Rich, 2026-10-17). What the join's node showed, its open work, shows on its receiver; the edges keep the join's
 * id, layer and work, so a join is still picked by its edge and its flow runs along it. The namespace's own link
 * between the same two elements is left out where a join's edge draws it, so no two fibers lie on one another. */
function addJoins({nodes, links}) {
  const byId = new Map();
  for (const node of nodes) byId.set(node.id, node);
  const joined = new Set();
  for (const join of S.joins) {
    if (!byId.has(join.receiver)) continue;
    const work = join.open_work || [];
    for (const provider of join.providers) {
      if (provider === join.receiver || !byId.has(provider)) continue;
      links.push({source: join.receiver, target: provider, k: 'encounter', layer: join.layer, join: join.id, work});
      joined.add(join.receiver + '>' + provider).add(provider + '>' + join.receiver);
    }
  }
  if (!joined.size) return;
  let kept = 0;
  for (const link of links) {
    if (link.k === 'tree' && joined.has(link.source + '>' + link.target)) continue;
    links[kept++] = link;
  }
  links.length = kept;
}

/* A node's name with the count of the parts it holds beneath it, VIEW-051. */
export const heldName = (name, held) => held ? `${name} +${held}` : name;
/* Each element's open work as the map shows it: its own, then that of the joins it receives, which have no node of
 * their own to show it on; worked out once for a whole drawing. */
export function workShown() {
  const shown = new Map();
  for (const {element} of S.elements.values()) shown.set(element.id, element.open_work || []);
  for (const join of S.joins) {
    const own = shown.get(join.receiver), work = join.open_work;
    if (!own || !work?.length) continue;
    shown.set(join.receiver, [...new Set([...own, ...work])]);
  }
  return shown;
}
/* The node the selection is drawn on in the 3D map: the selected node's, or a join's receiving element's. */
export const selectedNode = () => {
  const id = S.selected;
  return id && id.startsWith('p:') ? joinOf(id)?.receiver ?? id : id;
};
/* The node a key stands for in the 3D map: a join's, 'p:<id>', is its receiving element's, as a join has no node of
 * its own; each map's nodes indexed once by id, so a frame looks a node up without walking them. */
const INDEXED = new WeakMap();
export function nodeIn(data, key) {
  if (!data || !key) return undefined;
  let byId = INDEXED.get(data.nodes);
  if (!byId || byId.size !== data.nodes.length) {
    byId = new Map();
    for (const node of data.nodes) byId.set(node.id, node);
    INDEXED.set(data.nodes, byId);
  }
  const found = byId.get(key);
  if (found || typeof key !== 'string' || !key.startsWith('p:')) return found;
  const join = S.joins.find(one => 'p:' + one.id === key);
  return join ? byId.get(join.receiver) : undefined;
}
/* A selection is an element's id or a join as 'p:<id>', the same keys the 3D view uses. */
/* A join as the map code holds it: `providers` are the ids of every element it holds, each a provider;
 * `provider` and `provider_address` name the first, the one that names the join beside its receiver. */
export const withProviders = join => ({...join, providers: (join.elements || []).map(each => each.element_id),
  provider: join.elements?.[0]?.element_id, provider_address: join.elements?.[0]?.address});
export const joinOf = key => S.joins.find(join => 'p:' + join.id === key);
/* The Address a selection stands for: an element's own, or for a join its receiving element's. */
export const addressOf = id => {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return join ? join.receiver_address : S.elements.get(id)?.element.address;
};
