const $ = (id) => document.getElementById(id);
// The chair token arrives in the URL fragment (never sent to the server in the URL bar) and
// is kept for this tab only.
(() => {
  const m = location.hash.match(/token=([0-9a-fA-F]+)/);
  if (m) { try { sessionStorage.setItem("rt-token", m[1]); } catch {} history.replaceState(null, "", location.pathname); }
})();
const TOKEN = (() => { try { return sessionStorage.getItem("rt-token") || ""; } catch { return ""; } })();
const authed = (url, init = {}) => fetch(url, { ...init, headers: { ...(init.headers || {}), authorization: "Bearer " + TOKEN } });
// User-keyed dictionaries are Maps, so a seat named "__proto__" is just a name.
const state = { tables: new Map(), current: null, pinned: false, seen: new Set(), harnesses: [], live: new Set() };
// Harness models come from each harness's advertised options once its session opens; only
// OpenRouter models have a catalog to offer here (R §9.4).
const MODEL_HINTS = {};

function table(id) {
  if (!state.tables.has(id)) state.tables.set(id, { id, items: [], seats: new Map(), order: [], topic: "", status: "starting", jev: false, objective: "", base: 512 });
  return state.tables.get(id);
}

// acp-host events name the harness as a "table/seat" string; agent-monitor events carry a
// { pid, id } object whose id is that same string (or null when the host gave none).
function harnessId(data) {
  const h = data.harness;
  if (typeof h === "string") return h;
  if (h && typeof h.id === "string") return h.id;
  return null;
}

function tableOf(data) {
  if (data.table) return data.table;
  const h = harnessId(data);
  if (h && h.includes("/")) return h.split("/")[0];
  return null;
}

function seatOf(data) {
  if (data.seat) return data.seat;
  const h = harnessId(data);
  if (h && h.includes("/")) return h.split("/").slice(1).join("/");
  return null;
}

function apply(line) {
  const d = line.data || {}; const id = tableOf(d); if (!id) return;
  // Sequence numbers restart with each server run; table ids do not.
  const key = id + ":" + line.seq;
  if (state.seen.has(key)) return;
  state.seen.add(key);
  const t = table(id); const name = seatOf(d); const ev = line.event;
  const seat = (n) => { if (!t.seats.has(n)) { t.seats.set(n, { name: n, state: "starting", allowance: t.base, live: "", harness: "", prompts: [], monitor: "" }); t.order.push(n); } return t.seats.get(n); };
  const known = (n) => n && t.seats.has(n) ? t.seats.get(n) : null;
  const push = (item) => t.items.push(item);
  switch (ev) {
    case "roundtable.opened":
      if (!state.pinned && !line.replay) state.current = id;
      t.objective = d.objective; t.topic = d.topic; t.jev = d.jev_configured; t.status = "starting";
      t.base = d.base_allowance; t.seats.forEach(s => { s.allowance = t.base; });
      d.seats.forEach(s => { const x = seat(s.name); x.harness = s.harness + (s.settings.model ? " · " + s.settings.model : ""); });
      push({ kind: "opening", text: d.objective, workspace: d.workspace });
      // With no starting topic, topic #1 is the objective itself, shown just above.
      push({ kind: "divider", text: "Topic #1: " + (d.topic === d.objective ? "the objective" : d.topic) });
      break;
    case "roundtable.seat.ready": { const s = seat(name); s.state = "ready"; s.agent = d.name; s.protocol = d.protocol; t.status = "live"; push({ kind: "sys", text: `${name} joined as ${d.name} (ACP v${d.protocol})${d.tools ? "" : " · no Roundtable tools: harness lacks HTTP MCP"}` }); break; }
    case "roundtable.seat.failed": seat(name).state = "failed"; push({ kind: "sys", level: "bad", text: `${name} could not start: ${d.error}` }); break;
    case "roundtable.seat.gone": seat(name).state = "gone"; push({ kind: "sys", level: "bad", text: `${name} left: ${d.detail}` }); break;
    case "roundtable.floor": { const s = seat(name); s.state = "floor"; s.allowance = d.allowance; s.live = ""; break; }
    case "acp.agent.text": { const s = known(name); if (s && !d.thought && ["floor", "working", "reviewing"].includes(s.state)) s.live = (s.live + d.text).slice(-400); break; }
    case "acp.agent.tool": { const s = known(name); if (s && d.title) s.tool = d.title; break; }
    case "acp.permission": if (!d.allowed) push({ kind: "sys", level: "warn", text: `${name}: permission refused (${d.reason})` }); break;
    case "roundtable.contribution": {
      const s = seat(name); s.state = "ready"; s.live = "";
      if (d.accepted) s.allowance = t.base;
      push({ kind: d.accepted ? "msg" : "veto", seat: name, who: (t.seats.get(name) || {}).agent, id: d.id, text: d.text, judged: d.judged, after: d.after_work, truncated: d.truncated, limit: d.limit, reasons: d.reasons, note: d.note, scores: d.scores });
      break;
    }
    case "roundtable.pass": { const s = seat(name); s.state = "ready"; s.live = ""; push({ kind: "sys", text: `${name} passed` }); break; }
    case "roundtable.work.started": seat(name).state = "working"; push({ kind: "sys", text: `${name} is working in the workspace` }); break;
    case "roundtable.review": { const s = seat(name); s.state = "reviewing"; push({ kind: "sys", text: `${name} is the only one free and was asked to review the materials while the others work` }); break; }
    case "roundtable.background": { const s = seat(name); s.state = d.items ? "working" : "ready"; push({ kind: "sys", text: d.items ? `${name} reports ${d.items} background job${d.items > 1 ? "s" : ""} still running; its turns are skipped until they end` : `${name}'s background work ended` }); break; }
    case "roundtable.skipped": { push({ kind: "sys", text: `${name} skipped (${d.reason}); its next reply may use the larger limit` }); break; }
    case "roundtable.ratings.asked": push({ kind: "sys", text: `Rating round: ${d.seats.join(", ")} are rating each other` }); break;
    case "roundtable.rating": push({ kind: "sys", text: `${d.from_name} rated ${d.to_name}: ${d.points.toFixed(1)} points (${Object.entries(d.ratings).map(([k, v]) => k + " " + v).join(", ")})` }); break;
    case "roundtable.turn.failed": { const s = seat(name); if (s.state === "floor") s.state = "ready"; push({ kind: "sys", level: "warn", text: `${name}: turn failed: ${d.error}` }); break; }
    case "roundtable.topic.polling": push({ kind: "sys", text: `Topic complete. Asking ${d.seats.join(", ") || "nobody"} for the next topic…` }); break;
    case "roundtable.topic.proposed": push({ kind: "sys", text: `${name} proposes: ${d.text}` }); break;
    case "roundtable.topic": t.topic = d.topic; push({ kind: "divider", text: `Topic #${d.index}: ${d.topic}`, how: d.how }); break;
    case "roundtable.chair": push({ kind: "chair", text: d.text }); break;
    case "roundtable.held": t.status = d.held ? "held" : "live"; push({ kind: "sys", level: d.held ? "warn" : "", text: d.held ? "The chair is holding the table." : "The table resumed." }); break;
    case "roundtable.settings": t.jev = d.jev_configured; break;
    case "roundtable.feedback": push({ kind: "sys", text: `${d.from_name} rated ${d.to_name}: ${Object.entries(d.ratings).map(([k, v]) => k + " " + v).join(", ")}${d.note ? " · " + d.note : ""}` }); break;
    case "roundtable.notice": push({ kind: "sys", level: d.level === "error" ? "bad" : d.level === "warn" ? "warn" : "", text: d.text }); break;
    case "roundtable.ended": if (!line.replay) loadPast(); t.status = "ended"; t.seats.forEach(s => { if (s.state !== "gone") s.state = "ended"; }); push({ kind: "sys", level: "bad", text: `Table ended: ${d.reason}` }); break;
    // What each agent actually receives, exactly as sent (the participant prompt included).
    case "acp.prompt.sent": { const s = known(name); if (s) s.prompts.push(d.text); break; }
    // AgentSight (R §10.2). Failures already arrive as engine notices; this is status only.
    case "monitor.attached": { const s = known(name); if (s) s.monitor = `observing (${d.capture})`; push({ kind: "sys", text: `AgentSight is observing ${name} (${d.capture} capture)` }); break; }
    case "monitor.unavailable": { const s = known(name); if (s) s.monitor = "not observed"; break; }
    case "monitor.observation": { const s = known(name); if (s) s.monitor = `observed: ${d.comm} ${d.activity && (d.activity.op || d.activity.kind) || ""}`.trim(); break; }
    case "acp.prompt.completed": { const s = known(name); if (s && ["working", "reviewing"].includes(s.state)) s.state = "ready"; break; }
  }
  if (!state.current) state.current = id;
  scheduleRender();
}

let pending = false;
function scheduleRender() { if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; render(); }); } }

function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

// Rendering updates the page in place: the feed only appends new items, seat cards are built
// once and patched, and text is written only when it changed. Rebuilding nodes on every event
// would drop the reader's text selection, scroll position and open panels.
const view = { table: null, items: null, shown: 0, seats: new Map() };

function setText(node, text) { if (node.textContent !== text) node.textContent = text; }
function setClass(node, cls) { if (node.className !== cls) node.className = cls; }

function render() {
  const sel = $("tableSelect"); const ids = [...state.tables.keys()];
  const label = (id) => { const x = state.tables.get(id); const o = (x.objective || id).replace(/\s+/g, " "); return (o.length > 48 ? o.slice(0, 47) + "…" : o) + " · " + x.status; };
  const want = ids.map(label).join("|");
  if (sel.dataset.labels !== want) { sel.innerHTML = ""; ids.forEach(id => { const o = el("option", "", label(id)); o.value = id; sel.appendChild(o); }); sel.dataset.labels = want; }
  if (sel.value !== (state.current || "")) sel.value = state.current || "";
  const t = state.current && state.tables.get(state.current);
  const status = $("status");
  setText(status, t ? t.status : "no table"); setClass(status, "pill " + (t ? t.status : ""));
  if (!t) return;
  setText($("topic"), t.topic || "—");
  setText($("jevHint"), t.jev ? "JEV evaluates every message." : "JEV has no OpenRouter key: messages are not shared until a key is set.");
  setText($("holdBtn"), t.status === "held" ? "Resume" : "Hold");
  const closed = t.status === "ended" || t.status === "stopped";
  ["sendBtn", "holdBtn", "advanceBtn", "endBtn"].forEach(b => { if ($(b).disabled !== closed) $(b).disabled = closed; });
  if ($("guidance").disabled !== closed) $("guidance").disabled = closed;
  const placeholder = closed ? "This table is not running; you are reading its record." : "Guidance from the chair: delivered to every participant at its next turn";
  if ($("guidance").placeholder !== placeholder) $("guidance").placeholder = placeholder;
  document.querySelectorAll(".pastitem").forEach(b => b.classList.toggle("current", b.dataset.id === state.current));

  // A different table: start its seats and feed from scratch, once.
  const seats = $("seats"); const feed = $("feed");
  if (view.table !== t.id || view.items !== t.items) {
    view.table = t.id; view.items = t.items; view.shown = 0; view.seats = new Map();
    seats.textContent = ""; feed.textContent = "";
  }

  t.order.forEach(n => {
    const s = t.seats.get(n);
    let card = view.seats.get(n);
    if (!card) {
      card = { box: el("div", "seat"), state: el("span"), meta: el("div", "meta"), live: el("div", "live"), monitor: el("div", "meta"), details: null, shownPrompts: 0 };
      const top = el("div", "top"); top.appendChild(el("span", "name", n)); top.appendChild(card.state);
      card.box.append(top, card.meta, card.live, card.monitor);
      seats.appendChild(card.box); view.seats.set(n, card);
    }
    setClass(card.state, "state " + s.state); setText(card.state, s.state === "floor" ? "has the floor" : s.state);
    setText(card.meta, `${s.agent ? s.agent + " · " : ""}${s.harness || ""} · ${s.allowance ? s.allowance + " chars" : "no length limit"}`);
    const live = s.live || (s.tool && (s.state === "floor" || s.state === "working") ? "⚙ " + s.tool : "");
    setText(card.live, live); card.live.hidden = !live;
    setText(card.monitor, s.monitor ? "AgentSight: " + s.monitor : ""); card.monitor.hidden = !s.monitor;
    if (s.prompts.length && !card.details) {
      card.details = el("details", "prompts"); card.summary = el("summary");
      card.details.appendChild(card.summary); card.box.appendChild(card.details);
    }
    if (card.details) {
      setText(card.summary, `Prompts received (${s.prompts.length})`);
      for (; card.shownPrompts < s.prompts.length; card.shownPrompts++) {
        const k = card.shownPrompts;
        card.details.append(el("div", "hint", k === 0 ? "First turn" : `Prompt ${k + 1}`), el("pre", "prompt", s.prompts[k]));
      }
    }
  });

  const atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
  for (; view.shown < t.items.length; view.shown++) feed.appendChild(renderItem(t.items[view.shown]));
  if (atBottom) feed.scrollTop = feed.scrollHeight;
}

function renderItem(item) {
  switch (item.kind) {
    case "opening": { const b = el("div", "opening"); b.appendChild(el("strong", "", "Objective")); b.appendChild(el("div", "", item.text)); b.appendChild(el("div", "hint", "Workspace: " + item.workspace)); return b; }
    case "divider": { const d = el("div", "divider"); d.appendChild(el("span", "", item.text + (item.how ? `  (${item.how})` : ""))); return d; }
    case "msg": case "veto": {
      const m = el("div", "msg" + (item.kind === "veto" ? " veto" : "")); const who = el("div", "who");
      who.appendChild(el("b", "", item.who || item.seat)); if (item.who) who.appendChild(el("span", "badge", item.seat)); if (item.id) who.appendChild(el("span", "id", item.id));
      if (item.kind === "veto") who.appendChild(el("span", "badge", "vetoed: " + item.reasons.join("; ")));
      if (!item.judged && item.kind === "msg") who.appendChild(el("span", "badge", "unjudged"));
      if (item.after) who.appendChild(el("span", "badge", "after work"));
      // Length against the allowance it was measured by (Unicode characters, as the engine counts).
      const length = [...item.text].length;
      who.appendChild(el("span", "badge", item.limit ? `${length} / ${item.limit} chars` : `${length} chars`));

      m.appendChild(who); m.appendChild(el("div", "text", item.text));
      if (item.kind === "veto") m.title = item.note || ""; return m;
    }
    case "chair": { const m = el("div", "msg chair"); const who = el("div", "who"); who.appendChild(el("b", "", "Chair")); m.appendChild(who); m.appendChild(el("div", "text", item.text)); return m; }
    case "work": { const d = el("details", "sys"); d.appendChild(el("summary", "", `${item.seat} finished working`)); if (item.text) d.appendChild(el("div", "note", item.text)); return d; }
    default: return el("div", "sys " + (item.level || ""), item.text);
  }
}

async function post(url, body) {
  const r = await authed(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || r.statusText); return j;
}
const cmd = (body) => state.current && post(`/api/tables/${state.current}/command`, body).catch(e => alert(e.message));

$("tableSelect").onchange = (e) => { state.current = e.target.value; state.pinned = true; render(); };

// Past tables come from the records on disk, including earlier runs of the server.
async function loadPast() {
  const box = $("past");
  try {
    const [past, live] = await Promise.all([authed("/api/history").then(r => r.json()), authed("/api/tables").then(r => r.json())]);
    state.live = new Set(live.tables || []);
    box.innerHTML = "";
    if (!past.tables || !past.tables.length) { box.textContent = "No recorded tables yet."; return; }
    past.tables.forEach(p => {
      const b = el("button", "pastitem"); b.type = "button"; b.dataset.id = p.id;
      b.appendChild(el("span", "obj", (p.objective || p.id).replace(/\s+/g, " ")));
      const when = p.started_ms ? new Date(p.started_ms).toLocaleString() : "";
      const status = p.ended ? "ended" : state.live.has(p.id) ? "running" : "stopped";
      b.appendChild(el("span", "hint", `${when} · ${status} · ${p.contributions} accepted · ${p.topics} topic${p.topics == 1 ? "" : "s"}`));
      b.onclick = () => openPast(p.id);
      box.appendChild(b);
    });
    render();
  } catch (e) { box.textContent = "Could not load past tables: " + e.message; }
}

async function openPast(id) {
  state.current = id; state.pinned = true;
  const t = state.tables.get(id);
  if (!t || !t.items.length) {
    const r = await authed("/api/history/" + encodeURIComponent(id)).then(r => r.json());
    (r.events || []).forEach(line => apply({ ...line, replay: true }));
    const x = table(id);
    if (x.status !== "ended" && !state.live.has(id)) { x.status = "stopped"; x.seats.forEach(s => { if (s.state !== "gone") s.state = "stopped"; }); }
  }
  render();
}
$("sendBtn").onclick = () => { const v = $("guidance").value.trim(); if (v) { cmd({ kind: "guidance", text: v }); $("guidance").value = ""; } };
$("guidance").onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("sendBtn").click(); };
$("holdBtn").onclick = () => { const t = state.tables.get(state.current); cmd({ kind: t && t.status === "held" ? "resume" : "hold" }); };
$("advanceBtn").onclick = () => { const v = prompt("Next topic (leave empty to have everyone propose one):", ""); if (v !== null) cmd({ kind: "advance", text: v.trim() || null }); };
$("endBtn").onclick = () => { if (confirm("End this table? Every participant's harness is shut down.")) cmd({ kind: "end" }); };

function seatRow(seed = {}) {
  const row = el("div", "seatrow");
  const name = el("input"); name.placeholder = "Name"; name.value = seed.name || "";
  // Resume an earlier identity: its session continues, so the agent keeps its genesis name and
  // its profile (owner's AgentIdentity). The session lives in the harness that opened it.
  const identity = el("select"); identity.appendChild(el("option", "", "New agent"));
  identity.title = "Resume an earlier agent, so it keeps its name and its ratings";
  (state.identities || []).filter(x => x.context && x.context.session && x.context.harness).forEach((x, k) => {
    const o = el("option", "", `${x.name} (${x.ratings ? x.points + " pts" : "unscored"})`); o.value = String(k + 1); o.identity = x; identity.appendChild(o);
  });
  const harness = el("select"); const custom = el("option", "", "custom command…"); custom.value = "";
  state.harnesses.forEach(h => { const o = el("option", "", `${h.name}${h.available ? "" : " (unavailable)"}`); o.value = h.id; o.disabled = !h.available; harness.appendChild(o); });
  harness.appendChild(custom); harness.value = seed.harness ?? (state.harnesses.find(h => h.available)?.id || "");
  const model = el("input"); model.placeholder = "Model (optional)"; model.value = seed.model || ""; model.setAttribute("list", "modelHints");
  model.onfocus = async () => {
    const dl = $("modelHints"); dl.innerHTML = "";
    let names = MODEL_HINTS[harness.value];
    const opencode = /^opencode/.test(harness.value);
    if (!names && (opencode || harness.value === "pi-acp" || harness.value === "openrouter-acp" || /openrouter/.test(command.value))) {
      // OpenRouter models come from the published catalog, never a fixed list (R §9.4).
      if (!state.openrouterModels) { const r = await authed("/api/models").then(r => r.json()).catch(() => ({})); state.openrouterModels = (r.models || []).map(m => m.id); }
      // OpenCode names OpenRouter models with its provider prefix.
      names = opencode ? state.openrouterModels.map(m => "openrouter/" + m) : state.openrouterModels;
    }
    (names || []).forEach(m => { const o = el("option"); o.value = m; dl.appendChild(o); });
  };
  const command = el("input"); command.placeholder = "Custom ACP command"; command.value = seed.command || ""; command.disabled = harness.value !== "";
  // OpenRouter-model harnesses need the key to run at all.
  harness.onchange = () => { command.disabled = harness.value !== ""; if (harness.value === "openrouter-acp" || harness.value === "pi-acp") shareBox.checked = true; };
  // An OpenCode seat on an OpenRouter model needs the key too.
  model.onchange = () => { if (/^opencode/.test(harness.value) && model.value.startsWith("openrouter/")) shareBox.checked = true; };
  const share = el("label", "hint"); const shareBox = el("input"); shareBox.type = "checkbox"; shareBox.style.width = "auto"; shareBox.checked = !!seed.share;
  share.appendChild(shareBox); share.appendChild(document.createTextNode(" key")); share.title = "Give this agent the OpenRouter key (OpenRouter-model harnesses such as Pi)";
  identity.onchange = () => {
    const chosen = identity.selectedOptions[0].identity;
    if (!chosen) return;
    const ctx = chosen.context;
    if (state.harnesses.some(h => h.id === ctx.harness)) { harness.value = ctx.harness; command.value = ""; } else { harness.value = ""; command.value = ctx.harness; }
    command.disabled = harness.value !== "";
    model.value = (ctx.settings && ctx.settings.model) || "";
    if (!name.value) name.value = chosen.name;
  };
  const remove = el("button", "", "✕"); remove.type = "button"; remove.onclick = () => row.remove();
  const tail = el("div", "row"); tail.appendChild(share); tail.appendChild(remove);
  [name, identity, harness, model, command, tail].forEach(x => row.appendChild(x));
  row.read = () => {
    const chosen = identity.selectedOptions[0].identity;
    return { name: name.value.trim(), harness: harness.value || null, command: harness.value ? null : command.value.trim(), model: model.value.trim() || null, share_openrouter_key: shareBox.checked, resume_session: chosen ? chosen.context.session : null };
  };
  $("seatRows").appendChild(row);
}

async function loadHarnesses() {
  // Identities change after every table, so they are read each time the form opens.
  const ids = await authed("/api/identities").then(r => r.json());
  state.identities = ids.identities || [];
  if (ids.errors && ids.errors.length) alert("Some identity profiles could not be read:\n" + ids.errors.join("\n"));
  if (state.harnesses.length) return;
  const r = await authed("/api/harnesses").then(r => r.json());
  if (!r.harnesses) { alert("Open the page with the URL Roundtable printed at start (it carries the chair token)."); return; }
  state.harnesses = r.harnesses.sort((a, b) => (b.available - a.available) || (a.source === "builtin") - (b.source === "builtin") || a.name.localeCompare(b.name));
  $("harnessNote").textContent = r.note || `${r.harnesses.filter(h => h.available).length} harnesses available from ACP autoselection.`;
}

$("newBtn").onclick = async () => {
  await loadHarnesses();
  const f = $("newForm"); if (!$("seatRows").children.length) { seatRow({ name: "Seat 1" }); seatRow({ name: "Seat 2" }); }
  if (!f.workspace.value) f.workspace.value = "workspace";
  await fillFromSettings(f);
  $("newDialog").showModal();
};
// The form starts from the owner's saved settings (/settings), so a new table follows them
// unless the form is changed for that table.
async function fillFromSettings(f) {
  const r = await authed("/api/settings/list").then(r => r.json()).catch(() => null);
  if (!r || !r.settings) return;
  const value = (key) => (r.settings.find(s => s.key === key) || {}).value;
  const count = (v) => (v === "off" || v === undefined) ? "" : v;
  f.topics.checked = value("table.topics") === "on";
  f.base.value = count(value("limits.reply"));
  f.recovery.value = count(value("limits.recovery"));
  f.rounds.value = count(value("table.rounds"));
}
$("addSeat").onclick = () => seatRow({ name: "Seat " + ($("seatRows").children.length + 1) });
$("newForm").addEventListener("submit", () => { state.pinned = false; });
$("newForm").onsubmit = async (e) => {
  if (e.submitter && e.submitter.value !== "create") return;
  e.preventDefault(); const f = e.target;
  const body = {
    objective: f.objective.value, topic: f.topic.value || null, workspace: f.workspace.value,
    base_allowance: f.base.value ? Number(f.base.value) : null,
    recovery_allowance: Number(f.recovery.value) || 1024, rounds: f.rounds.value ? Number(f.rounds.value) : null, topics: f.topics.checked,
    seats: [...$("seatRows").children].map(r => r.read()),
  };
  $("createBtn").disabled = true;
  try { const r = await post("/api/tables", body); state.current = r.id; table(r.id); $("newDialog").close(); render(); }
  catch (err) { alert(err.message); } finally { $("createBtn").disabled = false; }
};

$("settingsBtn").onclick = async () => {
  const s = await authed("/api/settings").then(r => r.json());
  $("keyState").textContent = s.openrouter_key_set ? "A key is set." : "No key set.";
  $("settingsDialog").showModal();
};
$("settingsForm").onsubmit = async (e) => {
  if (e.submitter && e.submitter.value !== "save") return;
  e.preventDefault(); await post("/api/settings", { openrouter_key: e.target.key.value }); e.target.key.value = ""; $("settingsDialog").close();
};

if (!TOKEN) {
  $("feed").innerHTML = ""; $("feed").appendChild(el("div", "empty", "Open Roundtable with the URL it printed at start; that link carries the chair token for this run."));
} else {
  const source = new EventSource("/api/events?token=" + encodeURIComponent(TOKEN));
  source.onmessage = (m) => apply(JSON.parse(m.data));
  loadPast();
}
