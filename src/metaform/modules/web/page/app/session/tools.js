/* An agent's session as ACP gives it, VIEW-039 and BASE-052: diffs, files and tool calls, permission requests,
 * questions, notices and signals. */
import '/page/app/agents/pickers.js';  // the part before runs first, so the parts run in the page's order
import {h, fill} from '/page/app/core/dom.js';
import {S} from '/page/app/core/reads.js';
import {joinOf} from '/page/app/graph/data.js';
import {nameOf} from '/page/app/map2d/inside.js';
import {plural} from '/page/app/memory/manage.js';
import {select} from '/page/app/selection/select.js';
import {dated, linked} from '/page/app/board/refs.js';
import {wrote} from '/page/app/board/history.js';
import {confirmAct} from '/page/app/core/controls.js';
import {D, ticketOf, ticketPart, PROMPT_WORDS} from '/page/app/agents/dispatch.js';
import {agentName} from '/page/app/agents/pickers.js';

/* ---------- an agent's session as ACP gives it, VIEW-039 and BASE-052 ----------
 * The thread, the plan as a checklist, each tool call with its diffs and the parts of the map its files belong to,
 * each permission request with the agent's own options, the session's settings, its slash commands and its usage,
 * drawn alike in the chat dock and the agent window from `GET /api/dispatch-sessions`, read again on each dispatch
 * event. Each piece is drawn again only when what it shows changed, so nothing under the person's hand flickers. */
export function clip(text, most) {
  const said = String(text ?? '');
  return said.length > most ? said.slice(0, most - 1).trimEnd() + '…' : said;
}
export const isIntake = (workId, session = null) => {
  const known = session || D.sessions.findLast(one => one.work_id === workId);
  return known?.task_name ? known.task_name === 'intake' : String(workId || '').startsWith('intake-');
};
/* Whether a work id is a helper's, one the system agent started with a brief, dispatch helper: it is never a ticket. */
export const isHelper = workId => String(workId || '').startsWith('helper-');
/* Whether a session is the person's own system agent, by what its runner says it is, `role`, and for a session from
 * before roles were kept, by what it is about: never an intake agent or a sentinel, which are about the system too, so
 * My agent never opens the intake and the intake is never called "your system agent" (UX review round 2, 2026-10-17,
 * combined F3). `state` is the session's state line, `workId` its work id. */
export const isSystemState = (state, workId) => Boolean(state)
  && (state.role ? state.role === 'system' : state.about === 'system') && !isIntake(workId);
/* The same for a session row, read through the states the agents key holds. */
export const isSystemSession = (session, states) => isSystemState(states?.[session.session_id], session.work_id);
/* What a session works on, in words: the intake, or its ticket's part. An intake's work id is never a ticket. */
export const workPart = workId => isIntake(workId) ? 'the intake' : isHelper(workId) ? 'a brief from your system agent'
  : ticketPart(ticketOf(workId));
/* A mode that lets the agent act without asking: named so by the agents that offer one, as bypassPermissions, yolo or
 * full access are, so choosing it is a decision the person sees and confirms. */
const SKIPS = /bypass|yolo|full[-_ ]?access|danger|skip[-_ ]?perm|no[-_ ]?approv|never[-_ ]?ask|without[-_ ]?ask/i;
export const skipsPrompts = option => Boolean(option) && SKIPS.test(`${option.value} ${option.name}`);
// the tool calls opened to their detail, by session and line, kept as the thread is drawn again
const OPENED = new Set();
const TOOL_ICON = {read: 'i-file', edit: 'i-pen', delete: 'i-trash', move: 'i-move', search: 'i-search',
  execute: 'i-terminal', think: 'i-spark', fetch: 'i-globe', switch_mode: 'i-gear'};
export const STATUS_WORDS = {pending: 'pending', in_progress: 'running', completed: 'done', failed: 'failed'};
const statusOf = line => line.data?.status || /\(([\w ]+)\)\s*$/.exec(line.text || '')?.[1] || 'pending';
const titleOf = line => line.data?.title || String(line.text || '').replace(/\s*\([\w ]+\)\s*$/, '') || 'A tool call';
export const countOf = number => number >= 1e6 ? `${(number / 1e6).toFixed(1).replace(/\.0$/, '')}M`
  : number >= 1e3 ? `${(number / 1e3).toFixed(1).replace(/\.0$/, '')}k` : String(number);
/* A unified patch drawn as it reads: each line with its numbers before and after, added and removed in their colors. */
function unifiedDiff(patch) {
  const rows = [];
  let old = 0, now = 0;
  const lines = String(patch || '').split('\n');
  if (lines.at(-1) === '') lines.pop();
  const row = (kind, before, after, sign, text, word) => h('div', {class: `dl ${kind}`},
    h('span', {class: 'ln', 'aria-hidden': 'true'}, before), h('span', {class: 'ln', 'aria-hidden': 'true'}, after),
    h('span', {class: 'sg', 'aria-hidden': 'true'}, sign), word ? h('span', {class: 'visually-hidden'}, word) : null,
    h('code', {}, text || ' '));
  for (const line of lines) {
    if (line.startsWith('--- ') || line.startsWith('+++ ')) continue;
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
    if (hunk) {
      old = Number(hunk[1]); now = Number(hunk[2]);
      rows.push(row('hunk', '', '', '', line));
      continue;
    }
    if (line.startsWith('\\')) { rows.push(row('meta', '', '', '', line.slice(2))); continue; }
    const sign = line[0], text = line.slice(1);
    if (sign === '+') rows.push(row('add', '', now++, '+', text, 'added'));
    else if (sign === '-') rows.push(row('del', old++, '', '−', text, 'removed'));
    else rows.push(row('ctx', old++, now++, '', text));
  }
  return h('div', {class: 'udiff'}, rows);
}
/* The parts of the map a file belongs to, each a chip that selects the part and flies both views to it. */
export function nodeChips(nodes = []) {
  return (nodes || []).map(nodeChip);
}
function nodeChip(node) {
  const key = node.kind === 'join' ? 'p:' + node.id : node.id;
  const known = node.kind === 'join' ? Boolean(joinOf(key)) : S.elements.has(key);
  const name = known ? nameOf(key, node.address) : node.address || key;
  return h('button', {class: 'chip nodechip', type: 'button', disabled: !known,
    title: known ? `Select ${name} on the map (${node.address})` : `${node.address}: not in the map shown`,
    onclick: event => { event.stopPropagation(); select(key, true); }},
  h('i', {class: 'dot', 'aria-hidden': 'true'}), clip(name, 32));
}
const delta = (added, removed) => h('span', {class: 'delta'}, h('b', {class: 'add'}, `+${added}`),
  h('b', {class: 'del'}, `−${removed}`));
/* One file's edit: a tool call's, or a commit's in the board's Archive, which can also say a file deleted, renamed or
 * binary. */
export function fileDetail(diff) {
  return h('div', {class: 'file'},
    h('div', {class: 'filehead'}, h('i', {class: 'i i-file', 'aria-hidden': 'true'}),
      h('span', {class: 'path', title: diff.path}, diff.path),
      diff.created ? h('span', {class: 'badge ok'}, 'New file') : null,
      diff.deleted ? h('span', {class: 'badge'}, 'Deleted') : null,
      diff.was ? h('span', {class: 'badge', title: diff.was}, `Renamed from ${diff.was}`) : null,
      diff.binary ? h('span', {class: 'badge'}, 'Binary') : null,
      delta(diff.added ?? 0, diff.removed ?? 0)),
    (diff.nodes || []).length ? h('div', {class: 'chips'}, nodeChips(diff.nodes)) : null,
    unifiedDiff(diff.patch),
    diff.truncated ? h('p', {class: 'hint'}, 'The diff is cut short here; the file holds the rest.') : null);
}
/* What a tool call acts on: its diffs, the places it reads or writes, and the terminals it runs. */
function toolDetail(data) {
  const located = (data.locations || []).filter(place => !(data.diffs || []).some(diff => diff.path === place.path));
  const terminals = data.terminals || [];
  return [(data.diffs || []).map(fileDetail),
    located.length ? h('ul', {class: 'places'}, located.map(placeRow)) : null,
    terminals.length ? h('p', {class: 'hint'},
      `Runs in ${plural(terminals.length, 'terminal')}: ${terminals.join(', ')}`) : null];
}
const placeRow = place => h('li', {},
  h('i', {class: 'i i-file', 'aria-hidden': 'true'}),
  h('span', {class: 'path'}, place.line ? `${place.path}:${place.line}` : place.path),
  (place.nodes || []).length ? h('span', {class: 'chips'}, nodeChips(place.nodes)) : null);
/* A tool call: one compact row, its kind, title, files and status; one with something to show opens to it. */
export function toolRow(line, tag, key) {
  const data = line.data || null, status = statusOf(line), title = titleOf(line);
  const kind = data?.kind || 'other';
  const added = (data?.diffs || []).reduce((sum, diff) => sum + (diff.added || 0), 0);
  const removed = (data?.diffs || []).reduce((sum, diff) => sum + (diff.removed || 0), 0);
  const files = [...new Set([...(data?.diffs || []), ...(data?.locations || [])].map(one => one.path))];
  const more = Boolean(data && ((data.diffs || []).length || (data.locations || []).length
    || (data.terminals || []).length));
  const open = more && OPENED.has(key);
  const detail = more ? h('div', {class: 'tooldetail', hidden: !open}, open ? toolDetail(data) : null) : null;
  // the detail is drawn the first time it opens, and kept open as the thread is drawn again
  const toggle = () => {
    const now = detail.hidden;
    detail.hidden = !now;
    if (now && !detail.childNodes.length) fill(detail, toolDetail(data));
    head.setAttribute('aria-expanded', String(now));
    OPENED[now ? 'add' : 'delete'](key);
  };
  const head = h(more ? 'button' : 'div', {class: 'toolhead', ...(more ? {type: 'button', 'aria-expanded': String(open),
    title: open ? 'Hide what it changed' : 'Show what it changed', onclick: toggle} : {})},
  h('i', {class: `i ${TOOL_ICON[kind] || 'i-tool'} kind`, 'aria-hidden': 'true'}),
  h('span', {class: 'title'}, title),
  files.length ? h('span', {class: 'files', title: files.join('\n')},
    files.length === 1 ? files[0].split('/').pop() : `${files.length} files`) : null,
  added || removed ? delta(added, removed) : null,
  h('span', {class: 'toolstate', 'data-status': status}, h('i', {'aria-hidden': 'true'}),
    STATUS_WORDS[status] || status),
  more ? h('i', {class: 'i i-chev', 'aria-hidden': 'true'}) : null);
  return h(tag, {class: 'tool', 'data-status': status, 'data-key': key}, head, detail);
}
const PERMIT_TITLES = {allow_once: 'Let it do this once',
  allow_always: 'Let it do this, and the same again without asking', reject_once: 'Do not let it do this',
  reject_always: 'Do not let it, and never ask again'};
/* How a session's permission requests are answered, dispatch_prompts' choices in a card's few words, and whose choice
 * the one in force is. */
export const ANSWERING = {ask_all: 'Ask each time', 'approve-reads': 'Approve reads only',
  'approve-all': 'Approve all'};
const ANSWERING_FROM = {session: 'chosen for this session', launch: 'given at this launch', project: 'project setting'};
/* Choose how a running session's permission requests are answered from now on: its later requests at once, and one
 * waiting now that the choice approves. Approve all lets the agent act without asking, so it is confirmed once. The
 * answer, or null when it was not chosen or not written. */
export async function answerAs(work, session, how, agent) {
  const name = agentName(agent);
  if (how === 'approve-all' && !await confirmAct({title: `Let ${name} act without asking?`,
    text: [`Every permission request of this session is approved from now on, this one too: ${name} runs any tool `
      + 'without asking you, including ones that change or delete files.',
    'You can choose another answer at any time.'],
    verb: 'Approve all', cancel: 'Keep asking', danger: true})) return null;
  return wrote('/api/dispatch-session-prompts', {work_id: work, session: session.session_id, prompts: how,
    ...(how === 'approve-all' ? {confirm: true} : {})});
}
/* A permission request, as the agent put it: what it would do and the agent's own options, each a button, with Allow
 * all, and how the session's requests are answered, a picker that changes it; while it waits it stands out, and once
 * answered it says what was chosen. `session` is the running session's read, its `prompts` the answer in force;
 * `answered` is told the request was answered from this card. */
export function permissionCard(line, work, tag, agent, {session = null, answered = null} = {}) {
  const data = line.data || {}, state = data.state || 'waiting';
  const name = agentName(agent);
  const chosen = (data.options || []).find(option => option.option_id === data.chosen);
  const live = state === 'waiting' && session?.state === 'running' && Boolean(session.session_id);
  const allowAll = live ? h('button', {type: 'button', class: 'btn sm allowall',
    title: `Allow this and every later request of this session, with no more asking`,
    onclick: () => choose('approve-all')}, 'Allow all') : null;
  const answer = h('div', {class: 'answers', role: 'group', 'aria-label': 'Answer the request'},
    (data.options || []).map(option => h('button', {type: 'button', 'data-option': option.option_id,
      class: `btn sm ${/^allow/.test(option.kind) ? (option.kind === 'allow_once' ? 'primary' : '') : 'danger'}`,
      title: (Object.hasOwn(PERMIT_TITLES, option.kind) ? PERMIT_TITLES[option.kind] : '') || option.name,
      onclick: event => permit(event, option)}, option.name)), allowAll);
  const settle = said => {
    card.classList.replace('waiting', 'answered');
    fill(answer, h('p', {class: 'said'}, h('i', {class: 'i i-check', 'aria-hidden': 'true'}), said));
    mode?.remove();
    answered?.(data.request);
  };
  async function permit(event, option) {
    const buttons = [...answer.querySelectorAll('button')];
    const picked = event.currentTarget;  // read before the await, after which the event has no currentTarget
    for (const button of buttons) button.disabled = true;
    picked.classList.add('chosen');
    const done = await wrote('/api/dispatch-permit', {work_id: work, request: data.request, option: option.option_id});
    if (!done) {
      for (const button of buttons) button.disabled = false;
      picked.classList.remove('chosen');
      return;
    }
    settle(`${done.answer || option.name}, answered by you.`);
  }
  // how the session's requests are answered, in force now, and a change of it; one approving this request answers it
  const held = Object.hasOwn(ANSWERING, session?.prompts || '') ? session.prompts : '';
  const pick = live ? h('select', {'aria-label': `How ${name}'s permission requests are answered`,
    onchange: () => choose(pick.value)},
  held ? null : h('option', {value: '', disabled: true, selected: true}, 'Not known'),
  Object.entries(ANSWERING).map(([value, words]) => h('option', {value, selected: value === held}, words))) : null;
  const mode = pick ? h('label', {class: 'answering',
    title: `${PROMPT_WORDS[held]?.[0] || 'How its requests are answered'}`
      + `${session.prompts_from ? ` (${ANSWERING_FROM[session.prompts_from] || session.prompts_from})` : ''}`},
  h('span', {}, 'Answers'), pick,
  session.prompts_from ? h('small', {}, ANSWERING_FROM[session.prompts_from] || session.prompts_from) : null) : null;
  async function choose(how) {
    const controls = [...card.querySelectorAll('.answers button, .answering select')];
    for (const control of controls) control.disabled = true;
    const done = await answerAs(work, session, how, agent);
    if (!done) {
      for (const control of controls) control.disabled = false;
      pick.value = held;
      return;
    }
    pick.value = how;
    for (const control of controls) control.disabled = false;
    if ((done.approved || []).includes(data.request)) {
      settle(`Allowed: ${ANSWERING[how].toLowerCase()}, chosen by you.`);
    }
  }
  const said = state === 'answered' ? `${data.answer || chosen?.name || 'Answered'}: answered.`
    : state === 'cancelled' ? 'Not answered: its turn ended before an answer.'
    : state === 'unmatched'
      ? `Answered at the node with “${data.answer || ''}”, which none of its options matched, so it was refused.` : '';
  const allowed = state === 'answered' && /^allow/.test(chosen?.kind || '');
  const card = h(tag, {class: `permission ${state}`, 'data-request': data.request},
    h('div', {class: 'ask'}, h('span', {class: 'eyebrow'}, state === 'waiting' ? 'Waiting for you' : 'Permission'),
      h('b', {}, `${name} asks to ${data.title || 'use a tool'}`),
      data.kind ? h('span', {class: 'chip'}, data.kind) : null),
    data.said ? h('p', {class: 'why'}, ...linked(data.said)) : null,
    data.detail ? h('div', {class: 'tooldetail'}, toolDetail(data.detail)) : null,
    state === 'waiting' ? answer
      : h('p', {class: 'said'}, h('i', {class: `i ${allowed ? 'i-check' : 'i-close'}`, 'aria-hidden': 'true'}), said),
    mode);
  return card;
}
const ELICITATION_SAID = {declined: 'Declined.', cancelled: 'Not answered: its turn ended first.',
  withdrawn: 'Withdrawn by the agent before an answer.', completed: 'Completed in the browser.',
  expired: 'Not answered in time, so nothing ran.'};
/* A question the agent put to the person, ACP's elicitation: who asks and what; a one-question form's choices as
 * buttons, with its free-text companion, as claude-agent-acp's "Other", as a field beside them; any other form as a
 * field per question; or a page to open, its full address and host shown, a warning on a host in another script, and
 * a link opened only by the person's own click. The answer goes as the person would write it at the node, through
 * dispatch permit, and the card then says what it became: answered, declined, withdrawn by the agent or completed. */
export function elicitationCard(line, work, tag, agent) {
  const data = line.data || {}, state = data.state || 'waiting';
  const fields = data.fields || [], questions = fields.filter(field => !field.note_of);
  const asker = data.subagent ? `${agentName(agent)}'s subagent ${data.subagent}` : agentName(agent);
  const send = async answer => {
    const controls = [...card.querySelectorAll('button, input, select')];
    for (const control of controls) control.disabled = true;
    const done = await wrote('/api/dispatch-permit', {work_id: work, request: data.request, option: answer});
    if (!done) { for (const control of controls) control.disabled = false; return; }
    card.classList.replace('waiting', 'answered');
    const said = done.action === 'decline' ? 'Declined by you.' : data.consent ? 'Allowed once by you.'
      : data.secret ? 'Answered by you.' : `${answer}: answered by you.`;
    fill(acts, h('p', {class: 'said'}, h('i', {class: 'i i-check', 'aria-hidden': 'true'}), said));
  };
  const decline = h('button', {type: 'button', class: 'btn sm danger',
    title: 'Do not answer; the agent goes on without it', onclick: () => send('decline')}, 'Decline');
  const acts = data.consent ? consentActs(data.consent, send, decline) : data.url ? pageActs(data, send, decline)
    : questions.length === 1 && (questions[0].choices || []).length && !questions[0].many
      ? choiceActs(questions[0], fields, send, decline)
      : formActs(fields, questions, data, send, decline);
  const said = state === 'answered' ? (data.consent ? 'Allowed once.'
    : data.secret || !data.answer ? 'Answered.' : `${data.answer}: answered.`)
    : (Object.hasOwn(ELICITATION_SAID, state) ? ELICITATION_SAID[state] : '') || state;
  const waiting = state === 'waiting', settled = state === 'answered' || state === 'completed';
  const card = h(tag, {class: `permission elicitation ${state}`, 'data-request': data.request},
    h('div', {class: 'ask'}, h('span', {class: 'eyebrow'}, waiting ? 'Waiting for your answer' : 'Question'),
      h('b', {}, data.consent ? `${asker} asks for your consent`
        : data.url ? `${asker} asks you to open a page` : `${asker} asks`)),
    h('p', {class: 'why'}, ...linked(data.message || '')),
    data.problem && waiting ? h('p', {class: 'hint'}, `The last answer could not be read: ${data.problem}.`) : null,
    data.deadline && waiting
      ? h('p', {class: 'hint'}, data.consent  // unanswered, a consent card is closed and its call refused
        ? `Unanswered by ${dated(data.deadline)}, it is closed and nothing runs.`
        : `It goes on without your answer at ${dated(data.deadline)}.`) : null,
    data.secret && waiting
      ? h('p', {class: 'hint'}, 'It asks for a secret: the answer is kept out of the thread.') : null,
    waiting ? acts
      : h('p', {class: 'said'}, h('i', {class: `i ${settled ? 'i-check' : 'i-close'}`, 'aria-hidden': 'true'}), said));
  return card;
}
/* A call of the agent's that is the person's decision, a consent card: the command it stands for, and Allow, which
 * runs it once, and Decline. The caution is the card's message. It is answered here alone, never at the map's node,
 * where agents write (UX review, person-consent F5). */
function consentActs(consent, send, decline) {
  return h('div', {class: 'answers', role: 'group', 'aria-label': 'Give or refuse your consent'},
    h('div', {class: 'address'}, h('p', {class: 'host'}, 'It runs, as if you ran it yourself:'),
      h('code', {class: 'url'}, consent.command || consent.tool || '')),
    h('button', {type: 'button', class: 'btn sm primary', title: 'You consent: it runs this once',
      onclick: () => send('accept')}, 'Allow once'),
    decline);
}
/* A page to open: its host, a warning when the host is written in another script, its full address, the link, and
 * Accept and Decline. */
function pageActs(data, send, decline) {
  const host = data.host || '';
  const coded = host.split('.').some(part => part.startsWith('xn--')) || /[^\x00-\x7f]/.test(host);
  const acts = h('div', {class: 'answers', role: 'group', 'aria-label': 'Answer the question'},
    h('a', {class: 'btn sm', href: data.url, target: '_blank', rel: 'noopener noreferrer',
      title: 'Open the page in a new tab; nothing opens it but you'},
    h('i', {class: 'i i-globe', 'aria-hidden': 'true'}), 'Open the page'),
    h('button', {type: 'button', class: 'btn sm primary', title: 'You consent: say so to the agent',
      onclick: () => send('accept')}, 'Accept'),
    decline);
  acts.prepend(h('div', {class: 'address'}, h('p', {class: 'host'}, 'Host: ', h('b', {}, host || 'none')),
    coded ? h('p', {class: 'warn'}, 'The host is written in another script: check it is the one you expect.') : null,
    h('code', {class: 'url'}, data.url)));
  return acts;
}
/* One question with choices: each a button, and its own-words companion as a field beside them. */
function choiceActs(question, fields, send, decline) {
  const own = fields.filter(field => field.note_of === question.key)[0];
  const sendOwn = () => { if (words.value.trim()) send(words.value.trim()); };
  const words = own ? h('input', {type: 'text', class: 'own',
    placeholder: own.description || own.title || 'Your own words', 'aria-label': own.title || 'Your own words',
    autocomplete: 'off', onkeydown: event => { if (event.key === 'Enter') sendOwn(); }}) : null;
  return h('div', {class: 'answers', role: 'group', 'aria-label': 'Answer the question'},
    question.choices.map(([, title]) => h('button', {type: 'button', class: 'btn sm',
      onclick: () => send(words && words.value.trim() ? `${title}, ${words.value.trim()}` : title)}, title)),
    words, words ? h('button', {type: 'button', class: 'btn sm primary', title: 'Answer in your own words',
      onclick: sendOwn}, 'Send') : null, decline);
}
/* Any other form: a field per question, sent as one `key: value` line for each field filled. */
function formActs(fields, questions, data, send, decline) {
  const takes = field => (field.choices || []).length ? (field.choices || []).map(([, title]) => title).join(', ')
    : field.note_of ? 'your own words' : field.type || 'text';
  const inputs = fields.map(field => {
    const label = field.note_of ? `${field.key} (${field.title})`
      : questions.length === 1 ? field.title : `${field.key} (${field.title})`;
    const input = (field.choices || []).length && !field.many
      ? h('select', {'data-key': field.key}, h('option', {value: ''}, '—'),
        field.choices.map(([, title]) => h('option', {value: title}, title)))
      : h('input', {type: data.secret && field.secret ? 'password' : 'text', 'data-key': field.key, autocomplete: 'off',
        placeholder: `${field.many ? 'any of ' : ''}${takes(field)}`, value: field.default ?? ''});
    return h('label', {class: 'field'}, h('span', {}, label, field.required ? ' *' : ''), input);
  });
  const submit = () => send(inputs.map(label => label.querySelector('[data-key]'))
    .filter(input => input.value.trim()).map(input => `${input.dataset.key}: ${input.value.trim()}`).join('\n'));
  return h('div', {class: 'answers form', role: 'group', 'aria-label': 'Answer the question'}, inputs,
    h('div', {class: 'row'}, h('button', {type: 'button', class: 'btn sm primary', onclick: submit}, 'Send'), decline));
}
/* One of ACP's session notices, the agent's own word on its state, such as an MCP server it could not start: a quiet
 * line by severity, info, warning or error, and any other severity plain. */
export function noticeRow(line) {
  const data = line.data || {};
  const severity = ['info', 'warning', 'error'].includes(data.severity) ? data.severity : 'other';
  return h('div', {class: `system agent-notice ${severity}`, role: severity === 'error' ? 'alert' : null},
    h('b', {}, data.title || 'Notice'), data.description ? ` ${data.description}` : '');
}
/* A signal a session raised, said in words; a permission waiting is its card, so it is not said twice. */
export function signalWords(text) {
  let found;
  try { found = JSON.parse(text); } catch { return text; }
  if (['permission-waiting', 'question-waiting'].includes(found.signal)) return null;
  return `Signal: ${String(found.signal || '').replace(/-/g, ' ')}${found.active === false ? ', cleared' : ''}.`;
}
/* The rows of a thread for keyedFill, in the order the session wrote them: the agent's words and the person's as
 * bubbles, its thinking folded to a few quiet lines that open on a click, each tool call one compact row, each
 * permission request a card with the agent's own options, and what Metaform said or noticed as a quiet line. The plan
 * is drawn apart, as a checklist; a turn's end and the session's state are not lines of the conversation. */
