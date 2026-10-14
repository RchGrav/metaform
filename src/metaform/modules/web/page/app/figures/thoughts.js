/* Each figure's public work update, carried by the existing dispatch read and event stream. */
import * as THREE from 'three';
import {eyeOf} from '/page/agents3d.js';
import {h} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {ROAM} from '/page/app/figures/agents.js';
import {G, wake3d} from '/page/app/map3d/graph3d.js';
import {figureWords} from '/page/app/map3d/readout.js';
import {D} from '/page/app/agents/dispatch.js';
import {speechBubble} from '/page/app/figures/bubble.js';

const THOUGHTS = new Map(), LABELS = new Map(), POINT = new THREE.Vector3(), GAZE = new THREE.Vector3();
let scope = '';
/* Cut only at a word where there is one. Text is always set as text, never interpreted as markup. */
export function thoughtText(text) {
  const line = String(text || '').split(/\r?\n/).filter(part => part.trim()).at(-1)?.trim().replace(/\s+/g, ' ') || '';
  if (line.length <= 140) return line;
  const start = line.slice(0, 139), word = start.lastIndexOf(' ');
  return (word > 0 ? start.slice(0, word) : start).trimEnd() + '…';
}
/* A short fragment keeps the previous readable line until it has words or the stream has paused. */
export function updateThoughts(found) {
  const here = `${S.project}/${S.base}`;
  if (scope !== here) {
    for (const label of LABELS.values()) label.el.remove();
    LABELS.clear(); THOUGHTS.clear(); scope = here;
  }
  const active = new Set();
  for (const session of [...(found.sessions || []), ...(found.subagents || [])]) {
    const id = session.session_id;
    active.add(id);
    const state = THOUGHTS.get(id) || {text: '', pending: null};
    state.working = session.parent ? !/input|wait|completed|failed|cancelled|canceled|ended|error|disconnected/i.test(session.state)
      : session.state === 'running' && session.activity === 'working';
    const line = session.latest_message;
    if (line?.session_id === id && line.kind === 'agent_message_chunk') {
      const text = thoughtText(line.text), key = `${line.name}:${line.seq}:${text}`;
      if (state.pending?.key !== key) state.pending = {key, text, since: performance.now(), complete: line.complete};
      else state.pending.complete ||= line.complete;
      acceptLine(state);
    }
    THOUGHTS.set(id, state);
  }
  for (const [id, state] of THOUGHTS) if (!active.has(id)) state.working = false;
  wake3d(900);
}
function acceptLine(state) {
  const next = state.pending;
  if (!next?.text) return;
  const paused = performance.now() - next.since >= 700 && (next.text.length >= 12 || /[.!?…]$/.test(next.text));
  if (next.complete || next.text.length >= 24 && next.text.split(' ').length >= 4
    || paused) state.text = next.text;
}
function labelFor(id, session, mode) {
  const key = `${mode}:${id}`;
  let label = LABELS.get(key);
  if (label?.session !== session) { label?.el.remove(); LABELS.delete(key); label = null; }
  if (label) return label;
  const words = h('span', {class: 'agent-thought-words'});
  const cloud = h('div', {class: 'agent-thought-cloud'}, words);
  const name = h('div', {class: 'agent-thought-name'}, figureWords(id).card.title);
  const el = h('div', {class: 'agent-thought', 'data-work': id, 'data-session': session, 'data-map': mode}, cloud, name);
  document.body.append(el);
  label = {el, cloud, words, name, session, text: '', bubble: null};
  LABELS.set(key, label);
  return label;
}
function paintBubble(label, text) {
  if (text === label.text) return;
  label.text = text;
  label.words.textContent = text;
  label.bubble = speechBubble(text);
  const {canvas, tip} = label.bubble;
  canvas.setAttribute('aria-hidden', 'true');
  label.cloud.replaceChildren(canvas, label.words);
  label.cloud.style.left = `${-tip[0]}px`;
  label.cloud.style.top = `${-tip[1]}px`;
}
function sessionOf(figure, sessions) {
  return figure.child?.session || sessions.filter(one => one.work_id === figure.id && one.state === 'running').at(-1)?.session_id;
}
/* Overlay coordinates keep the letters the same size through every camera zoom, in front of map geometry. */
export function placeThoughts3d(sessions = D.sessions) {
  const placed = [], live = new Set();
  if (!G) return;
  const camera = G.camera(), area = G.renderer().domElement.getBoundingClientRect();
  for (const [id, figure] of ROAM.figures) {
    const session = sessionOf(figure, sessions);
    if (!session) continue;
    const label = labelFor(id, session, '3d');
    live.add(`3d:${id}`);
    // Anchor the shared renderer's tail to the actual head, including character bob and lean.
    eyeOf(figure.mesh, POINT, GAZE);
    const point = POINT.project(camera), sx = point.x, sy = point.y, sz = point.z;
    const x = area.left + (sx + 1) * area.width / 2;
    const y = area.top + (1 - sy) * area.height / 2;
    const visible = area.width > 0 && Math.abs(sz) < 1 && x >= area.left && x <= area.right
      && y >= area.top && y <= area.bottom && figure.mesh.visible && figure.stage !== 'leaving';
    placeLabel(label, figure, {x, y, area, visible}, placed);
  }
  cleanLabels('3d', live);
}
/* Called by the 2D view's own frame loop once that view's ticket is ready for it. */
export function placeThoughts2d(figures, sessions = D.sessions) {
  const placed = [], live = new Set();
  for (const [id, figure] of figures) {
    const session = sessionOf(figure, sessions);
    if (!session) continue;
    const label = labelFor(id, session, '2d'), box = figure.g.getBoundingClientRect();
    const area = figure.g.closest('#map2d').getBoundingClientRect();
    live.add(`2d:${id}`);
    placeLabel(label, figure, {x: box.left + box.width / 2, y: box.top,
      area, visible: box.width > 0 && box.bottom > area.top && box.top < area.bottom
        && box.right > area.left && box.left < area.right}, placed);
  }
  cleanLabels('2d', live);
}
function placeLabel(label, figure, at, placed) {
  const state = THOUGHTS.get(label.session);
  if (state) acceptLine(state);
  const on = Boolean(at.visible && !figure.done && state?.working && state.text
    && !['returning', 'flourish', 'leaving'].includes(figure.stage));
  label.el.classList.toggle('on', on);
  label.el.classList.toggle('figure-visible', Boolean(at.visible));
  if (!at.visible) return;
  if (on) paintBubble(label, state.text);
  const title = figureWords(figure.id).card.title;
  if (label.name.textContent !== title) label.name.textContent = title;
  label.el.style.left = `${at.x}px`;
  label.el.style.top = `${at.y}px`;
  if (on) {
    const {width, height, tip} = label.bubble;
    const rect = {left: at.x - tip[0], right: at.x - tip[0] + width,
      top: at.y - tip[1], bottom: at.y - tip[1] + height};
    // Keep the tail on its figure. Overlaps can only change stacking without moving that anchor.
    const overlap = placed.some(other => rect.left < other.right + 8 && rect.right > other.left - 8
      && rect.top < other.bottom + 8 && rect.bottom > other.top - 8);
    label.el.style.zIndex = overlap ? '23' : '';
    placed.push(rect);
  }
}
function cleanLabels(mode, live) {
  for (const [key, label] of LABELS) if (key.startsWith(`${mode}:`) && !live.has(key)) {
    label.el.classList.remove('on', 'figure-visible');
    if (!ROAM.figures.has(label.el.dataset.work)) { label.el.remove(); LABELS.delete(key); }
  }
}
