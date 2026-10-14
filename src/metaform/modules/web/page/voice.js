/* Voice: speak instead of typing, in every box where a person writes to an agent.
 *
 * A mic sits beside the chat's compose box, and beside any field marked data-voice, such as the mascot's reply field.
 * Click it to start or stop listening; hold Ctrl+Space (or Option+Space on a Mac) to talk while held, or tap it to
 * start and tap again to stop. What is said appears in the box as it is said, editable; voice_send review leaves it
 * there for Enter, auto sends it after a pause. Escape while listening stops and drops what was not yet heard.
 *
 * Which engine hears is the voice module's choice, /api/voice/status: Whisper on this machine's server when it serves
 * speech well, or Whisper in this page's own worker, voice-worker.js, on WebGPU or WebAssembly; the person's own
 * transcription endpoint, or the browser's speech service, only when chosen. A model is downloaded once, after the
 * person agrees to its size. Silence is never sent: a simple voice activity detector in the page keeps only speech,
 * with a short lead-in. Partial results come about once a second while the person speaks, each a quick pass of the
 * utterance so far; the final pass replaces them when the utterance ends.
 *
 * The control is quiet until used. While listening, a soft ring follows the voice's level, eased like a spring; under
 * reduced motion it holds still. */

const SR = 16000;                 // Whisper's sample rate
const FRAME = 4096;               // samples per capture block at the device's rate, about 85 ms at 48 kHz
const LEAD = 0.35;                // seconds kept before speech starts, so the first syllable is not cut
const HANG = 1.2;                 // seconds of silence that end an utterance while listening hands-free
const AUTO_PAUSE = 1.4;           // seconds of quiet after the last words before auto sends
const PARTIAL_EVERY = 1000;       // ms between partial passes while speaking
const TAP = 350;                  // ms: a shorter press of the key starts hands-free listening instead of holding
const FIELDS = '#helpdesk .say, .mascot-bubble input.reply, textarea[data-voice], input[data-voice]';
const WAKE_HEAD = 2.5;            // seconds of each stretch of speech heard for the wake phrase; the rest is never heard
const WAKE_WAIT = 8000;           // ms after a bare wake phrase in which the next words are the message
const WAKE_LONGEST = 12;          // seconds: a stretch longer than this is let go without being heard
const MIC = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"/></svg>';
const MAC = /Mac|iPhone|iPad/.test(navigator.userAgentData?.platform || navigator.platform || '');
export const VOICE_KEY = MAC ? 'Ctrl+Space or ⌥Space' : 'Ctrl+Space';

const V = {
  status: null, engine: 'off', why: '', variant: 'wasm', ready: false,
  field: null, button: null, mode: null,         // the box being spoken into, its mic, and 'hold' or 'free'
  stream: null, audio: null, node: null, source: null,
  floor: 0.003, level: 0, shown: 0, velocity: 0, frame: 0,
  lead: [], segment: null, speaking: false, quiet: 0, lastVoice: 0,
  base: '', live: '', writing: false, busy: false, lastPartial: 0, finals: Promise.resolve(),
  worker: null, loaded: null, asks: new Map(), next: 0,
  recognition: null, pressed: 0, clip: null, sendTimer: 0, timings: [],
};
// The wake phrase: on, the microphone stays open and each stretch of speech has only its first seconds heard, here,
// for the phrase; what follows the phrase goes to the person's system agent. The indicator shows while it is on.
const W = {on: false, suspended: false, phrase: '', armed: 0, heard: Promise.resolve(), indicator: null, talking: false};
// Speech out: the replies of the agent the person talks to, spoken in their mascot's voice.
const T = {seen: new Map(), spoken: new Set(), timer: 0, queue: Promise.resolve(), audio: null, stopNow: null};
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const el = (tag, attrs = {}, html = '') => Object.assign(document.createElement(tag), attrs, html ? {innerHTML: html} : {});

/* ---------- which engine hears, and whether this browser can run it ---------- */
async function readStatus() {
  try {
    const answer = await fetch('/api/voice/status', {cache: 'no-store'});
    V.status = answer.ok ? await answer.json() : null;
    if (!answer.ok) V.why = (await answer.json().catch(() => ({}))).error || 'Voice is not on here.';
  } catch { V.status = null; V.why = 'Voice could not reach the server.'; }
  return V.status;
}
async function webgpu() {
  try { return Boolean(navigator.gpu && await navigator.gpu.requestAdapter()); } catch { return false; }
}
async function chooseEngine() {
  const st = V.status;
  if (!st || st.available === false) return {engine: 'off', why: st?.why || V.why || 'Voice is not on here.', hidden: true};
  if (st.chosen === 'off') return {engine: 'off', why: st.why, hidden: true};
  const speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!navigator.mediaDevices?.getUserMedia && st.engine !== 'browser-speech')
    return {engine: 'off', why: 'The microphone needs a secure page: open Metaform at 127.0.0.1, localhost or https.'};
  if (st.engine === 'browser-speech')
    return speech ? {engine: 'browser-speech', why: st.why} : {engine: 'off', why: 'This browser has no speech service; choose another voice_engine.'};
  if (st.engine === 'browser') {
    if (typeof WebAssembly !== 'object' || typeof Worker !== 'function')
      return {engine: 'off', why: 'This browser cannot run Whisper: it has no WebAssembly.'};
    let forced = null;
    try { forced = localStorage.getItem('metaform.voice.device'); } catch { /* storage may be blocked */ }
    V.variant = forced === 'wasm' || forced === 'webgpu' ? forced : (await webgpu() ? 'webgpu' : 'wasm');
    return {engine: 'browser', why: `${st.why} It runs on ${V.variant === 'webgpu' ? 'WebGPU' : 'WebAssembly'}.`};
  }
  return {engine: st.engine, why: st.why};
}

/* ---------- the mic beside each box ---------- */
function micFor(field) {
  if (field.dataset.voiceMic) return;
  field.dataset.voiceMic = '1';
  const button = el('button', {type: 'button', className: 'voice-mic', title: `Speak (hold ${VOICE_KEY})`},
    `<span class="voice-halo" aria-hidden="true"></span><span class="voice-ring" aria-hidden="true"></span>${MIC}`);
  button.setAttribute('aria-label', `Speak into this box; hold ${VOICE_KEY} to talk`);
  button.setAttribute('aria-pressed', 'false');
  button.setAttribute('aria-keyshortcuts', MAC ? 'Control+Space Alt+Space' : 'Control+Space');
  button.addEventListener('pointerdown', event => event.preventDefault());  // the box keeps the focus, and stays open
  button.addEventListener('click', event => { event.preventDefault(); toggle(field, button); });
  const send = field.closest('form')?.querySelector('.send, [type=submit]');
  if (send && send.parentElement === field.parentElement) send.before(button); else field.after(button);
  paintMic(button);
  field.addEventListener('input', () => {  // the person's own edit while listening: what they wrote stands
    if (V.writing || V.field !== field) return;
    V.base = field.value; V.live = '';
  });
}
function paintMic(button) {
  const off = V.engine === 'off';
  button.hidden = Boolean(V.hiddenWhy);
  button.disabled = off;
  button.classList.toggle('voice-off', off);
  button.title = off ? V.why : `Speak (hold ${VOICE_KEY}) · ${V.why}`;
}
function attach(root = document) {
  for (const field of root.querySelectorAll(FIELDS)) micFor(field);
}

/* ---------- consent: a model is downloaded once, after the person agrees to its size ---------- */
const mb = bytes => bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;
function need() {
  const st = V.status;
  if (V.engine === 'server' && st.server.installed && !st.server.downloaded)
    return {engine: 'server', model: st.server.model, size: st.server.size,
      where: "this machine's Metaform home", key: `server:${st.server.model}`};
  if (V.engine === 'browser') {
    const it = st.browser[V.variant];
    if (!it.present) return {engine: 'browser', model: st.browser.model, variant: V.variant, size: it.to_download,
      where: "this Metaform's home, and this browser keeps a copy", key: `browser:${st.browser.model}:${V.variant}`};
  }
  return null;
}
function ask(button, missing) {
  return new Promise(done => {
    document.querySelector('.voice-ask')?.remove();
    const box = el('div', {className: 'voice-ask', role: 'dialog'});
    box.setAttribute('aria-label', 'Download a speech model');
    box.innerHTML = `<p><b>Voice needs Whisper ${missing.model}</b>, ${mb(missing.size)}.</p>
      <p>It downloads once from Hugging Face into ${missing.where}. What you say stays on this device.</p>
      <div class="voice-bar" hidden><span></span></div>
      <div class="voice-acts"><button type="button" class="btn sm quiet voice-no">Not now</button><button type="button" class="btn sm primary voice-yes">Download ${mb(missing.size)}</button></div>`;
    place(box, button);
    const finish = value => { box.classList.add('leaving'); setTimeout(() => box.remove(), reduced() ? 0 : 220); done(value); };
    box.querySelector('.voice-no').onclick = () => finish(false);
    box.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); finish(false); } });
    box.querySelector('.voice-yes').onclick = async () => {
      const yes = box.querySelector('.voice-yes'), bar = box.querySelector('.voice-bar');
      yes.disabled = true; yes.textContent = 'Downloading…'; bar.hidden = false;
      const watch = setInterval(async () => {
        const st = await readStatus();
        const progress = st && (missing.engine === 'server' ? st.server.downloading : st.browser[missing.variant]?.downloading);
        if (progress?.total) bar.firstElementChild.style.width = `${Math.round(100 * progress.done / progress.total)}%`;
      }, 600);
      try {
        const answer = await fetch('/api/voice/download', {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({engine: missing.engine, model: missing.model, variant: missing.variant})});
        const said = await answer.json().catch(() => ({}));
        clearInterval(watch);
        if (!answer.ok) { note(said.error || 'The model did not download.'); return finish(false); }
        await readStatus();
        finish(true);
      } catch (error) { clearInterval(watch); note(String(error.message || error)); finish(false); }
    };
    box.querySelector('.voice-yes').focus();
  });
}
function place(box, button) {
  document.body.append(box);
  const at = button.getBoundingClientRect(), width = Math.min(300, innerWidth - 16);
  box.style.width = `${width}px`;
  box.style.left = `${Math.max(8, Math.min(innerWidth - width - 8, at.right - width))}px`;
  box.style.bottom = `${Math.max(8, innerHeight - at.top + 8)}px`;
  requestAnimationFrame(() => box.classList.add('shown'));
}
let noteTimer = 0;
function note(text) {
  let box = document.querySelector('.voice-note');
  if (!box) { box = el('div', {className: 'voice-note', role: 'status'}); document.body.append(box); }
  box.textContent = text;
  const button = V.button || document.querySelector('.voice-mic');
  if (button) {
    const at = button.getBoundingClientRect();
    box.style.right = `${Math.max(8, innerWidth - at.right)}px`;
    box.style.bottom = `${Math.max(8, innerHeight - at.top + 8)}px`;
  }
  box.classList.add('shown');
  clearTimeout(noteTimer);
  noteTimer = setTimeout(() => box.classList.remove('shown'), 4500);
}

/* ---------- listening ---------- */
async function toggle(field, button) {
  if (V.field) return stop(false);
  return start(field, button, 'free');
}
async function start(field, button, mode) {
  if (V.engine === 'off' || V.field) return;
  const missing = need();
  if (missing && !(await ask(button, missing))) return;
  if (W.on && !W.suspended) { W.suspended = true; closeMic(); }  // one microphone: the box has it while spoken into
  Object.assign(V, {field, button, mode, base: field.value, live: '', clip: null, segment: null, speaking: false,
    lead: [], quiet: 0, busy: false, lastPartial: 0});
  if (V.base && !/\s$/.test(V.base)) V.base += ' ';
  button.classList.add('listening');
  button.setAttribute('aria-pressed', 'true');
  field.classList.add('voice-live');
  clearTimeout(V.sendTimer);
  try {
    if (V.engine === 'browser-speech') return listenWithBrowser();
    if (V.engine === 'browser') warmWorker();
    await openMic();
  } catch (error) {
    stop(true);
    note(error?.name === 'NotAllowedError' ? 'The microphone was not allowed. Allow it in the browser to speak.'
      : `The microphone could not open: ${error?.message || error}`);
  }
}
async function stop(cancel) {
  const field = V.field, button = V.button;
  if (!field) return;
  if (V.recognition) { const it = V.recognition; V.recognition = null; try { it.stop(); } catch { /* ended */ } }
  if (V.segment && !cancel && V.speaking) finishSegment();
  else V.segment = null;
  closeMic();
  V.field = null;
  V.speaking = false;
  button?.classList.remove('listening', 'speaking');
  button?.setAttribute('aria-pressed', 'false');
  if (button) button.style.removeProperty('--voice-level');
  await V.finals;
  if (cancel) { V.live = ''; write(field); }
  field.classList.remove('voice-live', 'voice-partial');
  if (!cancel && V.status?.send === 'auto' && field.value.trim()) submitSoon(field, 0);
  field.focus();
  if (W.on && W.suspended) { W.suspended = false; openMic().catch(() => wakeOff('The microphone could not open again.')); }
}
async function openMic() {
  V.stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true,
    noiseSuppression: true, autoGainControl: true}});
  const Context = window.AudioContext || window.webkitAudioContext;
  V.audio = new Context();
  V.source = V.audio.createMediaStreamSource(V.stream);
  V.node = V.audio.createScriptProcessor(FRAME, 1, 1);
  V.node.onaudioprocess = event => hear(event.inputBuffer.getChannelData(0), V.audio.sampleRate);
  V.source.connect(V.node);
  V.node.connect(V.audio.destination);  // a processor runs only while connected; it writes silence
  if (!reduced()) V.frame = requestAnimationFrame(meter);
}
function closeMic() {
  cancelAnimationFrame(V.frame);
  try { V.node?.disconnect(); V.source?.disconnect(); } catch { /* already */ }
  V.stream?.getTracks().forEach(track => track.stop());
  V.audio?.close().catch(() => {});
  Object.assign(V, {stream: null, audio: null, node: null, source: null, level: 0, shown: 0, velocity: 0});
}

/* The block of audio just captured: resampled to 16 kHz, weighed for speech, kept only while speaking. */
function resample(input, rate) {
  if (rate === SR) return Float32Array.from(input);
  const ratio = rate / SR, out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {  // the mean of each span: a low-pass and a decimation in one
    const from = Math.floor(i * ratio), to = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = from; j < to; j++) sum += input[j];
    out[i] = sum / Math.max(1, to - from);
  }
  return out;
}
function hear(input, rate) {
  if (!V.field && !(W.on && !W.suspended)) return;
  if (!V.field && W.talking) { V.level = 0; return; }  // the mascot's own voice is not heard as the person's
  let energy = 0;
  for (let i = 0; i < input.length; i++) energy += input[i] * input[i];
  const rms = Math.sqrt(energy / input.length), now = performance.now() / 1000;
  // The noise floor follows quiet quickly and loud slowly, so speech never becomes the floor.
  V.floor = rms < V.floor ? V.floor * 0.7 + rms * 0.3 : V.floor * 0.995 + rms * 0.005;
  const voiced = rms > Math.max(V.floor * 3, 0.006);
  V.level = Math.min(1, Math.max(0, (20 * Math.log10(rms + 1e-9) + 60) / 50));
  const block = resample(input, rate);
  if (voiced) V.lastVoice = now;
  if (!V.speaking) {
    V.lead.push(block);
    while (V.lead.reduce((n, one) => n + one.length, 0) > LEAD * SR) V.lead.shift();
    if (voiced) {
      V.speaking = true;
      V.segment = [...V.lead];
      V.lead = [];
      (V.button || W.indicator)?.classList.add('speaking');
      clearTimeout(V.sendTimer);
    }
    return;
  }
  V.segment.push(block);
  const length = V.segment.reduce((n, one) => n + one.length, 0) / SR;
  if (length >= (V.status?.max_seconds || 120) - 1) return finishSegment();
  if ((V.mode === 'free' || !V.field) && now - V.lastVoice > HANG) return finishSegment();
  if (!V.field && length > WAKE_LONGEST && Date.now() > W.armed) { V.segment = null; V.speaking = false; return; }
  if (V.field && now * 1000 - V.lastPartial > PARTIAL_EVERY && !V.busy && length > 0.6 && partials()) {
    V.lastPartial = now * 1000;
    partial(join(V.segment));
  }
}
const partials = () => V.engine === 'server' || V.engine === 'browser';
const join = blocks => {
  const out = new Float32Array(blocks.reduce((n, one) => n + one.length, 0));
  let at = 0;
  for (const one of blocks) { out.set(one, at); at += one.length; }
  return out;
};
function finishSegment() {
  const blocks = V.segment;
  V.segment = null;
  V.speaking = false;
  (V.button || W.indicator)?.classList.remove('speaking');
  if (!blocks) return;
  const field = V.field, samples = join(blocks);
  // Trailing silence past the hang is not sent: only speech, its lead-in and a short tail.
  const keep = Math.min(samples.length, Math.ceil((samples.length / SR - Math.max(0, HANG - 0.3)) * SR));
  const audio = V.mode === 'free' || !field ? samples.subarray(0, Math.max(keep, Math.floor(0.5 * SR))) : samples;
  if (!field) { W.heard = W.heard.then(() => wakeHeard(audio)); return; }
  V.finals = V.finals.then(() => final(audio, field));
}
async function partial(audio) {
  V.busy = true;
  try {
    const heard = await transcribe(audio, true);
    if (heard && heard.text != null && V.speaking) { V.live = heard.text; write(V.field, true); }
  } catch { /* a partial that fails is passed over; the final pass says what went wrong */ }
  finally { V.busy = false; }
}
async function final(audio, field) {
  if (!field) return;
  field.classList.add('voice-partial');
  try {
    const heard = await transcribe(audio, false);
    const text = (heard?.text || '').trim();
    if (text) {
      V.base += (V.base && !/\s$/.test(V.base) ? ' ' : '') + text + ' ';
      V.clip = {text, wav: wav(audio)};
    }
    V.live = '';
    write(field);
    if (text && V.status?.send === 'auto' && V.mode === 'free') submitSoon(field, AUTO_PAUSE * 1000);
  } catch (error) {
    V.live = '';
    write(field);
    note(String(error?.message || error));
  } finally { field.classList.remove('voice-partial'); }
}
function write(field, partially = false) {
  if (!field) return;
  V.writing = true;
  field.value = (V.base + (V.live ? V.live : '')).replace(/\s+$/, partially ? '' : ' ');
  field.classList.toggle('voice-partial', partially);
  field.dispatchEvent(new Event('input', {bubbles: true}));
  V.writing = false;
  field.scrollTop = field.scrollHeight;
  try { field.setSelectionRange(field.value.length, field.value.length); } catch { /* not a text field */ }
}
function submitSoon(field, wait) {
  clearTimeout(V.sendTimer);
  V.sendTimer = setTimeout(() => {
    if (V.speaking || !field.value.trim()) return;
    const form = field.closest('form');
    if (form) form.requestSubmit();
    else field.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    if (V.field === field) V.base = '';
  }, wait);
}

/* ---------- the engines ---------- */
async function transcribe(audio, partially) {
  if (V.engine === 'browser') return inWorker(audio, partially);
  const language = V.status?.language && V.status.language !== 'auto' ? `&language=${encodeURIComponent(V.status.language)}` : '';
  const answer = await fetch(`/api/voice/transcribe?partial=${partially ? 1 : 0}${language}`, {method: 'POST',
    headers: {'Content-Type': 'audio/wav'}, body: wav(audio)});
  const said = await answer.json().catch(() => ({}));
  if (!answer.ok) throw new Error(said.next ? `${said.error} ${said.next}` : said.error || 'Voice did not answer.');
  return said.busy ? null : said;
}
function warmWorker() {
  if (V.loaded) return V.loaded;
  const st = V.status;
  V.worker = new Worker('/page/voice-worker.js', {type: 'module'});
  V.loaded = new Promise((done, fail) => {
    V.worker.onmessage = ({data}) => {
      if (data.type === 'loaded') { V.timings.push({loaded: Math.round(data.took)}); return done(data.took); }
      const asked = V.asks.get(data.id);
      if (data.type === 'error' && data.id == null) { V.loaded = null; return fail(new Error(data.message)); }
      if (!asked) return;
      V.asks.delete(data.id);
      if (data.type === 'result') {
        V.timings.push({partial: asked.partial, seconds: asked.seconds, took: Math.round(data.took)});
        asked.done({text: data.text, took: data.took, engine: 'browser'});
      }
      else asked.fail(new Error(data.message));
    };
    V.worker.onerror = event => { V.loaded = null; fail(new Error(event.message || 'The voice worker failed.')); };
  });
  V.worker.postMessage({type: 'load', repo: st.browser[V.variant].repo, variant: V.variant,
    runtime: `/api/voice/files/${st.browser.runtime}ort-wasm-simd-threaded.asyncify.wasm`});
  V.loaded.catch(error => note(`Whisper could not start in this browser: ${error.message}`));
  return V.loaded;
}
async function inWorker(audio, partially) {
  await warmWorker();
  if (partially && V.asks.size) return null;  // one pass at a time; the next partial carries these words too
  // transformers.js does not tell the language itself, so auto is the browser's own language here.
  const id = ++V.next, language = V.status?.language && V.status.language !== 'auto' ? V.status.language
    : (navigator.language || 'en').slice(0, 2).toLowerCase();
  return new Promise((done, fail) => {
    V.asks.set(id, {done, fail, partial: partially, seconds: +(audio.length / SR).toFixed(2)});
    const copy = Float32Array.from(audio);
    V.worker.postMessage({type: 'run', id, audio: copy, partial: partially, language}, [copy.buffer]);
  });
}
function listenWithBrowser() {
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const it = new Speech();
  V.recognition = it;
  it.continuous = true;
  it.interimResults = true;
  it.lang = V.status?.language && V.status.language !== 'auto' ? V.status.language : navigator.language;
  it.onresult = event => {
    let finished = '', interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) finished += event.results[i][0].transcript;
      else interim += event.results[i][0].transcript;
    }
    if (finished.trim()) V.base += finished.trim() + ' ';
    V.live = interim.trim();
    write(V.field, Boolean(V.live));
    V.button?.classList.toggle('speaking', Boolean(V.live));
    if (finished.trim() && V.status?.send === 'auto' && V.mode === 'free') submitSoon(V.field, AUTO_PAUSE * 1000);
  };
  it.onerror = event => { if (event.error !== 'no-speech' && event.error !== 'aborted') note(`The browser's speech service stopped: ${event.error}.`); };
  it.onend = () => { if (V.recognition === it && V.field) { try { it.start(); } catch { stop(false); } } };
  it.start();
}

/* WAV, 16-bit mono at 16 kHz: what the server engine, an endpoint and an agent that takes audio all read. */
function wav(samples) {
  const out = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (at, words) => { for (let i = 0; i < words.length; i++) out.setUint8(at + i, words.charCodeAt(i)); };
  text(0, 'RIFF'); out.setUint32(4, 36 + samples.length * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
  out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true); out.setUint32(24, SR, true);
  out.setUint32(28, SR * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true); text(36, 'data');
  out.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 0x7fff, true);
  return new Blob([out.buffer], {type: 'audio/wav'});
}

/* The level, eased like a spring with no overshoot: quick to rise with the voice, slower to settle. */
function meter() {
  const shown = V.button && V.field ? V.button : W.indicator;
  if (!shown || !V.audio) return;
  const target = V.level, stiffness = target > V.shown ? 0.32 : 0.12;
  V.velocity = V.velocity * 0.55 + (target - V.shown) * stiffness;
  V.shown = Math.max(0, Math.min(1, V.shown + V.velocity));
  shown.style.setProperty('--voice-level', V.shown.toFixed(3));
  V.frame = requestAnimationFrame(meter);
}

/* ---------- the key: hold to talk, tap to start or stop ---------- */
function isKey(event) {
  return event.code === 'Space' && !event.shiftKey && !event.metaKey
    && ((event.ctrlKey && !event.altKey) || (MAC && event.altKey && !event.ctrlKey));
}
function targetField() {
  const active = document.activeElement;
  if (active?.matches?.(FIELDS)) return active;
  const say = document.querySelector('#helpdesk .say');
  if (say && document.querySelector('#helpdesk')?.hidden) document.querySelector('#dockTab')?.click();
  return say;
}
function micOf(field) {
  const scope = field.closest('form') || field.parentElement;
  return scope?.querySelector('.voice-mic') || field.nextElementSibling;
}
addEventListener('keydown', event => {
  if (V.field && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); stop(true); return; }
  if (W.talking && event.key === 'Escape') { T.stopNow?.(); return; }  // a reply being read out stops; Escape goes on
  if (event.code === 'Space' && event.ctrlKey && event.shiftKey && !event.altKey && !event.metaKey) {
    event.preventDefault();
    event.stopPropagation();
    if (!event.repeat) { if (W.on) wakeOff(); else wakeOn(); }
    return;
  }
  if (!isKey(event) || V.engine === 'off' || V.hiddenWhy) return;
  event.preventDefault();
  event.stopPropagation();
  if (event.repeat) return;
  if (V.field && V.mode === 'free') { stop(false); return; }
  const field = targetField();
  if (!field) return;
  V.pressed = performance.now();
  field.focus();
  start(field, micOf(field), 'hold');
}, true);
addEventListener('keyup', event => {
  if (!V.pressed || !(event.code === 'Space' || event.key === 'Control' || event.key === 'Alt')) return;
  const held = performance.now() - V.pressed;
  V.pressed = 0;
  if (!V.field) return;
  if (held < TAP) { V.mode = 'free'; return; }  // a tap: listening goes on hands-free until the next tap
  stop(false);
}, true);

/* ---------- an agent that takes audio: the recording rides beside its transcript ---------- */
/* What app.js adds to a chat message: the clip of what was just said, kept on the server for the agent, when the
 * person's voice_send_audio is `accepted`, the agent's session declared audio, and the message still holds the
 * words the clip says. Otherwise nothing, and the transcript alone is sent. */
export async function voiceAudio(text, accepts) {
  const clip = V.clip;
  V.clip = null;
  if (!clip || !accepts || V.status?.send_audio !== 'accepted' || !String(text).includes(clip.text)) return {};
  try {
    const answer = await fetch('/api/voice/clip', {method: 'POST', headers: {'Content-Type': 'audio/wav'}, body: clip.wav});
    const said = await answer.json();
    return answer.ok && said.clip ? {audio: said.clip} : {};
  } catch { return {}; }
}

/* ---------- the wake phrase ---------- */
const norm = text => text.toLowerCase().normalize('NFKD').replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
function distance(a, b) {  // Levenshtein, for a phrase heard a little differently than it is written
  const row = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let last = row[0];
    row[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const kept = row[j];
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, last + (a[i - 1] === b[j - 1] ? 0 : 1));
      last = kept;
    }
  }
  return row[b.length];
}
/* What follows the wake phrase in `text`, '' for the phrase alone, or null when the phrase is not near its start. */
export function afterPhrase(text, phrase) {
  const want = norm(phrase);
  if (!want) return null;
  const tokens = String(text).trim().split(/\s+/), words = tokens.map(norm), size = want.split(' ').length;
  for (let at = 0; at <= 2 && at < words.length; at++) {
    const kept = [];
    for (let i = at; i < words.length && kept.length < size; i++) if (words[i]) kept.push(i);
    if (kept.length < size) break;
    const said = kept.map(i => words[i]).join(' ');
    if (distance(said, want) <= Math.max(1, Math.floor(want.length / 4)))
      return tokens.slice(kept.at(-1) + 1).join(' ').replace(/^[\s,.;:!?-]+/, '').trim();
  }
  return null;
}
async function wakeHeard(audio) {
  if (!W.on) return;
  try {
    if (Date.now() < W.armed) {  // the phrase was said alone: these words are the message
      W.armed = 0;
      const heard = await transcribe(audio, false);
      return tell((heard?.text || '').trim());
    }
    const head = audio.subarray(0, Math.min(audio.length, Math.floor(WAKE_HEAD * SR)));
    const quick = await transcribe(head, false);
    const rest = afterPhrase(quick?.text || '', W.phrase);
    if (rest === null) return;  // not for the mascot: nothing of it is kept
    const whole = audio.length > head.length ? afterPhrase((await transcribe(audio, false))?.text || '', W.phrase) : rest;
    if (whole && whole.split(' ').length >= 2) return tell(whole);
    W.armed = Date.now() + WAKE_WAIT;
    wakeShow('Go ahead…');
    window.metaform?.mascotSaid?.('Yes?');
    setTimeout(() => { if (W.armed && Date.now() >= W.armed) { W.armed = 0; wakeShow(); } }, WAKE_WAIT + 50);
  } catch (error) { note(String(error?.message || error)); }
}
async function tell(text) {
  if (!text) return wakeShow();
  wakeShow('Sending to your agent…');
  try { await tellSystem(text); } finally { setTimeout(() => wakeShow(), 1200); }
}
/* What the person said after the wake phrase goes to their system agent, as the chat sends it: through the mascot
 * where the page offers it, otherwise the chat dock's own Call and compose box, the dock put back as it was. */
async function tellSystem(text) {
  T.expect = Date.now();
  const ask = window.metaform?.mascotAsk;
  if (typeof ask === 'function') return ask(text);
  const dock = document.querySelector('#dock'), resting = dock && !dock.className.startsWith('open');
  const joined = () => (document.querySelector('#helpdesk .with')?.textContent || '').startsWith('With');
  if (!joined()) {
    const call = document.querySelector('#helpdesk .call');
    if (call && call.textContent.trim() === 'Call') call.click();
    for (let i = 0; i < 900 && !joined(); i++) await new Promise(done => setTimeout(done, 100));
  }
  const say = document.querySelector('#helpdesk .say');
  if (!say) return;
  say.value = text;
  say.closest('form')?.requestSubmit();
  if (resting) document.querySelector('#helpdesk .min')?.click();
}
function wakeShow(words) {
  if (!W.indicator) {
    W.indicator = el('button', {type: 'button', className: 'voice-wake'}, '<span class="voice-dot" aria-hidden="true"></span><span class="voice-said"></span>');
    W.indicator.setAttribute('aria-pressed', 'true');
    W.indicator.onclick = () => wakeOff();
    document.body.append(W.indicator);
  }
  const said = words || (W.suspended ? 'Wake phrase paused' : `Listening for “${W.phrase}”`);
  W.indicator.querySelector('.voice-said').textContent = said;
  W.indicator.title = `${said}. Click, or Ctrl+Shift+Space, to stop listening.`;
  W.indicator.setAttribute('aria-label', W.indicator.title);
  W.indicator.classList.toggle('armed', Boolean(words));
  requestAnimationFrame(() => W.indicator?.classList.add('shown'));
}
export async function wakeOn() {
  if (W.on) return;
  const phrase = V.status?.wake?.phrase || '';
  if (!phrase) return note('Choose a mascot, or set voice_wake_phrase, for the wake phrase.');
  if (!['server', 'browser'].includes(V.engine))
    return note('The wake phrase is heard only on this device: choose voice_engine server, browser or auto.');
  const missing = need();
  if (missing && !(await ask(document.querySelector('.voice-mic') || document.body, missing))) return;
  Object.assign(W, {on: true, phrase, armed: 0});
  if (V.engine === 'browser') warmWorker();
  try { if (!V.field) await openMic(); } catch (error) { return wakeOff(`The microphone could not open: ${error?.message || error}`); }
  wakeShow();
  if (V.audio?.state === 'suspended') {  // the browser waits for a first touch of the page before it hears
    wakeShow('Listening starts at your first click');
    const resume = () => { V.audio?.resume(); wakeShow(); };
    addEventListener('pointerdown', resume, {once: true, capture: true});
    addEventListener('keydown', resume, {once: true, capture: true});
  }
}
export function wakeOff(why) {
  if (!W.on) return;
  Object.assign(W, {on: false, armed: 0, suspended: false});
  if (!V.field) closeMic();
  const shown = W.indicator;
  W.indicator = null;
  if (shown) { shown.classList.remove('shown'); setTimeout(() => shown.remove(), reduced() ? 0 : 260); }
  if (why) note(why);
}

/* ---------- speech out: the agent's replies, in the mascot's voice ---------- */
function speakable(text) {
  return String(text).replace(/```[\s\S]*?```/g, ' (the code is in the chat) ').replace(/`([^`]+)`/g, '$1')
    .replace(/https?:\/\/\S+/g, 'a link').replace(/[*_#>|~]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 900);
}
function shouldSpeak() {
  const tts = V.status?.tts;
  if (!tts || tts.engine === 'off' || tts.speak === 'never') return false;
  if (tts.speak === 'always') return true;
  return !document.querySelector('#dock')?.className.startsWith('open');  // minimized: while the chat is put away
}
function character() {
  const chosen = V.status?.wake?.mascot;
  return chosen && V.status.tts.voices[chosen] ? chosen : null;
}
/* Whether an agent's line asked to be said aloud is spoken: the person's voice settings speak, in any way but never. */
export function mayAnnounce() {
  const tts = V.status?.tts;
  return Boolean(tts && tts.engine !== 'off' && tts.speak !== 'never');
}
export function speakReply(text) {
  const words = speakable(text);
  if (!words) return Promise.resolve();
  const tts = V.status?.tts, brought = tts?.engines?.[tts.engine];  // an engine a module brings, such as elevenlabs
  T.queue = T.queue.then(() => (brought?.ready
    ? speakServer(words).catch(error => { note(`${tts.engine} did not speak: ${error.message}`); return speakBrowser(words); })
    : speakBrowser(words)));
  return T.queue;
}
function talking(on, text) {
  W.talking = on;
  if (on && text) window.metaform?.mascotSaid?.(text);
  window.metaform?.mascotSpeaking?.(on);
}
function browserVoice(profile) {
  const all = speechSynthesis.getVoices();
  if (profile?.voice) { const named = all.find(one => one.name === profile.voice); if (named) return named; }
  const lang = (navigator.language || 'en').slice(0, 2).toLowerCase();
  const fitting = all.filter(one => one.lang.toLowerCase().startsWith(lang)).sort((a, b) => a.name.localeCompare(b.name));
  if (!fitting.length) return null;
  const name = character() || '';
  let hash = 0;
  for (const letter of name) hash = (hash * 31 + letter.charCodeAt(0)) >>> 0;
  return fitting[hash % fitting.length];
}
function speakBrowser(words) {
  if (!('speechSynthesis' in window)) return Promise.resolve();
  const profile = V.status?.tts?.voices?.[character()] || V.status?.tts?.default || {};
  const parts = words.match(/[^.!?]+[.!?]*\s*/g) || [words];  // a sentence at a time: long utterances stall some engines
  return new Promise(done => {
    let left = parts.length;
    T.stopNow = () => { speechSynthesis.cancel(); talking(false); done(); };
    talking(true, words);
    for (const part of parts) {
      const one = new SpeechSynthesisUtterance(part.trim());
      const voice = browserVoice(profile);
      if (voice) one.voice = voice;
      one.pitch = profile.pitch || 1;
      one.rate = profile.rate || 1;
      one.onend = one.onerror = () => { if (--left === 0) { talking(false); done(); } };
      speechSynthesis.speak(one);
    }
  });
}
async function speakServer(words) {
  const answer = await fetch('/api/voice/speak', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: words, character: character()})});
  if (!answer.ok) throw new Error((await answer.json().catch(() => ({}))).error || `status ${answer.status}`);
  const format = answer.headers.get('X-Voice-Format') || '';
  talking(true, words);
  try {
    if (format.startsWith('pcm_')) return await playPcm(answer.body, Number(format.split('_')[1]) || 22050);
    const blob = await answer.blob();  // MP3: played whole once it is in; pcm plays as it streams
    const audio = new Audio(URL.createObjectURL(blob));
    T.audio = audio;
    await new Promise(done => { audio.onended = audio.onerror = done; audio.play().catch(done); });
  } finally { talking(false); }
}
/* Raw 16-bit PCM, played as it arrives: each chunk scheduled right after the last, so the first words are heard while
 * the rest is still being made. */
async function playPcm(body, rate) {
  const Context = window.AudioContext || window.webkitAudioContext, out = new Context();
  let at = out.currentTime + 0.05, carry = new Uint8Array(0);
  const reader = body.getReader();
  T.stopNow = () => { reader.cancel().catch(() => {}); out.close().catch(() => {}); };
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    const bytes = new Uint8Array(carry.length + value.length);
    bytes.set(carry); bytes.set(value, carry.length);
    const whole = bytes.length - bytes.length % 2;
    carry = bytes.slice(whole);
    if (!whole) continue;
    const samples = new Int16Array(bytes.buffer.slice(0, whole));
    const buffer = out.createBuffer(1, samples.length, rate), data = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) data[i] = samples[i] / 32768;
    const source = out.createBufferSource();
    source.buffer = buffer;
    source.connect(out.destination);
    at = Math.max(at, out.currentTime);
    source.start(at);
    at += buffer.duration;
  }
  await new Promise(done => setTimeout(done, Math.max(0, (at - out.currentTime) * 1000)));
  out.close().catch(() => {});
}
/* The chat's thread, watched for the agent's reply to what the person just sent: once its turn ends, the words it
 * wrote since are spoken, if voice_speak says so now. History already on the page is never read out. */
function watchReplies() {
  const log = document.querySelector('#helpdesk .log');
  if (!log || T.watching) return;
  T.watching = true;
  const mark = () => { for (const one of log.querySelectorAll('.bubble.theirs')) if (!T.seen.has(one.textContent)) T.seen.set(one.textContent, Date.now()); };
  mark();
  for (const text of T.seen.keys()) T.spoken.add(text);
  new MutationObserver(() => {
    mark();
    clearTimeout(T.timer);
    T.timer = setTimeout(() => {
      if (!T.expect || log.querySelector('.system.waiting')) return;
      const fresh = [...log.querySelectorAll('.bubble.theirs')].map(one => one.textContent)
        .filter(text => !T.spoken.has(text) && (T.seen.get(text) || 0) >= T.expect);
      if (!fresh.length) return;
      fresh.forEach(text => T.spoken.add(text));
      T.expect = 0;
      if (shouldSpeak()) speakReply(fresh.join(' '));
    }, 900);
  }).observe(log, {childList: true, subtree: true, characterData: true});
  document.querySelector('#helpdesk .compose')?.addEventListener('submit', () => { T.expect = Date.now(); }, true);
}

/* ---------- start ---------- */
async function boot() {
  await readStatus();
  const chosen = await chooseEngine();
  Object.assign(V, {engine: chosen.engine, why: chosen.why, hiddenWhy: chosen.hidden ? chosen.why : ''});
  attach();
  for (const button of document.querySelectorAll('.voice-mic')) paintMic(button);
  if (!V.observing) {  // a field drawn later, such as the mascot's reply field, gets its mic as it appears
    V.observing = true;
    new MutationObserver(records => {
      for (const record of records) for (const node of record.addedNodes) if (node.nodeType === 1) {
        if (node.matches(FIELDS)) micFor(node); else attach(node);
      }
    }).observe(document.body, {childList: true, subtree: true});
  }
  document.documentElement.dataset.voice = V.engine;
  watchReplies();
  if (V.status?.wake?.on && !W.on && !V.hiddenWhy) wakeOn();
  window.metaform = window.metaform || {};
  window.metaform.voice = voice;
}
export const voice = {state: () => ({engine: V.engine, why: V.why, variant: V.variant, listening: Boolean(V.field),
  mode: V.mode, status: V.status, timings: V.timings.slice(-20), wake: {on: W.on, phrase: W.phrase, armed: W.armed > Date.now()},
  talking: W.talking}), refresh: async () => { await boot(); }, wakeOn, wakeOff, speak: speakReply, afterPhrase};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true}); else boot();
