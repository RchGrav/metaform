/* A figure's eyes as a camera: what it sees, a picture from its view, what the person is looking at, and the
 * mascot's eyes for the person. */
import '/page/app/figures/attention.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {$, css, reduced} from '/page/app/core/dom.js';
import {pageVitals} from '/page/app/core/vitals.js';
import {S} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {ROAM, ballOf, isSystemTalk, conversing, sizeOf} from '/page/app/figures/agents.js';
import {PULL, TOWARD, SPOT, facingOf} from '/page/app/figures/walk.js';
import {MASCOT, mascotGlyph} from '/page/app/figures/mascot.js';
import {faceToward, TURNED} from '/page/app/figures/attention.js';
import {INUSE, shownNode} from '/page/app/map3d/light.js';
import {G, FRAMES, afterFrames, noMoreFrames, wake3d} from '/page/app/map3d/graph3d.js';
import {AT, signsFor} from '/page/app/map3d/labels.js';
import {flowModeNow} from '/page/app/flow/flow.js';
import {tintOf, fxDot, fxLine} from '/page/app/flow/fx3d.js';
import {MODE, V3, FLIGHT} from '/page/app/camera/flight.js';
import {small3d, meetEnds, MEET} from '/page/app/camera/fly3d.js';
import {PHYS} from '/page/app/views/bar.js';
import {labelOf} from '/page/app/map2d/inside.js';
import {FOLLOW, FOLLOW_PACE, autoZoom2d, fullFit2d, follow2d, followPassed} from '/page/app/map2d/camera.js';
import {note2d, nodeAt2d, edgeAt2d} from '/page/app/map2d/hover.js';
import {M} from '/page/app/map2d/build.js';
import {ROAM2D} from '/page/app/figures/roam2d.js';
import {D, ticketOf, showFollowed} from '/page/app/agents/dispatch.js';
import {tabNow} from '/page/app/panel/prompts.js';
import {WS} from '/page/app/workspace/workspace.js';
import {toast} from '/page/app/core/controls.js';
import {figureAt, mascotTakes} from '/page/app/figures/ask.js';
import {WATCHED} from '/page/app/figures/bubble3d.js';
import {nodeAt3d, linkAt3d, purposeOf} from '/page/app/map3d/pick3d.js';
import {CLICK_LEAD} from '/page/app/session/text.js';

/* Who sees: the calling agent's own figure, by the work its runner gave it, or else the person's mascot, which is the
 * system agent's figure and the person's. A refusal says why. */
function seer(work, role) {
  const figure = work ? ROAM.figures.get(work) : null;  // its own figure, an embodied conversation agent's too
  if (figure?.mesh) return {mesh: figure.mesh, who: figure.glyph, figure};
  // the person's own agent
  if (role === 'system' && MASCOT.mesh) return {mesh: MASCOT.mesh, who: MASCOT.glyph, mascot: true};
  if (work && conversing(ticketOf(work)) && !isSystemTalk(ticketOf(work)))
    return {refuse: 'You have no body on the map yet: the person can give you one, or ask for one with web_embody.'};
  if (work && ticketOf(work) && !ticketOf(work).held) {
    return {refuse: 'No figure is drawn for your ticket on this page yet: it walks onto the map once your session is '
      + 'working there.'};
  }
  if (MASCOT.mesh) return {mesh: MASCOT.mesh, who: MASCOT.glyph, mascot: true};
  return {refuse: mascotGlyph() ? 'The mascot is not drawn yet: the 3D map is not open.'
    : 'No mascot is chosen: web_mascot is none.'};
}
/* A figure's eyes as a camera: at its eye anchor, facing its gaze, with its own field of view, `eyeOf`. `agent`, the
 * view is an agent's eyes now; `agentMode`, the agent view V turns on and off and A never changes. */
export const EYE = {camera: new THREE.PerspectiveCamera(68, 1.5, 0.05, 1e6), at: new THREE.Vector3(),
  dir: new THREE.Vector3(), look: new THREE.Vector3(), width: 768, height: 512, target: null, debug: false, view: false,
  saved: null, k: 0, started: 0, mesh: null, agent: false, agentMode: false, hand: null};
function eyeCamera(mesh, aspect = EYE.width / EYE.height) {
  eyeOf(mesh, EYE.at, EYE.dir);
  const camera = EYE.camera;
  camera.fov = mesh.userData.fov || 68;
  camera.aspect = aspect;
  camera.near = Math.max(0.01, mesh.scale.x * 0.05);
  camera.far = G.camera().far || 1e6;
  camera.position.copy(EYE.at);
  camera.up.set(0, 1, 0);
  camera.lookAt(EYE.look.copy(EYE.at).add(EYE.dir));
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  return camera;
}
/* What a figure perceives now, VIEW-005: the elements and joins in its field of view, within SIGHT of its size and
 * hidden by nothing nearer, nearest first, at most SEEN of them and the rest as a count; each with how far its surface
 * is, which way it is, and whether it is in reach, selected or being worked; the figures it perceives so; and the
 * nearest one ahead, what it faces. Nothing it cannot perceive is listed. */
const SIGHT = 12, SEEN = 12, FIGURES = 6, REACH = 1.5;
function seeFrom(mesh, camera) {
  const data = G.graphData(), eye = EYE.at, seen = [], size = ROAM.drawn || sizeOf(data), range = size * SIGHT;
  const drawn = node => node.x !== undefined && node.__threeObj?.visible !== false && shownNode(node);
  const balls = data.nodes.filter(drawn);
  for (const node of balls) {
    if (node.t !== 'el' && node.t !== 'purpose') continue;
    const point = new THREE.Vector3(node.x, node.y, node.z), away = point.distanceTo(eye);
    const surface = Math.max(0, away - ballOf(node)), v = point.clone().project(camera);
    if (surface > range || !inFrame(v) || hiddenBehind(balls, eye, point, away, node)) continue;
    seen.push(perceived(node, surface, bearingOf(v), size));
  }
  seen.sort((one, two) => one.distance - two.distance);
  const figures = figuresSeen(mesh, camera, eye, balls, range);
  const ahead = seen.find(one => one.bearing === 'ahead') || seen[0];
  return {fov: Math.round(camera.fov), range: Math.round(range), facing: ahead?.address || null,
    in_view: seen.slice(0, SEEN), ...(seen.length > SEEN ? {more: seen.length - SEEN} : {}),
    figures: figures.slice(0, FIGURES), ...(figures.length > FIGURES ? {more_figures: figures.length - FIGURES} : {})};
}
/* An element or a join as a figure perceives it: its address, name and kind, how far its surface is and which way,
 * and, only when so, in reach, selected or being worked. */
function perceived(node, surface, bearing, size) {
  const {address, name, kind, selected, active} = seenEntry(node, surface);
  return {address, name, kind, distance: Math.round(surface * 10) / 10, bearing,
    ...(surface <= size * REACH ? {in_reach: true} : {}), ...(selected ? {selected} : {}), ...(active ? {active} : {})};
}
/* A point projected by a camera is in its frame: in front of it and inside its edges. */
const inFrame = v => v.z > -1 && v.z < 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1;
/* Which way a point in the frame is: left, right or ahead, and above or below. */
function bearingOf(v) {
  const across = v.x < -0.33 ? 'left' : v.x > 0.33 ? 'right' : 'ahead';
  const up = v.y > 0.45 ? 'above' : v.y < -0.45 ? 'below' : null;
  return [across, up].filter(Boolean).join(', ');
}
/* Whether a nearer node lies across the line of sight from the eye to a point. */
function hiddenBehind(balls, eye, point, away, own) {
  return balls.some(other => {
    if (other === own) return false;
    AT.set(other.x, other.y, other.z);
    const along = TOWARD.subVectors(AT, eye).dot(SPOT.subVectors(point, eye).normalize());
    if (along <= 0 || along >= away - ballOf(own || other)) return false;
    return AT.distanceTo(PULL.copy(eye).addScaledVector(SPOT, along)) < ballOf(other);
  });
}
/* An element or a join as a figure sees it: its address, name and kind, how far, and whether it is selected or being
 * worked. */
function seenEntry(node, away) {
  const join = node.t === 'purpose' ? joinOf(node.id) : null;
  const worked = INUSE.parts.get(node.id) === true || Boolean(node.work?.length)
    || [...ROAM.figures.values()].some(figure => figure.target === node.id);
  return {address: join ? `${partAddress(join.receiver)}>${partAddress(join.providers[0])}` : node.address,
    name: join ? (join.purpose || 'a join') : node.name, kind: join ? 'join' : 'element',
    distance: Math.round(away * 10) / 10, selected: S.selected === node.id, active: worked};
}
/* The other figures it perceives, the mascot among them: in view, in range and hidden by no node, nearest first. */
function figuresSeen(mesh, camera, eye, balls, range) {
  const mascot = MASCOT.mesh ? [{mesh: MASCOT.mesh, glyph: MASCOT.glyph, mascot: true}] : [];
  const figures = [];
  for (const figure of [...ROAM.figures.values(), ...mascot]) {
    if (figure.mesh === mesh) continue;
    const point = figure.mesh.position, v = point.clone().project(camera), away = point.distanceTo(eye);
    if (away > range || !inFrame(v) || hiddenBehind(balls, eye, point, away, null)) continue;
    figures.push({character: figure.glyph,
      who: figure.mascot ? "the person's mascot" : `the agent on ${partAddress(figure.target) || 'its ticket'}`,
      distance: Math.round(away * 10) / 10, bearing: bearingOf(v)});
  }
  return figures.sort((one, two) => one.distance - two.distance);
}
const partAddress = id => S.elements.get(id)?.element.address
  || (String(id).startsWith('p:') ? joinOf(id)?.receiver_address : null) || null;
/* A picture from a figure's eyes, the scene as the page draws it, everything a module adds to it included, the figure
 * itself left out: a PNG, EYE.width by EYE.height, as base64. */
function lookFrom(mesh, camera, width = EYE.width, height = EYE.height) {
  const renderer = G.renderer();
  if (!EYE.target || EYE.target.width !== width || EYE.target.height !== height) {
    EYE.target?.dispose();
    EYE.target = new THREE.WebGLRenderTarget(width, height, {samples: 4});
    EYE.target.texture.colorSpace = THREE.SRGBColorSpace;
  }
  const was = renderer.getRenderTarget(), shown = mesh?.visible;
  if (mesh) mesh.visible = false;
  // the signs read as written from this eye too, for this picture only; the person's view keeps its own
  const signsBack = camera === G.camera() ? null : signsFor(camera);
  try {
    renderer.setRenderTarget(EYE.target);
    renderer.clear();
    renderer.render(G.scene(), camera);
    const pixels = new Uint8Array(width * height * 4);
    renderer.readRenderTargetPixels(EYE.target, 0, 0, width, height, pixels);
    const canvas = document.createElement('canvas');
    canvas.width = width; canvas.height = height;
    const pen = canvas.getContext('2d'), image = pen.createImageData(width, height);
    const row = width * 4;
    for (let at = 0; at < height; at++)  // the target is read bottom row first
      image.data.set(pixels.subarray((height - 1 - at) * row, (height - at) * row), at * row);
    pen.putImageData(image, 0, 0);
    drawPointer(pen, camera, width, height);
    return canvas.toDataURL('image/png').split(',')[1];
  } finally {
    renderer.setRenderTarget(was);
    if (mesh) mesh.visible = shown;
    signsBack?.();
  }
}
/* The pointer's ray drawn into a picture as the camera that took it sees it, from `pointerNow`: the line from where the
 * person's view casts it to what it hits, or on through the map, a cross where it starts in the picture and a ring on
 * what it hits. From the person's own camera the whole line is the point under the pointer. */
const ALONG = new THREE.Vector3();
function drawPointer(pen, camera, width, height) {
  const cast = POINTER.last;
  if (!cast) return;
  let far = cast.hit ? cast.origin.distanceTo(cast.hit) : 0;
  if (!cast.hit) for (const node of G.graphData().nodes) {
    if (node.x !== undefined) far = Math.max(far, cast.origin.distanceTo(ALONG.set(node.x, node.y, node.z)));
  }
  const onPicture = point => {
    const v = ALONG.copy(point).project(camera);
    return v.z > -1 && v.z < 1 ? [(v.x + 1) / 2 * width, (1 - v.y) / 2 * height] : null;
  };
  const points = [];
  for (let step = 0; step <= 48; step++) {
    const at = onPicture(cast.origin.clone().addScaledVector(cast.direction, far * step / 48));
    if (at) points.push(at);
  }
  pen.save();
  pen.strokeStyle = css('--pointer'); pen.lineWidth = 2; pen.shadowColor = css('--shadow'); pen.shadowBlur = 3;
  if (points.length > 1) {
    pen.beginPath(); pen.moveTo(...points[0]);
    for (const at of points) pen.lineTo(...at);
    pen.stroke();
  }
  if (points.length) {
    const [x, y] = points[0];
    pen.beginPath(); pen.moveTo(x - 9, y); pen.lineTo(x + 9, y); pen.moveTo(x, y - 9); pen.lineTo(x, y + 9);
    pen.stroke();
  }
  const hit = cast.hit && onPicture(cast.hit);
  if (hit) { pen.beginPath(); pen.arc(hit[0], hit[1], 11, 0, Math.PI * 2); pen.stroke(); }
  pen.restore();
}
/* see and look: from the caller's own figure; with an address, it turns to face it first, and what it sees is read
 * once it does, `faceToward`, so the picture is taken facing it. A figure at work on its ticket glances at it. */
export function sight(payload, node, answer) {
  if (!G) return answer({error: 'The 3D map is not open on this page.'});
  const who = seer(payload.work, payload.role);
  if (who.refuse) return answer({error: who.refuse});
  const seen = turn => answer({...seenBy(who, payload.act === 'look'), ...(turn ? {turn} : {})});
  wake3d(1500);
  if (!node) return seen(null);
  const turning = faceToward(who, node, payload.address);
  if (turning) return turning.then(turned => seen(turned.stopped_by));
  if (who.figure) {
    who.figure.lookAt = {node, until: who.figure.clock + 4};
    return facingThen(who.mesh, node, 3000, seen);
  }
  seen(null);
}
/* Once a figure faces a node, within TURNED degrees, or after `most` milliseconds, its deadline: then(turned or time).
 * It is looked at once each frame that turns the figure, `afterFrames`, never between. */
function facingThen(mesh, node, most, then) {
  const facing = new THREE.Vector3(), toward = new THREE.Vector3();
  wake3d(most + 500);
  const said = why => { noMoreFrames(check); clearTimeout(limit); then(why); };
  const check = () => {
    const nodes = G.graphData().nodes;
    let there = null;
    for (let at = 0; at < nodes.length && there === null; at++) if (nodes[at].id === node) there = nodes[at];
    if (!there || there.x === undefined) return said('its target left the map');
    toward.set(there.x, there.y, there.z).sub(mesh.position).setY(0);
    const off = toward.lengthSq() < 1e-8 ? 0 : facingOf(mesh, facing).angleTo(toward.normalize()) * 180 / Math.PI;
    if (off <= TURNED) said('turned');
  };
  const limit = setTimeout(() => said('time'), most);
  afterFrames(check);
}
/* What a figure sees, from where and which way, and with `picture` a picture of it. */
function seenBy(who, picture) {
  const camera = eyeCamera(who.mesh), seen = seeFrom(who.mesh, camera);
  const from = {character: who.who, as: who.mascot ? "the person's mascot" : 'your figure',
    eye: EYE.at.toArray().map(one => Math.round(one * 10) / 10),
    gaze: EYE.dir.toArray().map(one => Math.round(one * 100) / 100)};
  const pointer = pointerNow();
  return picture ? {from, ...seen, pointer, png: lookFrom(who.mesh, camera)} : {from, ...seen, pointer};
}
/* What the person is looking at now: the selection, the large map, each map's mode, the side tab, the flow, the
 * physics, the panes open, the elements in the 3D view, where the person's 3D view is, in the units see measures,
 * the mouse pointer on it, the agent they follow and whether they see through its eyes, and what they share with
 * agents. */
export function viewing() {
  const inView = [];
  if (G) for (const node of G.graphData().nodes) {
    if (node.t !== 'el' || node.x === undefined) continue;
    const v = SPOT.set(node.x, node.y, node.z).project(G.camera());
    if (inFrame(v)) inView.push({address: node.address, name: node.name});
  }
  return {selected: selectedNow(), large: $('.app').classList.contains('swapped') ? '2d' : '3d', mode3d: V3.mode,
    zoom2d: MODE.free ? 'free' : 'full fit', tab: tabNow(), flow: flowModeNow(), physics: PHYS.name,
    board: !$('#board').hidden, chat: !$('#helpdesk').hidden, panes: WS.on ? WS.layout() : null, in_view_3d: inView,
    view_3d: view3d(), pointer: pointerNow(), mascot_eyes: EYE.view && !EYE.agent, following: FOLLOW.work,
    agent_eyes: EYE.agent, sharing: sharing() ? shareSaid() : null, mascot_motion: mascotMotion(),
    clicked: clickedSaid(), vitals: pageVitals()};
}
/* The last thing the person clicked, which their system agent reads to know what "this" is: its kind, what names it,
 * the state it showed and the record behind that, and when. One object, written in place on every click. A listener
 * on the document in the capture phase reads what the pointer takes before the click's own handlers act, and changes
 * nothing the click does. The chat's own head, tabs, buttons and message box are not recorded, nor a Chat button or
 * the mascot's ask field, since the person goes there to ask, and a click that opens the chat must not replace what
 * they ask about; the chat's conversation is. Nothing typed is read. On the maps a press that moved is a drag of the
 * view, not a click. `told` is set once the click's line has gone to the system agent, from the chat (dock/send.js) or the mascot (ask.js). Ticket
 * code.interface.graphical#124, 2026-10-18. */
export const CLICKED = {at: 0, project: null, kind: null, address: null, name: null, item: null, agent: null,
  label: null, control: null, state: null, record: null, told: false, downX: 0, downY: 0};
const STATE_WORDS = {broken: 'flashing red', trouble: 'flashing red', question: 'glowing, a question waits',
  message: 'glowing, a message waits', missing: 'missing', 'under-construction': 'under construction',
  unbuilt: 'not built yet'};
// the state said where a part shows several: its fault, then what waits on the person, then its stage
const STATE_ORDER = ['broken', 'trouble', 'question', 'message', 'missing', 'under-construction', 'unbuilt'];
const TONE_WORDS = {error: 'an error', warn: 'a warning'};
const clip = text => {
  const one = String(text || '').replace(/\s+/g, ' ').trim();
  return one.length > 80 ? `${one.slice(0, 79)}…` : one || null;
};
function heard(kind) {
  const c = CLICKED;
  c.at = Date.now(); c.project = S.project; c.kind = kind; c.address = null; c.name = null; c.item = null;
  c.agent = null; c.label = null; c.control = null; c.state = null; c.record = null; c.told = false;
}
/* The state a map part shows, and the open ticket behind it: an element shows its own work and that of the joins it
 * receives, which have no node of their own; a join its own. */
function partState(element, join) {
  const shown = join ? join.open_work || []
    : [...(element.open_work || []), ...S.joins.filter(one => one.receiver === element.id)
      .flatMap(one => one.open_work || [])];
  const condition = STATE_ORDER.find(one => shown.includes(one));
  if (!condition) return;
  CLICKED.state = STATE_WORDS[condition];
  const behind = (S.tickets || []).find(ticket => !ticket.done && ticket.condition === condition && (join
    ? ticket.node_kind === 'join' && ticket.node_id === join.id
    : ticket.node_kind === 'element' ? ticket.node_id === element.id
      : ticket.node_kind === 'join' && ticket.receiver_address === element.address));
  const item = behind?.map?.item;
  CLICKED.record = item ? `#${item.split('#').pop()} ${condition}` : null;
}
function elementClicked(id) {
  const element = S.elements.get(id)?.element;
  if (!element) return false;
  heard('element');
  CLICKED.address = element.address;
  CLICKED.name = clip(labelOf(element));
  partState(element, null);
  return true;
}
function joinClicked(joinId, provider) {
  const join = joinOf('p:' + joinId);
  if (!join) return false;
  heard('join');
  CLICKED.address = `${join.receiver_address} > ${partAddress(provider) || partAddress(join.providers[0])}`;
  CLICKED.name = clip(join.purpose);
  partState(null, join);
  return true;
}
/* An agent's figure or a board card: the ticket it stands for, its agent and the ticket's condition. */
function ticketClicked(kind, workId, glyph) {
  const ticket = ticketOf(workId);
  heard(kind);
  CLICKED.label = glyph || null;
  CLICKED.item = ticket?.map?.item || null;
  CLICKED.name = clip(ticket?.map?.title || ticket?.task);
  CLICKED.address = !ticket ? null : ticket.node_kind === 'join'
    ? `${ticket.receiver_address} > ${ticket.provider_address}` : ticket.address || null;
  CLICKED.agent = D.sessions.filter(one => one.work_id === workId).at(-1)?.agent || ticket?.map?.agent || null;
  if (ticket?.condition && STATE_WORDS[ticket.condition]) {
    CLICKED.state = STATE_WORDS[ticket.condition];
    CLICKED.record = CLICKED.item ? `#${CLICKED.item.split('#').pop()} ${ticket.condition}` : null;
  }
  return true;
}
/* What a click on the 3D map takes, in the order its own handlers take it: the mascot where no node is hovered, an
 * agent's figure, the node within reach, the nearest join edge, `clickMascot`, `clickFigure` and `clickedAt3d`. */
function clicked3dAt(x, y) {
  if (!G) return false;
  // a click on the mascot opens its ask field: it is how the person asks about what they clicked before, so it never
  // takes that click's place, as the chat's own controls do not
  if (mascotTakes(x, y)) return true;
  const node = nodeAt3d(x, y);
  const work = figureAt(x, y);
  if (work) return ticketClicked('agent figure', work, ROAM.figures.get(work)?.glyph);
  if (node?.t === 'el') return elementClicked(node.id);
  if (node) {
    heard(node.t || 'node');
    CLICKED.label = clip(node.name);
    return true;
  }
  const link = linkAt3d(x, y);
  return link ? joinClicked(link.join, link.target.id) : false;
}
/* And on the 2D map: an agent's figure, the node within reach, the nearest join edge, as `clickPicked` takes them. */
function clicked2dAt(target, x, y) {
  const g = target.closest('g.agent2d');
  if (g) {
    const figure = [...ROAM2D.figures.values()].find(one => one.g === g);
    return figure ? ticketClicked('agent figure', figure.id, g.dataset.glyph) : false;
  }
  const key = nodeAt2d(x, y);
  if (key) return key.startsWith('p:') ? joinClicked(key.slice(2), null) : elementClicked(key);
  const edge = edgeAt2d(x, y);
  return edge ? joinClicked(edge.join.id, edge.provider) : false;
}
const CONTROLS = 'button, a[href], summary, select, input, label, [role="tab"], [role="menuitem"], [role="button"], '
  + '[role="switch"], [role="checkbox"]';
/* A control's visible label: never what is typed in a field, only what names it. */
function controlWords(control) {
  const field = /^(INPUT|TEXTAREA|SELECT)$/.test(control.tagName);
  const own = control.getAttribute('aria-label') || (field ? control.labels?.[0]?.textContent : control.textContent);
  return clip(own || control.getAttribute('title') || (field ? control.getAttribute('placeholder') : ''));
}
/* The cards that ask the person something, and where each says what it asks, tried in order: a button there answers
 * that question, and its label alone ("No", "Allow once", "Decline") does not say which (graphical#146). */
const ASKING = [['.question-form', '.asked'], ['.elicitation', '.why', '.ask b'], ['.permission', '.ask b'],
  ['div.confirm', '.ask'], ['#mergeAsk', '.body p']];  // div: the act button has the class confirm too
function askedIn(control) {
  for (const [card, ...heads] of ASKING) {
    const box = control.closest(card);
    if (!box) continue;
    for (const head of heads) {
      const said = clip(box.querySelector(head)?.textContent);
      if (said) return said;
    }
  }
  return null;
}
/* Where a control is: the window by its title, or the side panel's tab and the heading over it. */
function placeOf(target) {
  const box = target.closest('.window');
  if (box) return clip(box.querySelector('.bar .title')?.textContent);
  const pane = target.closest('.pane[role="tabpanel"]');
  if (!pane) return null;
  const tab = clip(document.getElementById(pane.getAttribute('aria-labelledby'))?.textContent);
  for (let at = target; at && at !== pane; at = at.parentElement) {
    const head = at.querySelector(':scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > summary');
    if (head && head !== target) return [tab, clip(head.textContent)].filter(Boolean).join(' · ');
  }
  return tab;
}
function clickedOn(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!event.isTrusted || !target) return;
  if ((target.closest('#dock') && !target.closest('#helpdesk .log')) || target.closest('input.reply, button.chat')) {
    return;
  }
  const x = event.clientX, y = event.clientY, moved = Math.hypot(x - CLICKED.downX, y - CLICKED.downY) > 4;
  const control = target.closest(CONTROLS);
  if (target.closest('#stage') && !control) { if (!moved) clicked3dAt(x, y); return; }
  if (target.closest('#viewport') && M.svg && !target.closest('.crumbs, button, a')) {
    if (!moved) clicked2dAt(target, x, y);
    return;
  }
  const card = target.closest('#board .card'), banner = target.closest('.banner');
  const asked = control && askedIn(control);
  if (asked) {  // a button that answers a question: the question, the button, and where the card is
    heard('question');
    CLICKED.label = asked;
    CLICKED.control = controlWords(control);
    CLICKED.name = placeOf(control);
    return;
  } else if (card) {
    ticketClicked('board card', card.dataset.id, null);
  } else if (banner) {
    heard('banner');
    CLICKED.label = clip(banner.querySelector('.title')?.textContent || banner.querySelector('.text')?.textContent);
    CLICKED.state = TONE_WORDS[[...banner.classList].find(one => TONE_WORDS[one])] || null;
  } else if (target.closest('#toast')) {
    heard('notice');
    CLICKED.label = clip(target.closest('#toast').textContent);
  } else if (target.closest('#helpdesk .log')) {
    let row = target;
    while (row.parentElement && !row.parentElement.matches('#helpdesk .log')) row = row.parentElement;
    if (!row.parentElement) return;  // the conversation's own space, between its cards
    heard('chat card');
    CLICKED.label = clip(row.querySelector('.bubble, .title, .head, summary')?.textContent || row.textContent);
  } else if (control) {
    heard('control');
    CLICKED.label = controlWords(control);
    CLICKED.name = placeOf(control);
    return;
  } else if (target.closest('.pane[role="tabpanel"]')) {
    heard('panel section');
    CLICKED.label = placeOf(target);
    return;
  } else return;
  if (control) CLICKED.control = controlWords(control);  // the button of a card, a banner or a notice
}
document.addEventListener('pointerdown', event => { CLICKED.downX = event.clientX; CLICKED.downY = event.clientY; },
  {capture: true, passive: true});
document.addEventListener('click', clickedOn, {capture: true, passive: true});
/* The click as web_viewing gives it: null before any, and on another project than the one shown. */
function clickedSaid() {
  const c = CLICKED;
  if (!c.at || c.project !== S.project) return null;
  return {kind: c.kind, address: c.address, name: c.name, item: c.item, agent: c.agent, label: c.label,
    control: c.control, state: c.state, record: c.record, at: new Date(c.at).toISOString(),
    seconds_ago: Math.round((Date.now() - c.at) / 1000), told: c.told, said: clickedWords()};
}
/* What the person clicked, in the words their system agent is told: what it is and what names it, then the state it
 * showed and the record behind that. */
export function clickedWords() {
  const c = CLICKED, quoted = text => text ? ` "${text}"` : '';
  const what = c.kind === 'element' ? `element ${c.address}${c.name ? ` (${c.name})` : ''}`
    : c.kind === 'join' ? `join ${c.address}`
      : c.kind === 'agent figure' || c.kind === 'board card'
        ? `${c.kind}${c.agent ? ` of ${c.agent}` : ''} on ${c.item || 'a ticket'}${c.address ? ` at ${c.address}` : ''}`
          + quoted(c.name)
        : `${c.kind}${quoted(c.label)}${c.control ? `, its button "${c.control}"` : ''}`
          + (c.name ? ` in ${c.name}` : '');
  return `${what}${c.state ? `, ${c.state}` : ''}${c.record ? ` (${c.record})` : ''}`;
}
/* The one line that tells the person's system agent what they last clicked: given within CLICK_FRESH of the click,
 * and only with the first message sent since it, by the chat, dock/send.js, or the mascot's ask field, ask.js, so
 * "this" in what they write names it. Ticket code.interface.graphical#124, 2026-10-18. */
const CLICK_FRESH = 120000;
export function clickedLine() {
  const ago = Date.now() - CLICKED.at;
  if (!CLICKED.at || CLICKED.told || CLICKED.project !== S.project || ago > CLICK_FRESH) return '';
  return `${CLICK_LEAD}${Math.round(ago / 1000)} s before: ${clickedWords()}.`;
}
/* How the mascot moved on this page over its last seconds, for an agent reading what the person sees, VIEW-005: each
 * frame's body on the screen, its facing and size, its own animation, the point it steers to, the camera and the
 * frame's time, written into typed arrays sized once, one per channel, so a frame allocates nothing. `mascotMotion`
 * reads them back as a summary per channel: its range, its usual step and how often its steps turn back a second,
 * which tells a shake from a deliberate move. */
const MOTION_SLOTS = 1024, MOTION_SPAN = 4000;  // frames kept, at 240 a second over 4 s; the ms a summary reads
// each channel, and the step under which a turn back is not counted
const MOTION_CHANNELS = [['screen_x', 0.5], ['screen_y', 0.5], ['yaw', 0.2], ['pitch', 0.2], ['scale', 1e-3],
  ['gait_y', 1e-3], ['gait_pitch', 1e-3], ['body_y', 1e-3], ['body_lean', 1e-3], ['want_x', 1e-2], ['want_y', 1e-2],
  ['want_z', 1e-2], ['camera_x', 1e-2], ['camera_y', 1e-2], ['camera_z', 1e-2]];
const MOTION_STATES = ['idle', 'sleep', 'attend', 'cross'];
const MOTION = {next: 0, at: new Float64Array(MOTION_SLOTS), frame: new Float32Array(MOTION_SLOTS),
  flags: new Uint8Array(MOTION_SLOTS), state: new Uint8Array(MOTION_SLOTS),
  channels: MOTION_CHANNELS.map(() => new Float32Array(MOTION_SLOTS))};
const ON_SCREEN = new THREE.Vector3(), FACING = new THREE.Vector3();
const PAGE = {id: Math.random().toString(36).slice(2, 10), loaded: new Date(performance.timeOrigin).toISOString()};
/* One frame of the mascot, from `mascot3d` once its body is placed: `want` is where it steers, or null. */
export function sampleMascot(mesh, want, passed, state, driven, leaving) {
  const slot = MOTION.next % MOTION_SLOTS, c = MOTION.channels, camera = G.camera(), canvas = G.renderer().domElement;
  MOTION.next++;
  MOTION.at[slot] = performance.now();
  MOTION.frame[slot] = passed * 1000;
  MOTION.flags[slot] = (MASCOT.speaking ? 1 : 0) | (driven ? 2 : 0) | (MASCOT.sleeping ? 4 : 0) | (leaving ? 8 : 0);
  const known = MOTION_STATES.indexOf(state);
  MOTION.state[slot] = known < 0 ? 255 : known;
  ON_SCREEN.copy(mesh.position).project(camera);
  c[0][slot] = (ON_SCREEN.x + 1) / 2 * canvas.width;
  c[1][slot] = (1 - ON_SCREEN.y) / 2 * canvas.height;
  mesh.getWorldDirection(FACING);
  c[2][slot] = Math.atan2(FACING.x, FACING.z) * 180 / Math.PI;
  c[3][slot] = Math.asin(Math.max(-1, Math.min(1, FACING.y))) * 180 / Math.PI;
  c[4][slot] = mesh.scale.x;
  const gait = mesh.children[0], body = gait?.children[0]?.children[0]?.children[0];
  c[5][slot] = gait ? gait.position.y : 0;
  c[6][slot] = gait ? gait.rotation.x : 0;
  c[7][slot] = body ? body.position.y : 0;
  c[8][slot] = body ? body.rotation.z : 0;
  c[9][slot] = want ? want.x : NaN;
  c[10][slot] = want ? want.y : NaN;
  c[11][slot] = want ? want.z : NaN;
  c[12][slot] = camera.position.x;
  c[13][slot] = camera.position.y;
  c[14][slot] = camera.position.z;
}
const median = values => {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
};
const fixed = value => value === null || !Number.isFinite(value) ? null : Math.round(value * 1000) / 1000;
/* The last seconds of the mascot's motion on this page, or null while no mascot is drawn: which page answers and when
 * it loaded, whether it is shown, whether the browser is speaking, the frame times, the share of frames and the
 * switches of each state, and per channel [least, most, median step, turns back a second]. */
function mascotMotion() {
  if (!MASCOT.mesh) return null;
  const now = performance.now(), slots = [];
  for (let back = 1; back <= Math.min(MOTION.next, MOTION_SLOTS); back++) {
    const slot = (MOTION.next - back) % MOTION_SLOTS;
    if (now - MOTION.at[slot] > MOTION_SPAN) break;
    slots.unshift(slot);
  }
  const seconds = slots.length > 1 ? (MOTION.at[slots.at(-1)] - MOTION.at[slots[0]]) / 1000 : 0;
  const frames = slots.map(slot => MOTION.frame[slot]).sort((a, b) => a - b);
  const share = bit => slots.length ? fixed(slots.filter(slot => MOTION.flags[slot] & bit).length / slots.length) : null;
  const switches = read => slots.slice(1).filter((slot, at) => read(slot) !== read(slots[at])).length;
  const channels = {};
  MOTION_CHANNELS.forEach(([name, least], index) => {
    const values = slots.map(slot => MOTION.channels[index][slot]).filter(Number.isFinite);
    const steps = values.slice(1).map((value, at) => value - values[at]);
    const back = steps.slice(1).filter((step, at) => Math.abs(step) > least && Math.abs(steps[at]) > least
      && step * steps[at] < 0).length;
    channels[name] = values.length ? [fixed(Math.min(...values)), fixed(Math.max(...values)),
      fixed(median(steps.map(Math.abs))), seconds ? fixed(back / seconds) : null] : null;
  });
  return {page: PAGE.id, loaded: PAGE.loaded, shown: document.visibilityState, focused: document.hasFocus(),
    glyph: MASCOT.glyph, seconds: fixed(seconds), frames: slots.length,
    frame_ms: frames.length ? [fixed(median(frames)), fixed(frames[Math.floor(frames.length * 0.95)]),
      fixed(frames.at(-1))] : null,
    speech: {mascot: Boolean(MASCOT.speaking), browser: Boolean(window.speechSynthesis?.speaking),
      queued: Boolean(window.speechSynthesis?.pending)},
    speaking: share(1), driven: share(2), sleeping: share(4), leaving: share(8),
    state_switches: switches(slot => MOTION.state[slot]), driven_switches: switches(slot => MOTION.flags[slot] & 2),
    columns: ['least', 'most', 'median step', 'turns back a second'], channels};
}
const rounded = (v, by = 10) => v.toArray().map(one => Math.round(one * by) / by);
/* Where the person's 3D view is and which way it looks, in the units see measures. */
const view3d = () => G ? {at: rounded(G.camera().position), gaze: rounded(G.camera().getWorldDirection(SPOT), 100)}
  : null;
/* The mouse pointer on the 3D map, VIEW-005: where it is in the map's area, the ray the person's camera casts through
 * it, and what that ray takes, as a click there would. Nothing once the pointer has left the 3D map or the page has
 * gone to another project, so no agent goes to where the pointer was. */
export const POINTER = {inside: false, x: 0, y: 0, project: null, at: 0, last: null};
$('#stage').addEventListener('pointermove', event => Object.assign(POINTER,
  {inside: true, x: event.clientX, y: event.clientY, project: S.project, at: Date.now()}), {passive: true});
$('#stage').addEventListener('pointerleave', () => { POINTER.inside = false; });
const RAY = new THREE.Raycaster(), NDC = new THREE.Vector2();
/* The ray through the pointer now, with where it is in the area, or null while it is off the map or the page has gone
 * to another project. */
function pointerRay() {
  if (!G || !POINTER.inside || POINTER.project !== S.project) return null;
  const area = $('#stage').getBoundingClientRect();
  if (!area.width || !area.height) return null;
  const x = POINTER.x - area.left, y = POINTER.y - area.top;
  RAY.setFromCamera(NDC.set(x / area.width * 2 - 1, -y / area.height * 2 + 1), G.camera());
  return {ray: RAY.ray, x, y, area};
}
export function pointerNow() {
  POINTER.last = null;
  const cast = pointerRay();
  if (!cast) return null;
  const {ray, x, y, area} = cast, hit = hitAt(POINTER.x, POINTER.y, ray);
  POINTER.last = {origin: ray.origin.clone(), direction: ray.direction.clone(), hit: hit?.at || null};
  return {pane: '3d', x: Math.round(x), y: Math.round(y), width: Math.round(area.width),
    height: Math.round(area.height), still_ms: Date.now() - POINTER.at,
    ray: {origin: rounded(ray.origin), direction: rounded(ray.direction, 1000)},
    hit: hit?.seen || null};
}
/* What the pointer's ray takes, as a click there takes it, `clickedAt3d`: an agent's figure, else the node whose reach
 * covers the pointer, else the nearest join edge, with the point of the map it is at; null when it takes nothing. */
const LINK_FROM = new THREE.Vector3(), LINK_TO = new THREE.Vector3();
function hitAt(x, y, ray) {
  const work = figureAt(x, y), figure = work ? ROAM.figures.get(work) : null;
  if (figure) {
    const at = figure.mesh.position.clone();
    return {at, seen: {kind: 'figure', work, character: figure.glyph, who: `the agent on ${partAddress(figure.target)
      || 'its ticket'}`, distance: Math.round(ray.origin.distanceTo(at) * 10) / 10, point: rounded(at)}};
  }
  const node = nodeAt3d(x, y);
  if (node) {
    const at = new THREE.Vector3(node.x, node.y, node.z), away = ray.origin.distanceTo(at);
    const seen = node.t === 'el' || node.t === 'purpose' ? seenEntry(node, away)
      : {kind: node.t || 'node', id: node.id, name: node.name || null, distance: Math.round(away * 10) / 10};
    return {at, seen: {...seen, point: rounded(at)}};
  }
  // a join is seen on its edge, having no node of its own
  const link = linkAt3d(x, y), purpose = link ? {id: purposeOf(link), t: 'purpose', work: link.work || []} : null;
  if (!purpose) return null;
  const at = new THREE.Vector3();
  ray.distanceSqToSegment(LINK_FROM.set(link.source.x, link.source.y, link.source.z),
    LINK_TO.set(link.target.x, link.target.y, link.target.z), null, at);
  return {at, seen: {...seenEntry(purpose, ray.origin.distanceTo(at)), on: 'edge', point: rounded(at)}};
}
/* web_capture, what the person sees, to the agent that asks: `view`, a picture from the person's own 3D camera, the
 * size of their 3D area up to 1280 pixels across, with the pointer's ray drawn in; `screen`, a frame of what they share
 * with agents. A page sharing nothing answers last, so a page of the person's that shares is the one heard. */
export function capture(payload, answer) {
  if (payload.source === 'screen') {
    const frame = shareFrame(true);
    if (frame.error) setTimeout(() => answer(frame), 1500); else answer(frame);
    return;
  }
  if (!G) return answer({error: 'The 3D map is not open on this page.'});
  const area = $('#stage').getBoundingClientRect();
  if (!area.width || !area.height) return answer({error: 'The 3D map has no room on the page now.'});
  const width = Math.min(1280, Math.round(area.width)), height = Math.round(width * area.height / area.width);
  const pointer = pointerNow();
  answer({source: 'view', width, height, view_3d: view3d(), pointer, png: lookFrom(null, G.camera(), width, height)});
}
/* What the person shares with agents: a screen, a window or a tab, chosen in the browser's own picker, which only the
 * person's click can open, getDisplayMedia. Agents take frames of it, web_capture, and the chat sends one with a
 * message, until the share ends, from the page or the browser's own Stop sharing. */
export const SHARE = {stream: null, video: null, label: '', surface: null};
export async function startShare() {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    toast('This browser cannot share a screen, window or tab with agents.');
    return false;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({video: true, audio: false});
  } catch (error) {
    toast(error?.name === 'NotAllowedError' ? 'Nothing is shared: the share was cancelled.'
      : `The share did not start: ${error?.message || error}`);
    return false;
  }
  stopShare(false);
  const video = Object.assign(document.createElement('video'), {muted: true, playsInline: true, srcObject: stream});
  await video.play().catch(() => {});
  const [track] = stream.getVideoTracks();
  track.addEventListener('ended', () => { if (SHARE.stream === stream) stopShare(); });
  const surface = track.getSettings?.().displaySurface || null;
  Object.assign(SHARE, {stream, video, label: track.label || '', surface});
  drawShare();
  toast(`Agents can see ${shareSaid()} until you stop sharing.`);
  return true;
}
export function stopShare(say = true) {
  const was = SHARE.stream;
  for (const track of was?.getTracks() || []) track.stop();
  Object.assign(SHARE, {stream: null, video: null, label: '', surface: null});
  drawShare();
  if (was && say) toast('Nothing is shared with agents now.');
}
export const sharing = () => SHARE.stream?.getVideoTracks()[0]?.readyState === 'live' && SHARE.video?.videoWidth > 0;
const shareSaid = () => ({monitor: 'your screen', window: 'that window', browser: 'that tab'})[SHARE.surface]
  || 'what you share';
/* One frame of the share as JPEG, at most 1920 pixels across. With nothing shared, an agent's ask offers the person
 * the share, `asked`. */
export function shareFrame(asked = false) {
  if (!sharing()) {
    if (asked) toast('An agent asks to see your screen.', {action: 'Share…', run: startShare});
    return {error: 'Nothing is shared with agents now: the person starts a share with Share a screen with agents, '
      + 'in the Agents menu, and picks a screen, window or tab.'};
  }
  const video = SHARE.video, scale = Math.min(1, 1920 / video.videoWidth);
  const canvas = Object.assign(document.createElement('canvas'),
    {width: Math.round(video.videoWidth * scale), height: Math.round(video.videoHeight * scale)});
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  return {source: 'screen', surface: SHARE.surface, label: SHARE.label, shared: [video.videoWidth, video.videoHeight],
    width: canvas.width, height: canvas.height, jpeg: canvas.toDataURL('image/jpeg', 0.85).split(',')[1]};
}
function drawShare() {
  const button = $('#shareBtn');
  button.textContent = SHARE.stream ? 'Stop sharing with agents' : 'Share a screen with agents…';
  button.title = SHARE.stream ? `Agents can see ${shareSaid()}: stop the share`
    : 'Pick a screen, window or tab in the browser\'s picker; agents can then see it with web_capture, and the chat '
      + 'can send a frame of it';
}
$('#shareBtn').onclick = () => SHARE.stream ? stopShare() : startShare();
drawShare();
/* Just in front of the person's 3D view, a little below its middle, near enough that a figure there is seen plainly:
 * where web_come brings a figure to get the person's attention. */
const BEFORE = new THREE.Vector3();
export function screenPoint(out, size = ROAM.drawn || 1) {
  const camera = G.camera();
  camera.getWorldDirection(BEFORE);
  return out.copy(camera.position).addScaledVector(BEFORE, size * 9).addScaledVector(camera.up, -size * 1.5);
}
/* Where an approach the agent chose, web_come, brings its body now, into `out`: `view`, in front of the person's view;
 * `pointer`, on the pointer's ray as near as `view`, so it stands under the mouse; `hit`, beside what the pointer
 * takes, on the person's side of it. Followed, it is read live, the hit at most every quarter second, and kept where
 * it last was while the pointer is off the map; otherwise it stays where it was when the agent asked. False when there
 * is no such place, as when the pointer takes nothing. */
export function approachPoint(come, size, out) {
  if (come.point && !come.follow) return out.copy(come.point);
  if (come.to === 'view') return out.copy(come.point = screenPoint(come.point || new THREE.Vector3(), size));
  const cast = pointerRay();
  if (come.to === 'pointer' && cast) {
    come.point = (come.point || new THREE.Vector3()).copy(cast.ray.origin)
      .addScaledVector(cast.ray.direction, size * 9);
  } else if (come.to === 'hit' && cast && !(performance.now() - (come.read || 0) < 250 && come.point)) {
    come.read = performance.now();
    const hit = hitAt(POINTER.x, POINTER.y, cast.ray)?.at;
    if (hit) {
      const toward = BEFORE.subVectors(G.camera().position, hit).normalize();
      come.point = (come.point || new THREE.Vector3()).copy(hit).addScaledVector(toward, size * 1.5);
    }
  }
  return come.point ? out.copy(come.point) : false;
}
/* The selection as the person sees it: an element by its address and name, or a join by its purpose. */
function selectedNow() {
  const chosen = S.selected, on = chosen ? (S.elements.get(chosen)?.element || null) : null;
  const join = chosen?.startsWith('p:') ? joinOf(chosen) : null;
  if (on) return {address: on.address, name: labelOf(on)};
  return join ? {join: join.purpose, receiver: join.receiver_address} : null;
}
/* A figure's eyes, for the person: the large 3D view eases to where the figure sees from, its own eye camera,
 * `eyeCamera`, with its near plane, and goes with it, never orbiting, and back to where the camera was, with the
 * person's near plane. The mascot's, E; a followed agent's, V. `mesh` is the body seen from; a new one while the view
 * is on takes the view over to it. A sign the camera met, and a flight still on its way, end as the view goes: the met
 * sign is drawn over the map at the rectangle its corners project to, which only matches the sign seen square on, so
 * from the eyes it was a stretched strip of its name, and the meeting's near plane hid everything before the eyes
 * (stretched label, code.interface.graphical#63, 2026-10-15). The ease takes EASE seconds by the clock from the press,
 * at any frame rate; leaving the view gives the person their camera at once, and a hand on it during the way back
 * puts the camera where it was at once, `handBack` (code.interface.graphical#81, 2026-10-15). */
const EASE = 0.9;
export function eyesOf(mesh, on = !EYE.view) {
  if (!G || (on && !mesh)) return false;
  const camera = G.camera(), controls = G.controls();
  if (on) {
    meetEnds(true);
    FLIGHT.on = false;
    V3.focus = V3.hold = null;
  }
  // still easing back to the person's view, the place it eases to is the one kept
  if (on && !EYE.view && !EYE.saved) {
    EYE.saved = {at: camera.position.clone(), turn: camera.quaternion.clone(), fov: camera.fov, near: camera.near};
  }
  if (on && EYE.mesh && EYE.mesh !== mesh) EYE.mesh.visible = true;
  if (on) EYE.mesh = mesh;
  EYE.view = V3.eyes = Boolean(on);
  EYE.agent = EYE.view && mesh !== MASCOT.mesh;
  WATCHED.mesh = EYE.agent ? EYE.mesh : null;  // its words at the bottom of the view, as it has no body there
  EYE.k = 0;
  EYE.started = performance.now();
  controls.enabled = !EYE.view;
  if (EYE.hand !== controls) { EYE.hand = controls; controls.addEventListener('start', handBack); }
  wake3d(1500);
  return EYE.view;
}
export const mascotEyes = (on = !EYE.view) => MASCOT.mesh ? eyesOf(MASCOT.mesh, on) : false;
/* The way back from a figure's eyes is over: the camera where it was, with its near plane, and the body seen again. */
function backHome(camera) {
  camera.position.copy(EYE.saved.at);
  camera.quaternion.copy(EYE.saved.turn);
  camera.fov = EYE.saved.fov;
  camera.near = EYE.saved.near;
  EYE.saved = null;
  if (EYE.mesh) EYE.mesh.visible = true;
  EYE.mesh = null;
}
/* A hand on the camera while it eases back from a figure's eyes: the camera is where it was at once, and the hand
 * moves it from there. */
function handBack() {
  if (EYE.view || !EYE.saved || !G) return;
  const camera = G.camera();
  backHome(camera);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  FRAMES.moved = true;
}
const EYEQ = new THREE.Quaternion();
export function eyes3d() {  // each frame: the large camera toward the figure's eyes, or back to where it was
  followWatch();
  // the agent's view is the large 3D map's: put in the small area, the agent view ends and the map goes back to the
  // person's view
  if ((EYE.view || EYE.agentMode) && small3d()) {
    EYE.agentMode = false;
    if (EYE.view) eyesOf(null, false);
  }
  if (!G || (!EYE.view && !EYE.saved)) return;
  const camera = G.camera(), mesh = EYE.mesh;
  EYE.k = reduced() ? 1 : Math.min(1, (performance.now() - EYE.started) / 1000 / EASE);
  const k = 1 - Math.pow(1 - EYE.k, 3);
  if (mesh) mesh.visible = !(EYE.view || (EYE.saved && EYE.k < 0.6));  // never seen from inside
  if (EYE.view && mesh) {
    const eye = eyeCamera(mesh, camera.aspect);
    camera.position.lerp(eye.position, Math.max(k, 0.25));
    camera.quaternion.slerp(EYEQ.copy(eye.quaternion), Math.max(k, 0.25));
    camera.fov += (eye.fov - camera.fov) * Math.max(k, 0.25);
    camera.near = eye.near;  // what stands just before the eyes is drawn, as its own look draws it
  } else if (EYE.saved) {
    camera.position.lerp(EYE.saved.at, k);
    camera.quaternion.slerp(EYE.saved.turn, k);
    camera.fov += (EYE.saved.fov - camera.fov) * k;
    if (EYE.k >= 1) backHome(camera);
  }
  camera.updateProjectionMatrix();
  // the labels, bubbles and readout placed after this in the frame read the camera as it is drawn, not as it was
  camera.updateMatrixWorld();
  FRAMES.moved = true;
}
/* The agents the person can follow, A: each agent's figure on the 3D map still at work, the oldest first. */
const onScreen = () => [...ROAM.figures.values()].filter(figure => figure.mesh && !figure.done);
const followSaid = figure => figure
  ? `Following: the ${figure.glyph} on ${partAddress(figure.target) || 'its ticket'}` : 'Following: none';
/* Follow an agent's figure, or none: both maps keep its figure in their middle, `followWatch`, the 2D map at the zoom
 * that frames its node, `autoZoom2d`, and goes back to full fit when none is followed, or stays where the hand left it
 * when a drag ended the following, `fit` false; the followed agent is named at the 2D map's corner and marked in the
 * agents key while it is followed, `showFollowed`. With the agent view on, the view goes over to the new one's eyes,
 * or back to the person's for none, and the agent view stays on for the next. Following takes the 3D camera from the
 * layout's own fits and from a flight under way, as a hand does. */
export function followFigure(figure, say = true, fit = true) {
  // each map's ease is timed from the press, so the first frame after it already goes toward the figure
  const now = performance.now();
  Object.assign(FOLLOW, {work: figure?.id || null, node: figure?.target || null, scale: null, around: null, at2d: now,
    at3d: now, go2d: null, go3d: null});
  if (EYE.agentMode && figure) eyesOf(figure.mesh, true);
  else if (EYE.agent) eyesOf(null, false);
  if (figure) {
    FLIGHT.on = false;
    V3.auto = false;
    V3.focus = V3.hold = null;
    wake3d();  // a map left to rest draws again, so its camera goes with the figure
    autoZoom2d(figure.target);
  } else if (fit) fullFit2d();
  FOLLOWED.glyph = figure?.glyph || null;
  showFollowed(figure?.id || null, FOLLOWED.glyph);
  if (say) note2d(followSaid(figure));
}
/* A: none, then each agent on the map in turn, then none again. */
export function followNext() {
  const all = onScreen(), at = all.findIndex(figure => figure.id === FOLLOW.work);
  followFigure(at < 0 ? all[0] || null : all[at + 1] || null);
}
/* V: the agent view on, the large 3D map seen from the followed agent's own eyes and from each agent A follows next,
 * or off, the person's view again. */
export function agentView() {
  if (EYE.view || EYE.agentMode) {
    EYE.agentMode = false;
    if (EYE.view) eyesOf(null, false);
    note2d('View: yours');
    return;
  }
  const figure = FOLLOW.work ? ROAM.figures.get(FOLLOW.work) : null;
  if (!figure?.mesh) return note2d('No agent is followed: A follows one');
  if (small3d()) return note2d("The agent's view is the large 3D map's: S swaps the maps");
  EYE.agentMode = true;
  eyesOf(figure.mesh, true);
  note2d(`View: the ${figure.glyph}'s`);
}
/* Each 3D frame: a followed agent that has left is replaced by the newest still on the map, or none; one that moves on
 * to another node gives the 2D map the zoom that frames that node; one drawn again in another character, `reglyph`,
 * keeps the view at its new body's eyes, and the old body, gone from the scene, is seen from no longer, and is named
 * by its new glyph. Outside an eye view the 3D camera goes with the figure, `follow3d`. */
function followWatch() {
  if (!FOLLOW.work) return;
  const figure = ROAM.figures.get(FOLLOW.work);
  if (!figure || figure.done) return followFigure(onScreen().at(-1) || null);
  if (EYE.agent && figure.mesh && figure.mesh !== EYE.mesh) eyesOf(figure.mesh, true);
  if (figure.target !== FOLLOW.node) { FOLLOW.node = figure.target; autoZoom2d(figure.target); }
  if (figure.glyph !== FOLLOWED.glyph) showFollowed(figure.id, FOLLOWED.glyph = figure.glyph);
  if (figure.mesh) followIn3d(figure.mesh.position);
}
const FOLLOWED = {glyph: null};
/* The followed figure in the middle of the 3D map, large or small, each frame: the point the camera turns about and
 * the camera itself go with the figure where it is drawn, its acts too, which can carry it toward the camera for
 * seconds, eased as the 2D camera is, `spring`, so the camera keeps its distance and its angle and the hand can still
 * turn about the figure and zoom. Not while the view is a figure's eyes, or easing back from them, nor while a flight
 * runs, which then ends where it was going, after which the camera goes on with the figure. The spring keeps where it
 * is itself, so a step too small to draw is not lost, and goes on from a point the hand moved, the wheel's. A camera
 * already there is not moved, so a figure at rest costs the map nothing. A met sign ends as the camera leaves it,
 * `meetEnds`; the camera's matrix is updated at once, so the labels and the speech bubble placed after this in the
 * frame stand where they are drawn. */
const FOLLOW3D = {by: new THREE.Vector3()};
function followIn3d(figureAt) {
  const passed = followPassed('at3d');
  if (!G || EYE.view || EYE.saved || FLIGHT.on) { FOLLOW.go3d = null; return; }
  const camera = G.camera(), target = G.controls().target, by = FOLLOW3D.by;
  const go = FOLLOW.go3d ||= {at: target.clone(), speed: new THREE.Vector3(), drawn: target.clone()};
  // the hand moved the turning point: the spring starts again from rest there, or its kept speed sweeps the camera
  if (!go.drawn.equals(target)) { go.at.copy(target); go.speed.set(0, 0, 0); }
  // `spring`'s step on each axis, worked out in numbers so the follow allocates nothing, CLAUDE.md 4.1
  const fade = Math.exp(-FOLLOW_PACE * passed), still = reduced();
  for (let axis = 0; axis < 3; axis++) {
    const goal = figureAt.getComponent(axis);
    if (still) { go.at.setComponent(axis, goal); go.speed.setComponent(axis, 0); continue; }
    const off = go.at.getComponent(axis) - goal, speed = go.speed.getComponent(axis), push = speed + FOLLOW_PACE * off;
    go.at.setComponent(axis, goal + (off + push * passed) * fade);
    go.speed.setComponent(axis, (speed - FOLLOW_PACE * push * passed) * fade);
  }
  by.subVectors(go.at, target);
  if (by.length() < camera.position.distanceTo(target) * 1e-5) return;
  if (MEET.on) meetEnds();
  V3.hold = null;
  target.add(by);
  camera.position.add(by);
  go.drawn.copy(target);
  camera.updateMatrixWorld();
  FRAMES.moved = true;
}
/* Each 2D frame, `roam2d`: the followed agent's flat figure kept in the middle of the 2D map, `follow2d`; at its node,
 * its own place there, so an act, a small hop in 2D, or a reach toward another part does not swing the map with it. */
export function followed2d(figures) {
  const flat = FOLLOW.work ? figures.get(FOLLOW.work) : null, at = flat?.stage === 'circling' && flat.place || flat;
  if (flat?.size) follow2d(at.x, at.y, flat.stage === 'circling');
}
/* A drag on either map is the hand taking the camera: it ends the following there, and the view stays where the hand
 * takes it; on the 3D map seen through a figure's eyes the hand turns nothing, so the following goes on. A click, on
 * a figure or a node, and the wheel do not end it; the wheel's zoom is the one followed at. */
const HAND = {at: null};
for (const map of ['#map2d', '#stage']) {
  $(map)?.addEventListener('pointerdown', event => { HAND.at = [event.clientX, event.clientY]; }, true);
  $(map)?.addEventListener('pointermove', event => {
    if (!HAND.at || !event.buttons || Math.hypot(event.clientX - HAND.at[0], event.clientY - HAND.at[1]) < 4) return;
    HAND.at = null;
    if (FOLLOW.work && (map === '#map2d' || !EYE.view)) followFigure(null, true, false);
  }, true);
}
addEventListener('pointerup', () => { HAND.at = null; }, true);
/* A project left: nothing followed, and the person's own view. */
export function leaveFollow() {
  Object.assign(FOLLOW, {work: null, node: null, scale: null, around: null, at2d: null, at3d: null, go2d: null,
    go3d: null});
  showFollowed(null, FOLLOWED.glyph = null);
  if (EYE.agent) eyesOf(null, false);
}
export function eyeDebug3d() {  // the eye anchor and the gaze ray of every figure, drawn for a check of `look`
  for (const mesh of [MASCOT.mesh, ...[...ROAM.figures.values()].map(figure => figure.mesh)]) {
    if (!mesh) continue;
    eyeOf(mesh, EYE.at, EYE.dir);
    const far = mesh.scale.x * 6;
    const tip = {x: EYE.at.x + EYE.dir.x * far, y: EYE.at.y + EYE.dir.y * far, z: EYE.at.z + EYE.dir.z * far};
    fxLine(EYE.at, tip, tintOf(css('--debug')), 1, 0.4);
    fxDot(EYE.at, mesh.scale.x * 0.12, tintOf(css('--debug')), 1, 0, 6, 10);
  }
}
