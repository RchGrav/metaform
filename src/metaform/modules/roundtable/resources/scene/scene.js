// The roundtable's scene, BASE-066: the seats round a round table, each seat's figure at its chair, a plant in the
// middle. It is built from the table's state, as the runner's watch server gives it at /state: every seat's place,
// facing, name, ring colour, raised hand and bubble. The figures are the web page's own, from agents3d.js, loaded and
// never changed. A figure never leaves its chair; it only turns about its own vertical axis.
//
// One module drives both surfaces: the person's watch page, seen from above, and the runner's headless renderer,
// which draws a seat's view from its own eyes, `eyeShot`. A facing is a bearing in degrees, clockwise from the far
// side of the table as the person sees it from above; a figure looks along its own +Z.

import * as THREE from 'three';
import { createAgent, GLYPHS, eyeOf } from '/page/agents3d.js';

// The figures a table gives its seats in order, each a different one: chosen to read apart at a glance.
// The flat flyers, a kite and a plane, come last: edge on they are hard to read.
const ORDER = ['owl', 'cubebot', 'jelly', 'moth', 'crystal', 'seahorse', 'mushroom', 'drone', 'snail', 'beetle',
  'puffer', 'gearling', 'slime', 'comet', 'wisp', 'kite', 'plane'];
const FIGURES = [...ORDER.filter((name) => GLYPHS.includes(name)), ...GLYPHS.filter((name) => !ORDER.includes(name))];

export function glyphOf(position) { return FIGURES[position % FIGURES.length]; }

// A facing as the figure's turn about Y: its +Z points along the bearing.
const yawOf = (facing) => Math.PI - THREE.MathUtils.degToRad(facing);

// ---------------------------------------------------------------- the placeholder hand

// The raised hand: an arm and a palm made of primitives, standing up beside the figure's head, on its right. Isolated here so the
// person's own hand model replaces this one function.
export function makeHand() {
  const hand = new THREE.Group();
  const skin = new THREE.MeshStandardMaterial({ color: 0xf2c9a0, roughness: 0.6 });
  const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 0.8, 14), skin);
  arm.position.y = 0.4; hand.add(arm);
  const palm = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.28, 0.09), skin);
  palm.position.y = 0.92; hand.add(palm);
  for (let i = 0; i < 4; i += 1) {
    const finger = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.03, 0.2, 8), skin);
    finger.position.set(-0.095 + i * 0.063, 1.15 - Math.abs(i - 1.5) * 0.02, 0); hand.add(finger);
  }
  const thumb = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.033, 0.16, 8), skin);
  thumb.position.set(0.17, 0.9, 0); thumb.rotation.z = -0.8; hand.add(thumb);
  return hand;
}

// ---------------------------------------------------------------- labels and bubbles

function textSprite(lines, { font = 26, pad = 14, width = 0, fill = 'rgba(14,18,30,0.86)', ink = '#eef2ff',
  border = 'rgba(160,180,255,0.6)', scale = 0.0062 } = {}) {
  const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
  ctx.font = `${font}px system-ui, sans-serif`;
  const inner = width || Math.max(...lines.map((line) => ctx.measureText(line).width));
  canvas.width = Math.ceil(inner + pad * 2); canvas.height = Math.ceil(lines.length * font * 1.25 + pad * 2);
  ctx.font = `${font}px system-ui, sans-serif`;
  ctx.fillStyle = fill; ctx.strokeStyle = border; ctx.lineWidth = 3;
  const r = 14, w = canvas.width, h = canvas.height;
  ctx.beginPath(); ctx.moveTo(r, 1.5); ctx.arcTo(w - 1.5, 1.5, w - 1.5, h - 1.5, r);
  ctx.arcTo(w - 1.5, h - 1.5, 1.5, h - 1.5, r); ctx.arcTo(1.5, h - 1.5, 1.5, 1.5, r); ctx.arcTo(1.5, 1.5, w - 1.5, 1.5, r);
  ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.fillStyle = ink; ctx.textBaseline = 'top';
  lines.forEach((line, i) => ctx.fillText(line, pad, pad + i * font * 1.25));
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }));
  sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
  sprite.renderOrder = 10;
  return sprite;
}

function wrapped(text, most = 46) {
  const lines = [];
  let line = '';
  for (const word of String(text).split(/\s+/)) {
    if (line && (line + ' ' + word).length > most) { lines.push(line); line = word; } else line = line ? `${line} ${word}` : word;
  }
  if (line) lines.push(line);
  return lines;
}

// ---------------------------------------------------------------- the room

function furniture(scene, table) {
  const wood = new THREE.MeshStandardMaterial({ color: 0x8a5a3b, roughness: 0.55 });
  const floor = new THREE.Mesh(new THREE.CircleGeometry(table.ring + 1.5, 64),
    new THREE.MeshStandardMaterial({ color: 0x1b2030, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; scene.add(floor);
  const top = new THREE.Mesh(new THREE.CylinderGeometry(table.radius, table.radius, 0.08, 64), wood);
  top.position.y = table.top - 0.04; scene.add(top);
  const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.3, table.top - 0.08, 20), wood);
  leg.position.y = (table.top - 0.08) / 2; scene.add(leg);
  // the plant in the middle: a pot, and leaves fanning up and out
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.14, 0.24, 24),
    new THREE.MeshStandardMaterial({ color: 0xc0623a, roughness: 0.7 }));
  pot.position.y = table.top + 0.12; scene.add(pot);
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x3fa34d, roughness: 0.5 });
  for (let i = 0; i < 9; i += 1) {
    const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8), leafMat);
    const turn = (i / 9) * Math.PI * 2, tilt = 0.35 + (i % 3) * 0.15;
    leaf.scale.set(1, 1.6, 0.45);  // low, under the seats' eye line
    leaf.position.set(Math.sin(turn) * 0.1, table.top + 0.24 + (i % 3) * 0.02, Math.cos(turn) * 0.1);
    leaf.rotation.set(Math.cos(turn) * tilt, 0, -Math.sin(turn) * tilt);
    scene.add(leaf);
  }
  return wood;
}

function chair(wood, x, z, facing) {
  const group = new THREE.Group();
  const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.08, 24), wood);
  seat.position.y = 0.45; group.add(seat);
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.1, 0.45, 12), wood);
  post.position.y = 0.22; group.add(post);
  group.position.set(x, 0, z); group.rotation.y = yawOf(facing);
  return group;
}

// ---------------------------------------------------------------- the table

// The scene for one table, drawn into `renderer`. `update(state)` brings it to the table's state; `frame(dt)` moves
// the figures' idle motion and, unless `snap`, eases each figure toward its facing.
export function createTable(renderer, { snap = false } = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0e16);
  scene.add(new THREE.HemisphereLight(0xdce6ff, 0x20202a, 1.5));
  const sun = new THREE.DirectionalLight(0xffffff, 2.0); sun.position.set(4, 9, 6); scene.add(sun);
  const seats = new Map();
  let built = null, wood = null, state = null;

  function build(given) {
    built = `${given.discussion}:${given.seats.length}`;
    wood = furniture(scene, given.table);
  }

  function seatOf(one, table) {
    let held = seats.get(one.position);
    if (held) return held;
    const figure = createAgent(glyphOf(one.position), { harness: one.harness });
    figure.position.set(one.x, table.seat_y, one.z);
    figure.rotation.y = yawOf(one.facing);
    scene.add(figure);
    scene.add(chair(wood, one.x, one.z, one.facing));
    const label = textSprite([one.name], { font: 30, pad: 10 });
    scene.add(label);
    held = { figure, label, name: one.name, bubble: null, bubbleText: null, hand: null, yaw: yawOf(one.facing) };
    seats.set(one.position, held);
    return held;
  }

  function update(given) {
    state = given;
    if (built !== `${given.discussion}:${given.seats.length}`) build(given);
    for (const one of given.seats) {
      const held = seatOf(one, given.table);
      held.yaw = yawOf(one.facing);
      if (snap) held.figure.rotation.y = held.yaw;
      held.label.position.set(one.x, given.table.seat_y + 1.05, one.z);
      held.label.material.opacity = one.gone ? 0.4 : 1;
      held.figure.visible = !one.gone;
      if (one.hand && !held.hand) { held.hand = makeHand(); held.hand.position.set(-0.75, -0.15, 0); held.figure.add(held.hand); }
      if (!one.hand && held.hand) { held.figure.remove(held.hand); held.hand = null; }
      if (one.bubble !== held.bubbleText) {
        if (held.bubble) { scene.remove(held.bubble); held.bubble.material.map.dispose(); held.bubble = null; }
        held.bubbleText = one.bubble;
        if (one.bubble) {
          held.bubble = textSprite(wrapped(one.bubble, 56), { font: 22, fill: 'rgba(250,250,255,0.95)', ink: '#141826',
            border: 'rgba(80,90,140,0.8)', scale: 0.0046 });
          scene.add(held.bubble);
        }
      }
      if (held.bubble) {
        const h = held.bubble.scale.y;
        held.bubble.position.set(one.x, given.table.seat_y + 1.28 + h / 2, one.z);
      }
      held.speaking = one.speaking;
    }
  }

  function frame(dt) {
    for (const held of seats.values()) {
      if (!snap) {
        let d = held.yaw - held.figure.rotation.y;
        d = Math.atan2(Math.sin(d), Math.cos(d));
        held.figure.rotation.y += d * Math.min(1, dt * 4);
      }
      held.figure.userData.update?.(dt, { busy: held.speaking ? 0.6 : 0 });
    }
  }

  // The view from a seat's own eyes, `eyeOf`, level along its facing and tipped a little down, 5 degrees, to the table, as a PNG
  // data URL. The seat's own figure, label and bubble are left out of its own view.
  const eyeCamera = new THREE.PerspectiveCamera(60, 4 / 3, 0.05, 200);
  const at = new THREE.Vector3(), dir = new THREE.Vector3();
  function eyeShot(position) {
    const held = seats.get(position), one = state?.seats.find((s) => s.position === position);
    if (!held || !one) throw new Error(`no seat ${position}`);
    const { fov, width, height } = state.eye;
    held.figure.rotation.y = held.yaw;
    eyeOf(held.figure, at, dir);
    const facing = THREE.MathUtils.degToRad(one.facing);
    dir.set(Math.sin(facing), Math.tan(THREE.MathUtils.degToRad(-5)), -Math.cos(facing)).normalize();
    eyeCamera.fov = fov; eyeCamera.aspect = width / height; eyeCamera.updateProjectionMatrix();
    eyeCamera.position.copy(at).addScaledVector(dir, 0.08);
    eyeCamera.lookAt(at.clone().add(dir));
    const hidden = [held.figure, held.label, held.bubble].filter(Boolean);
    hidden.forEach((thing) => { thing.visible = false; });
    renderer.setSize(width, height, false);
    renderer.render(scene, eyeCamera);
    const url = renderer.domElement.toDataURL('image/png');
    hidden.forEach((thing) => { thing.visible = !(thing === held.figure && one.gone); });
    return url;
  }

  return { scene, update, frame, eyeShot, get state() { return state; } };
}
