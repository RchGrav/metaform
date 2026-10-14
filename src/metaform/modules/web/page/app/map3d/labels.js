/* The 3D map's labels, VIEW-038, drawn in the scene: their presets per layout, outward signs, wrapping, painting,
 * each frame's placing, the met sign, and the page's work for each frame. */
import '/page/app/map3d/readout.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
// Ultra graphics, web_graphics: the 3D map in outer space, drawn by its own module through the hooks marked ULTRA.
import * as ULTRA from '/page/ultra.js';
import {$, css, reduced, h} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {ROAM} from '/page/app/figures/agents.js';
import {roam3d} from '/page/app/figures/roam3d.js';
import {mascotAwake} from '/page/app/figures/mascot.js';
import {has, colorOf, dim, dimmed, colored, DRIFT, isGlass} from '/page/app/map3d/light.js';
import {R, endOf, wave3d} from '/page/app/map3d/waves.js';
import {BLOOM} from '/page/app/map3d/bloom.js';
import {GHOSTS, ghost3d, ghostSign, SIGNALS, paint3d} from '/page/app/map3d/ghosts.js';
import {G, nodeSize, FRAMES, wake3d} from '/page/app/map3d/graph3d.js';
import {picked} from '/page/app/map3d/pick3d.js';
import {placeTip} from '/page/app/map3d/readout.js';
import {FLOW} from '/page/app/flow/flow.js';
import {flow3d} from '/page/app/flow/fx3d.js';
import {flight} from '/page/app/camera/flight.js';
import {small3d, SMALL_NAME, MEET, frameWhileSpreading, holdMet} from '/page/app/camera/fly3d.js';
import {PHYS, signsFacing} from '/page/app/views/bar.js';
import {joinTitle} from '/page/app/map2d/inside.js';

/* The labels of the 3D map, VIEW-038, are drawn inside the scene, each its element's whole name, wrapped at word
 * breaks, painted on a canvas and shown as a sign in the scene, standing out from the map's middle and facing the eye.
 * Its size and its opacity say how near it is: a label grows and shrinks with the map as it is zoomed, and from the
 * front of the map in view to its back it goes from its full size to a fifth of it; the nearest label is solid and the
 * farthest two thirds clear, so the near names stand out where the map is dense and the depth of the map reads from its
 * names as well as its nodes. Each stands a set distance out from its node on the side away from the map's middle, and
 * is drawn with the depth test as the nodes are, so the depth buffer orders labels and nodes together: a node nearer
 * the eye hides the part of a label behind it, a label behind a glass node is seen through the glass as the material
 * lets it through, VIEW-025, since what is behind the glass is drawn with the labels in it, and a nearer label is drawn
 * over a farther one. Nothing ranks over depth, the selected node, its neighbors and a lit or blinking node included. A
 * label that falls on a nearer node's sphere or on a nearer label keeps its own color: what is in front hides it by
 * depth or shows it through the glass. Every element keeps its label, VIEW-005; the text is in the theme's text color,
 * each letter outlined in the background's color, `stroke`, in place of a box behind the name, so the name reads over
 * what is behind it without a bar hiding the map; the outline fades with the label by its depth. A label is painted
 * again only when what it shows changes. */
/* How each physics preset treats the names, so a name can be read in every shape the map takes: `place`, where it
 * stands from its node, away from the map's middle ('out'), above it ('above'), or beside it, to the side of the way
 * service flows ('beside'); `least` and `most`, the screen pixels its letters are held between, so a map seen whole
 * never shrinks them to specks nor a near one blows them up; `declutter`, whether a name that would overlap one ranked
 * above it, the selection, its neighbours, then the hubs, then the rest, is left out until there is room; `farthest`,
 * how faint the farthest name is drawn, lower in a tight preset so the near ones stand out. Organic keeps the names as
 * they have always been drawn, held only from shrinking past reading. Every name faces the eye, never edge on or
 * mirrored. */
const LABEL_PRESETS = {
  organic: {place: 'out', least: 9, most: Infinity, declutter: false, farthest: 0.34},
  clusters: {place: 'above', least: 11, most: 22, declutter: true, farthest: 0.18},
  spread: {place: 'out', least: 12, most: 24, declutter: true, farthest: 0.4},
  calm: {place: 'out', least: 10, most: 22, declutter: true, farthest: 0.3},
  down: {place: 'beside', least: 11, most: 22, declutter: true, farthest: 0.4},
  across: {place: 'above', least: 11, most: 22, declutter: true, farthest: 0.4},
  radial: {place: 'out', least: 11, most: 22, declutter: true, farthest: 0.4},
  depth: {place: 'beside', least: 11, most: 22, declutter: true, farthest: 0.25},
  flat: {place: 'above', least: 11, most: 22, declutter: true, farthest: 0.6},
};
const RIGHT = new THREE.Vector3();
/* Outward signs, as they have always been drawn: away from the map's middle, sized by perspective, the far ones fading
 * to LABEL.farthest, none left out; their letters raised only where they would fall below `least` screen pixels, so a
 * map seen whole, as Spread leaves it, never shrinks them past reading. */
const OUTWARD_SIGNS = {place: 'out', least: 7, most: Infinity, declutter: false, farthest: 0.25};
// whether the signs stand out from the map's middle, so they turn round their nodes as the layout moves, `holdMet`
export const signsOut = () => (signsFacing() ? LABEL_PRESETS[PHYS.name] || LABEL_PRESETS.organic : OUTWARD_SIGNS).place
  === 'out';
export const LABEL = {size: 11, chosen: 13, wide: 9, line: 1.15, padX: 6, padY: 4, stroke: 2, after: 10,
  titleStep: 0.06,
  out: 12,  // how far a label stands out from its ball's surface, away from the map's middle, in the map's units
  // the size of a label's letters in the map, in its units, about an element's height; painted sharper at each
  // `sharper` step of the size it is seen at, up to `largest`; and the farthest label's opacity, the nearest solid
  letters: 10, largest: 4, sharper: 0.5, farthest: 0.34};
// by node id: the label's sprite, its canvas, what it shows and where it is on the screen
export const tags = new Map();
export const LABELS = {group: null, plane: null, on: true, only: null, pen: null, measured: new Map()};
export const OUT = new THREE.Vector3(), UP = new THREE.Vector3(), AT = new THREE.Vector3();
export const middle = new THREE.Vector3();
const Y_UP = new THREE.Vector3(0, 1, 0);  // the map's own up, which an outward sign keeps
const fontOf = look => `${look.weight} ${look.size}px ${look.family}`;
/* The name in lines no wider than the label's width, broken only between words, as the page wraps text; a word longer
 * than the width keeps its own line whole. Measured once for each name and look. */
function wrapped(text, look, oneLine = false) {
  const key = fontOf(look) + '\n' + text + (oneLine ? '\n1' : '');
  if (LABELS.measured.has(key)) return LABELS.measured.get(key);
  LABELS.pen = LABELS.pen || document.createElement('canvas').getContext('2d');
  LABELS.pen.font = fontOf(look);
  const most = LABEL.wide * look.size, lines = [];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const joined = lines.length ? lines.at(-1) + ' ' + word : null;
    if (joined !== null && LABELS.pen.measureText(joined).width <= most) lines[lines.length - 1] = joined;
    else lines.push(word);
  }
  if (!lines.length) lines.push('');
  if (oneLine && lines.length > 1) {  // one line, ended with an ellipsis where it runs past twice the usual width
    let line = text.trim();
    while (line.length > 1 && LABELS.pen.measureText(line + '…').width > most * 2) line = line.slice(0, -1).trimEnd();
    lines.splice(0, lines.length, line === text.trim() ? line : line + '…');
  }
  const widest = Math.max(...lines.map(line => LABELS.pen.measureText(line).width));
  const made = {lines, width: Math.ceil(widest) + 2 * LABEL.padX,
    height: Math.ceil(lines.length * look.size * LABEL.line) + 2 * LABEL.padY};
  LABELS.measured.set(key, made);
  return made;
}
function painted(tag, look, ratio, shape) {
  const canvas = tag.texture.image, pen = canvas.getContext('2d');
  canvas.width = Math.ceil(shape.width * ratio); canvas.height = Math.ceil(shape.height * ratio);
  pen.scale(ratio, ratio);
  pen.font = fontOf(look); pen.textAlign = 'center'; pen.textBaseline = 'middle';
  const step = look.size * LABEL.line, at = index => LABEL.padY + step * (index + 0.5);
  // each letter outlined in the background's color, so the name reads over the lines and nodes behind it, and
  // nothing more: a shadow, or a wide glow, around the letters hid every edge that ran behind them
  Object.assign(pen, {lineWidth: LABEL.stroke, lineJoin: 'round', strokeStyle: look.ground,
    shadowColor: 'transparent'});
  shape.lines.forEach((line, index) => pen.strokeText(line, shape.width / 2, at(index)));
  for (const blur of [...look.glow, 0]) {   // a reached part's glow of the background under it, then the text itself
    pen.shadowColor = blur ? look.ground : 'transparent'; pen.shadowBlur = blur * ratio;
    pen.fillStyle = look.color;
    shape.lines.forEach((line, index) => pen.fillText(line, shape.width / 2, at(index)));
  }
  tag.texture.dispose();                    // the canvas may have changed size
  tag.texture.needsUpdate = true;
  Object.assign(tag, {lines: shape.lines, width: shape.width, height: shape.height, color: look.color});
}
function labelFor(node) {
  let tag = tags.get(node.id);
  if (tag) return tag;
  if (!LABELS.group) {
    LABELS.group = new THREE.Group();
    G.scene().add(LABELS.group);
    // Measured and painted again once the page's face is there.
    const faces = [500, 600].map(weight => document.fonts.load(`${weight} ${LABEL.size}px ${css('--sans')}`));
    Promise.all(faces).then(() => {
      LABELS.measured.clear();
      for (const each of tags.values()) each.key = '';
      wake3d();
    }, () => {});
  }
  const texture = new THREE.CanvasTexture(document.createElement('canvas'));
  Object.assign(texture, {colorSpace: THREE.SRGBColorSpace, minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter, generateMipmaps: false});
  // A sign in the scene, standing out from the map's middle and turned to face the eye, so its name always reads as
  // written. `sprite` is the name it has always had in the page's reads.
  LABELS.plane ??= new THREE.PlaneGeometry(1, 1);
  // It is tested against what is nearer, so a nearer node or edge hides it, but writes no depth of its own and is
  // drawn after the map, so it never cuts out an edge or a node behind it: written into the depth, each letter and
  // its outline hid every edge drawn after it, however far behind.
  const sprite = new THREE.Mesh(LABELS.plane, new THREE.MeshBasicMaterial({map: texture, side: THREE.DoubleSide,
    depthTest: true, depthWrite: false, transparent: true, alphaTest: 0.02, toneMapped: false}));
  sprite.renderOrder = LABEL.after;
  sprite.raycast = () => {};                // a label is never picked in place of the node
  LABELS.group.add(sprite);
  tag = {id: node.id, text: node.name || '', sprite, texture, key: '', classes: [], lines: [], width: 0, height: 0,
    under: false, z: 0, hidden: true, rect: null, color: ''};
  tags.set(node.id, tag);
  return tag;
}
export function dropLabel(id) {
  const tag = tags.get(id);
  if (!tag) return;
  LABELS.group?.remove(tag.sprite);
  tag.texture.dispose(); tag.sprite.material.dispose();
  tags.delete(id);
}
/* What a label shows from its classes, as the page's own styles would give it. */
function lookOf(classes, palette) {
  const is = name => classes.includes(name);
  const chosen = is('sel'), reach = is('reach');
  const color = is('work-broken') ? palette.broken
    : reach ? palette.text : is('dim') ? palette.muted : chosen ? palette.signal : palette.text;
  return {size: chosen ? LABEL.chosen : LABEL.size, weight: chosen || reach ? 600 : 500, family: palette.sans, color,
    ground: palette.ground, glow: reach ? [10, 6, 3] : []};  // a reached part's name glows; the rest have a shadow
}
/* Each frame: every label is put above its node at the node's depth and sized for the screen, and the labels that
 * fall on a nearer sphere or a nearer label are marked under. */
export function layered() {
  const frame = labelFrame();
  if (LABELS.group) LABELS.group.visible = LABELS.on;
  UP.set(0, 1, 0).applyQuaternion(frame.camera.quaternion);
  RIGHT.set(1, 0, 0).applyQuaternion(frame.camera.quaternion);
  const {spheres, nearest, deepest} = measureSpheres(frame);
  const shown = [];
  for (const node of G.graphData().nodes) {
    const label = placeLabel(node, frame, nearest, deepest);
    if (label) shown.push(label);
  }
  // A preset that declutters leaves out a name that would overlap one ranked above it: the selection first, then its
  // neighbours, then the hubs by their joins, then the rest, nearest first; the selection and its neighbours always
  // keep theirs.
  if (frame.how.declutter) declutter(shown);
  shown.sort((one, two) => one.far - two.far);
  shown.forEach((label, index) => layerLabel(label, index, shown, spheres, frame));
  metSign(MEET.on ? tags.get(MEET.back?.id) : null);
}
/* What every label of this frame is measured by: the camera, the screen, the world units a pixel spans at a depth,
 * the palette, read once a frame and not once a label, the treatment of the names, and each node's joins. */
function labelFrame() {
  const now = performance.now(), camera = G.camera(), area = $('#stage').getBoundingClientRect();
  const height = area.height || 1, spread = camera.projectionMatrix.elements[5], ratio = G.renderer().getPixelRatio();
  const perPixel = depth => 2 * depth / (spread * height);
  const depthOf = node => -AT.set(node.x, node.y, node.z).applyMatrix4(camera.matrixWorldInverse).z;
  const palette = {text: css('--text'), muted: css('--muted'), signal: css('--signal'), broken: css('--broken'),
    exclude: css('--exclude'), ground: css('--ground'), sans: css('--sans')};
  // outward signs, web_signs' default, are drawn as they always were, held only from dropping below a readable floor;
  // facing signs take their physics preset's treatment, `LABEL_PRESETS`
  const how = signsFacing() ? LABEL_PRESETS[PHYS.name] || LABEL_PRESETS.organic : OUTWARD_SIGNS;
  const degree = new Map();  // a hub is a node with many joins: its name ranks after the selection and its neighbours
  if (how.declutter) for (const link of G.graphData().links) {
    for (const end of [endOf(link.source), endOf(link.target)]) degree.set(end, (degree.get(end) || 0) + 1);
  }
  return {now, camera, area, height, ratio, perPixel, depthOf, palette, how, degree};
}
/* Every node's sphere on the screen, the depths of the front and back of the names in view, and the map's middle,
 * its nodes' mean place, which the names stand away from. */
function measureSpheres({area, height, perPixel, depthOf}) {
  const spheres = [];
  let nearest = Infinity, deepest = -Infinity, placed = 0;
  middle.set(0, 0, 0);
  for (const node of G.graphData().nodes) {
    if (node.x === undefined) continue;
    const point = G.graph2ScreenCoords(node.x, node.y, node.z), depth = depthOf(node);
    spheres.push({id: node.id, x: point.x, y: point.y, far: depth, r: Math.cbrt(nodeSize(node)) * 3 / perPixel(depth)});
    middle.x += node.x; middle.y += node.y; middle.z += node.z; placed++;
    // the front and back of the map are those of the names in view, not of parts off the screen
    if (node.t === 'el' && depth > 0 && point.x >= 0 && point.x <= area.width && point.y >= 0 && point.y <= height) {
      nearest = Math.min(nearest, depth); deepest = Math.max(deepest, depth);
    }
  }
  if (placed) middle.divideScalar(placed);
  return {spheres, nearest, deepest};
}
/* One node's label placed for this frame, or null for a node that has none. A join has no name of its own on the
 * map; selected, its title fades in on it, its receiver and the parts that serve it, VIEW-038, and fades out when it
 * is no longer selected. */
function placeLabel(node, frame, nearest, deepest) {
  const titled = node.t === 'purpose' && (node.id === S.selected || tags.get(node.id)?.fade > 0);
  if (node.t !== 'el' && !titled) return null;
  const tag = labelFor(node);
  tag.text = titled ? joinTitle(node) : node.name || '';
  if (titled) {
    tag.fade = Math.max(0, Math.min(1, (tag.fade || 0) + (node.id === S.selected ? 1 : -1) * LABEL.titleStep));
    if (tag.fade > 0 && tag.fade < 1) wake3d();
  }
  tag.hidden = node.x === undefined;
  tag.sprite.visible = !tag.hidden && (!LABELS.only || LABELS.only.has(node.id));
  if (tag.hidden) return null;
  tag.classes = [node.id === S.selected ? 'sel' : S.neighbors.has(node.id) ? 'near' : S.selected ? 'dim' : '',
    ...(node.work || []).map(condition => `work-${condition}`), R.nodes.has(node.id) ? 'reach' : ''].filter(Boolean);
  const look = lookOf(tag.classes, frame.palette), how = frame.how;
  const depth = frame.depthOf(node), unit = frame.perPixel(Math.max(depth, 1e-3));
  const radius = Math.cbrt(nodeSize(node)) * 3;
  // Its letters are a set size in the map, in a set ratio to the balls, so the eye's own perspective makes it larger
  // near and smaller far as it does the nodes; `grown` is the size it is seen at, the pixels on the screen for one of
  // its canvas. From the front of the map in view to its back it fades, `back`.
  const back = deepest > nearest ? Math.min(1, Math.max(0, (depth - nearest) / (deepest - nearest))) : 0;
  const grown = LABEL.letters / LABEL.size / unit;
  const shape = wrapped(tag.text, look, tag.id === SMALL_NAME.id && small3d());
  tag.lookNow = look;
  tag.shape = shape;
  // its letters held between the preset's least and most screen pixels, `how`, so they are read at any zoom
  const onScreen = grown * LABEL.size, held = Math.min(how.most, Math.max(how.least, onScreen)) / onScreen;
  const seen = grown * held, size = LABEL.letters / LABEL.size * held;
  const wide = shape.width * size, tall = shape.height * size;
  placeSign(tag.sprite, node, how.place, radius, wide, tall);
  tag.sprite.scale.set(wide, tall, 1);
  const anchor = G.graph2ScreenCoords(tag.sprite.position.x, tag.sprite.position.y, tag.sprite.position.z);
  tag.rect = {left: anchor.x - shape.width * seen / 2, right: anchor.x + shape.width * seen / 2,
    top: anchor.y - shape.height * seen / 2, bottom: anchor.y + shape.height * seen / 2};
  tag.grown = seen;
  tag.ghost = titled ? 1 : ghostSign(node, seen, frame.now);  // a part not built has a faint name, VIEW-027
  const rank = node.id === S.selected ? 0 : S.neighbors.has(node.id) ? 1 : 2;
  return {tag, far: depth, look, back, rank, hub: frame.degree.get(node.id) || 0};
}
/* Pinned in the map a set distance from its node, so it is a thing of the scene: it swings round its node as the map
 * turns and goes behind the node as anything behind it does. Over the node, as a cluster's names sit over its knot;
 * to the side of a tree's flow, clear of the edges along it; or on the side away from the map's middle, so the outer
 * names stand outside the map, over the least of it.
 * web_signs: outward, each sign facing away from the map's middle, upright in the map, and turned round on its upright
 * axis when the eye is on the map's side of it, so its letters read as written and are never mirrored; or facing, each
 * sign turned to the eye and upright to it, read the same from any side and at any angle. */
function placeSign(sprite, node, place, ball, wide, tall) {
  if (place === 'above') {
    sprite.position.set(node.x, node.y, node.z).addScaledVector(UP, ball + LABEL.out * 0.4 + tall / 2);
  } else if (place === 'beside') {
    sprite.position.set(node.x, node.y, node.z).addScaledVector(RIGHT, ball + LABEL.out * 0.4 + wide / 2);
  } else {
    outward(node);
    sprite.position.set(node.x, node.y, node.z).addScaledVector(OUT, ball + LABEL.out);
  }
  if (signsFacing()) return sprite.quaternion.copy(G.camera().quaternion);
  outward(node);
  sprite.up.copy(Math.abs(OUT.y) > 0.98 ? UP : Y_UP);
  const eye = G.camera().position, at = sprite.position;
  const behind = (eye.x - at.x) * OUT.x + (eye.y - at.y) * OUT.y + (eye.z - at.z) * OUT.z < 0;
  sprite.lookAt(AT.copy(at).addScaledVector(OUT, behind ? -1 : 1));
}
/* The signs turned for one picture from an eye other than the person's, a figure's own, `lookFrom`: a facing sign
 * turned to that eye, an outward one turned round on its upright axis when that eye is behind it, so the picture reads
 * every name as written. Gives back what puts each sign as the person's view has it. */
const FACE = new THREE.Vector3(), TOWARD_EYE = new THREE.Vector3();
const TURNED = new THREE.Quaternion().setFromAxisAngle(Y_UP, Math.PI);
export function signsFor(camera) {
  const kept = [];
  for (const tag of tags.values()) {
    const sprite = tag.sprite;
    if (!sprite.visible) continue;
    kept.push([sprite, sprite.quaternion.clone()]);
    if (signsFacing()) { sprite.quaternion.copy(camera.quaternion); continue; }
    FACE.set(0, 0, 1).applyQuaternion(sprite.quaternion);  // a sign's face is its plane's +z
    if (FACE.dot(TOWARD_EYE.subVectors(camera.position, sprite.position)) < 0) sprite.quaternion.multiply(TURNED);
  }
  return () => { for (const [sprite, turn] of kept) sprite.quaternion.copy(turn); };
}
/* OUT, the way from the map's middle to a node, or up at the middle itself. */
function outward(node) {
  OUT.set(node.x - middle.x, node.y - middle.y, node.z - middle.z);
  if (OUT.lengthSq() < 1e-6) OUT.copy(UP); else OUT.normalize();
}
const overlaps = (one, two) => !(one.right <= two.left || two.right <= one.left || one.bottom <= two.top
  || two.bottom <= one.top);
function declutter(shown) {
  const kept = [];
  for (const label of [...shown].sort((one, two) => one.rank - two.rank || two.hub - one.hub || one.far - two.far)) {
    const box = label.tag.rect;
    const clash = kept.some(other => overlaps(box, other));
    if (clash && label.rank > 1) { label.tag.sprite.visible = false; label.out = true; continue; }
    kept.push(box);
  }
}
/* A label in its place among the others, nearest first: its opacity by its depth, faded with its title and its ghost;
 * under where a nearer sphere or label covers it; painted again when what it shows changed. */
function layerLabel(label, index, shown, spheres, {how, palette, ratio}) {
  // the nearest label solid, the farthest at the preset's `farthest` of it, the rest between by their depth
  // and a part not built's name as faint as its ghost, `ghostSign`
  label.tag.sprite.material.opacity = (1 - (1 - how.farthest) * label.back) * (label.tag.fade ?? 1) * label.tag.ghost;
  const box = label.tag.rect;
  const behind = spheres.some(sphere => sphere.id !== label.tag.id && sphere.far < label.far &&
    Math.hypot(Math.max(box.left, Math.min(sphere.x, box.right)) - sphere.x,
               Math.max(box.top, Math.min(sphere.y, box.bottom)) - sphere.y) < sphere.r);
  const covered = shown.slice(0, index).some(({tag: other, out}) => !out && overlaps(box, other.rect));
  const tag = label.tag;
  tag.under = (behind || covered) && !(MEET.on && tag === tags.get(MEET.back?.id));
  tag.z = shown.length - index;
  if (tag.under) tag.classes.push('under');
  const look = lookOf(tag.classes, palette);
  // painted for the size it is drawn at, in steps, so a near label is as sharp as one at its own size
  const sharp = ratio * Math.min(LABEL.largest, Math.max(1, Math.ceil(tag.grown / LABEL.sharper) * LABEL.sharper));
  const key = [tag.text, fontOf(look), look.color, look.ground, look.glow, sharp, tag.shape.lines.length].join('|');
  if (key !== tag.key) { painted(tag, look, sharp, tag.shape); tag.key = key; }
}
/* The met sign on the canvas, VIEW-005: while the camera meets a sign square on, the sign in the scene and its face
 * drawn flat on the screen look the same, so it is drawn on a layer over the map at the very rectangle its four
 * corners project to, frame by frame, and the sign in the scene is hidden. An edge passing through the sign's plane in
 * the map then never crosses its letters; when the meeting ends the sign in the scene is shown again where it was. */
export const MET = {box: null, pen: null, corner: new THREE.Vector3()};
function metSign(tag) {
  if (!MET.box) {
    MET.box = h('canvas', {class: 'metsign', 'aria-hidden': 'true'});
    MET.box.hidden = true;
    $('#stage').append(MET.box);
    MET.pen = MET.box.getContext('2d');
  }
  const box = MET.box, pen = MET.pen;
  if (!tag || tag.hidden || !tag.texture.image.width) { if (!box.hidden) box.hidden = true; return; }
  const area = $('#stage').getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
  const wide = Math.round(area.width * ratio), tall = Math.round(area.height * ratio);
  if (box.width !== wide || box.height !== tall) Object.assign(box, {width: wide, height: tall});
  tag.sprite.updateMatrixWorld();
  const {left, top, right, bottom} = cornersOnScreen(tag.sprite);
  pen.setTransform(ratio, 0, 0, ratio, 0, 0);
  pen.clearRect(0, 0, area.width, area.height);
  pen.globalAlpha = tag.sprite.material.opacity ?? 1;
  pen.drawImage(tag.texture.image, left, top, right - left, bottom - top);
  tag.sprite.visible = false;
  box.hidden = false;
}
/* The rectangle on the screen a sign's four corners project to. */
function cornersOnScreen(sprite) {
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  for (const [x, y] of [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) {
    const at = sprite.localToWorld(MET.corner.set(x, y, 0)), seen = G.graph2ScreenCoords(at.x, at.y, at.z);
    left = Math.min(left, seen.x); right = Math.max(right, seen.x);
    top = Math.min(top, seen.y); bottom = Math.max(bottom, seen.y);
  }
  return {left, top, right, bottom};
}
/* The page's work for each frame of the 3D map, run in the render chain before anything is drawn, `create3D`: the
 * camera's flight, the colors, the wave, the figures, the text, the lights, the labels, the dots and the tooltip. It
 * says whether the next frame has an ambient animation of its own to show, `FRAMES.busy`, drawn slowly once the map
 * is left alone, and whether the dots flow, `FRAMES.flowing`. */
export function prepare3d() {
  const now = performance.now(), data = G.graphData();
  frameWhileSpreading(now, data);
  holdMet(data);  // the small area's met node, followed as the layout moves it, before the flight puts the camera
  flight(now);
  G.camera().updateMatrixWorld();
  colorGlass(data);
  DRIFT.value = reduced() ? 0 : now / 1000;  // the distortion of the glass drifts, VIEW-025
  wave3d(data);
  roam3d(data);
  ghost3d(data, now);
  const signaled = paintSignals(data);
  layered();
  flow3d(now, data);
  // The bloom runs while a reach is lit and while any part has a record that gives off light, VIEW-029, for as long
  // as the record is open and not only at the moments of its flash: the glass's highlights are over full brightness
  // too, and a pass switched with each flash would make them blink with it.
  // ULTRA: in outer space ultra's own bloom glows on everything bright, and its sky, bodies and governor run here.
  if (BLOOM) BLOOM.enabled = !ULTRA.on() && (Boolean(R.key) || signaled);
  ULTRA.frame(now, data);
  placeTip();
  FRAMES.busy = !reduced() && (Boolean(R.key) || ROAM.figures.size > 0 || GHOSTS.built.size > 0 || signaled
    || mascotAwake());
  FRAMES.flowing = !reduced() && FLOW.count > 0 && FLOW.held === null;
}
/* A glass node is colored by the page, since the graph colors only the nodes it draws itself. */
function colorGlass(data) {
  for (const node of data.nodes) {
    const material = node.__threeObj?.material;
    if (isGlass(node) && material && !material.userData.pulsed) {
      colored(material, dimmed(node) ? dim(colorOf(node)) : colorOf(node));
    }
  }
}
/* Each node picked by its whole sphere, its record's condition painted on it, and whether any node signals. */
function paintSignals(data) {
  let signaled = false;
  for (const node of data.nodes) {
    if (node.__threeObj && node.__threeObj.raycast !== picked) node.__threeObj.raycast = picked;
    if ((node.work && node.work.length) || node.__threeObj?.material?.userData.lit) paint3d(node);
    signaled = signaled || SIGNALS.some(([condition]) => has(node, condition));
  }
  return signaled;
}
