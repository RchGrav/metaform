// The roundtable's page: the tables, opening one, and a table live with its stats and data. Every address is
// relative, so the token in the page's own address carries to every call. Text from the store is set as text, never
// as markup. Seats are named in text; nothing is told apart by colour.
'use strict';

const main = document.getElementById('main');
let leave = () => {};  // what the view in place stops when another replaces it: its event stream, its timer

// ------------------------------------------------------------------------------------------------ helpers

function el(tag, props, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const kid of kids.flat(Infinity)) if (kid !== null && kid !== undefined && kid !== false)
    node.append(kid instanceof Node ? kid : String(kid));
  return node;
}

function put(node, ...kids) {  // a node's children replaced, lists flattened and empty places left out
  node.replaceChildren(...kids.flat(Infinity).filter((kid) => kid !== null && kid !== undefined && kid !== false)
    .map((kid) => kid instanceof Node ? kid : String(kid)));
}

async function api(path, body) {
  const asked = body === undefined ? {} :
    {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
  const answer = await fetch('api/' + path, asked);
  const type = answer.headers.get('Content-Type') || '';
  const data = type.includes('json') ? await answer.json() : await answer.text();
  if (!answer.ok) throw new Error(typeof data === 'string' ? data : data.error || answer.statusText);
  return data;
}

const dollars = (value) => value === null || value === undefined ? '' :
  '$' + (value >= 0.01 || value === 0 ? value.toFixed(2) : value.toFixed(4));
const count = (value) => value === null || value === undefined ? '' : Number(value).toLocaleString('en-US');
const scores = (list) => list ? '[' + list.map((one) => one.toFixed(2)).join(', ') + ']' : '';
const when = (stamp) => stamp ? stamp.replace('T', ' ').replace('+00:00', ' UTC') : '';
const perMillion = (price) => price === null || price === undefined ? '' : '$' + +(price * 1e6).toFixed(3);

function facts(pairs) {
  return el('dl', {class: 'facts'}, pairs.filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([name, value]) => [el('dt', {text: name}), el('dd', {}, value)]));
}

function notice(text, error) {
  return el('div', {class: 'notice' + (error ? ' error' : ''), role: error ? 'alert' : 'status', text});
}

function failing(action) {
  return async (event) => {
    const button = event && event.currentTarget;
    if (button) button.disabled = true;
    try { await action(event); } catch (error) { main.prepend(notice(error.message, true)); }
    finally { if (button) button.disabled = false; }
  };
}

const STAGES = {discussion: 'discussion', synthesis: 'synthesis', ranking: 'ranking', top_three: 'top three',
                bottom_three: 'bottom three', host_summary: 'host summary', report: 'report'};

function stageText(table) {  // a table with topics: its open topic and the stage it is at
  return table.stage ? `topic ${table.topic.number} of ${table.topic.of}, ${STAGES[table.stage] || table.stage}` : '';
}

function limitsText(table) {
  if (table.imported) return 'not capped (imported)';
  return `${table.rounds} rounds, ${dollars(table.spend)}`;
}

// ------------------------------------------------------------------------------------------------ the tables

async function showTables() {
  await drawTables();
  const timer = setInterval(() => drawTables().catch(() => {}), 5000);
  leave = () => clearInterval(timer);
}

async function drawTables() {
  const {tables} = await api('tables');
  const rows = tables.map((one) => el('tr', {},
    el('td', {}, el('a', {href: `#/table/${one.number}`, text: one.number})),
    el('td', {}, el('a', {href: `#/table/${one.number}`, text: one.subject}),
       one.imported ? el('div', {class: 'soft small', text: 'imported'}) : null),
    el('td', {}, one.state, one.stage ? el('div', {class: 'soft small', text: stageText(one)}) : null),
    el('td', {class: 'small', text: one.seats.join(', ')}),
    el('td', {class: 'num', text: one.imported ? one.round : `${one.round} of ${one.rounds}`}),
    el('td', {class: 'num', text: one.imported ? dollars(one.spent) : `${dollars(one.spent)} of ${dollars(one.spend)}`}),
    el('td', {class: 'small', text: when(one.created)}),
    el('td', {class: 'small', text: when(one.ended)})));
  put(main, 
    el('h1', {text: 'Tables'}),
    el('p', {}, el('a', {href: '#/open', text: 'Open a table'})),
    tables.length ? el('div', {class: 'scroll panel'}, el('table', {},
      el('thead', {}, el('tr', {}, ['Table', 'Subject', 'State', 'Seats', 'Rounds', 'Spend', 'Started', 'Ended']
        .map((name) => el('th', {class: ['Rounds', 'Spend'].includes(name) ? 'num' : null, text: name})))),
      el('tbody', {}, rows))) : el('p', {class: 'soft', text: 'No tables yet.'}));
}

// ------------------------------------------------------------------------------------------------ opening a table

async function showOpen() {
  const [limits, {agents}] = await Promise.all([api('limits'), api('agents')]);
  const chosen = [];  // the seats in speaking order: {id, label}
  const picked = el('ol', {class: 'picked'});
  const reporter = el('select', {id: 'reporter'});

  function redraw() {
    put(picked, ...chosen.map((seat, at) => el('li', {},
      el('span', {text: seat.label === seat.id ? seat.id : `${seat.label} (${seat.id})`}), ' ',
      el('button', {type: 'button', 'aria-label': `Move ${seat.id} up`, disabled: at === 0,
                    onclick: () => { chosen.splice(at - 1, 0, ...chosen.splice(at, 1)); redraw(); }}, 'Up'), ' ',
      el('button', {type: 'button', 'aria-label': `Move ${seat.id} down`, disabled: at === chosen.length - 1,
                    onclick: () => { chosen.splice(at + 1, 0, ...chosen.splice(at, 1)); redraw(); }}, 'Down'), ' ',
      el('button', {type: 'button', 'aria-label': `Remove ${seat.id}`,
                    onclick: () => { chosen.splice(at, 1); redraw(); }}, 'Remove'))));
    if (!chosen.length) picked.append(el('li', {class: 'soft', text: 'No seats yet: add them below, in the order they speak.'}));
    const was = reporter.value;
    put(reporter, el('option', {value: '', text: `The reporter setting, ${limits.reporter}, when it is seated; else the first seat that can`}),
      ...chosen.filter((seat) => !seat.id.startsWith('agent:')).map((seat) => el('option', {value: seat.id, text: seat.id})));
    reporter.value = chosen.some((seat) => seat.id === was) ? was : '';
  }

  function add(id, label) {
    if (!chosen.some((seat) => seat.id === id)) chosen.push({id, label: label || id});
    redraw();
  }

  // the harness agents found here, with the models each offered when last read over ACP
  const harness = el('div', {});
  function drawAgents(list) {
    put(harness, ...list.map((agent) => {
      const models = el('div', {class: 'row'});
      const read = el('button', {type: 'button', disabled: !agent.found, onclick: failing(async () => {
        read.textContent = 'Reading…';
        try {
          const answer = await api(`agents/${agent.agent}/models`, {});
          agent.models = answer.models; agent.read = answer.read;
          drawAgents(list);
        } finally { read.textContent = 'Read its models over ACP'; }
      })}, 'Read its models over ACP');
      for (const model of agent.models || [])
        models.append(el('button', {type: 'button', onclick: () => add(`acp:${agent.agent}/${model.value}`,
          `${agent.agent} ${model.name}`)}, `Add ${model.name}`));
      return el('div', {class: 'panel'},
        el('h3', {text: agent.agent === 'claude' ? 'Claude Code' : agent.agent === 'codex' ? 'Codex' : agent.agent}),
        el('div', {class: 'small soft', text: agent.found ? `Found on this machine; started by ${agent.command}` :
          `Not found on this machine (${agent.command})`}),
        el('div', {class: 'small soft', text: agent.read ? `Models as it offered them at ${when(agent.read)}` :
          'Its models have not been read yet.'}),
        models, el('div', {class: 'row'}, read));
    }));
  }
  drawAgents(agents);

  // OpenRouter's model list, searchable
  const search = el('input', {type: 'search', id: 'search', placeholder: 'Search OpenRouter models', 'aria-label': 'Search OpenRouter models'});
  const only = {images: el('input', {type: 'checkbox', id: 'images'}), caches: el('input', {type: 'checkbox', id: 'caches'})};
  const list = el('div', {class: 'list'}, el('p', {class: 'soft', text: 'Reading OpenRouter’s model list…'}));
  let models = [];
  function drawModels() {
    const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
    const found = models.filter((one) => words.every((word) => (one.id + ' ' + one.name).toLowerCase().includes(word)) &&
      (!only.images.checked || one.images) && (!only.caches.checked || one.caches));
    put(list, el('table', {},
      el('thead', {}, el('tr', {}, el('th', {text: 'Model'}), el('th', {class: 'num', text: 'Prompt'}),
        el('th', {class: 'num', text: 'Completion'}), el('th', {class: 'num', text: 'Cache read'}),
        el('th', {class: 'num', text: 'Context'}), el('th', {text: 'Images'}), el('th', {text: 'Caches'}), el('th', {}))),
      el('tbody', {}, found.slice(0, 100).map((one) => el('tr', {},
        el('td', {}, one.id, el('div', {class: 'small soft', text: one.name})),
        el('td', {class: 'num', text: perMillion(one.prompt)}), el('td', {class: 'num', text: perMillion(one.completion)}),
        el('td', {class: 'num', text: perMillion(one.cache_read)}), el('td', {class: 'num', text: count(one.context)}),
        el('td', {text: one.images ? 'yes' : 'no'}), el('td', {text: one.caches ? 'yes' : 'no'}),
        el('td', {}, el('button', {type: 'button', onclick: () => add(one.id)}, 'Add')))))),
      el('p', {class: 'small soft', text: `${found.length} of ${models.length} models` +
        (found.length > 100 ? '; the first 100 are shown, search to narrow them' : '') +
        '. Prices are US dollars per million tokens.'}));
  }
  search.addEventListener('input', drawModels);
  only.images.addEventListener('change', drawModels);
  only.caches.addEventListener('change', drawModels);
  api('models').then((answer) => { models = answer.models; drawModels(); })
    .catch((error) => put(list, notice(`OpenRouter’s model list was not read: ${error.message}`, true)));

  const other = el('input', {id: 'other', placeholder: 'agent:<name>, a2a:<peer>, or any seat', 'aria-label': 'Another seat'});
  const subject = el('input', {id: 'subject', placeholder: 'from the opening when left empty'});
  const opening = el('textarea', {id: 'opening', placeholder: 'the Roundtable 2 opening when left empty and the table has topics'});
  const topics = el('textarea', {id: 'topics', placeholder: limits.topics.map((one) => one.name).join('\n')});
  const single = el('input', {type: 'checkbox', id: 'single'});
  const host = el('input', {id: 'host', placeholder: `${limits.host} when Codex offers it`});
  const synthesizer = el('input', {id: 'synthesizer', placeholder: 'the host when left empty'});
  const rounds = el('input', {id: 'rounds', type: 'number', min: 1, max: limits.rounds, value: limits.rounds});
  const spend = el('input', {id: 'spend', type: 'number', min: 0, max: limits.spend, step: '0.01', value: limits.spend});
  const folder = el('input', {id: 'folder', value: limits.folder});
  const told = el('div', {});

  const open = el('button', {type: 'submit', class: 'main'}, 'Open the table');
  const form = el('form', {onsubmit: failing(async (event) => {
    event.preventDefault();
    put(told, );
    open.disabled = true;
    try {
      const named = topics.value.split('\n').map((one) => one.trim()).filter(Boolean);
      const answer = await api('open', {subject: subject.value, opening: opening.value, seats: chosen.map((seat) => seat.id),
        rounds: rounds.value, spend: spend.value, reporter: reporter.value, folder: folder.value,
        topics: single.checked ? [] : named.length ? named : null, host: host.value, synthesizer: synthesizer.value});
      put(told, notice(`Table ${answer.discussion} is open. Its chair token, for an agent to chair it over MCP: ${answer.chair}` +
        (answer.notices ? '. ' + answer.notices.join(' ') : '')));
      setTimeout(() => { location.hash = `#/table/${answer.discussion}`; }, 1200);
    } catch (error) {
      put(told, notice(error.message, true));
    } finally { open.disabled = false; }
  })},
    el('label', {for: 'subject', text: 'Subject'}), subject,
    el('label', {for: 'opening', text: 'Opening'}), opening,
    el('label', {for: 'topics', text: 'Topics, in the order they open: one per line, a Roundtable 2 topic by its name or any topic\u2019s text (empty: the three Roundtable 2 topics)'}), topics,
    el('div', {class: 'row'}, single, el('label', {for: 'single', text: 'No topics: discuss the opening alone, with no synthesis, ranking or host'})),
    el('div', {class: 'row'}, el('label', {for: 'host', text: 'Host'}), host,
       el('label', {for: 'synthesizer', text: 'Synthesizer'}), synthesizer),
    el('h2', {text: 'Seats, in speaking order'}), picked,
    el('label', {for: 'reporter', text: 'Reporter'}), reporter,
    el('h2', {text: 'Limits'}),
    el('div', {class: 'row'}, el('label', {for: 'rounds', text: `Rounds, at most ${limits.rounds}`}), rounds,
       el('label', {for: 'spend', text: `Spend in US dollars, at most ${dollars(limits.spend)}`}), spend),
    el('label', {for: 'folder', text: 'Folder the ACP seats read in'}), folder,
    el('p', {}, open), told,
    el('h2', {text: 'What can sit'}),
    el('h3', {text: 'Harness agents on this machine'}), harness,
    el('h3', {text: 'OpenRouter models'}),
    limits.openrouter_key ? null : notice('OPENROUTER_API_KEY is not set where this server runs; Jev and every model seat need it.', true),
    el('div', {class: 'row'}, search, only.images, el('label', {for: 'images', text: 'takes images'}),
       only.caches, el('label', {for: 'caches', text: 'caches'})), list,
    el('h3', {text: 'Another seat'}),
    el('div', {class: 'row'}, other, el('button', {type: 'button', onclick: () => { if (other.value.trim()) add(other.value.trim()); other.value = ''; }}, 'Add')),
    limits.peers.length ? el('p', {class: 'small soft', text: `A2A peers named in the settings: ${limits.peers.join(', ')}`}) : null);
  redraw();
  put(main, el('h1', {text: 'Open a table'}), form);
}

// ------------------------------------------------------------------------------------------------ a table

async function showTable(number, tab) {
  let table = await api(`tables/${number}`);
  let latest = 0;
  const tabs = {live: 'Live', stats: 'Stats', data: 'Data'};
  const head = el('div', {});
  const body = el('div', {});
  const transcript = el('div', {id: 'transcript'});
  const turnOf = el('p', {id: 'turn-of'});

  function drawHead() {
    put(head, 
      el('h1', {text: `Table ${table.number}: ${table.subject}`}),
      table.imported_from ? el('p', {class: 'small soft', text: `Imported from ${table.imported_from.from}, where it was table ${table.imported_from.number}. Its record is only read.`}) : null,
      table.unpaid ? notice(table.reason, true) : null,
      facts([['State', table.state + (table.reason ? `: ${table.reason}` : '')],
             ['Topic', table.stage ? `${table.topic.number} of ${table.topic.of}: ${table.topic.title}` : null],
             ['Stage', table.stage ? STAGES[table.stage] || table.stage : null],
             ['Round', table.imported ? `${table.round}` : `${table.round} of ${table.rounds}` + (table.stage ? ' on this topic' : '')],
             ['Spent', table.imported ? dollars(table.spent) : `${dollars(table.spent)} of ${dollars(table.spend)}`],
             ['Limits', limitsText(table)],
             ['Seats', table.seats.join(', ')], ['Reporter', table.reporter],
             ['Host', table.host], ['Synthesizer', table.synthesizer],
             ['Started', when(table.created)], ['Ended', when(table.ended)],
             ['Runner', table.imported ? null : table.runner],
             ['Report error', table.report_error]]),
      el('div', {class: 'panel small'}, el('b', {text: 'Legend. '}), table.legend.scores,
        table.legend.failed ? el('div', {text: table.legend.failed}) : null),
      el('div', {class: 'tabs', role: 'tablist'}, Object.entries(tabs).map(([key, name]) =>
        el('button', {role: 'tab', 'aria-selected': String(key === tab), onclick: () => { location.hash = `#/table/${number}/${key}`; }}, name))));
  }

  function turnNode(turn) {
    const parts = [el('b', {text: turn.turn}), turn.topic ? ` · topic ${turn.topic}` : '', ` · round ${turn.round} · `,
      el('b', {text: turn.seat}), ` · ${turn.outcome}`];
    if (turn.scores) parts.push(` · ${scores(turn.scores)}`);
    if (turn.failed && turn.failed.length) parts.push(` · failed: ${turn.failed.join(', ')}`);
    const use = [];
    if (turn.prompt_tokens !== undefined) use.push(`${count(turn.prompt_tokens)} prompt tokens`);
    if (turn.cached_tokens !== undefined) use.push(`${count(turn.cached_tokens)} cached`);
    if (turn.cost !== undefined) use.push(dollars(turn.cost));
    if (turn.jev_cost !== undefined) use.push(`Jev ${dollars(turn.jev_cost)}`);
    if (turn.model) use.push(turn.model);
    const node = el('div', {class: 'turn', 'data-n': turn.n}, el('div', {class: 'head'}, parts));
    if (turn.entered) node.append(el('div', {class: 'text', text: turn.text}));
    else if (turn.text) node.append(el('details', {}, el('summary', {text: 'Its text'}), el('div', {class: 'text', text: turn.text})));
    if (turn.reason) node.append(el('div', {class: 'small soft', text: turn.reason}));
    if (turn.truncated) node.append(el('details', {}, el('summary', {text: 'Truncated to 512; its full original'}), el('div', {class: 'text', text: turn.original})));
    if (use.length) node.append(el('div', {class: 'small soft', text: use.join(' · ')}));
    return node;
  }

  async function moreTurns() {
    const answer = await api(`tables/${number}/turns?since=${latest}`);
    for (const old of transcript.querySelectorAll('[data-unjudged]')) old.remove();
    for (const turn of answer.turns) {
      const node = turnNode(turn);
      if (turn.outcome === 'unjudged') node.setAttribute('data-unjudged', '');
      if (turn.outcome === 'comment' && chair) chair.entered(turn);
      transcript.append(node);
    }
    latest = Math.max(latest, answer.latest);
  }

  function drawTurnOf() {
    const stage = table.stage && table.stage !== 'discussion' ? ` (${STAGES[table.stage] || table.stage})` : '';
    turnOf.textContent = table.turn_of ? `${table.state === 'held' ? 'Held; next' : 'Now'}: ${table.turn_of}'s turn${stage}` :
      table.state === 'ending' ? 'Ending: the report is being written.' : '';
  }

  // What each topic's stages gave, under the transcript: why its discussion ended, the synthesis with its ideas, every
  // seat's ranking and explanations, the host's summary, and the Borda count, which is derived.
  const staged = el('div', {id: 'topics'});
  async function drawTopics() {
    if (!table.stage) return;
    const {topics} = await api(`tables/${number}/topics`);
    const answer = (one) => el('div', {class: 'turn'}, el('div', {class: 'head'}, el('b', {text: one.name}),
      one.ranking ? ` · ${one.ranking.join(', ')}` : one.error ? ` · ${one.error}` : ''),
      one.text && !one.ranking ? el('div', {class: 'text', text: one.text}) : null,
      one.truncated ? el('details', {}, el('summary', {text: 'Cut to its limit; its full original'}), el('div', {class: 'text', text: one.original})) : null);
    put(staged, topics.filter((topic) => topic.opened).map((topic) => el('div', {class: 'panel'},
      el('h3', {text: `Topic ${topic.number}: ${topic.title}`}),
      topic.why ? el('p', {class: 'small soft', text: `Its discussion ended: ${topic.why}`}) : null,
      topic.synthesis ? [el('h3', {text: `Synthesis by ${topic.synthesis.name}`}),
        topic.synthesis.ideas.length ? el('ol', {}, topic.synthesis.ideas.map((idea) => el('li', {}, el('b', {text: `${idea.id} ${idea.name}`}), ` ${idea.summary}`)))
          : el('div', {class: 'text', text: topic.synthesis.text})] : null,
      topic.rankings.length ? [el('h3', {text: 'Rankings, best first'}), topic.rankings.map(answer)] : null,
      topic.borda ? el('p', {class: 'small soft', text: `${topic.borda.label} Order: ${topic.borda.order.join(', ')}.`}) : null,
      topic.top_three.length ? [el('h3', {text: 'Top three'}), topic.top_three.map(answer)] : null,
      topic.bottom_three.length ? [el('h3', {text: 'Bottom three'}), topic.bottom_three.map(answer)] : null,
      topic.host_summary ? [el('h3', {text: `Host summary by ${topic.host_summary.name}`}),
        el('div', {class: 'text', text: topic.host_summary.text || topic.host_summary.error || ''})] : null)));
  }

  // The chair's panel is made once; a change only sets its buttons and shows or hides the comment block, so what the
  // chair is typing survives every turn that lands. A comment sent waits in a line under it until its turn arrives.
  function chairPanel() {
    if (table.imported) return null;
    const said = el('textarea', {id: 'comment', 'aria-label': 'Comment', placeholder: 'A comment, entered at the next gap between turns, never judged'});
    const problem = el('div', {});
    const waits = el('div', {id: 'comment-waiting'});
    const events = el('div', {id: 'events'});  // what is going wrong, told to the chair alone, never to a seat or Jev
    const out = el('div', {id: 'seats-out'});  // seats degraded, unavailable or gone, each with its reseat
    const waiting = [];  // the comments sent and not yet entered, oldest first
    let sending = false;
    function drawWaiting() {
      put(waits, waiting.map((text) => el('div', {class: 'small soft', text: `Waiting for the next gap between turns: ${text}`})));
    }
    const act = (action, body) => async () => {
      sending = true;
      set();
      try {
        const given = typeof body === 'function' ? body() : body || {};
        const answer = await api(`tables/${number}/${action}`, given);
        put(problem);
        for (const old of main.querySelectorAll('.notice[role="status"]')) old.remove();
        if (action === 'comment') {
          if (said.value === given.text) said.value = '';
          waiting.push(given.text.trim());
          drawWaiting();
        } else head.after(notice(`${action}: the table is ${answer.state}.`));
        await refresh();
      } catch (error) {
        put(problem, notice(error.message, true));
      } finally {
        sending = false;
        set();
      }
    };
    const hold = el('button', {type: 'button', onclick: act('hold')}, 'Hold');
    const go = el('button', {type: 'button', onclick: act('continue')}, 'Continue');
    const end = el('button', {type: 'button', onclick: act('end')}, 'End');
    const advance = el('button', {type: 'button', onclick: act('advance'), hidden: !table.stage},
      'End this topic\u2019s discussion');
    const send = el('button', {type: 'button', onclick: act('comment', () => ({text: said.value}))}, 'Comment');
    const commenting = el('div', {}, el('label', {for: 'comment', text: 'Comment'}), said, el('div', {class: 'row'}, send), waits);
    function set() {
      const closed = table.state === 'ended' && !table.report_error;
      hold.disabled = sending || closed || table.state !== 'running';
      go.disabled = sending || closed || table.state === 'ended';
      end.disabled = sending || closed;
      end.textContent = table.state === 'ended' ? 'Ask for the report again' : 'End';
      advance.disabled = sending || table.state === 'ended' || table.stage !== 'discussion' || !!table.advance_asked;
      send.disabled = sending;
      commenting.hidden = table.state === 'ended';
      const ailing = table.seats_detail.filter((seat) => seat.gone || seat.availability.state !== 'active');
      put(out, ailing.length ? [el('h3', {text: 'Seats not well'}), ailing.map((seat) => el('div', {class: 'row small'},
        el('b', {text: seat.name}), ` ${seat.gone ? 'left' : seat.availability.state}: ${seat.gone || seat.availability.reason || ''}`,
        el('button', {type: 'button', disabled: sending || table.state === 'ended',
          onclick: act('reseat', {seat: seat.seat})}, 'Reseat')))] : null);
      put(events, table.events.length ? [el('h3', {text: 'Operational events'}), table.events.map((one) =>
        el('div', {class: 'small'}, el('b', {text: one.kind.replace('_', ' ')}), ` · ${when(one.created)} · ${one.text}`))] : null);
    }
    function entered(turn) {  // a comment's turn arrived: its waiting line goes
      const at = waiting.indexOf(turn.text);
      if (at >= 0) { waiting.splice(at, 1); drawWaiting(); }
    }
    set();
    return {panel: el('div', {class: 'panel', id: 'chair'}, el('h3', {text: 'The chair'}),
      el('div', {class: 'row'}, hold, go, advance, end), problem, out, events, commenting), set, entered};
  }
  let chair = null;

  let pending = Promise.resolve();
  function refresh() {  // one at a time, so a turn is never added twice
    pending = pending.then(refreshNow, refreshNow);
    return pending;
  }

  async function refreshNow() {
    table = await api(`tables/${number}`);
    drawHead();
    drawTurnOf();
    if (tab === 'live') {
      if (chair) chair.set();
      await moreTurns();
      await drawTopics();
    }
  }

  async function drawLive() {
    chair = chairPanel();
    put(body, turnOf, chair && chair.panel, el('h2', {text: 'Transcript'}),
      el('div', {class: 'panel'}, el('h3', {text: 'Opening'}), el('div', {class: 'text', text: table.opening})), transcript,
      table.stage ? [el('h2', {text: 'Topics and their stages'}), staged] : null);
    drawTurnOf();
    await moreTurns();
    await drawTopics();
    if (table.state === 'ended' && (table.imported || table.export)) return;
    const stream = new EventSource(`api/tables/${number}/events`);
    stream.addEventListener('change', () => refresh().catch(() => {}));
    const was = leave;
    leave = () => { stream.close(); was(); };
  }

  async function drawStats() {
    const stats = await api(`tables/${number}/stats`);
    const questions = Object.keys(stats.excluded_by);  // the nouls the table judged on, and repeat
    const seats = el('table', {},
      el('thead', {}, el('tr', {}, ['Seat', 'Asked', 'Ran', 'Kept / taken', 'Outcomes', ...questions.map((one) => `Excluded: ${one}`),
        'Prompt tokens', 'Cached', 'Cache write', 'Cache hits', 'Cost', 'Jev'].map((name) => el('th', {text: name})))),
      el('tbody', {}, stats.seats.map((seat) => el('tr', {},
        el('td', {}, el('b', {text: seat.name}), el('div', {class: 'small soft', text: `${seat.seat} (${seat.kind})`}),
          seat.gone ? el('div', {class: 'small', text: `left: ${seat.gone}`}) : null),
        el('td', {class: 'small', text: seat.asked}),
        el('td', {class: 'small', text: seat.ran.join(', ') || 'not recorded'}),
        el('td', {class: 'num', text: `${seat.kept} / ${seat.taken}`}),
        el('td', {class: 'small', text: Object.entries(seat.outcomes).map(([key, value]) => `${key} ${value}`).join(', ')}),
        ...questions.map((one) => el('td', {class: 'num', text: seat.excluded_by[one] ?? 'unknown'})),
        el('td', {class: 'num', text: seat.turns_with_use ? count(seat.prompt_tokens) : ''}),
        el('td', {class: 'num', text: seat.turns_with_use ? count(seat.cached_tokens) + (seat.cached_share !== undefined && seat.cached_share !== null ? ` (${Math.round(seat.cached_share * 100)}%)` : '') : ''}),
        el('td', {class: 'num', text: seat.turns_with_use ? count(seat.cache_write_tokens) : ''}),
        el('td', {class: 'num', text: seat.turns_with_use ? `${seat.cache_hits} of ${seat.turns_with_use}` : ''}),
        el('td', {class: 'num', text: seat.turns_with_use ? dollars(seat.cost) : ''}),
        el('td', {class: 'num', text: seat.jev_cost ? dollars(seat.jev_cost) : ''})))));
    const sessions = stats.seats.filter((seat) => seat.session_reported);
    const filter = el('select', {id: 'per-turn-seat', 'aria-label': 'Seat'}, el('option', {value: '', text: 'every seat'}),
      stats.seats.map((seat) => el('option', {value: seat.name, text: seat.name})));
    const perTurn = el('div', {class: 'scroll'});
    function drawPerTurn() {
      const rows = stats.per_turn.filter((one) => !filter.value || one.seat === filter.value);
      put(perTurn, el('table', {},
        el('thead', {}, el('tr', {}, ['Turn', 'Round', 'Seat', 'Outcome', 'Model', 'Prompt tokens', 'Cached', 'Cache write', 'Cost', 'Jev']
          .map((name) => el('th', {text: name})))),
        el('tbody', {}, rows.map((one) => el('tr', {},
          el('td', {text: `T${String(one.n).padStart(2, '0')}`}), el('td', {class: 'num', text: one.round}), el('td', {text: one.seat}),
          el('td', {text: one.outcome}), el('td', {class: 'small', text: one.model || ''}),
          el('td', {class: 'num', text: count(one.prompt_tokens)}), el('td', {class: 'num', text: count(one.cached_tokens)}),
          el('td', {class: 'num', text: count(one.cache_write_tokens)}), el('td', {class: 'num', text: dollars(one.cost)}),
          el('td', {class: 'num', text: dollars(one.jev_cost)}))))));
    }
    filter.addEventListener('change', drawPerTurn);
    drawPerTurn();
    put(body, 
      el('h2', {text: 'The table'}),
      facts([['Turns', stats.turns], ['Outcomes', Object.entries(stats.outcomes).map(([key, value]) => `${key} ${value}`).join(', ')],
             ['Vetoes by question', questions.map((one) => `${one} ${stats.excluded_by[one] ?? 'unknown'}`).join(', ')],
             ['Spent through OpenRouter', dollars(stats.spent)], ['Seats’ cost', dollars(stats.cost)], ['Jev’s cost', dollars(stats.jev_cost)],
             ['Prompt tokens', count(stats.prompt_tokens)], ['Cached tokens', count(stats.cached_tokens)],
             ['Cache write tokens', count(stats.cache_write_tokens)], ['Turns with a cache hit', stats.cache_hits]]),
      stats.not_recorded ? el('div', {class: 'panel small'}, el('b', {text: 'Not recorded for this table'}),
        el('ul', {}, stats.not_recorded.map((one) => el('li', {text: one})))) : null,
      el('p', {class: 'small soft', text: 'A vetoed turn counts once under each question it failed. An OpenRouter seat’s prompt tokens include its cached ones; Claude Code counts its input without its cache reads and writes. An ACP seat’s cost is its agent’s notional figure on the person’s subscription.'}),
      el('h2', {text: 'Each seat'}), el('div', {class: 'scroll panel'}, seats),
      sessions.length ? [el('h2', {text: 'Claude Code and Codex sessions, as each agent reported at its end'}),
        el('div', {class: 'scroll panel'}, el('table', {},
          el('thead', {}, el('tr', {}, ['Seat', 'Model', 'Last turn', 'Session tokens', 'Session cost'].map((name) => el('th', {text: name})))),
          el('tbody', {}, sessions.map((seat) => {
            const said = seat.session_reported, tokens = said.tokens || {}, spent = said.spent || {};
            return el('tr', {}, el('td', {text: seat.name}), el('td', {text: said.model || ''}),
              el('td', {class: 'small', text: `${count(tokens.input_tokens)} input, ${count(tokens.cached_read_tokens)} cache read, ` +
                `${count(tokens.cached_write_tokens)} cache write, ${count(tokens.output_tokens)} output`}),
              el('td', {class: 'num', text: count(spent.tokens)}),
              el('td', {class: 'num', text: spent.cost ? dollars(spent.cost.amount) : 'not reported'}));
          }))))] : null,
      el('h2', {text: 'Each turn'}), el('div', {class: 'row'}, el('label', {for: 'per-turn-seat', text: 'Seat'}), filter), perTurn);
  }

  async function drawData() {
    const report = el('div', {});
    const context = el('div', {});
    const choose = el('select', {id: 'context-seat', 'aria-label': 'Seat'},
      table.seats_detail.map((seat) => el('option', {value: seat.position, text: `${seat.name} (${seat.seat})`})));
    async function drawContext() {
      const seat = table.seats_detail.find((one) => String(one.position) === choose.value);
      put(context, el('p', {class: 'soft', text: 'Reading…'}));
      const {turns} = await api(`tables/${number}/seats/${seat.position}/context`);
      const parts = [el('p', {class: 'small soft', text: `Every message the table sent ${seat.name}, exactly as sent, and what ${seat.name} replied.` +
        (seat.kind === 'acp' ? ' As a Claude Code or Codex session it also had its harness’s own context, which is not shown.' : '')})];
      turns.forEach((turn, at) => {
        if (turn.received !== undefined) parts.push(el('h3', {text: `Turn ${at + 1}: arrived`}), el('pre', {text: turn.received}));
        if (turn.replied !== undefined) {
          const what = turn.n ? ` (T${turn.n}, round ${turn.round}: ${turn.outcome}${turn.scores ? ', ' + scores(turn.scores) : ''})` : '';
          parts.push(el('h3', {text: `Turn ${at + 1}: ${seat.name} replied${what}`}), el('pre', {text: turn.replied}));
        }
      });
      if (!turns.length) parts.push(el('p', {class: 'soft', text: 'Nothing has been sent to this seat yet.'}));
      put(context, ...parts);
    }
    choose.addEventListener('change', () => drawContext().catch((error) => put(context, notice(error.message, true))));
    const files = [['discussion.json', 'The discussion: the table, the legend, the summary and every turn'],
                   ['all-in-one.json', 'All in one: the discussion and every seat’s file'],
                   ['export.json', 'The export, as the table writes it beside the report'],
                   ...table.seats_detail.map((seat) => [`seat-${seat.position}.json`, `${seat.file}: ${seat.name}’s own file, every turn it received and replied`])];
    put(body, 
      el('h2', {text: 'Downloads'}),
      el('ul', {}, files.map(([file, what]) => el('li', {}, el('a', {href: `api/tables/${number}/download/${file}`, download: true, text: what}))),
        table.report ? el('li', {}, el('a', {href: `api/tables/${number}/report`, download: `${table.number}-${table.subject}.md`, text: 'The report, as Markdown'})) : null),
      el('h2', {text: 'Each seat’s context as it arrived'}), el('div', {class: 'row'}, el('label', {for: 'context-seat', text: 'Seat'}), choose), context,
      el('h2', {text: 'The report'}), report,
      el('h2', {text: 'The rules, as the table stated them'}), el('pre', {text: table.rules}),
      table.imported_from && table.imported_from.what_happened ? [el('h2', {text: 'What happened'}),
        el('ul', {}, table.imported_from.what_happened.map((one) => el('li', {text: one})))] : null);
    async function drawReport() {
      if (table.report) put(report, el('pre', {class: 'report', text: await api(`tables/${number}/report`)}));
      else put(report, el('p', {class: 'soft', text: table.report_error || 'No report has been written yet.'}));
    }
    await drawReport();
    await drawContext();
    if (table.report || table.imported || table.state === 'ended' && table.export) return;
    const stream = new EventSource(`api/tables/${number}/events`);  // the report, when it is written
    stream.addEventListener('change', failing(async () => {
      table = await api(`tables/${number}`);
      drawHead();
      if (table.report || table.state === 'ended') { stream.close(); await drawReport(); }
    }));
    const was = leave;
    leave = () => { stream.close(); was(); };
  }

  drawHead();
  put(main, head, body);
  if (tab === 'stats') await drawStats();
  else if (tab === 'data') await drawData();
  else await drawLive();
}

// ------------------------------------------------------------------------------------------------ the views

async function route() {
  leave();
  leave = () => {};
  const [, view, number, tab] = (location.hash.replace(/^#/, '') || '/').split('/');
  try {
    if (view === 'open') await showOpen();
    else if (view === 'table' && number) await showTable(Number(number), tab || 'live');
    else await showTables();
  } catch (error) {
    put(main, notice(error.message, true));
  }
}

window.addEventListener('hashchange', route);
route();
