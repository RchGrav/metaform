/* The chat's own commands, Call for the system agent, stops that land once a start answers, and chat on anything the
 * page shows. */
import '/page/app/dock/helpdesk.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/page/app/core/dom.js';
import {read} from '/page/app/core/reads.js';
import {DOCK, STANDBY, dockState, dockNote} from '/page/app/dock/embody.js';
import {openHelpdesk} from '/page/app/dock/threads.js';
import {drawHelpdesk} from '/page/app/dock/helpdesk.js';
import {reaching, startFailed, syncResume, stayedOff} from '/page/app/dock/send.js';
import {wrote} from '/page/app/board/history.js';
import {agentName, summonAgent} from '/page/app/agents/pickers.js';
import {isIntake, workPart} from '/page/app/session/tools.js';
import {showGallery} from '/page/app/session/apps.js';
import {commandsOf} from '/page/app/session/settings.js';
import {openIntakeChat, posted} from '/page/app/intake/intake.js';

/* The chat's own commands, offered with the agent's when the person types / in the message box. */
const DOCK_COMMANDS = [{name: 'help', description: "What the chat's commands do"},
  {name: 'list', description: 'The agents at work, numbered'},
  {name: 'chat', hint: '<number>', description: 'Talk with an agent at work, by its number in /list'},
  {name: 'system', description: 'Start a chat with your system agent'},
  {name: 'fork', hint: '[text]',
    description: 'A side conversation with the agent on view that knows all it knows, under Subagents'},
  {name: 'apps', description: 'The views the enabled modules offer, each opened in a panel'}];
export const dockOffered = () => {
  const agents = commandsOf(DOCK.target ? DOCK.state : null, DOCK.agent);
  const own = DOCK_COMMANDS.filter(one => !agents.some(agent => agent.name === one.name));
  return [...agents, ...own.map(one => ({...one, from: 'This chat'}))];
};
export async function dockCommand(text) {
  const [command, ...rest] = text.slice(1).trim().split(/\s+/);
  // a command the agent on view offers is the agent's: it goes to the agent as the message it is
  if (DOCK.target && commandsOf(DOCK.state, DOCK.agent).some(one => one.name === command)) {
    if (await wrote('/api/dispatch-message', {work_id: DOCK.target, session: DOCK.session, text})) drawHelpdesk();
    return;
  }
  if (Object.hasOwn(CHAT_COMMANDS, command)) return CHAT_COMMANDS[command](text, command, rest);
  dockNote(`${text} is not a command here. Type /help.`);
}
/* What each of the chat's own commands does: (text, command, rest). */
const CHAT_COMMANDS = {
  help: () => dockNote('/list shows the agents at work · /chat <number> talks with one of them · /system calls '
    + 'your system agent · /fork [text] starts a side conversation with the agent on view · /apps lists the views the '
    + "modules offer · the agent's own commands are offered as you type /."),
  list: listAgents,
  chat: (text, command, rest) => chatWith(rest[0]),
  system: () => callSystem(),
  fork: (text, command) => forkSession(text.slice(1).trim().slice(command.length).trim()),
  apps: () => showGallery(),
};
async function listAgents() {
  let found = [];
  try { found = (await read('dispatch-sessions', {thread: 'false'})).sessions || []; }
  catch (error) { return dockNote(error.message); }
  DOCK.list = found.filter(one => one.state === 'running');
  const line = (one, index) => `${index + 1}. ${agentName(one.agent)} on ${workPart(one.work_id)}`
    + (one.activity ? ' · ' + one.activity : '');
  return dockNote(DOCK.list.length ? DOCK.list.map(line).join('\n') : 'No agent is at work right now.');
}
async function chatWith(number) {
  const chosen = DOCK.list[Number(number) - 1];
  if (!chosen) return dockNote('Type /list first, then /chat with the number of the agent.');
  openHelpdesk(chosen.work_id, `${agentName(chosen.agent)} on ${workPart(chosen.work_id)}`,
    'It answers when its current step ends.', chosen.session_id, null, {focus: true});
  return dockNote(`You are now talking with ${DOCK.label}. Its work goes on while you talk.`);
}
/* A fork keeps the session's whole conversation and leaves the session at its work; what follows /fork, when anything
 * does, is its first turn, and it shows under Subagents once its agent has made it. */
async function forkSession(first) {
  if (!DOCK.target || !DOCK.live) {
    return dockNote('A fork is made of an agent at work: open its thread, then type /fork.');
  }
  const done = await posted('/api/dispatch-fork', {work_id: DOCK.target, session: DOCK.session,
    ...(first ? {text: first} : {})});
  return dockNote(done.ok ? 'The fork was made; its thread is under Subagents.'
    : `${done.body?.error || 'The fork was not made.'}${done.body?.next ? ` Next: ${done.body.next}` : ''}`);
}
/* Call: the person's system agent starts with the agent and settings chosen in the line at the top, resuming the
 * last conversation while Resume is checked, which the server's system chat does. A start that fails says why in
 * the chat, and what was written for it goes back into the box. */
export async function callSystem() {
  syncResume();
  dockState($('#dock').className.startsWith('open') ? $('#dock').className : 'open');
  Object.assign(DOCK, {since: Date.now(), waiting: STANDBY});
  $('#helpdesk .call').textContent = 'Dismiss';
  const call = DOCK.calling = {};
  drawHelpdesk();  // the chat says it is reaching the agent, where its first words will come
  const agent = summonAgent();
  const done = await posted('/api/system-chat', agent ? {agent} : {});
  const started = done.ok ? done.body : null;
  if (DOCK.calling !== call) {  // dismissed while it was being reached: it is stopped as soon as it answers
    if (started) stayedOff(await stopOnceStarted(started.work_id));
    return null;
  }
  DOCK.calling = null;
  if (!started) {
    $('#helpdesk .call').textContent = DOCK.target ? 'Dismiss' : 'Call';
    startFailed(done.body?.error || 'The agent did not start.', done.body?.next);
    return null;
  }
  DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, 'your system agent', STANDBY, started.session_id, 'system');
  reaching(started);
  return started;
}
/* An agent dismissed while it was being reached is still starting when the start answers, and a stop sent then finds
 * nothing to stop yet: it is stopped once its session is there, looked for every half second for up to half a
 * minute, or not at all when its start failed. */
async function stopOnceStarted(work) {
  for (let tries = 0; tries < 60; tries++) {
    let rows = [];
    try { rows = (await read('dispatch-sessions', {id: work, thread: 'false'})).sessions || []; } catch { rows = []; }
    if (rows.some(one => one.state === 'running')) return wrote('/api/dispatch-stop', {work_id: work});
    const failedNow = one => /^it (failed|did not start)/.test(one.how || '')
      && Date.now() - Date.parse(one.started || '') < 60000;
    if (rows.some(failedNow)) return null;
    await new Promise(wait => setTimeout(wait, 500));
  }
  return null;
}
/* Chat on anything the page shows, VIEW-042: a ticket, open or done, a node, a question, or an agent's session. An
 * agent at work on it is talked to directly; otherwise one starts to talk, and Dismiss stops it. */
export async function talkAbout(given, label) {
  // an intake's agent is a conversation already, never a ticket: its chat opens on its session
  if (isIntake(given.id)) return openIntakeChat(given.id, null);
  const agent = summonAgent();  // the agent a new chat starts with; one at work on it is talked to as it is
  DOCK.talking = true;  // a message written meanwhile waits for this start, and starts no other
  let done;
  try { done = await posted('/api/talk', {...given, ...(agent ? {agent} : {})}); } finally { DOCK.talking = false; }
  const started = done.ok ? done.body : null;
  if (!started) {
    startFailed(done.body?.error || 'The agent did not start.', done.body?.next);
    return null;
  }
  if (started.conversation) DOCK.mine = started.work_id;
  openHelpdesk(started.work_id, label, started.state === 'running' ? 'It answers when its current step ends.' : STANDBY,
    started.session_id, started.conversation ? 'conversation' : null);
  reaching(started);
  return started;
}
