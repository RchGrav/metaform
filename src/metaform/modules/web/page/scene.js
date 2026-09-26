/* The 3D view's drawing, VIEW-005 and VIEW-010: every vertex kind is one instanced mesh and every edge style one line
 * batch, so a frame costs the same few draw calls whatever the size of the map. The layout runs in a worker.
 * Labels are drawn only for the nearest elements, up to a fixed budget per frame. */
import * as THREE from '/vendor/three/three.module.min.js';

const KINDS = ['el', 'purpose', 'encounter', 'sub'];
const SIZE = {purpose: 1.3, encounter: 1.0, sub: 0.7};
const LABELS = 80;          // the most element labels drawn at once
const CURVED = 20000;       // above this many fibers, they are drawn straight
const SEGMENTS = 6;         // pieces of each curved fiber

export class Scene {
  constructor(host, {colors, onPick, onHover, reduced}) {
    this.host = host; this.colors = colors; this.onPick = onPick; this.onHover = onHover; this.reduced = reduced;
    this.renderer = new THREE.WebGLRenderer({antialias: true});
    this.renderer.setPixelRatio(Math.min(2, devicePixelRatio || 1));
    this.renderer.info.autoReset = false;
    host.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(colors.ground);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1e7);
    this.target = new THREE.Vector3();
    this.orbit = {radius: 400, theta: 0.6, phi: 1.2};
    this.nodes = []; this.links = []; this.index = new Map(); this.selected = null; this.neighbors = new Set();
    this.joinOfSelected = new Set(); this.members = {el: [], purpose: [], encounter: [], sub: []};
    this.meshes = {}; this.lines = {}; this.glow = null; this.dirty = true; this.flight = null; this.fitted = false;
    this.labels = document.createElement('div'); this.labels.className = 'labels3d';
    host.append(this.labels);
    this.tags = new Map(); this.chosen = []; this.lastChoice = 0;
    this.worker = new Worker('/page/layout.js');
    this.worker.onmessage = ({data}) => { if (data.type === 'positions') this.positioned(data); };
    this.raycaster = new THREE.Raycaster();
    this.wire();
    this.resize();
    addEventListener('resize', () => this.resize());
    requestAnimationFrame(() => this.frame());
  }

  /* ---------- data ---------- */
  /* Add what arrived. The batches are rebuilt only when the map has doubled since the last build, and once more
   * when the last page is in, so a map arriving in hundreds of pages is rebuilt a handful of times, VIEW-010. */
  update(data, final = false) {
    const ids = new Set(data.nodes.map(node => node.id));
    if (!this.nodes.length || this.nodes.some(node => !ids.has(node.id))) {  // a changed view starts a new layout
      this.worker.postMessage({type: 'reset'}); this.nodes = []; this.links = []; this.index = new Map(); this.fitted = false;
      this.built = 0; this.chosen = []; this.tags.clear(); this.labels.replaceChildren();
    }
    const fresh = data.nodes.filter(node => !this.index.has(node.id));
    for (const node of fresh) { this.index.set(node.id, this.nodes.length); this.nodes.push({...node, x: 0, y: 0, z: 0}); }
    const linkKey = link => `${link.k}|${link.source}|${link.target}`;
    const had = new Set(this.links.map(linkKey));
    const newLinks = data.links.filter(link => !had.has(linkKey(link)));
    this.links.push(...newLinks);
    for (const node of data.nodes) { const own = this.nodes[this.index.get(node.id)]; if (own) Object.assign(own, node, {x: own.x, y: own.y, z: own.z}); }
    this.worker.postMessage({type: 'add', stride: this.reduced() ? 25 : 1,
      nodes: fresh.map(node => ({id: node.id, t: node.t})), links: newLinks.map(({source, target, k}) => ({source, target, k}))});
    if (final || !this.built || this.nodes.length >= this.built * 2) this.build();
  }

  /* The worker's newest positions wait for the next frame; on a large map they are applied at most four times a
   * second, so settling never starves orbiting, VIEW-010. */
  positioned(data) { this.pending = data; }

  applyPositions() {
    const large = this.nodes.length > 20000;
    if (!this.pending || (large && !this.pending.settled && performance.now() - (this.applied || 0) < 250)) return;
    const {positions, count, settled} = this.pending;
    this.pending = null; this.applied = performance.now();
    for (let i = 0; i < count && i < this.nodes.length; i++) {
      const node = this.nodes[i];
      node.x = positions[i * 3]; node.y = positions[i * 3 + 1]; node.z = positions[i * 3 + 2];
    }
    this.place();
    if (!this.fitted && (settled || count > 0)) { this.fitted = settled; if (settled) this.fit(false); }
  }

  /* ---------- building the batches ---------- */
  build() {
    this.built = this.nodes.length;
    for (const object of [...Object.values(this.meshes), ...Object.values(this.lines), this.glow]) {
      if (!object) continue;
      this.scene.remove(object); object.geometry.dispose(); object.material.dispose();
    }
    this.meshes = {}; this.lines = {};
    this.members = {};
    const round = new THREE.IcosahedronGeometry(1, 1), small = new THREE.IcosahedronGeometry(1, 0);  // 80 and 20 triangles
    for (const kind of KINDS) {
      const members = this.nodes.filter(node => node.t === kind);
      this.members[kind] = members;
      const mesh = new THREE.InstancedMesh(kind === 'el' ? round : small, new THREE.MeshBasicMaterial({transparent: kind !== 'el', opacity: kind === 'el' ? 1 : 0.85}), Math.max(1, members.length));
      mesh.count = members.length;
      mesh.userData.kind = kind;
      mesh.frustumCulled = false;
      this.meshes[kind] = mesh; this.scene.add(mesh);
    }
    const elements = this.members.el;
    const glowGeometry = new THREE.BufferGeometry();
    glowGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(elements.length * 3), 3));
    glowGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(elements.length * 3), 3));
    this.glow = new THREE.Points(glowGeometry, new THREE.PointsMaterial({size: 26, map: glowTexture(), vertexColors: true, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true, opacity: 0.55}));
    this.glow.frustumCulled = false;
    this.scene.add(this.glow);
    const fibers = this.links.filter(link => link.k === 'face' || link.k === 'tie');
    this.curved = fibers.length <= CURVED;
    const styles = {
      fiber: {links: fibers, pieces: this.curved ? SEGMENTS : 1, material: new THREE.LineBasicMaterial({vertexColors: true, transparent: true, opacity: 0.6, depthWrite: false, blending: THREE.AdditiveBlending})},
      tree: {links: this.links.filter(link => link.k === 'tree'), pieces: 1, material: new THREE.LineDashedMaterial({color: this.colors.tree, dashSize: 3, gapSize: 3, transparent: true, opacity: 0.8})},
      sub: {links: this.links.filter(link => link.k === 'sub'), pieces: 1, material: new THREE.LineBasicMaterial({vertexColors: true, transparent: true, opacity: 0.5})},
    };
    for (const [style, {links, pieces, material}] of Object.entries(styles)) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(links.length * pieces * 6), 3));
      geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(links.length * pieces * 6), 3));
      const line = new THREE.LineSegments(geometry, material);
      line.userData = {links, pieces, style};
      line.frustumCulled = false;
      this.lines[style] = line; this.scene.add(line);
    }
    const ties = fibers.filter(link => link.k === 'tie');
    const arrows = new THREE.InstancedMesh(new THREE.ConeGeometry(1.6, 5, 8), new THREE.MeshBasicMaterial({color: this.colors.signal}), Math.max(1, ties.length));
    arrows.count = ties.length; arrows.userData = {ties}; arrows.frustumCulled = false;
    this.meshes.arrow = arrows; this.scene.add(arrows);
    this.recolor();
    this.place();
  }

  /* ---------- colors and positions ---------- */
  recolor() {
    const color = new THREE.Color();
    for (const kind of KINDS) {
      const mesh = this.meshes[kind];
      this.members[kind].forEach((node, i) => { mesh.setColorAt(i, color.set(this.colors.node(node, this.selected, this.neighbors))); });
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
    const glowColors = this.glow.geometry.attributes.color;
    this.members.el.forEach((node, i) => { color.set(this.colors.node(node, this.selected, this.neighbors)); glowColors.setXYZ(i, color.r, color.g, color.b); });
    glowColors.needsUpdate = true;
    for (const line of Object.values(this.lines)) {
      const {links, pieces} = line.userData;
      const colors = line.geometry.attributes.color;
      links.forEach((link, i) => {
        color.set(this.colors.link(link));
        if (this.selected && link.k !== 'tree' && !this.touches(link)) color.multiplyScalar(0.35);
        for (let v = 0; v < pieces * 2; v++) colors.setXYZ(i * pieces * 2 + v, color.r, color.g, color.b);
      });
      colors.needsUpdate = true;
    }
    this.dirty = true;
  }

  touches(link) {
    return link.join ? this.joinOfSelected.has(link.join) : link.source === this.selected || link.target === this.selected;
  }

  place() {
    const matrix = new THREE.Matrix4(), scale = new THREE.Vector3(), quaternion = new THREE.Quaternion(), position = new THREE.Vector3();
    for (const kind of KINDS) {
      const mesh = this.meshes[kind];
      this.members[kind].forEach((node, i) => {
        const size = kind === 'el' ? this.radius(node) : SIZE[kind];
        matrix.compose(position.set(node.x, node.y, node.z), quaternion.identity(), scale.setScalar(size));
        mesh.setMatrixAt(i, matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
    const glowPositions = this.glow.geometry.attributes.position;
    this.members.el.forEach((node, i) => glowPositions.setXYZ(i, node.x, node.y, node.z));
    glowPositions.needsUpdate = true;
    const a = new THREE.Vector3(), b = new THREE.Vector3(), control = new THREE.Vector3(), point = new THREE.Vector3();
    const previous = new THREE.Vector3(), bend = new THREE.Vector3();
    for (const line of Object.values(this.lines)) {
      const {links, pieces} = line.userData;
      const positions = line.geometry.attributes.position;
      links.forEach((link, i) => {
        const from = this.nodes[this.index.get(link.source)], to = this.nodes[this.index.get(link.target)];
        a.set(from.x, from.y, from.z); b.set(to.x, to.y, to.z);
        if (pieces === 1) { positions.setXYZ(i * 2, a.x, a.y, a.z); positions.setXYZ(i * 2 + 1, b.x, b.y, b.z); return; }
        // A fiber bows away from the straight line by a fifth of its length, like the prototype's curvature.
        control.copy(a).add(b).multiplyScalar(0.5);
        bend.subVectors(b, a).cross(this.camera.up);
        if (bend.lengthSq() < 1e-9) bend.set(1, 0, 0);
        control.add(bend.normalize().multiplyScalar(a.distanceTo(b) * 0.18));
        previous.copy(a);
        for (let s = 1; s <= pieces; s++) {
          const t = s / pieces, u = 1 - t;
          point.set(u * u * a.x + 2 * u * t * control.x + t * t * b.x, u * u * a.y + 2 * u * t * control.y + t * t * b.y,
            u * u * a.z + 2 * u * t * control.z + t * t * b.z);
          const at = (i * pieces + s - 1) * 2;
          positions.setXYZ(at, previous.x, previous.y, previous.z); positions.setXYZ(at + 1, point.x, point.y, point.z);
          previous.copy(point);
        }
      });
      positions.needsUpdate = true;
      if (line.userData.style === 'tree') line.computeLineDistances();
    }
    const arrows = this.meshes.arrow, up = new THREE.Vector3(0, 1, 0), direction = new THREE.Vector3();
    arrows.userData.ties.forEach((link, i) => {
      const from = this.nodes[this.index.get(link.source)], to = this.nodes[this.index.get(link.target)];
      direction.set(to.x - from.x, to.y - from.y, to.z - from.z);
      const length = direction.length() || 1;
      direction.divideScalar(length);
      position.set(to.x, to.y, to.z).addScaledVector(direction, -Math.min(length * 0.5, 9));
      matrix.compose(position, quaternion.setFromUnitVectors(up, direction), scale.setScalar(1));
      arrows.setMatrixAt(i, matrix);
    });
    arrows.instanceMatrix.needsUpdate = true;
    this.dirty = true;
  }

  radius(node) { return 2.2 + Math.min(6, Math.sqrt(node.joins || 0) * 1.4) + (node.role === 'DE' ? 2.5 : node.role === 'VE' ? 1.5 : 0); }

  /* ---------- selection, camera ---------- */
  select(id, fly) {
    this.selected = id;
    const node = this.nodes[this.index.get(id)];
    this.neighbors = this.colors.neighbors(id);
    this.joinOfSelected = this.colors.joinsOf(id);
    this.recolor();
    if (fly && node) this.flyTo(new THREE.Vector3(node.x, node.y, node.z), 90);
  }

  flyTo(point, radius, animate = true) {
    const from = {target: this.target.clone(), radius: this.orbit.radius};
    if (!animate || this.reduced()) { this.target.copy(point); this.orbit.radius = radius; this.flight = null; this.dirty = true; return; }
    this.flight = {from, to: {target: point.clone(), radius}, start: performance.now(), duration: 900};
  }

  fit(animate = true) {
    if (!this.nodes.length) return;
    const box = new THREE.Box3();
    for (const node of this.nodes) box.expandByPoint(new THREE.Vector3(node.x, node.y, node.z));
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(60, sphere.radius / Math.sin((this.camera.fov * Math.PI / 180) / 2) * 1.1);
    this.flyTo(sphere.center, radius, animate);
  }

  pause() { this.worker.postMessage({type: 'pause'}); }
  resume() { this.worker.postMessage({type: 'resume'}); }
  relayout() { this.fitted = false; this.worker.postMessage({type: 'relayout'}); }

  resize() {
    const box = this.host.getBoundingClientRect();
    this.camera.aspect = Math.max(1, box.width) / Math.max(1, box.height);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(Math.max(1, box.width), Math.max(1, box.height));
    this.dirty = true;
  }

  wire() {
    const canvas = this.renderer.domElement;
    let drag = null;
    canvas.addEventListener('pointerdown', event => { drag = {x: event.clientX, y: event.clientY, pan: event.button === 2 || event.shiftKey, moved: false}; this.flight = null; });
    canvas.addEventListener('contextmenu', event => event.preventDefault());
    addEventListener('pointerup', event => {
      if (drag && !drag.moved && event.target === canvas) { const node = this.pick(event); if (node) this.onPick(node); }
      drag = null;
    });
    canvas.addEventListener('pointermove', event => {
      if (!drag) return this.hover(event);
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      drag.moved = true; drag.x = event.clientX; drag.y = event.clientY;
      if (drag.pan) {
        const scale = this.orbit.radius / this.host.clientHeight;
        const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 0), up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 1);
        this.target.addScaledVector(right, -dx * scale).addScaledVector(up, dy * scale);
      } else {
        this.orbit.theta -= dx * 0.006;
        this.orbit.phi = Math.min(Math.PI - 0.05, Math.max(0.05, this.orbit.phi - dy * 0.006));
      }
      this.dirty = true;
    });
    canvas.addEventListener('wheel', event => { event.preventDefault(); this.flight = null; this.orbit.radius *= event.deltaY > 0 ? 1.12 : 0.89; this.dirty = true; }, {passive: false});
  }

  pick(event) {
    const box = this.renderer.domElement.getBoundingClientRect();
    const pointer = new THREE.Vector2(((event.clientX - box.left) / box.width) * 2 - 1, -((event.clientY - box.top) / box.height) * 2 + 1);
    this.raycaster.setFromCamera(pointer, this.camera);
    const hits = this.raycaster.intersectObjects(KINDS.map(kind => this.meshes[kind]), false);
    if (!hits.length) return null;
    return this.members[hits[0].object.userData.kind][hits[0].instanceId] || null;
  }

  hover(event) {
    const now = performance.now();
    if (now - (this.hovered || 0) < 80) return;
    this.hovered = now;
    this.onHover(this.pick(event), event);
  }

  /* ---------- frames ---------- */
  frame() {
    requestAnimationFrame(() => this.frame());
    this.applyPositions();
    if (this.flight) {
      const {from, to, start, duration} = this.flight;
      const t = Math.min(1, (performance.now() - start) / duration), k = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      this.target.lerpVectors(from.target, to.target, k);
      this.orbit.radius = from.radius + (to.radius - from.radius) * k;
      if (t >= 1) this.flight = null;
      this.dirty = true;
    }
    if (!this.dirty) return this.placeLabels(false);
    const {radius, theta, phi} = this.orbit;
    this.camera.position.set(this.target.x + radius * Math.sin(phi) * Math.sin(theta), this.target.y + radius * Math.cos(phi),
      this.target.z + radius * Math.sin(phi) * Math.cos(theta));
    this.camera.lookAt(this.target);
    this.camera.updateMatrixWorld();
    this.renderer.info.reset();
    this.renderer.render(this.scene, this.camera);
    this.dirty = false;
    this.placeLabels(true);
  }

  /* Up to LABELS element labels: the selected element and its joined ones first, then the nearest in view. */
  placeLabels(moved) {
    const now = performance.now();
    if (now - this.lastChoice > 250) {
      this.lastChoice = now;
      const view = new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(this.camera.projectionMatrix, this.camera.matrixWorldInverse));
      const point = new THREE.Vector3();
      const inView = [];
      for (const node of this.members?.el || []) {
        point.set(node.x, node.y, node.z);
        if (view.containsPoint(point)) inView.push([node, point.distanceToSquared(this.camera.position)]);
      }
      inView.sort((a, b) => a[1] - b[1]);
      const first = inView.filter(([node]) => node.id === this.selected || this.neighbors.has(node.id));
      const rest = inView.filter(([node]) => !(node.id === this.selected || this.neighbors.has(node.id)));
      this.chosen = [...first, ...rest].slice(0, LABELS).map(([node]) => node);
      const keep = new Set(this.chosen.map(node => node.id));
      for (const [id, tag] of this.tags) if (!keep.has(id)) { tag.remove(); this.tags.delete(id); }  // at most LABELS exist
      moved = true;
    }
    if (!moved) return;
    const box = this.renderer.domElement.getBoundingClientRect(), point = new THREE.Vector3(), rim = new THREE.Vector3();
    const up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1);
    for (const node of this.chosen) {
      let tag = this.tags.get(node.id);
      if (!tag) { tag = document.createElement('span'); tag.textContent = node.name; this.labels.append(tag); this.tags.set(node.id, tag); }
      point.set(node.x, node.y, node.z).project(this.camera);
      rim.set(node.x, node.y, node.z).addScaledVector(up, this.radius(node)).project(this.camera);
      tag.hidden = point.z > 1;
      tag.style.left = ((point.x + 1) / 2 * box.width) + 'px';
      tag.style.top = ((1 - rim.y) / 2 * box.height) + 'px';  // above the sphere's rim, so a label never sits on it
      tag.className = node.id === this.selected ? 'sel' : this.neighbors.has(node.id) ? 'near' : this.selected ? 'dim' : '';
    }
  }

  labelled() { return [...this.tags.keys()]; }

  drawn() {
    const count = style => this.lines[style]?.userData.links.length || 0;
    return {calls: this.renderer.info.render.calls, elements: this.meshes.el?.count || 0, purposes: this.meshes.purpose?.count || 0,
      encounters: this.meshes.encounter?.count || 0, subtypes: this.meshes.sub?.count || 0,
      faces: (this.lines.fiber?.userData.links.filter(link => link.k === 'face').length || 0) / 3,
      ties: this.meshes.arrow?.count || 0, tree: count('tree'), labels: this.labels.childElementCount};
  }
}

let glow = null;
function glowTexture() {
  if (glow) return glow;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, 'rgba(255,255,255,1)'); gradient.addColorStop(0.25, 'rgba(255,255,255,0.45)'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
  context.fillStyle = gradient; context.fillRect(0, 0, 64, 64);
  glow = new THREE.CanvasTexture(canvas);
  return glow;
}
