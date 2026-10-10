// Metaform agents 3D: seventeen procedural, animated agent characters for a Three.js graph.
//
//   import { createAgent, GLYPHS, drawGlyph, placeAgentOnCurve } from './metaform-agents-3d.js';
//   const agent = createAgent(drawGlyph(sessionId), { harness: 'codex' });
//   scene.add(agent);
//   // each frame:
//   agent.userData.update(dt, { busy: 0..1 });   // busy speeds up the idle motion
//   placeAgentOnCurve(agent, edgeCurve, u);
//
// Conventions: Y up, +Z is the travel direction, pivot at the body centre,
// largest dimension about 1.6 units. No external assets; everything is built in code.

import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export const GLYPHS = [
  'jelly', 'gearling', 'kite', 'moth', 'drone', 'snail', 'crystal', 'wisp',
  'comet', 'beetle', 'slime', 'plane', 'puffer', 'owl', 'cubebot', 'mushroom',
  'seahorse',
];

// A harness's ring colour, by the agent id the dispatch module names it with, claude, codex or gemini, VIEW-039,
// and by the longer names harnesses go by.
export const HARNESS_RING = {
  claude: 0xd97757, 'claude-code': 0xd97757, codex: 0xe8e8e8, gemini: 0x4f8cff, 'gemini-cli': 0x4f8cff, pi: 0xff5fa2,
  hermes: 0x38e0a0, opencode: 0xf5c542, crush: 0xa78bfa, other: 0x7d88b0,
};

// ---------------------------------------------------------------- drawn from the id

// A ticket's character comes from its id, so it is the same on every load of the page; two at work at once never
// share one, the second taking the next free character after its own.
function spread(text) {
  let hash = 0x811c9dc5;  // FNV-1a
  for (const char of String(text)) { hash ^= char.codePointAt(0); hash = Math.imul(hash, 0x01000193) >>> 0; }
  return hash;
}
const assigned = new Map();
// A ticket assigned to an agent's glyph, VIEW-040, is drawn as that glyph; tickets sharing it are one agent's.
export function drawGlyph(sessionId, own = null) {
  if (GLYPHS.includes(own)) { assigned.set(sessionId, own); return own; }
  if (assigned.has(sessionId)) return assigned.get(sessionId);
  const inUse = new Set(assigned.values());
  const start = spread(sessionId) % GLYPHS.length;
  const order = GLYPHS.map((_, step) => GLYPHS[(start + step) % GLYPHS.length]);
  const g = order.find((name) => !inUse.has(name)) ?? order[0];
  assigned.set(sessionId, g);
  return g;
}
export function releaseGlyph(sessionId) { assigned.delete(sessionId); }

// ---------------------------------------------------------------- materials

const INK = 0x0b0f24;

function vinyl(color, o = {}) {
  return new THREE.MeshPhysicalMaterial({
    color, roughness: o.rough ?? 0.38, metalness: o.metal ?? 0,
    clearcoat: o.coat ?? 0.8, clearcoatRoughness: 0.25,
    sheen: o.sheen ?? 0.3, sheenColor: new THREE.Color(0xffffff), sheenRoughness: 0.6,
    emissive: new THREE.Color(o.glow ?? color), emissiveIntensity: o.glowAmt ?? 0.12,
    transparent: o.opacity !== undefined, opacity: o.opacity ?? 1,
    side: o.side ?? THREE.FrontSide, flatShading: !!o.flat,
  });
}
const glowMat = (color, amt = 2.2) =>
  new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: amt, roughness: 0.4 });
const inkMat = () => new THREE.MeshPhysicalMaterial({ color: INK, roughness: 0.15, clearcoat: 1 });
const whiteMat = () => new THREE.MeshBasicMaterial({ color: 0xffffff });

// Inverted-hull outline: a back-face shell pushed out along the normals.
// Gives the 3D agents the dark outline of the 2D glyphs.
const outlineMat = new THREE.ShaderMaterial({
  uniforms: { thickness: { value: 0.028 }, color: { value: new THREE.Color(INK) } },
  vertexShader: `uniform float thickness;
    void main(){ vec3 p = position + normal * thickness;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0); }`,
  fragmentShader: `uniform vec3 color; void main(){ gl_FragColor = vec4(color,1.0); }`,
  side: THREE.BackSide,
});

function mesh(geo, mat, { outline = true, parent, pos, rot, scale } = {}) {
  const m = new THREE.Mesh(geo, mat);
  if (pos) m.position.set(...pos);
  if (rot) m.rotation.set(...rot);
  if (scale) (typeof scale === 'number' ? m.scale.setScalar(scale) : m.scale.set(...scale));
  if (outline) {
    const o = new THREE.Mesh(geo, outlineMat);
    o.raycast = () => {};
    m.add(o);
  }
  if (parent) parent.add(m);
  return m;
}

// Cute face: two glossy eyes with a white catch-light, placed on a surface facing +Z.
function eyes(parent, { y = 0, z = 0.5, gap = 0.16, r = 0.075, color = INK } = {}) {
  const out = [];
  for (const s of [-1, 1]) {
    const g = new THREE.Group();
    g.position.set(s * gap, y, z);
    mesh(new THREE.SphereGeometry(r, 20, 14), new THREE.MeshPhysicalMaterial({ color, roughness: 0.1, clearcoat: 1 }),
      { parent: g, outline: false, scale: [1, 1.15, 0.6] });
    mesh(new THREE.SphereGeometry(r * 0.32, 10, 8), whiteMat(), { parent: g, outline: false, pos: [r * 0.3, r * 0.4, r * 0.45] });
    parent.add(g);
    out.push(g);
  }
  return out;
}

// Profiles are written top to bottom; reversed so the normals face outward.
const lathe = (pts, seg = 48) => new THREE.LatheGeometry([...pts].reverse().map(([x, y]) => new THREE.Vector2(x, y)), seg);

// Tube whose radius varies along its length.
function taperTube(pointFn, radiusFn, tubular = 96, radial = 20) {
  const path = new (class extends THREE.Curve { getPoint(t, v = new THREE.Vector3()) { return v.copy(pointFn(t)); } })();
  const geo = new THREE.TubeGeometry(path, tubular, 1, radial, false);
  const pos = geo.attributes.position, frames = path.computeFrenetFrames(tubular, false);
  const v = new THREE.Vector3(), c = new THREE.Vector3();
  for (let i = 0; i <= tubular; i++) {
    const t = i / tubular; path.getPoint(t, c); const r = radiusFn(t);
    for (let j = 0; j <= radial; j++) {
      const k = i * (radial + 1) + j;
      v.fromBufferAttribute(pos, k).sub(c).multiplyScalar(r).add(c);
      pos.setXYZ(k, v.x, v.y, v.z);
    }
  }
  geo.computeVertexNormals();
  return geo;
}

// Chain of capsule segments that trails with a phase lag: tentacles, tails.
function chain(parent, { n = 6, len = 0.1, r = 0.035, mat, pos = [0, 0, 0], axis = -1 }) {
  const root = new THREE.Group(); root.position.set(...pos); parent.add(root);
  const segs = []; let p = root;
  for (let i = 0; i < n; i++) {
    const g = new THREE.Group(); if (i) g.position.y = axis * len; p.add(g);
    mesh(new THREE.CapsuleGeometry(r * (1 - i / (n * 1.4)), len, 6, 12), mat, { parent: g, pos: [0, axis * len / 2, 0] });
    segs.push(g); p = g;
  }
  return { root, segs };
}
function waveChain(ch, t, { amp = 0.35, freq = 3, lag = 0.6, axis = 'z', phase = 0 }) {
  ch.segs.forEach((s, i) => { s.rotation[axis] = Math.sin(t * freq - i * lag + phase) * amp * (0.4 + i / ch.segs.length); });
}

// Scalloped fan fin in the XY plane, opening toward +X from its hinge at the origin.
function fanGeo(r, spread, scallops = 5) {
  const sh = new THREE.Shape(); sh.moveTo(0, 0);
  for (let i = 0; i <= scallops * 2; i++) {
    const a = -spread / 2 + (spread * i) / (scallops * 2), rr = i % 2 ? r : r * 0.82;
    sh.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  sh.closePath();
  return new THREE.ExtrudeGeometry(sh, { depth: 0.012, bevelEnabled: true, bevelSize: 0.008, bevelThickness: 0.006, bevelSegments: 2 }).translate(0, 0, -0.006);
}

// ---------------------------------------------------------------- the seventeen

const BUILD = {
  jelly(root) {
    const col = 0xb79cff;
    const bell = mesh(lathe([[0, 0.42], [0.2, 0.4], [0.36, 0.3], [0.45, 0.12], [0.47, -0.02], [0.4, -0.06], [0.3, -0.02], [0, -0.02]]),
      vinyl(col, { glowAmt: 0.45, sheen: 1 }), { parent: root });
    mesh(new THREE.SphereGeometry(0.13, 24, 16), glowMat(0xfff2c4, 3), { parent: bell, outline: false, pos: [0, 0.12, 0] });
    const light = new THREE.PointLight(0xffe7a8, 1.2, 1.6); light.position.y = 0.12; bell.add(light);
    eyes(bell, { y: 0.18, z: 0.41, gap: 0.14 });
    const tent = [];
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2;
      tent.push(chain(root, { n: 7, len: 0.085, r: 0.035, mat: vinyl(0xb79cff, { glowAmt: 0.4 }), pos: [Math.sin(a) * 0.27, -0.03, Math.cos(a) * 0.27] }));
    }
    return (t, s) => {
      const p = Math.sin(t * 2.4 * s);
      bell.scale.set(1 + 0.07 * p, 1 - 0.09 * p, 1 + 0.07 * p);
      tent.forEach((c, i) => { waveChain(c, t * s, { amp: 0.4, freq: 2.4, lag: 0.7, axis: 'x', phase: i });
        waveChain(c, t * s, { amp: 0.25, freq: 1.7, lag: 0.5, axis: 'z', phase: i * 2 }); });
      light.intensity = 1 + 0.4 * Math.sin(t * 3);
    };
  },

  gearling(root) {
    const shape = new THREE.Shape(); const teeth = 9, ro = 0.62, ri = 0.5;
    for (let i = 0; i < teeth * 4; i++) {
      const a = (i / (teeth * 4)) * Math.PI * 2, r = (i % 4 < 2) ? ro : ri;
      i ? shape.lineTo(Math.cos(a) * r, Math.sin(a) * r) : shape.moveTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    const hole = new THREE.Path(); hole.absarc(0, 0, 0.4, 0, Math.PI * 2, true); shape.holes.push(hole);
    const gear = mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.12, bevelEnabled: true, bevelSize: 0.025, bevelThickness: 0.025, bevelSegments: 3, curveSegments: 32 }),
      vinyl(0xb6f36b, { metal: 0.3, rough: 0.3 }), { parent: root, pos: [0, 0, -0.06] });
    const body = mesh(new THREE.SphereGeometry(0.38, 40, 28), vinyl(0x9ade52), { parent: root, scale: [1, 1, 0.85] });
    mesh(new THREE.SphereGeometry(0.39, 40, 12, Math.PI / 2 - 0.75, 1.5, Math.PI / 2 - 0.2, 0.36), inkMat(), { parent: body, outline: false });
    const eye = mesh(new THREE.SphereGeometry(0.06, 20, 14), glowMat(0xd7ff9e, 3), { parent: body, outline: false, pos: [0, 0, 0.4], scale: [1, 1, 0.6] });
    return (t, s) => {
      gear.rotation.z = t * 0.8 * s;
      { const a = Math.sin(t * 1.6 * s) * 0.55; eye.position.set(Math.sin(a) * 0.39, 0, Math.cos(a) * 0.39); }
      body.rotation.y = Math.sin(t * 0.8) * 0.15;
    };
  },

  kite(root) {
    const sh = new THREE.Shape(); sh.moveTo(0, 0.62); sh.lineTo(0.42, 0.12); sh.lineTo(0, -0.5); sh.lineTo(-0.42, 0.12); sh.closePath();
    const sail = mesh(new THREE.ExtrudeGeometry(sh, { depth: 0.04, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.02, bevelSegments: 3 }),
      vinyl(0xffd166, { glowAmt: 0.18 }), { parent: root, pos: [0, 0.1, -0.02] });
    const spar = vinyl(0x8a5a1a);
    mesh(new THREE.CylinderGeometry(0.018, 0.018, 1.12), spar, { parent: sail, outline: false, pos: [0, 0.06, 0.08] });
    mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.84), spar, { parent: sail, outline: false, pos: [0, 0.12, 0.08], rot: [0, 0, Math.PI / 2] });
    eyes(sail, { y: 0.2, z: 0.1, gap: 0.14, r: 0.06 });
    const tail = chain(root, { n: 8, len: 0.08, r: 0.014, mat: vinyl(0xffb347), pos: [0, -0.4, 0.02] });
    const bows = [2, 5, 7].map((i) => mesh(new THREE.OctahedronGeometry(0.05), vinyl(0xff7a6b), { parent: tail.segs[i], pos: [0, -0.08, 0], scale: [1.4, 0.8, 0.5] }));
    return (t, s) => {
      root.rotation.z = Math.sin(t * 1.2) * 0.12;
      sail.rotation.x = Math.sin(t * 1.7) * 0.08;
      waveChain(tail, t * s, { amp: 0.5, freq: 4, lag: 0.7, axis: 'z' });
      bows.forEach((b, i) => (b.rotation.y = t * 3 + i));
    };
  },

  moth(root) {
    const body = mesh(new THREE.CapsuleGeometry(0.13, 0.42, 10, 20), vinyl(0xc9483a), { parent: root, rot: [Math.PI / 2, 0, 0] });
    const head = mesh(new THREE.SphereGeometry(0.15, 28, 20), vinyl(0xc9483a), { parent: root, pos: [0, 0.02, 0.36] });
    eyes(head, { y: 0.03, z: 0.12, gap: 0.07, r: 0.05 });
    for (const s of [-1, 1]) {
      mesh(taperTube((t) => new THREE.Vector3(s * (0.04 + t * 0.14), 0.1 + t * 0.24, 0.4 + t * 0.14), (t) => 0.012 * (1 - t * 0.5), 24, 8), vinyl(0x3a0e09), { parent: root, outline: false });
    }
    const wingShape = new THREE.Shape();
    wingShape.moveTo(0, 0.05); wingShape.bezierCurveTo(0.25, 0.45, 0.72, 0.35, 0.66, 0.02);
    wingShape.bezierCurveTo(0.7, -0.3, 0.3, -0.42, 0, -0.1); wingShape.closePath();
    const wingGeo = new THREE.ExtrudeGeometry(wingShape, { depth: 0.02, bevelEnabled: true, bevelSize: 0.015, bevelThickness: 0.01, bevelSegments: 2, curveSegments: 24 });
    wingGeo.rotateX(-Math.PI / 2);
    const wings = [-1, 1].map((s) => {
      const piv = new THREE.Group(); piv.position.set(s * 0.06, 0.04, 0.05); root.add(piv);
      const w = mesh(wingGeo, vinyl(0xff7a6b, { glowAmt: 0.25, side: THREE.DoubleSide }), { parent: piv, scale: [s * 1.25, 1, 1.25] });
      mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.02, 24), glowMat(0xffc2b8, 1.4), { parent: w, outline: false, pos: [0.4, 0.035, 0.05] });
      return { piv, s };
    });
    return (t, s) => {
      const f = Math.sin(t * 14 * s);
      wings.forEach(({ piv, s: side }) => (piv.rotation.z = side * (0.75 + f * 0.55)));
      root.position.y = Math.sin(t * 5) * 0.03;
    };
  },

  drone(root) {
    const body = mesh(new THREE.SphereGeometry(0.4, 40, 28), vinyl(0x6ff0c0), { parent: root, scale: [1.05, 0.8, 0.9] });
    eyes(body, { y: 0.02, z: 0.36, gap: 0.14, r: 0.07 });
    mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.2), vinyl(0x2a6b58), { parent: root, pos: [0, 0.38, 0] });
    const hub = mesh(new THREE.SphereGeometry(0.06, 16, 12), vinyl(0x2bb88a), { parent: root, pos: [0, 0.49, 0] });
    const rotor = new THREE.Group(); hub.add(rotor);
    for (let i = 0; i < 3; i++) mesh(new THREE.CapsuleGeometry(0.035, 0.5, 4, 10), vinyl(0xbafbe3, { opacity: 0.85 }), { parent: rotor, rot: [0, (i * Math.PI * 2) / 3, Math.PI / 2], pos: [0, 0, 0] }).geometry.translate(0, 0.28, 0);
    const box = mesh(new RoundedBoxGeometry(0.3, 0.22, 0.3, 3, 0.04), vinyl(0xd9a66b), { parent: root, pos: [0, -0.5, 0] });
    mesh(new THREE.BoxGeometry(0.31, 0.04, 0.05), vinyl(0x8a5a2a), { parent: box, outline: false });
    mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.2), inkMat(), { parent: root, outline: false, pos: [0, -0.32, 0] });
    return (t, s) => {
      rotor.rotation.y = t * 22 * s;
      root.position.y = Math.sin(t * 2) * 0.05;
      box.rotation.z = Math.sin(t * 2 - 0.8) * 0.12;
    };
  },

  snail(root) {
    const bodyMat = vinyl(0xffc9dc, { glowAmt: 0.22 });
    // Foot: a flattened capsule along Z whose vertices carry a travelling ripple.
    const footGeo = new THREE.CapsuleGeometry(0.15, 0.8, 12, 28, 40);
    footGeo.rotateX(Math.PI / 2); footGeo.scale(1.15, 0.75, 1);
    const base = footGeo.attributes.position.array.slice();
    const foot = mesh(footGeo, bodyMat, { parent: root, pos: [0, -0.3, 0.05] });
    const head = new THREE.Group(); root.add(head);
    mesh(new THREE.SphereGeometry(0.17, 28, 20), bodyMat, { parent: head, scale: [1, 0.95, 1] });
    eyes(head, { y: 0.0, z: 0.15, gap: 0.075, r: 0.045 });
    const stalks = [-1, 1].map((s) => {
      const g = new THREE.Group(); g.position.set(s * 0.07, 0.1, 0.03); g.rotation.z = -s * 0.2; head.add(g);
      mesh(new THREE.CylinderGeometry(0.02, 0.025, 0.22), bodyMat, { parent: g, pos: [0, 0.11, 0] });
      mesh(new THREE.SphereGeometry(0.045, 16, 12), bodyMat, { parent: g, pos: [0, 0.23, 0] });
      return g;
    });
    const shell = new THREE.Group(); root.add(shell);
    mesh(new THREE.SphereGeometry(0.4, 48, 32), vinyl(0xff8fb8, { coat: 1, glowAmt: 0.16 }), { parent: shell, scale: [0.62, 1, 1] });
    const spiral = (side) => taperTube((t) => { const a = t * Math.PI * 4.2, r = 0.34 * (1 - t) + 0.02;
      return new THREE.Vector3(side * (0.25 * Math.sqrt(1 - (r / 0.4) ** 2) + 0.005), Math.sin(a) * r, Math.cos(a) * r); }, () => 0.022, 160, 10);
    const groove = vinyl(0xb8416f);
    for (const side of [-1, 1]) mesh(spiral(side), groove, { parent: shell, outline: false });

    const pos = footGeo.attributes.position;
    // wave travels tail (-Z) to head (+Z): phase = k*z - w*t
    const K = 8, AMP = 0.022;
    const wave = (z, t) => Math.sin(K * z - t);
    return (t, s) => {
      const w = t * 4.5 * s;
      for (let i = 0; i < pos.count; i++) {
        const x = base[i * 3], y = base[i * 3 + 1], z = base[i * 3 + 2];
        const h = wave(z, w);
        const low = y < 0 ? 1 : 0.35;                 // sole ripples most, back a little
        pos.setY(i, y + h * AMP * low);
        pos.setZ(i, z + Math.cos(K * z - w) * 0.012);  // bunch and stretch along the foot
        pos.setX(i, x * (1 + h * 0.04));
      }
      pos.needsUpdate = true; footGeo.computeVertexNormals();
      // head rides the front of the wave and leans into each push
      const hw = wave(0.55, w);
      head.position.set(0, -0.2 + hw * 0.015, 0.52 + Math.cos(K * 0.55 - w) * 0.02);
      head.rotation.x = -hw * 0.06;
      // shell sits on the back: small bob and a slow side-to-side settle, no spinning
      shell.position.set(0, 0.05 + wave(-0.1, w) * 0.012, -0.12);
      shell.rotation.z = Math.sin(t * 0.9) * 0.04;
      // eye stalks sway on their own and sometimes pull in
      stalks.forEach((g, i) => {
        g.rotation.x = Math.sin(t * 1.7 + i * 1.3) * 0.22;
        const pull = Math.max(0, Math.sin(t * 0.5 + i * 2)) ** 12;
        g.scale.y = 1 - pull * 0.6;
      });
    };
  },

  crystal(root) {
    const pts = [[0, 0.8], [0.3, 0.35], [0.32, -0.35], [0, -0.72]];
    const geo = new THREE.LatheGeometry([...pts].reverse().map(([x, y]) => new THREE.Vector2(x, y)), 6);
    const cMat = new THREE.MeshPhysicalMaterial({ color: 0x7cc4ff, roughness: 0.05, metalness: 0, clearcoat: 1, iridescence: 1, iridescenceIOR: 1.6,
      emissive: 0x5aa8ff, emissiveIntensity: 0.45, flatShading: true, transparent: true, opacity: 0.9 });
    const gem = mesh(geo, cMat, { parent: root });
    const core = mesh(new THREE.OctahedronGeometry(0.12), glowMat(0xeaf6ff, 2.4), { parent: root, outline: false, scale: [1, 2, 1] });
    eyes(root, { y: 0.02, z: 0.3, gap: 0.09, r: 0.05 });
    const shards = [0, 1, 2].map((i) => {
      const piv = new THREE.Group(); root.add(piv);
      mesh(new THREE.OctahedronGeometry(0.07), cMat, { parent: piv, pos: [0.55, 0, 0], scale: [0.7, 1.4, 0.7] });
      piv.rotation.set(0.3 * i, (i * Math.PI * 2) / 3, 0.25);
      return piv;
    });
    return (t, s) => {
      gem.rotation.y = t * 0.6 * s;
      core.material.emissiveIntensity = 2 + Math.max(0, Math.sin(t * 2.5)) * 3;
      shards.forEach((p, i) => (p.rotation.y = t * 1.2 * s + (i * Math.PI * 2) / 3));
      root.position.y = Math.sin(t * 1.6) * 0.04;
    };
  },

  wisp(root) {
    const geo = lathe([[0, 0.55], [0.22, 0.52], [0.36, 0.38], [0.42, 0.1], [0.42, -0.3], [0.4, -0.45], [0.001, -0.45]], 64);
    const base = geo.attributes.position.array.slice();
    const mat = vinyl(0xe4ebfa, { glowAmt: 0.5, glow: 0xa9bcff, sheen: 1 });
    const body = mesh(geo, mat, { parent: root });
    eyes(body, { y: 0.18, z: 0.38, gap: 0.13, r: 0.07 });
    const pos = geo.attributes.position;
    return (t, s) => {
      for (let i = 0; i < pos.count; i++) {
        const x = base[i * 3], y = base[i * 3 + 1], z = base[i * 3 + 2];
        if (y < -0.1) {
          const a = Math.atan2(z, x), k = (-0.1 - y) / 0.35;
          pos.setY(i, y + Math.sin(a * 6 + t * 4 * s) * 0.07 * k);
          const sw = 1 + Math.sin(t * 2 + y * 6) * 0.05 * k;
          pos.setX(i, x * sw); pos.setZ(i, z * sw);
        }
      }
      pos.needsUpdate = true; geo.computeVertexNormals();
      root.position.y = Math.sin(t * 1.5) * 0.06;
      mat.emissiveIntensity = 0.45 + Math.sin(t * 1.5) * 0.25;
    };
  },

  comet(root) {
    const head = mesh(new THREE.SphereGeometry(0.34, 40, 28), vinyl(0xff9f43, { glowAmt: 0.9, glow: 0xff8a1f }), { parent: root, pos: [0, 0, 0.25] });
    eyes(head, { y: 0.05, z: 0.31, gap: 0.12, r: 0.065 });
    const light = new THREE.PointLight(0xffa14a, 2, 2); head.add(light);
    const N = 26, bits = [];
    const bitMat = [0xffc38a, 0xff9f43, 0xffe0a8].map((c) => glowMat(c, 2));
    for (let i = 0; i < N; i++) {
      const m = mesh(new THREE.SphereGeometry(1, 12, 10), bitMat[i % 3], { parent: root, outline: false });
      bits.push({ m, off: i / N, ang: Math.random() * 6.28, rad: 0.05 + Math.random() * 0.2 });
    }
    return (t, s) => {
      for (const b of bits) {
        const u = (b.off + t * 0.9 * s) % 1;
        b.m.position.set(Math.cos(b.ang + u * 3) * b.rad * (1 + u), Math.sin(b.ang + u * 3) * b.rad * (1 + u), 0.1 - u * 1.2);
        b.m.scale.setScalar(0.1 * (1 - u) + 0.01);
      }
      light.intensity = 1.8 + Math.sin(t * 7) * 0.3;
      head.rotation.z = Math.sin(t * 2) * 0.1;
    };
  },

  beetle(root) {
    const shellMat = vinyl(0x2ec4b6, { metal: 0.35, rough: 0.2, coat: 1 });
    const elytra = [-1, 1].map((s) => {
      const piv = new THREE.Group(); piv.position.set(s * 0.01, 0.06, 0.18); root.add(piv);
      const g = new THREE.SphereGeometry(0.4, 32, 24, s < 0 ? Math.PI : 0, Math.PI, 0, Math.PI / 2);
      mesh(g, shellMat, { parent: piv, pos: [0, 0, -0.22], scale: [0.85, 0.75, 1.15] });
      mesh(new THREE.SphereGeometry(0.06, 12, 10), vinyl(0xbaf5ef), { parent: piv, outline: false, pos: [s * 0.18, 0.2, -0.18], scale: [1, 0.4, 1] });
      return { piv, s };
    });
    mesh(new THREE.SphereGeometry(0.33, 28, 18), vinyl(0x136b63), { parent: root, pos: [0, 0.03, -0.04], scale: [0.95, 0.55, 1.2] });
    const head = mesh(new THREE.SphereGeometry(0.17, 28, 20), vinyl(0x1b7f75), { parent: root, pos: [0, 0.06, 0.42] });
    eyes(head, { y: 0.04, z: 0.14, gap: 0.07, r: 0.045, color: 0xe6fffc });
    for (const s of [-1, 1]) mesh(taperTube((t) => new THREE.Vector3(s * (0.05 + t * 0.14), 0.1 + t * 0.12, 0.12 + t * 0.14), () => 0.012, 20, 8), inkMat(), { parent: head, outline: false });
    const legs = [];
    for (const s of [-1, 1]) for (let i = 0; i < 3; i++) {
      const piv = new THREE.Group(); piv.position.set(s * 0.26, -0.04, 0.2 - i * 0.22); root.add(piv);
      mesh(new THREE.CapsuleGeometry(0.025, 0.24, 4, 8), inkMat(), { parent: piv, outline: false, pos: [s * 0.12, -0.08, 0], rot: [0, 0, s * 1.0] });
      legs.push({ piv, ph: i * 2.1 + (s > 0 ? Math.PI : 0) });
    }
    return (t, s) => {
      legs.forEach((l) => (l.piv.rotation.y = Math.sin(t * 12 * s + l.ph) * 0.4));
      const open = Math.max(0, Math.sin(t * 0.7)) ** 6 * 0.5;
      elytra.forEach(({ piv, s: side }) => (piv.rotation.z = -side * open));
      root.position.y = Math.abs(Math.sin(t * 12 * s)) * 0.015;
    };
  },

  slime(root) {
    const geo = lathe([[0, 0.5], [0.18, 0.47], [0.34, 0.33], [0.46, 0.05], [0.5, -0.22], [0.46, -0.3], [0.001, -0.3]], 64);
    const g = new THREE.Group(); g.position.y = -0.3; root.add(g);
    const body = mesh(geo, vinyl(0x7bd88f, { coat: 1, rough: 0.12, glowAmt: 0.3 }), { parent: g, pos: [0, 0.3, 0] });
    mesh(new THREE.SphereGeometry(0.18, 20, 14), glowMat(0xc8ffd2, 0.9), { parent: body, outline: false, pos: [0, 0, 0], scale: [1, 0.8, 1] });
    eyes(body, { y: 0.1, z: 0.42, gap: 0.13, r: 0.07 });
    mesh(new THREE.TorusGeometry(0.05, 0.014, 8, 20, Math.PI), inkMat(), { parent: body, outline: false, pos: [0, 0.0, 0.46], rot: [0, 0, Math.PI] });
    return (t, s) => {
      const p = Math.sin(t * 3 * s);
      g.scale.set(1 + p * 0.1, 1 - p * 0.13, 1 + p * 0.1);
      g.position.y = -0.3 + Math.max(0, -p) * 0.06;
    };
  },

  plane(root) {
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    const nose = V(0, 0, 0.8), tail = V(0, 0, -0.6), keel = V(0, -0.2, -0.45);
    const tris = [[nose, V(-0.7, 0.08, -0.6), tail], [nose, tail, V(0.7, 0.08, -0.6)], [nose, keel, tail], [nose, tail, keel]];
    const mk = (list, col) => {
      const g = new THREE.BufferGeometry().setFromPoints(list.flat()); g.computeVertexNormals();
      return mesh(g, vinyl(col, { side: THREE.DoubleSide, flat: true, rough: 0.6, coat: 0.3, glowAmt: 0.25 }), { parent: root, outline: false });
    };
    const wings = mk(tris.slice(0, 2), 0xf1f5ff);
    mk(tris.slice(2), 0xb9c6ea);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BufferGeometry().setFromPoints(tris.flat())), new THREE.LineBasicMaterial({ color: INK }));
    root.add(edge);
    eyes(root, { y: 0.07, z: 0.25, gap: 0.08, r: 0.04 });
    return (t) => {
      root.rotation.z = Math.sin(t * 1.1) * 0.25;
      root.rotation.x = Math.sin(t * 0.9) * 0.06;
      root.position.y = Math.sin(t * 1.1 + 1) * 0.06;
    };
  },

  puffer(root) {
    // Fan fin: a scalloped fan in the XY plane that opens toward +X from its hinge.
    const fan = (r, spread) => {
      const sh = new THREE.Shape(); sh.moveTo(0, 0);
      const n = 5;
      for (let i = 0; i <= n * 2; i++) {
        const a = -spread / 2 + (spread * i) / (n * 2), rr = i % 2 ? r : r * 0.82;
        sh.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
      }
      sh.closePath();
      return new THREE.ExtrudeGeometry(sh, { depth: 0.012, bevelEnabled: true, bevelSize: 0.008, bevelThickness: 0.006, bevelSegments: 2 }).translate(0, 0, -0.006);
    };
    const finMat = vinyl(0xf5b700, { side: THREE.DoubleSide, glowAmt: 0.25 });

    const body = new THREE.Group(); root.add(body);
    mesh(new THREE.SphereGeometry(0.42, 48, 32), vinyl(0xffd23f, { glowAmt: 0.18 }), { parent: body });
    mesh(new THREE.SphereGeometry(0.425, 48, 24, 0, Math.PI * 2, Math.PI * 0.6, Math.PI * 0.4), vinyl(0xfff3c4), { parent: body, outline: false });
    eyes(body, { y: 0.1, z: 0.37, gap: 0.16, r: 0.075 });
    mesh(new THREE.TorusGeometry(0.035, 0.014, 8, 16), vinyl(0xc97f00), { parent: body, outline: false, pos: [0, -0.07, 0.415] });

    // spikes stand along the surface normals and lengthen when it puffs up
    const spikes = [], ico = new THREE.IcosahedronGeometry(1, 2).attributes.position, seen = new Set();
    for (let i = 0; i < ico.count; i++) {
      const v = new THREE.Vector3().fromBufferAttribute(ico, i).normalize(), k = v.toArray().map((n) => n.toFixed(2)).join();
      if (seen.has(k) || v.z > 0.72 || (Math.abs(v.x) > 0.8 && Math.abs(v.y) < 0.4)) continue; seen.add(k);
      const piv = new THREE.Group(); piv.position.copy(v).multiplyScalar(0.41);
      piv.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v); body.add(piv);
      mesh(new THREE.ConeGeometry(0.026, 0.12, 8).translate(0, 0.06, 0), vinyl(0xe0a800), { parent: piv, outline: false });
      spikes.push(piv);
    }

    // pectoral fins: stick out just behind the eyes, angled back, flutter fast
    const pecs = [-1, 1].map((s) => {
      const hinge = new THREE.Group(); hinge.position.set(s * 0.38, -0.04, 0.02); hinge.scale.x = s; root.add(hinge);
      const flap = new THREE.Group(); hinge.add(flap);
      mesh(fan(0.2, 1.3), finMat, { parent: flap, outline: false, rot: [0, 0.55, 0] });
      return flap;
    });
    // tail fin: upright fan behind the body, sweeping side to side
    const tail = new THREE.Group(); tail.position.set(0, 0, -0.38); root.add(tail);
    mesh(new THREE.CylinderGeometry(0.06, 0.1, 0.14, 16).rotateX(Math.PI / 2), vinyl(0xffd23f), { parent: tail, pos: [0, 0, -0.05] });
    mesh(fan(0.26, 1.5), finMat, { parent: tail, outline: false, pos: [0, 0, -0.1], rot: [0, Math.PI / 2, 0] });
    // small dorsal fin, up and back
    const dorsal = new THREE.Group(); dorsal.position.set(0, 0.3, -0.24); dorsal.rotation.x = 1.25; root.add(dorsal);
    mesh(fan(0.13, 1.1), finMat, { parent: dorsal, outline: false, rot: [0, Math.PI / 2, 0] });

    return (t, s) => {
      // swim: tail sweeps, body yaws against it, fins flutter
      const sweep = Math.sin(t * 5 * s);
      tail.rotation.y = sweep * 0.45;
      root.rotation.y = -sweep * 0.06;
      pecs.forEach((f, i) => (f.rotation.y = Math.sin(t * 14 * s + i * Math.PI) * 0.45));
      dorsal.rotation.z = Math.sin(t * 5 * s + 1) * 0.15;
      root.position.y = Math.sin(t * 2) * 0.03;
      // every few seconds it puffs up, holds, and lets out
      const c = (t * 0.22) % 1;
      const puff = c < 0.12 ? c / 0.12 : c < 0.3 ? 1 : c < 0.45 ? 1 - (c - 0.3) / 0.15 : 0;
      const e = puff * puff * (3 - 2 * puff);
      body.scale.setScalar(0.88 + e * 0.22);
      spikes.forEach((p) => (p.scale.y = 0.35 + e * 0.9));
    };
  },

  owl(root) {
    const body = mesh(lathe([[0, 0.5], [0.24, 0.48], [0.38, 0.3], [0.42, 0], [0.38, -0.3], [0.22, -0.48], [0, -0.5]], 48),
      vinyl(0xc08552, { sheen: 0.8 }), { parent: root });
    mesh(new THREE.SphereGeometry(0.3, 28, 20), vinyl(0xf0d3a8, { sheen: 0.8 }), { parent: body, outline: false, pos: [0, -0.16, 0.2], scale: [0.95, 1.05, 0.72] });
    for (const s of [-1, 1]) mesh(new THREE.ConeGeometry(0.08, 0.24, 12), vinyl(0x9a6436), { parent: body, pos: [s * 0.24, 0.52, 0], rot: [0, 0, -s * 0.35] });
    const lids = [];
    for (const s of [-1, 1]) {
      const g = new THREE.Group(); g.position.set(s * 0.155, 0.16, 0.37); g.rotation.y = s * 0.28; body.add(g);
      mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.06, 32), vinyl(0xfff4e0), { parent: g, rot: [Math.PI / 2, 0, 0] });
      const pupil = new THREE.Group(); pupil.position.z = 0.03; g.add(pupil);
      eyes(pupil, { y: 0, z: 0.01, gap: 0, r: 0.08 });
      const lid = mesh(new THREE.SphereGeometry(0.14, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), vinyl(0x9a6436), { parent: g, outline: false, rot: [Math.PI / 2, 0, 0], pos: [0, 0, 0.01] });
      lids.push(lid);
    }
    mesh(new THREE.ConeGeometry(0.05, 0.12, 12), vinyl(0xf5a623), { parent: body, pos: [0, 0.02, 0.44], rot: [Math.PI / 2 + 0.5, 0, 0] });
    const wings = [-1, 1].map((s) => {
      const piv = new THREE.Group(); piv.position.set(s * 0.36, 0.1, -0.02); body.add(piv);
      mesh(new THREE.SphereGeometry(0.2, 20, 14), vinyl(0x9a6436), { parent: piv, pos: [s * 0.02, -0.18, 0], scale: [0.35, 1, 0.8] });
      return { piv, s };
    });
    return (t, s) => {
      const blink = (t % 4) > 3.82 ? 1 : 0;
      lids.forEach((l) => (l.scale.y = blink ? 1 : 0.05));
      body.rotation.y = Math.sin(t * 0.7) * 0.35;
      wings.forEach(({ piv, s: side }) => (piv.rotation.z = side * (0.1 + Math.max(0, Math.sin(t * 3 * s)) * 0.3)));
    };
  },

  cubebot(root) {
    const body = mesh(new RoundedBoxGeometry(0.8, 0.72, 0.7, 4, 0.12), vinyl(0xff6b35, { metal: 0.2, rough: 0.3 }), { parent: root });
    const screen = mesh(new RoundedBoxGeometry(0.58, 0.34, 0.06, 3, 0.05), inkMat(), { parent: body, outline: false, pos: [0, 0.06, 0.34] });
    const eyeMat = glowMat(0x9dffb0, 2.6);
    const eyeL = mesh(new RoundedBoxGeometry(0.11, 0.11, 0.03, 2, 0.02), eyeMat, { parent: screen, outline: false, pos: [-0.12, 0, 0.035] });
    const eyeR = mesh(new RoundedBoxGeometry(0.11, 0.11, 0.03, 2, 0.02), eyeMat, { parent: screen, outline: false, pos: [0.12, 0, 0.035] });
    for (let i = 0; i < 4; i++) mesh(new THREE.BoxGeometry(0.07, 0.03, 0.02), inkMat(), { parent: body, outline: false, pos: [-0.15 + i * 0.1, -0.2, 0.355] });
    mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.22), inkMat(), { parent: body, outline: false, pos: [0, 0.47, 0] });
    const bulbMat = glowMat(0xfff36b, 3);
    mesh(new THREE.SphereGeometry(0.06, 16, 12), bulbMat, { parent: body, pos: [0, 0.6, 0] });
    const thr = mesh(new THREE.CylinderGeometry(0.16, 0.24, 0.1, 24), vinyl(0x5a2a10), { parent: root, pos: [0, -0.42, 0] });
    const flame = mesh(new THREE.ConeGeometry(0.14, 0.26, 20), glowMat(0x7fd8ff, 2.5), { parent: thr, outline: false, pos: [0, -0.16, 0], rot: [Math.PI, 0, 0] });
    return (t, s) => {
      root.position.y = Math.sin(t * 2.5) * 0.04;
      bulbMat.emissiveIntensity = (Math.sin(t * 6 * s) > 0) ? 3.5 : 0.3;
      const bl = (t % 3.3) > 3.15 ? 0.15 : 1; eyeL.scale.y = eyeR.scale.y = bl;
      eyeL.position.x = -0.12 + Math.sin(t * 0.9) * 0.03; eyeR.position.x = 0.12 + Math.sin(t * 0.9) * 0.03;
      flame.scale.set(1, 0.8 + Math.random() * 0.4 * s, 1);
    };
  },

  mushroom(root) {
    const g = new THREE.Group(); g.position.y = -0.45; root.add(g);
    const stem = mesh(lathe([[0.001, 0.55], [0.18, 0.55], [0.2, 0.4], [0.24, 0.1], [0.22, 0], [0.001, 0]], 40), vinyl(0xf6ead2, { sheen: 0.8 }), { parent: g });
    eyes(stem, { y: 0.25, z: 0.2, gap: 0.08, r: 0.045 });
    const capGeo = lathe([[0.001, 0.95], [0.25, 0.92], [0.45, 0.78], [0.56, 0.58], [0.5, 0.5], [0.001, 0.52]], 48);
    const cap = mesh(capGeo, vinyl(0xd64545, { coat: 1, rough: 0.25 }), { parent: g });
    const dots = [[0, 0.95, 0.07], [0.3, 0.82, 0.8], [0.3, 0.82, 2.6], [0.3, 0.82, 4.4], [0.48, 0.65, 1.7], [0.48, 0.65, 3.5], [0.48, 0.65, 5.5]];
    for (const [r, y, a] of dots) {
      const d = mesh(new THREE.SphereGeometry(0.075, 16, 10), vinyl(0xffffff), { parent: cap, outline: false });
      const n = new THREE.Vector3(Math.sin(a) * r, y - 0.55, Math.cos(a) * r).normalize();
      d.position.set(Math.sin(a) * r, y, Math.cos(a) * r); d.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), n); d.scale.set(1, 0.35, 1);
    }
    return (t, s) => {
      const ph = (t * 1.1 * s) % 1, hop = Math.max(0, Math.sin(ph * Math.PI * 2));
      g.position.y = -0.45 + hop * 0.2;
      const sq = ph > 0.5 ? Math.sin((ph - 0.5) * Math.PI * 2) * 0.12 : 0;
      g.scale.set(1 + sq, 1 - sq, 1 + sq);
      cap.rotation.y = Math.sin(t * 2) * 0.2;
    };
  },

  // Seahorse, after how the animal swims: a rigid upright body, a fast-rippling dorsal
  // fin for thrust, pectoral fins that steer, buoyancy for up and down, and a prehensile
  // tail that hangs loose while swimming and coils tight to anchor while working.
  seahorse(root) {
    const orange = vinyl(0xff8a2a, { glowAmt: 0.16 }), belly = vinyl(0xffd25a, { glowAmt: 0.2 });
    const crestMat = vinyl(0xa64ad6, { glowAmt: 0.25 });
    const N = 110, LB = 0.78, LT = 0.62, neck = new THREE.Vector2(-0.05, 0.36);  // (z, y); snout faces +Z
    const NB = Math.round(N * LB / (LB + LT));
    const pts = Array.from({ length: N + 1 }, () => new THREE.Vector3());
    const heading = new Float32Array(N + 1);
    const rad = (u) => {               // u: 0 neck .. 1 tail tip
      const b = LB / (LB + LT);
      if (u < b) { const k = u / b; return 0.12 + Math.sin(Math.min(1, k * 1.25) * Math.PI) * 0.09 + (1 - k) * 0.02; }
      const k = (u - b) / (1 - b); return 0.1 * (1 - k) ** 1.15 + 0.022;
    };
    // body bend is fixed; only the tail's curl changes (c: -1 back .. +1 forward, tight)
    function spine(curl) {
      let z = neck.x, y = neck.y, th = -Math.PI / 2 - 0.42;
      const ds = (LB + LT) / N;
      for (let i = 0; i <= N; i++) {
        const sArc = i * ds; pts[i].set(0, y, z); heading[i] = th;
        const k = sArc < LB ? 1.05 : curl * 3.1 * (1 + ((sArc - LB) / LT) * 5);
        th += k * ds; z += Math.cos(th) * ds; y += Math.sin(th) * ds;
      }
    }
    const pointAt = (u) => { const f = u * N, i = Math.min(N - 1, Math.floor(f)); return pts[i].clone().lerp(pts[i + 1], f - i); };
    const bU = NB / N;
    // body: round section; tail: four-sided section, as in the real animal
    const buildBody = () => taperTube((u) => pointAt(u * bU), (u) => rad(u * bU), NB, 18);
    const buildTail = () => taperTube((u) => pointAt(bU + u * (1 - bU)), (u) => rad(bU + u * (1 - bU)) * 1.05, N - NB, 4);

    spine(0.2);
    const body = mesh(buildBody(), orange, { parent: root });
    const tail = mesh(buildTail(), orange, { parent: root });
    const tailOutline = tail.children[0];

    const frame = (u) => { const p = pointAt(u), i = Math.round(u * N), th = heading[i];
      return { p, th, fz: -Math.sin(th), fy: Math.cos(th) }; };   // (fz, fy) points to the belly side

    // belly plates and the purple frill on the neck: fixed to the rigid body, placed once
    for (let i = 0; i < 7; i++) {
      const u = bU * (0.14 + i * 0.105), f = frame(u), r = rad(u);
      mesh(new THREE.SphereGeometry(1, 20, 12), belly, { parent: root, outline: false,
        pos: [0, f.p.y + f.fy * r * 0.58, f.p.z + f.fz * r * 0.58], rot: [-(f.th + Math.PI / 2), 0, 0], scale: [r * 0.86, 0.062, r * 0.5] });
    }
    for (let i = 0; i < 3; i++) {
      const u = bU * (0.02 + i * 0.09), f = frame(u), r = rad(u);
      mesh(new THREE.SphereGeometry(1, 18, 12), crestMat, { parent: root,
        pos: [0, f.p.y - f.fy * r * 0.95, f.p.z - f.fz * r * 0.95], scale: [0.022, 0.06 * (1 - i * 0.12), 0.06 * (1 - i * 0.12)] });
    }

    // dorsal fin: a membrane on the lower back whose rays ripple side to side in a fast travelling wave
    const FC = 26, FR = 5;                 // columns along the back, rows from base to edge
    const finGeo = new THREE.BufferGeometry();
    const finPos = new Float32Array(FC * FR * 3), finCol = new Float32Array(FC * FR * 3), idx = [];
    const cBase = new THREE.Color(0x8a3cc8), cEdge = new THREE.Color(0xcf8cff);
    for (let c = 0; c < FC; c++) for (let r = 0; r < FR; r++) {
      const k = c * FR + r, col = cBase.clone().lerp(cEdge, r / (FR - 1));
      finCol.set([col.r, col.g, col.b], k * 3);
      if (c < FC - 1 && r < FR - 1) idx.push(k, k + FR, k + 1, k + 1, k + FR, k + FR + 1);
    }
    finGeo.setAttribute('position', new THREE.BufferAttribute(finPos, 3));
    finGeo.setAttribute('color', new THREE.BufferAttribute(finCol, 3));
    finGeo.setIndex(idx);
    const finMat = new THREE.MeshPhysicalMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.92,
      roughness: 0.3, clearcoat: 0.6, emissive: 0x6a2aa0, emissiveIntensity: 0.35 });
    const fin = new THREE.Mesh(finGeo, finMat); root.add(fin);
    const finBase = [];
    for (let c = 0; c < FC; c++) {
      const q = c / (FC - 1), u = bU * (0.46 + q * 0.36), f = frame(u), r = rad(u);
      finBase.push({ y: f.p.y - f.fy * r * 0.9, z: f.p.z - f.fz * r * 0.9, ny: -f.fy, nz: -f.fz, h: 0.27 * Math.sin(Math.PI * (0.15 + q * 0.85)) ** 0.7 });
    }
    function rippleFin(t, power) {
      // wave runs head to tail along the fin; amplitude grows toward the free edge
      const w = t * Math.PI * 2 * (6 + power * 4);
      for (let c = 0; c < FC; c++) for (let r = 0; r < FR; r++) {
        const b = finBase[c], v = r / (FR - 1), k = (c * FR + r) * 3;
        const h = b.h * v * (0.92 + 0.08 * power);
        finPos[k] = Math.sin(c * 0.9 - w) * 0.035 * v * (0.6 + power * 0.6);
        finPos[k + 1] = b.y + b.ny * h; finPos[k + 2] = b.z + b.nz * h;
      }
      finGeo.attributes.position.needsUpdate = true; finGeo.computeVertexNormals();
    }

    // head: tube snout, side eyes, still coronet
    const head = new THREE.Group(); root.add(head);
    const n0 = frame(0); head.position.set(0, n0.p.y + 0.13, n0.p.z + 0.06); head.rotation.x = 0.05;
    mesh(new THREE.SphereGeometry(0.17, 32, 24), orange, { parent: head, scale: [0.9, 1, 1.05] });
    mesh(new THREE.CylinderGeometry(0.055, 0.065, 0.26, 20).rotateX(Math.PI / 2), orange, { parent: head, pos: [0, -0.02, 0.24] });
    mesh(new THREE.TorusGeometry(0.05, 0.018, 10, 24), vinyl(0xe06a12), { parent: head, outline: false, pos: [0, -0.02, 0.37] });
    for (const sd of [-1, 1]) {
      const e = new THREE.Group(); e.position.set(sd * 0.13, 0.04, 0.05); e.rotation.y = sd * (Math.PI / 2 - 0.35); head.add(e);
      eyes(e, { y: 0, z: 0, gap: 0, r: 0.055 });
    }
    [0, 1, 2].forEach((i) => mesh(new THREE.SphereGeometry(1, 18, 12), crestMat, { parent: head,
      pos: [0, 0.17 - i * 0.05, -0.08 - i * 0.07], scale: [0.022, 0.06, 0.06] }));
    // pectoral fins just behind the head, one per side
    const pecs = [-1, 1].map((sd) => {
      const hinge = new THREE.Group(); hinge.position.set(sd * 0.12, -0.08, -0.08); hinge.scale.x = sd; head.add(hinge);
      const flap = new THREE.Group(); hinge.add(flap);
      mesh(fanGeo(0.11, 1.2, 4), vinyl(0xffb066, { side: THREE.DoubleSide, glowAmt: 0.25 }), { parent: flap, outline: false, rot: [0, 0.5, Math.PI] });
      return { flap, sd };
    });

    let curl = 0.2, lean = 0;
    // ctx: busy 0..1 (working, so anchored), turn (rad/s, + = left), climb (units/s)
    return (t, s, ctx = {}) => {
      const busy = ctx.busy ?? 0, turn = ctx.turn ?? 0, climb = ctx.climb ?? 0, dt = ctx.dt ?? 1 / 60;
      // tail: anchored = tight forward coil; swimming = loose, flexing gently forward and back
      const target = busy > 0.5 ? 1 : 0.15 + Math.sin(t * 0.7) * 0.45;
      curl += (target - curl) * Math.min(1, dt * (busy > 0.5 ? 2.5 : 1.2));
      spine(curl);
      const g = buildTail(); tail.geometry.dispose(); tail.geometry = g; tailOutline.geometry = g;

      // thrust: dorsal fin ripples hard while swimming, idles while anchored
      rippleFin(t, 1 - busy * 0.75);

      // steering: the pectoral on the outside of the turn beats harder
      pecs.forEach(({ flap, sd }) => {
        const amp = 0.45 + Math.max(-0.3, Math.min(0.4, sd * turn * 0.25));
        flap.rotation.y = Math.sin(t * 22 + (sd > 0 ? 0 : Math.PI)) * amp;
      });
      // stability: lean a little into a turn and settle back; never roll over
      lean += (Math.max(-0.25, Math.min(0.25, -turn * 0.12)) - lean) * Math.min(1, dt * 3);
      root.rotation.z = lean;

      // buoyancy: slow rise and sink, nose tips with the climb, body stays upright
      root.position.y = Math.sin(t * 0.55) * 0.05 + Math.sin(t * 1.4) * 0.012;
      root.rotation.x = Math.max(-0.25, Math.min(0.25, -climb * 0.25)) + Math.sin(t * 0.5) * 0.03;
    };
  },
};

// ---------------------------------------------------------------- public API

// Build one agent. Pass { halo: true, harness } to add a ring in the harness colour.
const _wq = new THREE.Quaternion(), _wp = new THREE.Vector3(), _ev = new THREE.Euler();
export function createAgent(name, { harness = 'other', halo = false } = {}) {
  if (!BUILD[name]) throw new Error(`unknown agent glyph: ${name}`);
  const agent = new THREE.Group(); agent.name = `agent-${name}`;
  const fit = new THREE.Group(), centre = new THREE.Group(), body = new THREE.Group();
  agent.add(fit); fit.add(centre); centre.add(body);
  const anim = BUILD[name](body);

  // fit to ~1.6 units, centred on the pivot (measured at rest)
  anim(0, 1); body.position.set(0, 0, 0); body.rotation.set(0, 0, 0); body.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(body), size = box.getSize(new THREE.Vector3());
  fit.scale.setScalar(1.6 / Math.max(size.x, size.y, size.z));
  centre.position.copy(box.getCenter(new THREE.Vector3())).negate();

  let ring;
  if (halo) {
    const col = HARNESS_RING[harness] ?? HARNESS_RING.other;
    ring = new THREE.Mesh(new THREE.TorusGeometry(0.72, 0.035, 12, 64),
      new THREE.MeshBasicMaterial({ color: col, toneMapped: false, transparent: true, opacity: 0.95 }));
    ring.rotation.x = Math.PI / 2; ring.position.y = -0.95; agent.add(ring);
  }

  let t = Math.random() * 10, prev = null;
  const smooth = { turn: 0, climb: 0 };
  agent.userData = {
    glyph: name, harness, turnRate: 0,
    // dt in seconds; busy 0..1 speeds the motion up (working rather than travelling)
    update(dt, { busy = 0 } = {}) {
      t += dt;
      // turn rate and climb rate, read from how the graph moved the agent since last frame
      agent.getWorldQuaternion(_wq); agent.getWorldPosition(_wp);
      _ev.setFromQuaternion(_wq, 'YXZ');
      let turn = 0, climb = 0;
      if (prev && dt > 0) {
        let dy = _ev.y - prev.yaw; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
        turn = dy / dt; climb = (_wp.y - prev.y) / dt;
      }
      prev = { yaw: _ev.y, y: _wp.y };
      smooth.turn += (turn - smooth.turn) * Math.min(1, dt * 4);
      smooth.climb += (climb - smooth.climb) * Math.min(1, dt * 4);
      agent.userData.turnRate = smooth.turn;   // read by orientAgent, which leans a flyer into its turn
      anim(t, 1 + busy * 1.5, { busy, turn: smooth.turn, climb: smooth.climb, dt });
      if (ring) { ring.rotation.z += dt * (0.6 + busy * 3); ring.material.opacity = 0.75 + Math.sin(t * 3) * 0.2 + busy * 0.05; }
    },
  };
  return agent;
}

const _q = new THREE.Quaternion(), _e = new THREE.Euler(0, 0, 0, 'YXZ');
// The characters that walk, creep or hop keep upright in a turn; the seahorse leans by itself. The rest fly or swim and
// lean into a turn, as a body moving through air or water does.
const UPRIGHT = new Set(['snail', 'beetle', 'slime', 'mushroom', 'seahorse']);
const LEAN = 0.09, MOST_LEAN = 0.35;   // radians of lean for each radian a second of turn, and the most
// Turn the agent's +Z toward a direction, upright, smoothing over a few frames.
// Built from yaw and a small pitch, so facing straight backward never flips.
// `smoothing` is the share of the way turned in a frame at 60 frames a second; given the frame's `dt` in seconds, the
// share is that of the time that passed, so a figure turns at one pace whatever the frame rate.
export function orientAgent(agent, direction, smoothing = 0.2, dt = null) {
  const h = Math.hypot(direction.x, direction.z);
  if (h < 1e-6) return;
  const lean = UPRIGHT.has(agent.userData.glyph) ? 0
    : Math.max(-MOST_LEAN, Math.min(MOST_LEAN, -(agent.userData.turnRate || 0) * LEAN));
  _e.set(-Math.atan2(direction.y, h) * 0.35, Math.atan2(direction.x, direction.z), lean);
  _q.setFromEuler(_e);
  agent.quaternion.slerp(_q, dt === null ? smoothing : 1 - Math.pow(1 - smoothing, Math.max(0, dt) * 60));
}
// Place the agent at u (0..1) along a THREE.Curve. reverse=true walks it from end to start.
export function placeAgentOnCurve(agent, curve, u, { reverse = false, lift = 0 } = {}) {
  const k = Math.min(Math.max(reverse ? 1 - u : u, 0), 1);
  agent.position.copy(curve.getPointAt(k)); agent.position.y += lift;
  const tan = curve.getTangentAt(k); if (reverse) tan.negate();
  orientAgent(agent, tan);
}
