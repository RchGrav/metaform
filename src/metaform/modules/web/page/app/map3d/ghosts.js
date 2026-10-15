/* Parts not built yet drawn as ghosts, VIEW-027, what a node is drawn as, its rise to solid, and the condition
 * painted on a node in 3D. */
import '/page/app/map3d/bloom.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// The Space theme, web_theme space: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {css, reduced} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {layerColor} from '/page/app/header/layers.js';
import {nodeById} from '/page/app/figures/agents.js';
import {paceOf, lightOf, has, colorOf, ownColor, dim, dimmed, colored, isGlass, nodeShape, bead,
  shine} from '/page/app/map3d/light.js';
import {R} from '/page/app/map3d/waves.js';
import {nodeSize} from '/page/app/map3d/graph3d.js';
import {hovered} from '/page/app/map3d/pick3d.js';
import {MEET} from '/page/app/camera/fly3d.js';

/* A part not built yet is a ghost, VIEW-027: its own node in its own color, three quarters clear, so it is seen to be
 * in the design and not yet there, and hides nothing behind it. A signal on it lights it as it lights any node,
 * VIEW-029. Its name is as faint as its node, `sign`, a little above it so it can still be read up close, and comes up
 * to full while the node is hovered, selected, met, beside the selection, or near enough that the name is large on the
 * screen, from `near` to `close` screen pixels for each pixel of its painted letters, `ghostSign`. When the part is
 * built its node and its name come up to solid over GHOST.solid seconds; with reduced motion at once. Why: the
 * characters that stood here moved all the time and drew the eye from everything else on the map; a ghost says the
 * same, that the part is still to come, and is quiet; and its name at full strength, on a map with many parts still to
 * come, filled the view with text. */
const GHOST = {opacity: 0.25, solid: 1.2, sign: 0.35, near: 2, close: 3};
// missing is absent, so not built
export const unbuilt = node => has(node, 'missing') || has(node, 'unbuilt') || has(node, 'under-construction');
export const GHOSTS = {now: new Set(), built: new Map()};   // the ids drawn as ghosts, and those built since, by when
/* A material made a ghost's: clear by `opacity`, and writing no depth, so what is behind it shows through whole. */
function ghostly(material, opacity) {
  Object.assign(material, {transparent: true, opacity, depthWrite: opacity >= 1});
  const back = material.userData.back;
  if (back) Object.assign(back, {transparent: true, opacity, depthWrite: opacity >= 1});
}
/* What a node is drawn as: a ghost while its part is not built, glass if it is an element, else the graph's own
 * sphere. A join's purpose node, which the graph draws itself, is made a ghost of its own here. */
export function nodeObject(node, glass = true) {
  if (unbuilt(node)) {
    const plain = () => new THREE.Mesh(nodeShape(node, Math.cbrt(nodeSize(node)) * 3),
      new THREE.MeshLambertMaterial({color: colorOf(node)}));
    const object = ULTRA.body(node) || (isGlass(node) && glass ? bead(node) : plain());  // ULTRA: a body in outer space
    object.material.userData.own = true;
    ghostly(object.material, GHOST.opacity);
    object.userData.ghost = true;
    return object;
  }
  return ULTRA.body(node) || (glass && isGlass(node) ? bead(node) : false);  // ULTRA
}
/* Each frame: a part built since it was drawn as a ghost comes up to solid. */
const eased = share => share * share * (3 - 2 * share);
const risenOf = (id, now) => Math.min(1, (now - GHOSTS.built.get(id)) / 1000 / GHOST.solid);
export function ghost3d(data, now) {
  for (const node of data.nodes) {
    if (unbuilt(node)) { GHOSTS.now.add(node.id); continue; }
    if (GHOSTS.now.delete(node.id) && !reduced()) GHOSTS.built.set(node.id, now);
  }
  for (const id of GHOSTS.built.keys()) {
    const node = nodeById(data, id), material = node?.__threeObj?.material;
    const risen = risenOf(id, now);
    if (material && !node.__threeObj.userData.ghost) {
      ghostly(material, GHOST.opacity + (1 - GHOST.opacity) * eased(risen));
    }
    if (risen >= 1 || !node) GHOSTS.built.delete(id);
  }
}
/* How strong a node's name is drawn for its ghost, 1 for a built part's: GHOST.sign while its part is not built, full
 * while it is hovered, selected, met, beside the selection or lit in a reach, and rising to full as its letters grow
 * on the screen from GHOST.near to GHOST.close, `grown`; a part built since rises with its node. */
export function ghostSign(node, grown, now) {
  const rising = GHOSTS.built.has(node.id);
  if (!rising && !unbuilt(node)) return 1;
  const shown = node.id === S.selected || node.id === hovered?.id || S.neighbors.has(node.id) || R.nodes.has(node.id)
    || (MEET.on && MEET.back?.id === node.id);
  if (shown) return 1;
  const near = eased(Math.min(1, Math.max(0, (grown - GHOST.near) / (GHOST.close - GHOST.near))));
  const faint = GHOST.sign + (1 - GHOST.sign) * near;
  return rising ? faint + (1 - faint) * eased(risenOf(node.id, now)) : faint;
}
export const SIGNALS = [['broken', '--broken'], ['trouble', '--broken'], ['question', '--question'],
  ['message', '--question']];
/* The condition of a node in 3D, MAP-046, VIEW-005 and VIEW-029: an open broken record flashes it red, steady red
 * with reduced motion; an open question or message keeps its color. While it is
 * lit the node gives off light in the color of what it signals, which the bloom spreads past its outline: a flash is
 * lit on its beat, a pulse swells for half its period and rests for the other half. The sphere takes its own material
 * first, so no other node of its color changes. Called every frame for the nodes that carry a record, and for a node
 * still lit when its record has closed, to put its light back. */
export function paint3d(node) {
  const object = node.__threeObj;
  if (!object || !object.material) return;
  const light = lightOf(node);
  // An open question glows in the question's color, pulsating, so it is seen with the whole map zoomed out, VIEW-021.
  const asked = has(node, 'question') || has(node, 'message');  // a message waits for the user, VIEW-030
  if (R.nodes.has(node.id) || (!light && !asked)) return unlight(object);  // a wave shows on it, or nothing to signal
  ownMaterial(object);
  const period = light ? paceOf(node) : 1;
  const beat = reduced() || (performance.now() / 1000) % period < period / 2;
  const shown = light ? (beat ? css(light[1]) : ownColor(node)) : colorOf(node);
  colored(object.material, dimmed(node) && !light ? dim(shown) : shown);
  const swell = reduced() ? 1 : Math.max(0, Math.sin(performance.now() / 1600 * 2 * Math.PI));
  const lit = light ? (beat ? 1 : 0) : swell;
  shine(object.material, light ? css(light[1]) : css('--question'), lit);
  object.material.userData.lit = true;
}
/* A node no longer lit gives off only its glass's own light again. */
function unlight(object) {
  if (!object.material.userData.lit) return;
  shine(object.material, null, 0);
  object.material.userData.lit = false;
}
/* The node takes a material of its own, so no other node of its color changes with it. */
function ownMaterial(object) {
  if (object.material.userData.own) return;
  object.material = object.material.clone();
  object.material.userData.own = true;
  object.material.transparent = true;
}

/* An encounter takes its layer's color. */
export function linkColor(link) {
  if (link.k === 'tree') return css('--tree');
  return layerColor(link.layer);
}
