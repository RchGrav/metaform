/* The page in an AI tool's frame, MCP-037: the map view of MCP Apps, `ui://metaform/map`. The same page, its 2D and
 * 3D maps and its panel, run inside the sandboxed frame an AI tool shows in its conversation. A frame reaches no
 * server of its own, so the page's reads of /api go to the MCP server's `metaform_view` tool through the AI tool,
 * writes are left to the web GUI, and there is no event stream. The view opens on the address the call named, and
 * each node the person selects is told to the agent in one line. Loaded only in the map view, never by the web GUI;
 * `scripts/build_map_view.mjs` puts it before the page's own code. Needs bridge.js, the mcp module's view side, over
 * the official MCP Apps SDK. */
'use strict';
(function () {
  const view = window.MetaformView;
  if (!view || view.config.view !== 'map') return;
  document.documentElement.classList.add('frame');
  const project = view.config.project || '';
  const READONLY = 'The map in your AI tool only reads; open the web GUI with metaform web start to change things.';
  const json = (body, status = 200) => new Response(JSON.stringify(body),
    {status, headers: {'Content-Type': 'application/json'}});

  /* /api/<read>?<params> as a call of the view's tool; the answer is the read's JSON, as the web GUI's server
   * gives it, or its error with the status the page expects of a refused read. */
  const native = window.fetch.bind(window);
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, 'https://view.invalid');
    if (!url.pathname.startsWith('/api/')) return native(input, options);
    if ((options.method || 'GET').toUpperCase() !== 'GET') return json({error: READONLY}, 403);
    const name = url.pathname.slice('/api/'.length);
    if (name === 'projects') return json({projects: project ? [{id: project}] : [], opened: project});
    const params = Object.fromEntries(url.searchParams);
    try { return json(await view.call(view.config.tool, {read: name, params})); }
    catch (error) { return json({error: error.message}, 404); }
  };
  /* A frame's document has no address of its own to keep the project in, so the page's history writes are let go. */
  for (const name of ['replaceState', 'pushState']) {
    const own = history[name].bind(history);
    history[name] = (...given) => { try { own(...given); } catch (error) { /* about:srcdoc keeps no address */ } };
  }
  /* No event stream reaches a frame: the map is read when the view opens, and opening it again reads it anew. */
  window.EventSource = class { constructor() { this.readyState = 2; } close() {} addEventListener() {} };

  /* The page selects its entry as it loads, and the view then turns to the call's address: neither is the person's
   * choice, so the agent is told only of what the person selects after that. */
  let address = null, loaded = false, turning = false;
  const focus = () => {
    if (!loaded || address === null || !window.metaform?.find) return;
    const id = window.metaform.find(address);
    turning = true;
    try { if (id) window.metaform.select(id); } finally { turning = false; }
  };
  view.on('toolinput', params => {
    address = String((params.arguments || {}).address ?? '');
    focus();
  });
  const ready = () => {
    window.metaform.onLoaded = () => { loaded = true; focus(); };
    window.metaform.onSelect = selected => { if (loaded && !turning) view.selected(selected); };
  };
  /* app.js sets window.metaform as it starts, after this file: the hooks go on once it is there. */
  let held = window.metaform;
  Object.defineProperty(window, 'metaform', {configurable: true, get: () => held,
    set(value) { held = value; Object.defineProperty(window, 'metaform', {value, writable: true, configurable: true}); ready(); }});
  /* The SDK reports the view's size as it changes; a failed handshake is shown in the view by bridge.js. */
  view.connect('metaform-map', ['inline', 'fullscreen']).catch(() => {});
})();
