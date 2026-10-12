/* Views the page draws for panes that have no part of the page as written: the questions waiting for the person,
 * the workflow runs with their pause, answer and resume, and the developer panes, which exist only while the page's
 * developer level is on (metaform web start --web-debug <level>). Each is {el, show}: a pane's section, and what
 * draws it as it shows. app.js lends the page's parts as `host`: h, fill, read, wrote, toast, confirmAct, select,
 * openMessages(record), project(), debug(), trace(). */
'use strict';

export function createViews(host) {
  const {h, fill} = host;
  const section = (id, label) => h('section', {class: 'pane', id, role: 'region', 'aria-label': label, hidden: true, tabindex: '-1'});
  const refusal = error => h('div', {class: 'failed', role: 'alert'}, h('p', {}, error.body?.error || error.message),
    error.body?.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, error.body.next)) : null);
  const when = text => { const at = new Date(text); return Number.isNaN(at.getTime()) ? String(text || '') : at.toLocaleString(); };

  /* ---------- Messages: what waits for the person at nodes, oldest first ---------- */
  const messages = {el: section('p-messages', 'Messages'), generation: 0};
  messages.show = async () => {
    const box = messages.el, generation = ++messages.generation;
    let found;
    try { found = (await host.read('messages', {open: true, limit: 0})).results || []; }
    catch (error) { if (generation === messages.generation) fill(box, refusal(error)); return; }
    if (generation !== messages.generation) return;
    fill(box, h('div', {class: 'eyebrow'}, 'Messages waiting for you'),
      found.length ? h('ul', {class: 'wsrows'}, found.map(record => h('li', {},
        h('button', {class: 'wsrow', type: 'button', title: 'Go to its node and read it', onclick: () => host.openMessages(record)},
          h('span', {class: `pill kind-${record.kind || 'message'}`}, record.kind || 'message'),
          h('span', {class: 'title'}, record.title || record.text || record.note || 'A message'),
          h('small', {}, record.node_address || record.address || '')))))
        : h('p', {class: 'empty'}, 'Nothing waits for you. Questions agents leave at nodes are listed here, oldest first.'));
  };

  /* ---------- Workflow runs: the open runs, and a run paused on the person answered and resumed ---------- */
  const STATE_WORDS = {submitted: 'Submitted', running: 'Running', waiting: 'Waiting on its calls', input_required: 'Waiting for you',
    completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled'};
  const runs = {el: section('p-runs', 'Workflow runs'), generation: 0, state: ''};
  runs.show = async () => {
    const box = runs.el, generation = ++runs.generation;
    let found;
    try { found = await host.read('workflow-runs', runs.state ? {state: runs.state} : {}); }
    catch (error) { if (generation === runs.generation) fill(box, refusal(error)); return; }
    if (generation !== runs.generation) return;
    const pick = h('select', {'aria-label': 'Runs shown', onchange: () => { runs.state = pick.value; runs.show(); }},
      h('option', {value: ''}, 'Open runs'), Object.entries(STATE_WORDS).map(([value, words]) => h('option', {value, selected: value === runs.state}, words)));
    if (!found.enabled) {
      fill(box, h('div', {class: 'eyebrow'}, 'Workflow runs'), h('p', {class: 'empty'}, 'Workflows are off in this project.'),
        h('p', {class: 'next'}, 'Next: ', h('code', {}, 'metaform enable workflow')));
      return;
    }
    const list = found.runs || [];
    fill(box, h('div', {class: 'wshead'}, h('div', {class: 'eyebrow'}, 'Workflow runs'), pick),
      list.length ? h('ul', {class: 'wsrows runs'}, list.map(drawRun)) : h('p', {class: 'empty'}, runs.state ? 'No run is in that state.' : 'No workflow run is open.'));
  };
  function drawRun(run) {
    const paused = run.state === 'input_required';
    const row = h('li', {class: `wsrun state-${run.state}`},
      h('div', {class: 'line'}, h('span', {class: `statechip ${run.state}`, title: `Its state: ${run.state}`}, STATE_WORDS[run.state] || run.state),
        h('code', {class: 'id'}, run.run), h('span', {class: 'kind'}, run.kind || ''), h('small', {}, when(run.updated))),
      run.message ? h('p', {class: 'reason'}, h('span', {class: 'k'}, paused ? 'What stopped it ' : 'Why '), run.message) : null,
      run.ticket ? h('p', {class: 'hint'}, `On ticket ${run.ticket}`) : null);
    if (paused) {
      const answer = h('textarea', {rows: 3, 'aria-label': `Your answer to run ${run.run}`, placeholder: 'Your answer, as the run asks it'});
      const resume = h('input', {type: 'checkbox', checked: Boolean(run.ticket), disabled: !run.ticket});
      const send = h('button', {class: 'btn primary sm', type: 'button', onclick: async () => {
        if (!answer.value.trim()) { answer.focus(); return host.toast('Write your answer first.'); }
        send.disabled = true;
        const done = await host.wrote('/api/workflow-answer', {run: run.run, answer: answer.value.trim(), resume: resume.checked});
        send.disabled = false;
        if (!done) return;
        host.toast(done.resumed ? `Answered; its agent is told to resume run ${run.run}.`
          : done.resume_error ? `Answered; its agent was not told: ${done.resume_error}` : done.next || 'Answered.');
        runs.show();
      }}, 'Answer');
      row.append(h('div', {class: 'answer'}, answer, h('div', {class: 'acts'},
        h('label', {class: 'check', title: run.ticket ? 'Send its agent the message to resume the run, as the person does' : 'No ticket\'s agent paused it: resume it yourself'}, resume, ' Tell its agent to resume'),
        send)));
    }
    if (!['completed', 'failed', 'cancelled'].includes(run.state)) {
      row.append(h('div', {class: 'acts'}, h('button', {class: 'btn sm danger', type: 'button', onclick: async () => {
        const reason = h('input', {type: 'text', 'aria-label': 'Why it is cancelled', placeholder: 'Why, kept with it'});
        if (!await host.confirmAct({title: `Cancel run ${run.run}?`, text: ['It stops, and so does every run below it; its caller receives the error cancelled.', reason],
          lost: ['The rest of its work, and of every run below it'], kept: ['What it recorded so far', 'Its record, marked cancelled, not completed'],
          verb: 'Cancel the run', cancel: 'Keep it'})) return;
        if (await host.wrote('/api/workflow-cancel', {run: run.run, reason: reason.value.trim()})) { host.toast(`Run ${run.run} is cancelled.`); runs.show(); }
      }}, 'Cancel run…')));
    }
    return row;
  }

  /* ---------- developer panes, with the developer level on ---------- */
  const prompts = {el: section('p-dev-prompts', 'Prompts sent'), generation: 0, filter: ''};
  prompts.show = async () => {
    const box = prompts.el, generation = ++prompts.generation;
    let found;
    try { found = await host.getJson(`/api/debug/prompts?project=${encodeURIComponent(host.project() || '')}`); }
    catch (error) { if (generation === prompts.generation) fill(box, refusal(error)); return; }
    if (generation !== prompts.generation) return;
    const list = h('div', {class: 'wsprompts'});
    const search = h('input', {type: 'search', placeholder: 'Find a prompt by its name, owner or words', 'aria-label': 'Find a prompt', value: prompts.filter,
      oninput: () => { prompts.filter = search.value; draw(); }});
    const draw = () => {
      const words = prompts.filter.trim().toLowerCase();
      const shown = found.prompts.filter(one => !words || `${one.owner} ${one.name} ${one.when} ${one.text}`.toLowerCase().includes(words));
      fill(list, shown.map(one => {
        const limit = one.budget?.limit, used = one.budget?.unit === 'characters' ? one.characters : one.bytes;
        return h('details', {class: 'entry'}, h('summary', {},
          h('span', {class: 'name'}, h('b', {}, one.owner), ` · ${one.name}`),
          h('span', {class: `size${limit && used > limit ? ' over' : ''}`}, limit ? `${used} of ${limit} ${one.budget.unit}` : `${one.bytes} bytes`)),
        h('dl', {class: 'facts'}, h('dt', {}, 'Source'), h('dd', {}, h('code', {}, one.source)),
          h('dt', {}, 'When sent'), h('dd', {}, one.when || 'No comment says.'),
          one.fills.length ? [h('dt', {}, 'Filled in'), h('dd', {}, one.fills.map(name => `<${name}/>`).join(' '))] : null,
          h('dt', {}, 'Budget'), h('dd', {}, one.budget ? `${one.budget.limit} ${one.budget.unit}, ${one.budget.of}` : 'None declared')),
        h('pre', {class: 'wstext', tabindex: '0'}, one.text || '(empty: sends nothing)'));
      }));
    };
    fill(box, h('div', {class: 'wshead'}, h('div', {class: 'eyebrow'}, `Prompts sent · ${found.prompts.length}, read-only`), search),
      h('p', {class: 'hint'}, `From the shipped prompt files of Metaform and ${found.modules.length} enabled modules, as they are sent; `
        + `the connect message holds ${found.connect.characters} of ${found.connect.limit} characters. A developer who wants other prompts writes a module.`),
      list);
    draw();
  };
  const traces = {el: section('p-dev-trace', 'Traces')};
  traces.show = () => {
    const box = traces.el, rows = host.trace();
    fill(box, h('div', {class: 'wshead'}, h('div', {class: 'eyebrow'}, `Traces · ${rows.length}, newest first`),
      h('button', {class: 'btn sm quiet', type: 'button', onclick: () => traces.show()}, 'Read again')),
    h('p', {class: 'hint'}, `Level ${host.debug()}: each read and write of the page with its status and time${host.debug() === 'trace' ? ', and its raw response' : ''}; `
      + `${host.debug() === 'info' ? 'verbose adds the events heard.' : 'the events heard are listed too.'}`),
    h('ol', {class: 'wstrace'}, [...rows].reverse().map(row => h('li', {class: `t-${row.kind}`},
      h('span', {class: 'at'}, new Date(row.at).toLocaleTimeString()), h('b', {}, row.kind), ' ', h('code', {}, row.what),
      row.status ? h('span', {class: `st${row.status >= 400 ? ' bad' : ''}`}, ` ${row.status}`) : null,
      row.ms !== undefined ? h('small', {}, ` ${row.ms} ms`) : null,
      row.raw ? h('details', {}, h('summary', {}, 'Raw'), h('pre', {class: 'wstext'}, row.raw)) : null))));
  };

  return {messages, runs, 'dev-prompts': prompts, 'dev-trace': traces};
}
