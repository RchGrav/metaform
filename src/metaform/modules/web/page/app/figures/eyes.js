/* A figure's eyes as a camera: what it sees, a picture from its view, what the person is looking at, and the
 * mascot's eyes for the person. */
import '/page/app/figures/attention.js';  // the part before runs first, so the parts run in the page's order
// The graph, glass and figures share the import map's one local Three.js runtime, VIEW-003 and VIEW-025.
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {$, css, reduced} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {ROAM, ballOf, isSystemTalk, conversing, sizeOf} from '/page/app/figures/agents.js';
import {PULL, TOWARD, SPOT, facingOf} from '/page/app/figures/walk.js';
import {MASCOT, mascotGlyph} from '/page/app/figures/mascot.js';
import {faceToward, TURNED} from '/page/app/figures/attention.js';
import {INUSE, shownNode} from '/page/app/map3d/light.js';
import {G, FRAMES, wake3d} from '/page/app/map3d/graph3d.js';
import {AT, signsFor} from '/page/app/map3d/labels.js';
import {flowModeNow} from '/page/app/flow/flow.js';
import {tintOf, fxDot, fxLine} from '/page/app/flow/fx3d.js';
import {MODE, V3} from '/page/app/camera/flight.js';
import {small3d} from '/page/app/camera/fly3d.js';
import {PHYS} from '/page/app/views/bar.js';
import {labelOf} from '/page/app/map2d/inside.js';
import {FOLLOW, autoZoom2d, fullFit2d} from '/page/app/map2d/camera.js';
import {note2d} from '/page/app/map2d/hover.js';
import {ticketOf} from '/page/app/agents/dispatch.js';
import {tabNow} from '/page/app/panel/prompts.js';
import {WS} from '/page/app/workspace/workspace.js';
import {toast} from '/page/app/core/controls.js';
import {figureAt} from '/page/app/figures/ask.js';
import {nodeAt3d, linkAt3d, purposeOf} from '/page/app/map3d/pick3d.js';

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
  saved: null, k: 0, mesh: null, agent: false, agentMode: false};
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
/* Once a figure faces a node, within TURNED degrees, or after `most` milliseconds: then(turned or time). */
function facingThen(mesh, node, most, then) {
  const began = performance.now(), facing = new THREE.Vector3(), toward = new THREE.Vector3();
  wake3d(most + 500);
  const check = () => {
    const there = G.graphData().nodes.find(one => one.id === node);
    if (!there || there.x === undefined) return then('its target left the map');
    toward.set(there.x, there.y, there.z).sub(mesh.position).setY(0);
    const off = toward.lengthSq() < 1e-8 ? 0 : facingOf(mesh, facing).angleTo(toward.normalize()) * 180 / Math.PI;
    if (off <= TURNED) return then('turned');
    if (performance.now() - began > most) return then('time');
    setTimeout(check, 50);
  };
  setTimeout(check, 50);
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
    agent_eyes: EYE.agent, sharing: sharing() ? shareSaid() : null};
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
  const link = linkAt3d(x, y), purpose = link ? G.graphData().nodes.find(one => one.id === purposeOf(link)) : null;
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
 * `eyeCamera`, and goes with it, never orbiting, and back to where the camera was. The mascot's, E; a followed agent's,
 * V. `mesh` is the body seen from; a new one while the view is on takes the view over to it. */
export function eyesOf(mesh, on = !EYE.view) {
  if (!G || (on && !mesh)) return false;
  const camera = G.camera(), controls = G.controls();
  // still easing back to the person's view, the place it eases to is the one kept
  if (on && !EYE.view && !EYE.saved) EYE.saved ={at: camera.position.clone(), turn: camera.quaternion.clone(), fov: camera.fov};
  if (on && EYE.mesh && EYE.mesh !== mesh) EYE.mesh.visible = true;
  if (on) EYE.mesh = mesh;
  EYE.view = V3.eyes = Boolean(on);
  EYE.agent = EYE.view && mesh !== MASCOT.mesh;
  EYE.k = 0;
  controls.enabled = !EYE.view && !EYE.saved;
  wake3d(1500);
  return EYE.view;
}
export const mascotEyes = (on = !EYE.view) => MASCOT.mesh ? eyesOf(MASCOT.mesh, on) : false;
const EYEQ = new THREE.Quaternion();
export function eyes3d(passed) {  // each frame: the large camera toward the figure's eyes, or back to where it was
  followWatch();
  // the agent's view is the large 3D map's: put in the small area, the agent view ends and the map goes back to the
  // person's view
  if ((EYE.view || EYE.agentMode) && small3d()) {
    EYE.agentMode = false;
    if (EYE.view) eyesOf(null, false);
  }
  if (!G || (!EYE.view && !EYE.saved)) return;
  const camera = G.camera(), mesh = EYE.mesh;
  EYE.k = reduced() ? 1 : Math.min(1, EYE.k + passed / 0.9);
  const k = 1 - Math.pow(1 - EYE.k, 3);
  if (mesh) mesh.visible = !(EYE.view || (EYE.saved && EYE.k < 0.6));  // never seen from inside
  if (EYE.view && mesh) {
    const eye = eyeCamera(mesh, camera.aspect);
    camera.position.lerp(eye.position, Math.max(k, 0.25));
    camera.quaternion.slerp(EYEQ.copy(eye.quaternion), Math.max(k, 0.25));
    camera.fov += (eye.fov - camera.fov) * Math.max(k, 0.25);
  } else if (EYE.saved) {
    camera.position.lerp(EYE.saved.at, k);
    camera.quaternion.slerp(EYE.saved.turn, k);
    camera.fov += (EYE.saved.fov - camera.fov) * k;
    if (EYE.k >= 1) {
      EYE.saved = null;
      G.controls().enabled = true;
      if (mesh) mesh.visible = true;
      EYE.mesh = null;
    }
  }
  camera.updateProjectionMatrix();
  FRAMES.moved = true;
}
/* The agents the person can follow, A: each agent's figure on the 3D map still at work, the oldest first. */
const onScreen = () => [...ROAM.figures.values()].filter(figure => figure.mesh && !figure.done);
const followSaid = figure => figure
  ? `Following: the ${figure.glyph} on ${partAddress(figure.target) || 'its ticket'}` : 'Following: none';
/* Follow an agent's figure, or none: the 2D map frames its node, `autoZoom2d`, and goes back to full fit when none is
 * followed; with the agent view on, the view goes over to the new one's eyes, or back to the person's for none, and
 * the agent view stays on for the next. */
export function followFigure(figure, say = true) {
  Object.assign(FOLLOW, {work: figure?.id || null, node: figure?.target || null});
  if (EYE.agentMode && figure) eyesOf(figure.mesh, true);
  else if (EYE.agent) eyesOf(null, false);
  if (figure) autoZoom2d(figure.target); else fullFit2d();
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
/* Each frame: a followed agent that has left is replaced by the newest still on the map, or none; one that moves on
 * to another node takes the 2D map with it. */
function followWatch() {
  if (!FOLLOW.work) return;
  const figure = ROAM.figures.get(FOLLOW.work);
  if (!figure || figure.done) return followFigure(onScreen().at(-1) || null);
  if (figure.target !== FOLLOW.node) { FOLLOW.node = figure.target; autoZoom2d(figure.target); }
}
/* A project left: nothing followed, and the person's own view. */
export function leaveFollow() {
  Object.assign(FOLLOW, {work: null, node: null});
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
