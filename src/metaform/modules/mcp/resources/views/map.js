/* The map view's share of the picture between the person and the agent, MCP-037: what the mcp module adds to the web
 * GUI's page in an AI tool's frame, after the page's own frame code (web/page/frame.js), which reads through the views'
 * tool, opens on the call's address and tells the agent what the person selects. This file turns the map to the
 * Address the agent names, as the node view turns (bridge.js's `turner`): a later Metaform call naming an Address, or
 * the view's own tool where the host calls it. It also gives the frame what the page has no control for: a switch to
 * full screen and a link to the web GUI, and the host's container height. `scripts/build_map_view.mjs` puts it after
 * frame.js; it changes nothing of the page's code. */
'use strict';
(function () {
  const view = window.MetaformView;
  if (!view || view.config.view !== 'map') return;
  const root = document.documentElement;

  /* The host's container: a fixed height the map fills, or a most it may grow to; full screen fills the screen. */
  const sized = document.createElement('style');
  sized.textContent = 'html.frame[data-sized="fixed"]:not([data-display="fullscreen"]) .app{height:var(--view-height)!important}'
    + 'html.frame[data-sized="flexible"]:not([data-display="fullscreen"]) .app{max-height:var(--view-max-height,none)}'
    + '#viewbar{position:fixed;top:calc(6px + var(--safe-top,0px));right:calc(8px + var(--safe-right,0px));z-index:50;'
    + 'display:flex;gap:6px}#viewbar[hidden]{display:none}'
    + '#viewbar button{font:12px var(--sans,system-ui);color:var(--text);background:var(--panel);border:1px solid var(--line);'
    + 'border-radius:var(--r,4px);padding:2px 8px;cursor:pointer;opacity:.85}#viewbar button:hover{opacity:1}';
  document.head.append(sized);

  /* Turn to an Address: its node selected on both maps, as a selection of the person's would, but quietly, so the
   * agent is not told it as the person's. The page's script, a module, runs after this one: its `window.metaform` is
   * waited for, said by its event `metaform:api`, then its `ready`, kept once the first map is drawn, so an Address
   * named while the map loads is turned to as soon as it can be, and no sooner. */
  const page = new Promise(done => {
    if (window.metaform?.ready) done(window.metaform);
    else window.addEventListener('metaform:api', () => done(window.metaform), {once: true});
  });
  view.turner(async address => {
    const wanted = String(address).replace(/^metaform:\/\//, '').split('#')[0];
    await (await page).ready;
    const id = window.metaform.find(wanted);
    if (id) view.quietly(() => window.metaform.select(id));
    return Boolean(id);
  });

  /* The bar, each button only where the host allows it. */
  const bar = document.createElement('div');
  bar.id = 'viewbar';
  bar.hidden = true;
  const button = (text, title, act) => {
    const made = document.createElement('button');
    made.type = 'button'; made.textContent = text; made.title = title; made.onclick = act;
    return made;
  };
  const mode = button('Full screen', 'Show the map on the whole screen', async () => {
    await view.display(view.host().displayMode === 'fullscreen' ? 'inline' : 'fullscreen');
    draw();
  });
  const web = button('Web GUI', 'Open the project in the web GUI, where the map is changed; metaform web start serves it',
    () => view.web());
  bar.append(web, mode);
  function draw() {
    mode.hidden = !view.modes().includes('fullscreen');
    mode.textContent = root.dataset.display === 'fullscreen' ? 'Inline' : 'Full screen';
    web.hidden = !view.can('openLinks') || !view.config.web;
    bar.hidden = mode.hidden && web.hidden;
  }
  view.on('hostcontextchanged', draw);
  const place = () => { document.body.append(bar); setTimeout(draw, 0); };
  if (document.body) place(); else document.addEventListener('DOMContentLoaded', place);
  /* The handshake is frame.js's; the bar is drawn once the host has answered it, or it has failed. */
  view.connected().then(draw);
})();
