/* The roundtable's tab, BASE-066: shown at the top of the large area only while a table runs in the project, and gone
 * when it ends. Its panel draws the table with the roundtable's own scene module, the one its runner's watch page and
 * renderer draw with, served at /roundtable/scene.js; beside it the discussion as it happens and the chair's controls,
 * Hold, a comment, Continue and End, with the pause after each turn counted down while the person watches. Clicking a
 * seat shows what that seat sees from its own eyes, drawn by the same scene. The Agents menu's Open roundtable opens
 * one. Everything goes through the web server's /api/roundtable, never the runner's loopback watch server. */
import '/page/app/loading/load.js';  // the part before runs first, so the parts run in the page's order
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {createTable} from '/roundtable/scene.js';
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {showAgentMenu} from '/page/app/settings/screen.js';
import {wrote} from '/page/app/board/history.js';

const WATCH = 3000;  // the watch is renewed this often while the tab shows; the table counts eight seconds from each
const NOULS = ['new', 'valuable', 'relevant', 'keep'];
const PHASES = {explore: 'the seats are exploring their controls', running: 'in discussion', held: 'held',
  ending: 'ending: the report is being written', ended: 'ended'};
export const RT = {project: null, number: null, since: 0, table: null, scene: null, pause: 0, keep: null,
  shown: false, busy: false, again: false, until: 0, view: null, watching: null};

/* ---------- reading the table ---------- */
function forget() {
  RT.number = null; RT.since = 0; RT.table = null; RT.until = 0;
  fill($('#roundtable .rtlog'));
  $('#roundtable .rteye').hidden = true;
  if (RT.view) { RT.view.renderer.dispose(); RT.view.renderer.domElement.remove(); RT.view = null; }
}
/* The table running in the project read again: its status, its scene, and the turns since the last read. A change
 * heard for the roundtable's tables comes here, as does the stream opening; nothing polls, since the table's runner
 * writes its beat every few seconds while it runs, and the page's own watch is a write too. Reads never overlap. */
export async function roundtableChanged() {
  if (RT.busy) { RT.again = true; return; }
  RT.busy = true;
  try {
    do { RT.again = false; await readTable(); } while (RT.again);
  } finally { RT.busy = false; }
}
async function readTable() {
  const project = S.project;
  if (RT.project !== project) { forget(); RT.project = project; }
  if (!project) return showStrip(false);
  let found;
  try { found = await read('roundtable', RT.number ? {since: RT.since} : {}); } catch { return; }
  if (S.project !== project) return;
  if (!found.table) { forget(); return showStrip(false); }
  if (found.table.discussion !== RT.number) {  // a new table: read its turns from the first
    const fresh = RT.number !== null;
    forget();
    RT.number = found.table.discussion;
    if (fresh) { RT.again = true; return; }
  }
  RT.table = found.table; RT.scene = found.scene; RT.pause = Number(found.pause) || 0; RT.keep = found.keep ?? null;
  const turns = found.turns?.turns || [], before = RT.since;
  RT.since = found.turns?.latest ?? RT.since;
  addTurns(turns);
  // a seat's turn just entered while the person watches: the table pauses roundtable_pause seconds for the chair
  if (RT.shown && before > 0 && turns.some(turn => turn.kind === 'seat' || turn.kind === 'none')
    && RT.table.state === 'running' && RT.pause > 0) RT.until = Date.now() + RT.pause * 1000;
  showStrip(true);
  drawState();
  if (RT.shown && !RT.view) RT.view = drawScene();
  else RT.view?.table.update(RT.scene);
}
/* ---------- the tab ---------- */
function showStrip(on) {
  $('#rtStrip').hidden = !on;
  if (!on && RT.shown) showTab(false);
  if (on) {
    const subject = String(RT.table.subject || '').replaceAll('-', ' ');
    fill($('#t-roundtable'), `Roundtable ${RT.table.discussion}`, subject ? h('small', {}, ` · ${subject}`) : null);
    $('#t-roundtable').title = `Roundtable ${RT.table.discussion} at ${RT.table.address}: ${subject}`;
  }
}
export function showTab(on) {
  RT.shown = on;
  $('#roundtable').hidden = !on;
  for (const [tab, chosen] of [[$('#t-map'), !on], [$('#t-roundtable'), on]]) {
    tab.setAttribute('aria-selected', String(chosen));
    tab.tabIndex = chosen ? 0 : -1;
  }
  clearInterval(RT.watching);
  RT.watching = null;
  if (on) {
    if (!RT.view && RT.scene) RT.view = drawScene();
    watch();
    RT.watching = setInterval(watch, WATCH);
    roundtableChanged();
  } else RT.until = 0;
}
/* The person is watching the table while its tab shows on a page in view: the table pauses after each turn for the
 * chair's controls, `roundtable watch`. */
function watch() {
  if (!RT.shown || !RT.number || document.visibilityState !== 'visible') return;
  if (!['running', 'held'].includes(RT.table?.state)) return;
  wrote('/api/roundtable', {act: 'watch', discussion: RT.number});
}
$('#t-map').onclick = () => showTab(false);
$('#t-roundtable').onclick = () => showTab(true);
$('#rtStrip').addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  showTab(!RT.shown);
  (RT.shown ? $('#t-roundtable') : $('#t-map')).focus();
});
document.addEventListener('visibilitychange', watch);
/* ---------- the state line, the countdown and the controls ---------- */
function drawState() {
  const table = RT.table, scene = RT.scene || {};
  const phase = scene.phase || table.state;
  const left = phase === 'explore' ? ` (${scene.explore_left} s)` : '';
  const turn = table.turn_of && phase === 'running' ? `; ${table.turn_of}'s turn` : '';
  const spent = Number(table.spent) > 0 ? ` · $${Number(table.spent).toFixed(2)} of $${Number(table.spend)}` : '';
  fill($('#roundtable .rtstate'), h('b', {}, `${PHASES[phase] || phase}${left}${turn}`),
    ` · round ${table.round} of ${table.rounds}${spent} · at ${table.address}`,
    table.reason && table.state !== 'running' ? h('span', {}, ` · ${table.reason}`) : null);
  const chair = $('#roundtable .rtchair'), open = ['running', 'held'].includes(table.state);
  chair.querySelector('.hold').disabled = table.state !== 'running';
  chair.querySelector('.go').disabled = !open;
  chair.querySelector('.end').disabled = table.state === 'ending';
  chair.querySelector('.rtcomment button').disabled = !open;
  countdown();
}
function countdown() {
  const left = Math.ceil((RT.until - Date.now()) / 1000), shown = RT.shown && left > 0 && RT.table?.state === 'running';
  const box = $('#roundtable .rtcount');
  box.hidden = !shown;
  if (shown) box.textContent = `Next turn in ${left} s: hold, comment, continue or end now.`;
}
setInterval(countdown, 250);
async function chair(act, more = {}) {
  if (!RT.number) return null;
  const done = await wrote('/api/roundtable', {act, discussion: RT.number, ...more});
  if (done) {
    if (act !== 'comment') RT.until = 0;
    roundtableChanged();
  }
  return done;
}
$('#roundtable .hold').onclick = () => chair('hold');
$('#roundtable .go').onclick = () => chair('continue');
$('#roundtable .end').onclick = async () => {
  if (await confirmAct({title: `End roundtable ${RT.number}?`, verb: 'End the table',
    text: 'The seats stop, and one model writes the report into docs/roundtables/.',
    kept: ['Every submission, kept or vetoed, stays readable in the review']})) chair('end');
};
$('#roundtable .rtcomment').onsubmit = async event => {
  event.preventDefault();
  const box = event.target.querySelector('textarea'), text = box.value.trim();
  if (!text) return;
  if (await chair('comment', {text})) { box.value = ''; toast('Your comment enters at the next gap between turns.'); }
};
/* ---------- the discussion ---------- */
// a turn's text without the turn and the seat the record puts before it, which the row shows by itself
const bare = turn => {
  const head = `${turn.turn} ${turn.seat}: `;
  return String(turn.shown || '').startsWith(head) ? turn.shown.slice(head.length) : String(turn.shown || '');
};
function addTurns(turns) {
  const log = $('#roundtable .rtlog');
  const pinned = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  for (const turn of turns) {
    if (log.querySelector(`[data-number="${turn.number}"]`)) continue;
    log.append(turnRow(turn));
  }
  if (pinned) log.scrollTop = log.scrollHeight;
}
function turnRow(turn) {
  const comment = turn.kind === 'person' || turn.kind === 'head';
  const vetoed = turn.kind === 'seat' && !turn.entered;
  const kind = comment ? 'comment' : turn.kind === 'none' ? 'none' : vetoed ? 'vetoed' : 'kept';
  const who = h('div', {class: 'who'}, comment && turn.kind === 'person' ? 'You' : turn.seat,
    h('small', {}, `${turn.turn}${vetoed ? ' · vetoed' : comment ? ' · comment' : ''}`));
  if (!vetoed) return h('li', {class: kind, 'data-number': turn.number}, who, h('p', {class: 'said'}, bare(turn)));
  // a vetoed turn is its four scores and a link to its text, as every seat is shown it
  const scores = h('p', {class: 'scores', 'aria-label': 'Jev\'s four scores'},
    (turn.nouls || []).map((value, i) => h('span', {class: RT.keep !== null && value < RT.keep ? 'low' : ''},
      `${NOULS[i]} ${Number(value).toFixed(2)}`)));
  const text = h('p', {class: 'said', hidden: true});
  const link = h('button', {class: 'text', type: 'button', title: turn.link, onclick: () => showText(turn, text, link)},
    'Read its text');
  return h('li', {class: kind, 'data-number': turn.number}, who, scores, link, text);
}
async function showText(turn, box, link) {
  if (!box.hidden) { box.hidden = true; link.textContent = 'Read its text'; return; }
  try {
    const found = await read('roundtable-submission', {discussion: RT.number, submission: turn.number});
    box.textContent = found.text;
  } catch (error) { box.textContent = error.message; }
  box.hidden = false;
  link.textContent = 'Hide its text';
}
/* ---------- the table drawn ---------- */
function drawScene() {
  const host = $('#roundtable .rtscene');
  const renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  host.prepend(renderer.domElement);
  const table = createTable(renderer);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.8, 0);
  table.update(RT.scene);
  const view = {renderer, table, camera, controls, last: performance.now(), size: null};
  view.size = () => {
    const width = host.clientWidth, height = host.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(view.size).observe(host);
  view.size();
  // from above and a little toward the first seat, as the watch page places it, drawn back in an area narrower than
  // a window so the whole ring stays in view
  const ring = RT.scene.table.ring, back = Math.max(1, 1.5 / camera.aspect);
  camera.position.set(0, (ring * 1.45 + 2.2) * back, (ring * 1.35 + 2) * back);
  controls.update();
  const frame = now => {
    if (RT.view !== view) return;
    requestAnimationFrame(frame);
    const dt = Math.min(0.1, (now - view.last) / 1000);
    view.last = now;
    if (!RT.shown) return;
    table.frame(dt);
    controls.update();
    renderer.render(table.scene, camera);
  };
  requestAnimationFrame(frame);
  pickSeats(view, host);
  return view;
}
/* A click on a seat, its figure, chair or name, shows what that seat sees from its own eyes, drawn by the scene's
 * own `eyeShot`, the view the runner draws for the seat's look; a drag only turns the camera. */
function pickSeats(view, host) {
  const ray = new THREE.Raycaster(), at = new THREE.Vector2();
  let down = null;
  view.renderer.domElement.addEventListener('pointerdown', event => { down = [event.clientX, event.clientY]; });
  view.renderer.domElement.addEventListener('pointerup', event => {
    if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
    const box = view.renderer.domElement.getBoundingClientRect();
    at.set((event.clientX - box.left) / box.width * 2 - 1, -(event.clientY - box.top) / box.height * 2 + 1);
    ray.setFromCamera(at, view.camera);
    const seat = seatHit(ray.intersectObjects(view.table.scene.children, true));
    if (seat) eyeView(view, seat);
  });
  host.querySelector('.rteye .close').onclick = () => { host.querySelector('.rteye').hidden = true; };
}
function seatHit(hits) {
  for (const hit of hits) {
    let top = hit.object;
    while (top.parent && top.parent.type !== 'Scene') top = top.parent;
    const seat = (RT.scene?.seats || []).find(one => Math.hypot(one.x - top.position.x, one.z - top.position.z) < 0.6);
    if (seat) return seat;
  }
  return null;
}
export function eyeView(view, seat) {
  let url;
  try { url = view.table.eyeShot(seat.position); } catch (error) { return toast(error.message); } finally {
    view.size();  // the eye view drew at its own size into the tab's canvas; the tab's size is put back
  }
  const eye = $('#roundtable .rteye');
  eye.querySelector('.title').textContent = `What ${seat.name} sees, facing as it does now`;
  eye.querySelector('img').src = url;
  eye.querySelector('img').alt = `The table from ${seat.name}'s own eyes`;
  eye.hidden = false;
}
/* ---------- Open roundtable, from the Agents menu ---------- */
const OPEN = {seats: [], offered: null};
async function openForm() {
  showAgentMenu(false);
  const box = $('#rtopen');
  box.hidden = false;
  fill($('#rtaddresses'), [...S.elements.values()].map(entry => h('option', {value: entry.element.address})));
  const selected = S.elements.get(S.selected)?.element?.address;
  if (selected && !box.querySelector('.address').value) box.querySelector('.address').value = selected;
  drawSeats();
  const hint = box.querySelector('.seats .hint');
  hint.textContent = 'Reading the agents and models available…';
  let offered;
  try { offered = await read('roundtable-seats'); } catch (error) { hint.textContent = error.message; return; }
  OPEN.offered = offered;
  const agents = box.querySelector('.add.agent select');
  fill(agents, offered.agents.flatMap(agent => agent.models.length
    ? h('optgroup', {label: agent.label}, agent.models.map(model =>
      h('option', {value: `acp:${agent.agent}/${model.value}`}, `${agent.label} · ${model.name}`)))
    : [h('option', {value: `acp:${agent.agent}/default`}, `${agent.label} · its default model`)]));
  box.querySelector('.add.agent').hidden = !offered.agents.length;
  fill($('#rtmodels'), offered.models.map(model => h('option', {value: model})));
  box.querySelector('.rounds').placeholder = String(offered.rounds);
  box.querySelector('.spend').placeholder = String(offered.spend);
  hint.textContent = [offered.agents.length ? 'Agents run on your own login.' : 'No agent can be seated here.',
    offered.key ? 'Models through OpenRouter are paid from your OpenRouter key.'
      : 'OPENROUTER_API_KEY is not set, so no model through OpenRouter can be seated.'].join(' ');
}
function drawSeats() {
  fill($('#rtopen .seats .chosen'), OPEN.seats.map((seat, i) => h('li', {}, seat,
    h('button', {class: 'btn sm quiet', type: 'button', title: 'Take this seat away',
      onclick: () => { OPEN.seats.splice(i, 1); drawSeats(); }}, 'Remove'))));
}
function addSeat(value) {
  const seat = String(value || '').trim();
  if (!seat || OPEN.seats.includes(seat)) return;
  OPEN.seats.push(seat);
  drawSeats();
}
$('#rtopen .add.agent button').onclick = () => addSeat($('#rtopen .add.agent select').value);
$('#rtopen .add.model button').onclick = () => {
  const field = $('#rtopen .add.model input');
  addSeat(field.value);
  field.value = '';
};
$('#rtopen .add.model input').onkeydown = event => {
  if (event.key === 'Enter') { event.preventDefault(); $('#rtopen .add.model button').click(); }
};
async function openTable() {
  const box = $('#rtopen'), field = name => box.querySelector(name).value.trim();
  if (!field('.address')) return toast('A table opens at an Address.');
  if (!OPEN.seats.length) return toast('A table needs one seat at least.');
  if (!field('.opening')) return toast('A table opens with its opening message.');
  const button = box.querySelector('.put');
  button.disabled = true;
  try {
    const done = await wrote('/api/roundtable', {act: 'open', address: field('.address'), seats: OPEN.seats.join(','),
      opening: field('.opening'), ...(field('.rounds') ? {rounds: Number(field('.rounds'))} : {}),
      ...(field('.spend') ? {spend: field('.spend')} : {})});
    if (!done) return;
    box.hidden = true;
    OPEN.seats = [];
    box.querySelector('.opening').value = '';
    toast(`Roundtable ${done.discussion} is open at ${done.address}.`);
    await roundtableChanged();
    if (RT.number === done.discussion) showTab(true);
  } finally { button.disabled = false; }
}
$('#rtopen .put').onclick = openTable;
$('#rtopen .close').onclick = () => { $('#rtopen').hidden = true; };
overlay($('#rtopen'), {close: () => { $('#rtopen').hidden = true; }, focus: '.address'});
$('#roundtableBtn').onclick = openForm;
Object.assign(window.metaform, {roundtable: () => ({number: RT.number, shown: RT.shown, until: RT.until,
  state: RT.table?.state || null, seats: (RT.scene?.seats || []).map(seat => seat.name)})});
