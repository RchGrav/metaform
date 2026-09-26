/* The 3D view's force layout, off the page's own thread, VIEW-010: d3-force-3d, fed as pages of the map arrive.
 * Positions already settled are kept when more of the map arrives, so the picture does not jump, VIEW-005. */
'use strict';
importScripts('/vendor/d3/d3-dispatch.min.js', '/vendor/d3/d3-timer.min.js', '/vendor/d3/d3-quadtree.min.js',
  '/vendor/d3/d3-binarytree.min.js', '/vendor/d3/d3-octree.min.js', '/vendor/d3/d3-force-3d.min.js');

/* Face edges and encounter ties pull harder than namespace edges, so function structure shapes the mesh, VIEW-005. */
const DISTANCE = {face: 14, tie: 30, sub: 8, tree: 60};
const STRENGTH = {face: 0.8, tie: 0.8, sub: 0.8, tree: 0.15};

let nodes = [], links = [], byId = new Map();
let paused = false, running = false, stride = 1, sent = 0;
const simulation = d3.forceSimulation([], 3).stop()
  .force('charge', d3.forceManyBody().strength(node => node.t === 'el' ? -140 : -18).theta(0.9))
  .force('link', d3.forceLink([]).id(node => node.id).distance(link => DISTANCE[link.k]).strength(link => STRENGTH[link.k]))
  .force('center', d3.forceCenter());

function place(node, near) {
  const spread = 20 + 4 * Math.cbrt(nodes.length);
  const base = near || {x: 0, y: 0, z: 0};
  const jitter = near ? 12 : spread;
  node.x = base.x + (Math.random() - 0.5) * jitter;
  node.y = base.y + (Math.random() - 0.5) * jitter;
  node.z = base.z + (Math.random() - 0.5) * jitter;
}

function add(newNodes, newLinks) {
  for (const node of newNodes) { nodes.push(node); byId.set(node.id, node); }
  const neighbor = new Map();
  for (const link of newLinks) {
    links.push(link);
    for (const [a, b] of [[link.source, link.target], [link.target, link.source]])
      if (!neighbor.has(a) && byId.get(b)?.x !== undefined) neighbor.set(a, byId.get(b));
  }
  for (const node of newNodes) place(node, neighbor.get(node.id));
  simulation.nodes(nodes);
  simulation.force('link').links(links);
  simulation.alpha(Math.max(simulation.alpha(), newNodes.length ? 0.6 : 0.3));
  start();
}

function post(settled) {
  const positions = new Float32Array(nodes.length * 3);
  nodes.forEach((node, index) => { positions[index * 3] = node.x; positions[index * 3 + 1] = node.y; positions[index * 3 + 2] = node.z; });
  postMessage({type: 'positions', positions, count: nodes.length, settled}, [positions.buffer]);
}

function step() {
  if (paused || !nodes.length) { running = false; return; }
  const ticks = nodes.length > 20000 ? 1 : 4;
  for (let tick = 0; tick < ticks; tick++) simulation.tick();
  const settled = simulation.alpha() <= simulation.alphaMin();
  if (settled || ++sent % stride === 0) post(settled);
  if (settled) { running = false; return; }
  setTimeout(step, 0);
}

function start() { if (!running && !paused) { running = true; setTimeout(step, 0); } }

onmessage = ({data}) => {
  if (data.type === 'reset') { nodes = []; links = []; byId = new Map(); simulation.nodes([]); simulation.force('link').links([]); }
  else if (data.type === 'add') { stride = data.stride || 1; add(data.nodes, data.links); }
  else if (data.type === 'pause') { paused = true; }
  else if (data.type === 'resume') { paused = false; simulation.alpha(Math.max(simulation.alpha(), 0.3)); start(); }
  else if (data.type === 'relayout') { for (const node of nodes) place(node, null); simulation.alpha(1); paused = false; start(); }
};
