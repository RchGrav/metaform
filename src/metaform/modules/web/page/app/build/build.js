/* The build panel, BASE-060: the modules and prompt of a build, its run and progress, and the remote agent's prompt
 * editor. */
import '/page/app/agents/asking.js';  // the part before runs first, so the parts run in the page's order
import {$, reduced, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {toast, segmented, progressBar, copyField} from '/page/app/core/controls.js';
import {S} from '/page/app/core/reads.js';
import {plural} from '/page/app/memory/manage.js';
import {dockOffered} from '/page/app/dock/commands.js';
import {syncResume} from '/page/app/dock/send.js';
import {discard} from '/page/app/task/task.js';
import {getJson} from '/page/app/panel/prompts.js';
import {clip} from '/page/app/session/tools.js';
import {slashCommands} from '/page/app/session/settings.js';
import {posted} from '/page/app/intake/intake.js';

/* ---------- the build panel, BASE-060 ----------
 * Four builds, each a large choice with what it makes: the project as an archive, the project with Metaform for a
 * remote agent, the installer, and the installer with every module. A build that takes modules starts from a shape
 * and lists every module found, each with what it does and whether a remote agent can use it; the project's metaform
 * is always carried by the project builds. The project builds can leave the project's files out, and the remote
 * agent's build takes a task, written in the prompt editor, or onboarding when none is written. One click builds;
 * its stages are a progress bar, the browser saves the file when it is done, and a project wheel's prompt is ready to
 * copy. The panel remembers each project's last choices in this browser. */
export const BUILD = {options: null, kind: null, picks: {}, files: true, task: '', job: null, project: null,
  editor: null, docs: null, tab: 'task', saved: {}, heard: new Map(), watching: null};
const BUILD_KEY = project => `metaform.build.${project}`;
function keptBuild(project) {
  try { return JSON.parse(localStorage.getItem(BUILD_KEY(project)) || '{}') || {}; } catch { return {}; }
}
function keepBuild() {
  if (!BUILD.project) return;
  try {
    localStorage.setItem(BUILD_KEY(BUILD.project), JSON.stringify({kind: BUILD.kind, picks: BUILD.picks,
      files: BUILD.files, task: BUILD.task, job: BUILD.job?.build_id || null}));
  } catch { /* storage can be blocked; the panel starts from its defaults */ }
}
const kindOfBuild = () => BUILD.options?.kinds.find(kind => kind.id === BUILD.kind) || null;
const shapeOf = id => BUILD.options?.shapes.find(shape => shape.id === id) || null;
/* The modules chosen for a build that takes them, kept for each build: a project wheel starts from the Remote agent
 * shape and an installer from the modules on at home with those `metaform start` and `demo` run, as the builds
 * themselves do, BASE-060. */
function pickOf(kind) {
  const known = new Set((BUILD.options?.modules || []).map(module => module.id));
  let pick = BUILD.picks[kind];
  if (!pick || !Array.isArray(pick.modules)) {
    const installer = BUILD.options?.defaults?.installer;
    const shape = kind === 'installer' ? 'home' : BUILD.options?.defaults?.shape || 'remote';
    pick = BUILD.picks[kind] = {shape, modules: [...(kind === 'installer' && Array.isArray(installer) ? installer
      : shapeOf(shape)?.modules || [])]};
  }
  pick.modules = pick.modules.filter(id => known.has(id));  // a module gone since is not offered
  return pick;
}
const sameSet = (one, two) => one.length === two.length && one.every(item => two.includes(item));
const STAGE_WORDS = {resolve: 'Resolve dependencies', collect: 'Collect them', 'pack modules': 'Pack the modules',
  'pack project': 'Pack the project', write: 'Write the file'};
const bytesOf = bytes => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB`
  : bytes >= 1024 ? `${Math.round(bytes / 1024)} KB` : `${bytes} B`;
async function openBuild() {
  const box = $('#build');
  box.hidden = false;
  if (BUILD.project !== S.project) restoreBuild(keptBuild(S.project));
  // read on each opening, so a module added or a prompt saved since shows
  if (!BUILD.options) fill($('#build .body'), h('p', {class: 'loading'}, 'Reading what can be built…'));
  try { BUILD.options = await getJson('/api/build/options'); } catch (error) {
    if (!BUILD.options) return fill($('#build .body'), h('div', {class: 'failed', role: 'alert'}, error.message));
  }
  const defaults = BUILD.options.defaults || {};
  BUILD.kind = BUILD.options.kinds.some(kind => kind.id === BUILD.kind) ? BUILD.kind
    : defaults.kind || BUILD.options.kinds[0].id;
  BUILD.files ??= defaults.files ?? true;
  drawBuild();
}
/* The project's last choices, kept in this browser, and its last build, read again while the server still has it. */
function restoreBuild(kept) {
  Object.assign(BUILD, {project: S.project, kind: kept.kind || null,
    picks: kept.picks && typeof kept.picks === 'object' ? kept.picks : {},
    files: kept.files ?? null, task: kept.task || '', job: null});
  if (!kept.job) return;
  getJson(`/api/build/${kept.job}`)
    .then(job => { if (BUILD.project === S.project && !BUILD.job) { BUILD.job = job; drawBuildRun(); } })
    .catch(() => { /* a build is kept while the server runs; an older one is gone */ });
}
function chooseKind(id) {
  BUILD.kind = id;
  keepBuild();
  drawBuild();
  $(`#build .kindcard[data-kind="${id}"]`)?.focus();
}
const KIND_ICONS = {archive: 'i-archive', project: 'i-send', installer: 'i-box', full: 'i-boxes'};
const kindCard = one => h('button', {type: 'button', role: 'radio', class: 'kindcard', 'data-kind': one.id,
  'aria-checked': String(one.id === BUILD.kind), tabindex: one.id === BUILD.kind ? '0' : '-1',
  onclick: () => chooseKind(one.id)},
h('i', {class: `i ${(Object.hasOwn(KIND_ICONS, one.id) ? KIND_ICONS[one.id] : '') || 'i-box'}`, 'aria-hidden': 'true'}),
h('b', {}, one.name), h('span', {}, one.summary));
/* The arrows move the choice round the builds, as in a group of radio buttons. */
function walkKinds(event, options) {
  if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
  event.preventDefault();
  const ids = options.kinds.map(one => one.id), at = ids.indexOf(BUILD.kind);
  chooseKind(ids[(at + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + ids.length) % ids.length]);
}
function drawBuild() {
  const options = BUILD.options, kind = kindOfBuild();
  if (!options || !kind) return;
  const takesProject = kind.takes_project;
  const kinds = h('div', {class: 'kinds', role: 'radiogroup', 'aria-label': 'What to build'},
    options.kinds.map(kindCard));
  kinds.addEventListener('keydown', event => walkKinds(event, options));
  const sections = [kinds];
  if (takesProject) sections.push(projectSection(kind));
  if (kind.takes_files) sections.push(filesSection(kind));
  if (kind.takes_modules) sections.push(modulesSection(kind));
  else if (kind.id === 'full') {
    sections.push(h('div', {class: 'section'}, h('div', {class: 'eyebrow'}, 'Modules'),
      h('p', {class: 'hint'}, `Every module found: ${options.modules.map(one => one.id).join(', ')}.`)));
  }
  if (kind.takes_prompt) sections.push(promptSection());
  fill($('#build .body'), sections, h('div', {class: 'run', 'aria-live': 'polite'}));
  const go = $('#build .go');
  go.textContent = `Build ${kind.name}`;
  go.disabled = Boolean(BUILD.job && BUILD.job.state === 'running')
    || (kind.id === 'installer' && !pickOf('installer').modules.length);
  $('#build .stages').textContent = kind.stages.map(stageWords).join(' → ');
  drawBuildRun();
}
const stageWords = stage => (Object.hasOwn(STAGE_WORDS, stage) ? STAGE_WORDS[stage] : '') || stage;
function projectSection(kind) {
  return h('div', {class: 'section project'}, h('div', {class: 'eyebrow'}, 'Project'),
    h('div', {class: 'line'}, h('b', {}, S.project), h('span', {class: 'hint'}, kind.id === 'project'
      ? 'Its map, carried as an archive in the wheel, and its files when they are included.'
      : 'Its map, and its files when they are included.')));
}
/* Whether the project's files go in, with what that means for the build said under it. */
function filesSection(kind) {
  const note = h('small', {class: 'hint files-note'});
  const drawFilesNote = () => {
    note.textContent = BUILD.files ? 'The project\'s files go in as they are; version control, virtual environments, '
      + 'caches and build folders never do.'
      : kind.id === 'project' ? 'Left out: the remote agent works on the map alone and returns no file changes.'
        : 'Left out: the archive holds the map alone.';
  };
  const files = h('input', {type: 'checkbox', role: 'switch', checked: BUILD.files,
    onchange: () => { BUILD.files = files.checked; keepBuild(); drawFilesNote(); }});
  drawFilesNote();
  return h('div', {class: 'section'}, h('label', {class: 'switch'}, files, 'Include the project\'s files'), note);
}
function modulesSection(kind) {
  const options = BUILD.options, pick = pickOf(kind.id);
  const shapes = segmented({label: 'Shape',
    value: options.shapes.find(shape => sameSet(shape.modules, pick.modules))?.id ?? '',
    options: options.shapes.map(shape => ({value: shape.id, label: shape.name,
      title: shape.modules.length ? `Ticks ${shape.modules.join(', ')}` : 'Ticks none'})),
    onchange: id => { pick.shape = id; pick.modules = [...shapeOf(id).modules]; keepBuild(); drawBuild(); }});
  const tally = h('span', {class: 'hint'}, `${plural(pick.modules.length, 'module')} chosen`);
  const rows = options.modules.map(module => moduleRow(module, kind, pick, {shapes, tally, options}));
  return h('div', {class: 'section modules'},
    h('div', {class: 'head'}, h('div', {class: 'eyebrow'}, 'Modules'), shapes, tally),
    h('div', {class: 'modlist'}, kind.id === 'project' ? metaformRow() : null, rows));
}
/* A module to tick: what it does, and whether a remote agent can use it and it is on at home. Ticking it names the
 * shape the modules now make, if any. */
function moduleRow(module, kind, pick, {shapes, tally, options}) {
  const on = pick.modules.includes(module.id);
  const tick = () => {
    pick.modules = box.checked ? [...new Set([...pick.modules, module.id])]
      : pick.modules.filter(id => id !== module.id);
    pick.shape = options.shapes.find(shape => sameSet(shape.modules, pick.modules))?.id || null;
    shapes.set(pick.shape ?? '');
    tally.textContent = `${plural(pick.modules.length, 'module')} chosen`;
    keepBuild();
    $('#build .go').disabled = kind.id === 'installer' && !pick.modules.length;
    row.classList.toggle('on', box.checked);
  };
  const box = h('input', {type: 'checkbox', checked: on, 'aria-describedby': `mod-${module.id}`, onchange: tick});
  const row = h('label', {class: `modrow${on ? ' on' : ''}`},
    box, h('span', {class: 'name'}, module.id),
    h('span', {class: 'about', id: `mod-${module.id}`}, module.summary || ''),
    h('span', {class: 'tags'}, kind.id === 'project' && !module.remote
      ? h('span', {class: 'badge off',
        title: 'It needs what a hosted agent does not have: a screen, local agents or compiled packages'},
      'Not for a remote agent') : null,
    module.home ? h('span', {class: 'badge', title: 'It is turned on in this home'}, 'On at home') : null));
  return row;
}
/* The project's metaform, always carried by a project build, as a row that cannot be unticked. */
function metaformRow() {
  return h('div', {class: 'modrow locked', title: 'A project build always carries the project\'s metaform'},
    h('i', {class: 'i i-lock', 'aria-hidden': 'true'}), h('span', {class: 'name'}, `${S.project}'s metaform`),
    h('span', {class: 'about'}, 'Always included: the map the remote agent works on.'),
    h('span', {class: 'tags'}, h('span', {class: 'badge ok'}, 'Included')));
}
/* The prompt the remote agent is given: the person's task, or with none written the onboarding, each wrapped in the
 * wrapper, as the build wraps them. */
function promptSection() {
  const prompts = BUILD.options.prompts, task = BUILD.task.trim();
  return h('div', {class: 'section prompt'}, h('div', {class: 'eyebrow'}, 'Prompt'),
    h('div', {class: 'promptcard'},
      h('div', {class: 'which'}, task
        ? [h('b', {}, 'Your task'), h('span', {class: 'first'}, clip(task.split('\n')[0], 120))]
        : [h('b', {}, 'Onboarding'), h('span', {class: 'first'}, 'No task written: the agent learns the project, '
          + 'tells you about it and waits for your instructions '
          + `(${prompts.onboarding.name}, version ${prompts.onboarding.number}).`)],
      h('small', {class: 'hint'}, `Wrapped in ${prompts.wrapper.name}, version ${prompts.wrapper.number}, which tells `
          + 'the agent what the wheel is and how to return its work.')),
      h('button', {class: 'btn', type: 'button', onclick: () => openBuildPrompt('task')},
        h('i', {class: 'i i-pen', 'aria-hidden': 'true'}), task ? 'Edit the task' : 'Write a task')));
}
/* The run: its stages as a bar, then the file, or the stage that failed with its error and next step. */
function drawBuildRun() {
  const host = $('#build .run');
  if (!host) return;
  const job = BUILD.job;
  if (!job) return fill(host);
  if (!job.build_id) {
    return fill(host, h('div', {class: 'eyebrow'}, 'The build did not start'),
      h('div', {class: 'failed', role: 'alert'}, h('b', {}, job.error || 'The build was refused.'),
        job.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, job.next)) : null));
  }
  const stages = job.stages || kindOfBuild()?.stages || [];
  const at = Math.max(0, stages.indexOf(job.stage));
  const share = job.state === 'done' ? 1 : stages.length ? at / stages.length : 0;
  const bar = progressBar({label: 'Build progress', value: share,
    words: job.state === 'done' ? 'Done' : job.state === 'failed'
      ? `Stopped at ${STAGE_WORDS[job.stage] || job.stage || 'the start'}`
      : `${STAGE_WORDS[job.stage] || 'Starting'}…`});
  bar.classList.toggle('stopped', job.state === 'failed');
  const steps = h('ol', {class: 'buildsteps'}, stages.map((stage, index) => buildStep(job, stage, index, at)));
  const title = job.state === 'done' ? 'Built' : job.state === 'failed' ? 'The build stopped' : 'Building';
  const parts = [h('div', {class: 'eyebrow'}, title), bar, steps];
  if (job.state === 'failed') {
    parts.push(h('div', {class: 'failed', role: 'alert'}, h('b', {}, job.error || 'The build failed.'),
      job.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, job.next)) : null));
  }
  if (job.state === 'done' && job.file) parts.push(...builtFile(job));
  fill(host, parts);
}
const STEP_WORDS = {done: 'done', stopped: 'stopped here', now: 'under way', later: 'to come'};
/* A stage of the run: done, stopped at, under way, or to come. */
function buildStep(job, stage, index, at) {
  const state = job.state === 'done' || index < at ? 'done'
    : index === at ? (job.state === 'failed' ? 'stopped' : 'now') : 'later';
  return h('li', {class: state}, h('i', {'aria-hidden': 'true'}),
    h('span', {class: 'visually-hidden'}, `${STEP_WORDS[state]}: `), STAGE_WORDS[stage] || stage);
}
/* The file built, to download again, and a project wheel's prompt to copy. */
function builtFile(job) {
  const link = h('a', {class: 'btn sm', href: `/api/build/${job.build_id}/download`, download: job.file},
    h('i', {class: 'i i-download', 'aria-hidden': 'true'}), 'Download again');
  const parts = [h('div', {class: 'result'}, h('i', {class: 'i i-check', 'aria-hidden': 'true'}),
    h('span', {class: 'file'},
      h('span', {}, h('b', {}, job.file), job.size ? h('small', {class: 'size'}, ` · ${bytesOf(job.size)}`) : null),
      h('small', {class: 'where'}, 'Saved by your browser; a copy stays in the builds folder of your Metaform home.')),
    link)];
  if (job.prompt) {
    parts.push(h('div', {class: 'wrapped'}, h('div', {class: 'eyebrow'}, 'The prompt for the remote agent'),
      h('p', {class: 'paste'}, `Upload ${job.file} to the agent and paste this as your message:`),
      copyField({label: 'the remote agent\'s prompt', text: job.prompt, rows: 8})));
  }
  return parts;
}
async function startBuild() {
  const kind = kindOfBuild();
  if (!kind) return;
  const given = {kind: kind.id};
  given.project = kind.takes_project ? S.project : null;  // `posted` sends the page's project with every write
  if (kind.takes_modules) {
    const pick = pickOf(kind.id);
    const shape = pick.shape && sameSet(shapeOf(pick.shape)?.modules || [], pick.modules) ? pick.shape : null;
    if (shape) given.shape = shape; else given.modules = pick.modules;
  }
  if (kind.takes_files) given.files = BUILD.files;
  if (kind.takes_prompt && BUILD.task.trim()) given.prompt = BUILD.task;
  $('#build .go').disabled = true;
  const sent = await posted('/api/build', given);
  if (!sent.ok) {
    BUILD.job = {build_id: null, stages: kind.stages, stage: null, state: 'failed', error: sent.body.error,
      next: sent.body.next};
    $('#build .go').disabled = false;
    return drawBuildRun();
  }
  BUILD.job = {build_id: sent.body.build_id, stages: sent.body.stages, stage: null, state: 'running', kind: kind.id};
  BUILD.watching = sent.body.build_id;
  keepBuild();
  drawBuildRun();
  showRun();
  // a quick build can be told before its id comes back: what was heard of it meanwhile is taken now, and read once
  // more, so a build that ended while the stream was away still ends here
  const heard = BUILD.heard.get(sent.body.build_id);
  BUILD.heard.clear();
  if (heard) await buildEvent(heard);
  else {
    getJson(`/api/build/${sent.body.build_id}`).then(endedMeanwhile)
      .catch(() => { /* the stream tells the rest */ });
  }
}
function endedMeanwhile(now) {
  if (BUILD.job?.build_id === now.build_id && now.state !== 'running' && BUILD.job.state === 'running') buildEvent(now);
}
/* A build's progress, pushed on the page's stream as each stage starts and as it ends; the file is saved at its end. */
export async function buildEvent(payload) {
  if (!payload) return;
  if (payload.build_id !== BUILD.job?.build_id) {  // another page's build, or this one's before its id came back
    BUILD.heard.set(payload.build_id, payload);
    if (BUILD.heard.size > 16) BUILD.heard.delete(BUILD.heard.keys().next().value);
    return;
  }
  Object.assign(BUILD.job, payload);
  if (payload.state !== 'running') {
    try { Object.assign(BUILD.job, await getJson(`/api/build/${payload.build_id}`)); }
    catch { /* the event said enough */ }
    if (BUILD.job.build_id !== payload.build_id) return;
    if (payload.state === 'done' && BUILD.watching === payload.build_id) saveBuilt(payload);
    else if (payload.state === 'failed' && $('#build').hidden) {
      toast(`The build stopped at ${STAGE_WORDS[payload.stage] || 'its start'}: `
        + `${String(payload.error || 'it failed').replace(/\.$/, '')}.`);
    }
    if ($('#build .go')) $('#build .go').disabled = false;
    drawBuildRun();
    return showRun();
  }
  drawBuildRun();
}
/* The file of the build this page started is saved by the browser as it ends. */
function saveBuilt(payload) {
  BUILD.watching = null;
  const link = h('a', {href: `/api/build/${payload.build_id}/download`, download: payload.file || ''});
  document.body.append(link); link.click(); link.remove();
  // the panel shows the result; a person who closed it while it built is told in a toast
  if ($('#build').hidden) toast(`Built ${payload.file}. Your browser saves it.`);
}
/* The run is brought into view as it starts and as it ends, where the person looks for it. */
function showRun() {
  requestAnimationFrame(() => $('#build .run')
    ?.scrollIntoView({block: 'nearest', behavior: reduced() ? 'auto' : 'smooth'}));
}
$('#buildBtn').onclick = openBuild;
$('#build .close').onclick = () => { $('#build').hidden = true; };
$('#build .go').onclick = startBuild;
overlay($('#build'), {kind: 'dialog', close: () => { $('#build').hidden = true; },
  focus: () => $('#build .kindcard[aria-checked="true"]')});
/* The prompt editor of the remote agent's build, VIEW-013: the task as the person writes it, and the wrapper and the
 * onboarding, the prompt store's own, each saved as its next version; the preview is the prompt as the build makes it,
 * the wheel's name filled in when it is built. */
async function openBuildPrompt(tab = 'task') {
  const box = $('#buildPrompt');
  const prompts = BUILD.options.prompts;
  BUILD.saved = {wrapper: {...prompts.wrapper}, onboarding: {...prompts.onboarding}};
  box.hidden = false;
  if (!BUILD.editor) {
    BUILD.editor = CodeMirror($('#buildPrompt .editor'), {lineNumbers: true, lineWrapping: true, mode: 'markdown'});
    BUILD.editor.on('change', () => buildPromptChanged());
  }
  BUILD.docs = {task: CodeMirror.Doc(BUILD.task, 'markdown'),
    wrapper: CodeMirror.Doc(prompts.wrapper.text, 'markdown'),
    onboarding: CodeMirror.Doc(prompts.onboarding.text, 'markdown')};
  const tabs = segmented({label: 'What to edit', value: tab, options: [{value: 'task', label: 'Task'},
    {value: 'onboarding', label: 'Onboarding'}, {value: 'wrapper', label: 'Wrapper'},
    {value: 'preview', label: 'Preview'}],
  onchange: value => showBuildPrompt(value)});
  fill($('#buildPrompt .tabbar'), tabs);
  showBuildPrompt(tab);
}
function showBuildPrompt(tab) {
  BUILD.tab = tab;
  const preview = tab === 'preview';
  $('#buildPrompt .editor').hidden = preview;
  $('#buildPrompt .preview').hidden = !preview;
  if (preview) fill($('#buildPrompt .preview'), wrappedPreview());
  else {
    BUILD.editor.swapDoc(BUILD.docs[tab]);
    setTimeout(() => { BUILD.editor.refresh(); BUILD.editor.focus(); }, 0);
  }
  buildPromptChanged();
}
function buildPromptChanged() {
  const tab = BUILD.tab, task = BUILD.docs.task.getValue();
  const saved = tab === 'wrapper' || tab === 'onboarding' ? BUILD.saved[tab] : null;
  const changed = saved ? BUILD.docs[tab].getValue() !== saved.text : false;
  const save = $('#buildPrompt .save');
  save.hidden = !saved;
  save.disabled = !changed;
  $('#buildPrompt .revert').hidden = !saved;
  $('#buildPrompt .revert').disabled = !changed;
  fill($('#buildPrompt .about'), promptAbout(tab, task, saved));
}
/* What the tab open edits, said above it. */
function promptAbout(tab, task, saved) {
  const onboarding = BUILD.saved.onboarding;
  if (tab === 'task') {
    return task.trim() ? 'The remote agent is given this task, as you write it, inside the wrapper.'
      : `Empty: the remote agent is given the onboarding, ${onboarding.name} version ${onboarding.number}, inside the `
        + 'wrapper.';
  }
  if (tab === 'preview') {
    return 'The prompt as the build makes it. The wheel\'s file name is filled in when it is built.';
  }
  return `${saved.name}, version ${saved.number}. Saved as a new version, it is what every build uses from then on; `
    + '{wheel}, {project} and {task} are filled in by the build.';
}
function wrappedPreview() {
  const task = BUILD.docs.task.getValue().trim();
  const filled = text => text.replaceAll('{project}', S.project);
  const inner = task || filled(BUILD.docs.onboarding.getValue()).trim();
  const text = filled(BUILD.docs.wrapper.getValue()).replace('{task}', inner).trim();
  const wheel = () => h('mark', {title: 'The wheel\'s file name, filled in when it is built'}, '‹wheel›');
  return h('pre', {class: 'prompt'},
    ...text.split('{wheel}').flatMap((part, index) => index ? [wheel(), part] : [part]));
}
async function saveBuildPrompt() {
  const tab = BUILD.tab, saved = BUILD.saved[tab];
  if (!saved) return;
  const sent = await posted('/api/save-prompt',
    {name: saved.name, text: BUILD.docs[tab].getValue(), parent: saved.number});
  if (!sent.ok) return toast(sent.body.error || 'The prompt was not saved.');
  Object.assign(saved, {number: sent.body.number, text: BUILD.docs[tab].getValue()});
  BUILD.options.prompts[tab] = {...saved};
  toast(`Saved ${saved.name} as version ${saved.number}. Every build uses it from now on.`);
  buildPromptChanged();
  if (!$('#build').hidden) drawBuild();
}
$('#buildPrompt .save').onclick = saveBuildPrompt;
$('#buildPrompt .revert').onclick = () => { BUILD.docs[BUILD.tab].setValue(BUILD.saved[BUILD.tab].text); };
// a prompt of the store changed and not saved is asked about before it is left, however the editor is closed
const unsaved = tab => BUILD.docs && BUILD.saved[tab] && BUILD.docs[tab].getValue() !== BUILD.saved[tab].text;
const promptKept = () => !['wrapper', 'onboarding'].some(unsaved)
  || discard('the unsaved changes to the prompts', 'Keep editing');
async function leaveBuildPrompt() { if (await promptKept()) closeBuildPrompt(); }
$('#buildPrompt .done').onclick = $('#buildPrompt .close').onclick = leaveBuildPrompt;
function closeBuildPrompt() {
  if (BUILD.docs) { BUILD.task = BUILD.docs.task.getValue(); keepBuild(); }
  $('#buildPrompt').hidden = true;
  if (!$('#build').hidden) drawBuild();
}
overlay($('#buildPrompt'), {kind: 'dialog', close: closeBuildPrompt, guard: promptKept});
// The dock's message box offers the commands as / is typed: the dock's own and those of the agent on view.
slashCommands($('#helpdesk .say'), dockOffered);
// The agent the chat's new chats start with is chosen as the first field of its settings popover, `dockPicker`.
syncResume();
