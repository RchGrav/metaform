/* The 3D view draws the map or a node's memory network, places new nodes beside their neighbours, keeps the layout
 * calm on small changes, and follows the theme. */
import '/page/app/flow/fx3d.js';  // the part before runs first, so the parts run in the page's order
// Ultra graphics, web_graphics: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {$, css} from '/page/app/core/dom.js';
import {S, MEM} from '/page/app/core/reads.js';
import {graphData} from '/page/app/graph/data.js';
import {ballOf} from '/page/app/figures/agents.js';
import {endOf} from '/page/app/map3d/waves.js';
import {G, grounded} from '/page/app/map3d/graph3d.js';
import {hovered, setHovered} from '/page/app/map3d/pick3d.js';
import {tags, dropLabel} from '/page/app/map3d/labels.js';
import {phaseOf} from '/page/app/flow/fx3d.js';
import {V3} from '/page/app/camera/flight.js';
import {PHYS, applyPhysics} from '/page/app/views/bar.js';
import {setMermaidReady, build2D} from '/page/app/map2d/build.js';
import {memoryData} from '/page/app/memory/graph.js';
import {posted} from '/page/app/intake/intake.js';

/* The 3D view draws the map, or the memory network of a node while one is open, VIEW-031. `previous` holds where
 * each node stood, the positions of what is drawn now unless given. */
export function draw3D(previous = null) {
  if (!G) return;
  if (MEM.key && S.loading) return;  // a memory network is drawn once the map and its items are read again
  previous = previous || new Map(G.graphData().nodes.map(node => [node.id, node]));
  const data = MEM.key ? memoryData() : graphData();
  keepPlaces(data, previous);
  arrivals(data);
  const named = new Set(data.nodes.filter(node => node.t === 'el').map(node => node.id));
  for (const id of [...tags.keys()]) if (!named.has(id)) dropLabel(id);
  if (hovered) setHovered(data.nodes.find(node => node.id === hovered.id) || null);
  $('#tip3d').hidden = !hovered;
  if (inPlace(data)) return;
  // A memory network is laid out before it is shown, so it opens settled and whole in view; the map keeps its own
  // layout running from where each node stands.
  G.warmupTicks(MEM.key ? 120 : 0);
  G.graphData(data);
  applyPhysics(PHYS.name, false);  // its chains of service and its parts read again
  V3.layouts++;
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
function arrivals(data) {
  const fresh = data.nodes.filter(node => node.x === undefined).length;
  if (!fresh || fresh === data.nodes.length || fresh > Math.max(3, data.nodes.length * 0.15)) return;
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
/* New data starts the 3D layout again at full strength, which shakes the map, so a change that adds or removes no node
 * and no link is copied onto what is drawn, which is drawn again where it stands, VIEW-018. */
const PLACE = new Set(['x', 'y', 'z', 'vx', 'vy', 'vz', 'fx', 'fy', 'fz', 'index', '__threeObj', 'source', 'target']);
const end = value => value && typeof value === 'object' ? value.id : value;
const linkKey = link => `${end(link.source)}>${end(link.target)}>${link.k}`;
function inPlace(data) {
  const shown = G.graphData();
  if (shown.nodes.length !== data.nodes.length || shown.links.length !== data.links.length) return false;
  const nodes = new Map(shown.nodes.map(node => [node.id, node]));
  if (data.nodes.some(node => !nodes.has(node.id))) return false;
  const links = new Map();
  for (const link of shown.links) listAt(links, linkKey(link)).push(link);
  const pairs = [];
  for (const link of data.links) {
    const same = links.get(linkKey(link));
    if (!same?.length) return false;
    pairs.push([same.shift(), link]);
  }
  const copy = (into, from) => {
    for (const [key, value] of Object.entries(from)) if (!PLACE.has(key)) into[key] = value;
  };
  for (const node of data.nodes) copy(nodes.get(node.id), node);
  for (const [into, from] of pairs) copy(into, from);
  G.refresh();
  return true;
}
/* A theme recolors both views in place, VIEW-023: the 3D view rereads its colors, the 2D map is drawn again. The
 * choice is the viewer's own, kept in this browser. */
/* The theme is the one choice of look: space draws the 3D map in outer space, ULTRA, and every other theme flat. */
export const PLAIN = {last: 'black'};
export function setTheme(name, keep = true) {
  document.documentElement.dataset.theme = name;
  if (name !== 'space') PLAIN.last = name;
  if ($('#theme') && $('#theme').value !== name) $('#theme').value = name;
  ULTRA.setting(name === 'space' ? 'ultra' : 'clean');
  if (keep && S.project) posted('/api/settings', {key: 'web_graphics', value: name === 'space' ? 'ultra' : 'clean'});
  try { localStorage.setItem('metaform.theme', name); } catch (error) { /* storage can be blocked; it still shows */ }
  if (G) recolor3d();
  setMermaidReady(false);
  build2D();
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
