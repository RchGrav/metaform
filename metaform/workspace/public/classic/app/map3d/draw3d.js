/* The 3D view draws the map, places new nodes beside their neighbours, keeps the layout calm on small changes, and
 * follows the theme. From the earlier page's map3d/draw3d.js; a node's memory network and the marks of open work,
 * which that file also drew, are not part of this page. */
import '/classic/app/flow/fx3d.js';  // the part before runs first, so the parts run in the page's order
// The Space theme, web_theme space: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/classic/ultra.js';
import {$, css} from '/classic/app/core/dom.js';
import {graphData} from '/classic/app/graph/data.js';
import {endOf} from '/classic/app/map3d/waves.js';
import {G, grounded, wake3d, FIBERS, ballOf} from '/classic/app/map3d/graph3d.js';
import {unbuilt} from '/classic/app/map3d/ghosts.js';
import {hovered, setHovered} from '/classic/app/map3d/pick3d.js';
import {tags, dropLabel, relabel} from '/classic/app/map3d/labels.js';
import {phaseOf} from '/classic/app/flow/fx3d.js';
import {V3} from '/classic/app/camera/flight.js';
import {PHYS, applyPhysics} from '/classic/app/views/bar.js';
import {setMermaidReady, build2D} from '/classic/app/map2d/build.js';

/* The 3D view draws the map. `previous` holds where each node stood, the positions of what is drawn now unless
 * given. */
export function draw3D(previous = null) {
  if (!G) return;
  const shown = G.graphData();
  previous = previous || new Map(shown.nodes.map(node => [node.id, node]));
  const fresh = graphData();
  // the map's nodes and links drawn already are kept, the same objects, so the graph makes again only what is new or
  // now looks otherwise
  const {data, same} = kept3d(shown, fresh);
  keepPlaces(data, previous);
  holdKept(data);
  arrivals(data);
  const named = new Set(data.nodes.filter(node => node.t === 'el').map(node => node.id));
  for (const id of [...tags.keys()]) if (!named.has(id)) dropLabel(id);
  if (hovered) setHovered(data.nodes.find(node => node.id === hovered.id) || null);
  $('#tip3d').hidden = !hovered;
  if (same) {  // nothing added, removed or to be made again: what changed was copied onto what is drawn, VIEW-018
    relabel();  // a name or a record changed in the same nodes
    FIBERS.version++;  // and the links' looks are read again
    wake3d();
    return;
  }
  G.warmupTicks(0);  // the map keeps its own layout running from where each node stands
  G.graphData(data);
  applyPhysics(PHYS.name, false);  // its chains of service and its parts read again
  V3.layouts++;
}
/* The graph to draw, built of the objects drawn now wherever they stand for the same thing: the graph library knows a
 * node or link by its object, so a node given as a new object was made again, with all it draws, for every node at
 * every change, and for every page of a load (critic F1, 2026-10-17). A node whose look its object was made for
 * changed, a part built or not built any more, of another role, address or layer, is given as new and so made again;
 * every other keeps its object and takes the new values. `same`: nothing new, gone or made again. */
function kept3d(shown, fresh) {
  const byId = new Map();
  for (const node of shown.nodes) byId.set(node.id, node);
  const nodes = [], links = [], pending = new Map();
  let same = shown.nodes.length === fresh.nodes.length && shown.links.length === fresh.links.length;
  for (const node of fresh.nodes) {
    const old = byId.get(node.id);
    if (old && sameLook(old, node)) { copyOnto(old, node); nodes.push(old); } else { nodes.push(node); same = false; }
  }
  for (const link of shown.links) listAt(pending, linkKey(link)).push(link);
  for (const link of fresh.links) {
    const old = pending.get(linkKey(link))?.pop();
    // a link to a node made again is made again too, so it joins the node's new object
    if (old && byId.get(end(old.source)) === nodeOf(nodes, end(link.source))
      && byId.get(end(old.target)) === nodeOf(nodes, end(link.target))) {
      copyOnto(old, link);
      links.push(old);
    } else { links.push(link); same = false; }
  }
  return {data: {nodes, links}, same};
}
let NODES_AT = null;
function nodeOf(nodes, id) {  // the node kept or made for an id, indexed once for the list
  if (!NODES_AT || NODES_AT.list !== nodes || NODES_AT.size !== nodes.length) {
    NODES_AT = {list: nodes, size: nodes.length, byId: new Map()};
    for (const node of nodes) NODES_AT.byId.set(node.id, node);
  }
  return NODES_AT.byId.get(id);
}
const sameLook = (old, node) => old.t === node.t && old.role === node.role && old.address === node.address
  && old.layer === node.layer && unbuilt(old) === unbuilt(node);
function copyOnto(into, from) {
  for (const key of Object.keys(from)) if (!PLACE.has(key)) into[key] = from[key];
}

/* Each node keeps where it was drawn, so the picture does not jump as pages arrive. */
function keepPlaces(data, previous) {
  for (const node of data.nodes) {
    const known = previous.get(node.id);
    if (known) Object.assign(node, {x: known.x, y: known.y, z: known.z, vx: known.vx, vy: known.vy, vz: known.vz,
      fx: known.fx, fy: known.fy, fz: known.fz});
  }
}
/* A list kept under a key of a map, made the first time the key is used. */
function listAt(map, key) {
  if (!map.has(key)) map.set(key, []);
  return map.get(key);
}
/* A node new to a map already laid out starts beside a node it is linked to, a little way off in a direction its id
 * gives, so it grows out of the part it belongs to and the layout only eases it into place: started where the layout
 * puts a node with no place, around the middle of the map, it was pulled across the whole map and the nodes it passed
 * were shaken. Nodes linked to nothing placed, and every node of a map with nothing placed yet or with much of it new,
 * are left to the layout, which warms itself for the share of nodes it has to place. */
/* While a branch opens or closes, `GROW.beside`, keys/walk.js FOCUS, every new part starts beside its receiver
 * whatever the share new, since the branch grows out of a map already laid out, and every part already drawn is held
 * where it stands, `pinned`, so only the branch moves. The hold ends at the next draw of any other change, which lays
 * the map out as before. */
export const GROW = {beside: false, pinned: new Set()};
function holdKept(data) {
  for (const node of data.nodes) {
    if (GROW.pinned.has(node.id) && !GROW.beside) Object.assign(node, {fx: undefined, fy: undefined, fz: undefined});
    else if (GROW.beside && node.x !== undefined && node.fx === undefined) {
      Object.assign(node, {fx: node.x, fy: node.y, fz: node.z});
      GROW.pinned.add(node.id);
    }
  }
  if (!GROW.beside) GROW.pinned.clear();
}
function arrivals(data) {
  const fresh = data.nodes.filter(node => node.x === undefined).length;
  if (!fresh || fresh === data.nodes.length
    || (!GROW.beside && fresh > Math.max(3, data.nodes.length * 0.15))) return;
  const byId = new Map(data.nodes.map(node => [node.id, node])), linked = new Map();
  for (const link of data.links) {
    const one = endOf(link.source), two = endOf(link.target);
    listAt(linked, one).push(two);
    listAt(linked, two).push(one);
  }
  // a chain of new nodes is placed one link at a time
  for (let round = 0, placedSome = true; placedSome && round < 8; round++) {
    placedSome = false;
    for (const node of data.nodes) {
      if (node.x !== undefined) continue;
      const beside = (linked.get(node.id) || []).map(id => byId.get(id)).find(other => other && other.x !== undefined);
      if (!beside) continue;
      placeBeside(node, beside);
      placedSome = true;
    }
  }
}
/* A new node a little way off a placed neighbour, in the direction its id gives. */
function placeBeside(node, beside) {
  const turn = phaseOf(node.id) * 2 * Math.PI, rise = phaseOf(node.id + '^') * 2 - 1, out = Math.sqrt(1 - rise * rise);
  const apart = ballOf(beside) + ballOf(node) + 6;
  Object.assign(node, {x: beside.x + Math.cos(turn) * out * apart, y: beside.y + rise * apart,
    z: beside.z + Math.sin(turn) * out * apart, vx: 0, vy: 0, vz: 0});
}
/* What a node or link is apart from where the layout puts it and what the graph library binds to it. */
const PLACE = new Set(['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz', 'index', '__threeObj', '__lineObj',
  '__arrowObj', '__photonsObj', '__curve', 'source', 'target']);
const end = value => value && typeof value === 'object' ? value.id : value;
const linkKey = link => `${end(link.source)}>${end(link.target)}>${link.k}>${link.join ?? ''}`;
/* A theme recolors both views in place, VIEW-023: the 3D view rereads its colors, the 2D map is drawn again. The
 * choice is the viewer's own, kept in this browser. */
/* The theme is the one choice of look: space draws the 3D map in outer space, ULTRA, and every other theme flat. */
export const PLAIN = {last: 'black'};
export function setTheme(name) {
  document.documentElement.dataset.theme = name;
  if (name !== 'space') PLAIN.last = name;
  if ($('#theme') && $('#theme').value !== name) $('#theme').value = name;
  ULTRA.setting(name === 'space' ? 'ultra' : 'clean');
  try { localStorage.setItem('metaform.theme', name); } catch (error) { /* storage can be blocked; it still shows */ }
  if (G) recolor3d();
  setMermaidReady(false);
  build2D(true, false, true);
}
/* The 3D view reads its colors again from the theme in force. */
function recolor3d() {
  G.backgroundColor(css('--ground')).linkOpacity(Number(css('--link-opacity'))).nodeColor(G.nodeColor())
    .linkColor(G.linkColor()).linkDirectionalParticleColor(G.linkDirectionalParticleColor());
  grounded();
}
$('#theme').value = document.documentElement.dataset.theme;
// a kept name that is no longer a theme
if ($('#theme').selectedIndex < 0) $('#theme').value = document.documentElement.dataset.theme = 'space';
$('#theme').onchange = () => setTheme($('#theme').value);
