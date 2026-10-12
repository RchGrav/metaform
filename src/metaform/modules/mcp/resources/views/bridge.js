/* The MCP Apps view side, io.modelcontextprotocol/ui revision 2026-01-26: what the map, node, trace and glossary views
 * use to talk to the AI tool that shows them, over the official SDK's App class (@modelcontextprotocol/ext-apps,
 * ext-apps.js beside this file, `window.McpApps`). The SDK makes the handshake, ui/initialize with the view's appInfo
 * and capabilities and then ui/notifications/initialized, reports the view's size, and carries the calls; this file
 * adds only what Metaform's views share: their settings, reading through the views' own tool, the host's theme, fonts,
 * style variables, container size and display mode, and the shared picture between the person and the agent: the one
 * line the agent is told about what the person selected, the view turning to the Address the agent names, and, where
 * the host calls a view's own tools (the draft's App-Provided Tools), the agent turning the view itself.
 * Sources: github.com/modelcontextprotocol/ext-apps, specification/2026-01-26/apps.mdx, specification/draft/apps.mdx
 * and the SDK's API reference. Nothing here runs outside a frame: on a page of its own, `MetaformView.framed` is
 * false and nothing is sent. */
'use strict';
(function () {
  const sdk = window.McpApps;
  const framed = window.parent !== window;
  const config = (() => {
    try { return JSON.parse(document.getElementById('metaform-view').textContent || '{}'); }
    catch (error) { return {}; }
  })();
  const listeners = [];  // [event, handler], put on the App when it is made, so nothing the host sends is missed
  const stops = new Set();  // what runs while the view is shown, stopped when the host tears it down
  let app = null;
  let host = {};
  let turner = null;  // the view's own way to turn to an Address, given by the view: address => found
  let current = '';  // the Address the view shows, by the person's selection or a turn
  let picked = '';  // the Address the person last selected
  let hushed = false;  // while the view turns itself, a selection is not the person's and is not told
  let opened;  // settled once the handshake is made or has failed, so a read asked for before it waits for it
  const ready = new Promise(settle => { opened = settle; });

  /* A handler for one of the App's events: toolinput, toolinputpartial, toolresult, toolcancelled,
   * hostcontextchanged. */
  function on(event, handler) {
    listeners.push([event, handler]);
    if (app) app.addEventListener(event, handler);
  }

  /* The host's context, whole at the handshake and in part on each change: the display mode, the container's size
   * (a fixed height the view fills, or a most it may grow to), the safe area, and, where the view follows the host's
   * look (`config.themed`), its theme and style variables. The host's fonts are taken in every view. */
  function styled(context) {
    host = {...host, ...context};
    const root = document.documentElement;
    if (context.displayMode) root.dataset.display = context.displayMode;
    const size = context.containerDimensions;
    if (size) {
      for (const name of ['--view-height', '--view-max-height']) root.style.removeProperty(name);
      if ('height' in size && size.height) root.style.setProperty('--view-height', `${size.height}px`);
      else if (size.maxHeight) root.style.setProperty('--view-max-height', `${size.maxHeight}px`);
      root.dataset.sized = 'height' in size ? 'fixed' : 'flexible';
    }
    const inset = context.safeAreaInsets;
    if (inset) for (const side of ['top', 'right', 'bottom', 'left']) {
      root.style.setProperty(`--safe-${side}`, `${inset[side] || 0}px`);
    }
    if (context.styles?.css?.fonts) sdk.applyHostFonts(context.styles.css.fonts);
    const variables = context.styles?.variables;
    if (!config.themed) {
      if (variables?.['--font-sans']) root.style.setProperty('--sans', variables['--font-sans']);
      if (variables?.['--font-mono']) root.style.setProperty('--mono', variables['--font-mono']);
      return;
    }
    if (context.theme) sdk.applyDocumentTheme(context.theme);
    if (variables) sdk.applyHostStyleVariables(variables);
  }

  /* What stopped the handshake, shown in the view rather than hidden: the view cannot work without it. */
  function failed(error) {
    const notice = document.getElementById('handshake') || document.createElement('p');
    notice.id = 'handshake';
    notice.setAttribute('role', 'alert');
    notice.textContent = `${config.failed || 'The AI tool did not connect this view.'} ${error?.message || ''}`.trim();
    notice.style.cssText = 'margin:8px 12px;font:13px system-ui,sans-serif;color:#ff8a80';
    document.body.prepend(notice);
  }

  /* The view's own tools, offered to a host that calls them while the view is open: view_show turns the view to an
   * Address, view_state says what it shows and what the person selected. Their descriptions are the mcp module's
   * prompts; an empty one leaves its tool out. */
  function ownTools() {
    const tools = [];
    if (config.show) tools.push({name: 'metaform_view_show', description: config.show,
      inputSchema: {type: 'object', required: ['address'], additionalProperties: false,
                    properties: {address: {type: 'string', description: 'An Address, or <address>#<n> for an item.'}}},
      annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false}});
    if (config.state) tools.push({name: 'metaform_view_state', description: config.state,
      inputSchema: {type: 'object', additionalProperties: false, properties: {}},
      annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false}});
    return tools;
  }
  const said = (template, address) => (template || '').split('{address}').join(address);
  async function ownCall(params) {
    if (params.name === 'metaform_view_state') {
      return {content: [{type: 'text', text: JSON.stringify({view: config.view, shows: current || null,
        selected: picked || null})}], structuredContent: {view: config.view, shows: current || null,
        selected: picked || null}};
    }
    if (params.name !== 'metaform_view_show') throw new Error(`No tool ${params.name} in this view.`);
    const address = String(params.arguments?.address || '').trim();
    const found = address && turner ? await turn(address) : false;
    return {content: [{type: 'text', text: said(found ? config.shown : config.absent, address)}],
      isError: !found};
  }

  /* Connect: the SDK's handshake over postMessage to the host, after which the host sends the call's input and
   * result. `modes` are the display modes the view offers, the server's choice for it unless given. Returns the App,
   * or null outside a frame. */
  async function connect(name, modes) {
    if (!framed) return null;
    if (!sdk) { failed(new Error('ext-apps.js is missing.')); return null; }
    const tools = ownTools();
    const capabilities = {availableDisplayModes: modes || config.modes || ['inline']};
    if (tools.length) capabilities.tools = {listChanged: false};
    app = new sdk.App({name, version: config.version || '0'}, capabilities, {autoResize: true});
    for (const [event, handler] of listeners) app.addEventListener(event, handler);
    app.addEventListener('hostcontextchanged', styled);
    if (tools.length) {
      app.onlisttools = async () => ({tools});
      app.oncalltool = ownCall;
    }
    app.onteardown = async () => { for (const stop of [...stops]) stop(); return {}; };
    try {
      await app.connect(new sdk.PostMessageTransport(window.parent, window.parent));
    } catch (error) {
      failed(error);
      opened();
      throw error;
    }
    styled(app.getHostContext() || {});
    opened();
    follow();
    return app;
  }

  /* Whether the host offers a capability the view uses: serverTools for reads, updateModelContext for the line
   * about a selection, openLinks for the web GUI. */
  const can = name => Boolean(app?.getHostCapabilities()?.[name]);

  /* A tool of the server, through the host; its structured content, or its text read as JSON, or its text. A read
   * asked for while the handshake is still being made, as the map page's first reads are, waits for it. */
  async function call(tool, args = {}) {
    if (framed && app) await ready;
    if (!can('serverTools')) throw new Error(config.noTools || 'This AI tool does not let its views read.');
    const result = await app.callServerTool({name: tool, arguments: args});
    const text = (result.content || []).filter(block => block.type === 'text').map(block => block.text).join('\n');
    if (result.isError) throw new Error(text || `${tool} failed`);
    if (result.structuredContent !== undefined) return result.structuredContent;
    try { return JSON.parse(text); } catch (error) { return text; }
  }

  /* `work` run now and every `ms` while the view is on screen, and never after the host tears it down: an
   * IntersectionObserver sees the frame scrolled out of the conversation, and the page's visibility a hidden tab.
   * Returns what stops it. */
  function poll(work, ms) {
    let timer = null, seen = true, busy = false;
    const tick = async () => {
      timer = null;
      if (!seen || document.hidden) return;
      if (!busy) { busy = true; try { await work(); } catch (error) { /* the next tick tries again */ } busy = false; }
      if (stops.has(stop)) timer = setTimeout(tick, ms);
    };
    const wake = () => { if (stops.has(stop) && timer === null && seen && !document.hidden) tick(); };
    const watcher = 'IntersectionObserver' in window
      ? new IntersectionObserver(entries => { seen = entries.some(entry => entry.isIntersecting); wake(); }) : null;
    watcher?.observe(document.body);
    document.addEventListener('visibilitychange', wake);
    function stop() {
      stops.delete(stop);
      clearTimeout(timer);
      watcher?.disconnect();
      document.removeEventListener('visibilitychange', wake);
    }
    stops.add(stop);
    tick();
    return stop;
  }

  /* What the agent is told about the person's selection, one line, replacing the last; the host sends it with the
   * person's next message. The words are the mcp module's view_selected prompt. A selection the view makes itself,
   * turning to an Address, is not the person's and is not told. */
  let told = '';
  function selected(address) {
    if (!address) return;
    current = address;
    if (hushed) return;
    picked = address;
    if (!config.selected || !can('updateModelContext')) return;
    const line = said(config.selected, address);
    if (line === told) return;
    told = line;
    app.updateModelContext({content: [{type: 'text', text: line}], structuredContent: {address}})
      .catch(() => { told = ''; });
  }

  /* `work` run as the view's own doing: a selection it makes is not told to the agent. */
  function quietly(work) {
    hushed = true;
    try { return work(); } finally { hushed = false; }
  }

  /* The view's way to turn to an Address, given once by the view; the turn is quiet. */
  async function turn(address) {
    if (!turner) return false;
    const found = await quietly(() => turner(address));
    if (found) current = address;
    return Boolean(found);
  }

  /* The Address the agent last named in a Metaform call, read through the views' tool while the view is on screen;
   * the view turns to each new one once. What was named before the view opened is where it opened. */
  let named = null, following = false;
  function follow() {
    if (following || !turner || !can('serverTools') || !config.tool) return;
    following = true;
    poll(async () => {
      const focus = await call(config.tool, {read: 'focus'});
      const seq = Number(focus?.seq || 0);
      if (named === null) { named = seq; return; }
      if (seq <= named) return;
      named = seq;
      if (focus.address && focus.address !== current) await turn(String(focus.address));
    }, 2500);
  }

  /* The display modes the host offers that the view does too, and a switch between inline and the next. */
  const modes = () => (host.availableDisplayModes || []).filter(mode => (config.modes || ['inline']).includes(mode));
  async function display(mode) {
    if (!app || !modes().includes(mode)) return host.displayMode || 'inline';
    const result = await app.requestDisplayMode({mode});
    styled({displayMode: result.mode});
    return result.mode;
  }

  /* The web GUI, where what the view only reads is changed, opened by the host where it opens links. */
  const web = () => (config.web && can('openLinks') ? app.openLink({url: config.web}) : Promise.resolve(null));

  /* Text to the clipboard, where the host's sandbox grants it (MCP Apps permissions.clipboardWrite). */
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (error) { return false; }
  }

  window.MetaformView = {framed, config, connect, on, call, can, selected, quietly, poll, display, modes, web, copy,
    host: () => host, app: () => app, shows: () => current,
    turner: handler => { turner = handler; if (app) follow(); },
    fullscreen: mode => display(mode || 'fullscreen')};
})();
