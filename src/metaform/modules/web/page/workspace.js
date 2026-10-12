/* The page's toolbar, its panes and their places, drawn from /api/workspace, web/README.md "Toolbar and panes".
 *
 * Modules declare what they offer, tools and panes, and the person arranges them: the toolbar's slots and its extra
 * tools, Edit Toolbar… to move them, the Window menu with a check for each pane and the workspaces, and panes docked
 * left, right, at the bottom or in the main area as tabs of groups, or floating. What the person leaves is saved in
 * the web module's settings through the server, never in this browser, so every project and every browser opens the
 * same way. The page's own parts do the work: its views are the panes' content, its overlays the menus and windows.
 *
 * app.js makes the workspace with a host that lends it the page's parts, `createWorkspace(host)`:
 *   h, fill, toast, confirmAct, overlay, movable, place, wrote(url, body), getJson(url),
 *   project() and selection(): the project shown and the selected node's address, or null;
 *   view(page): {el, show, docked} for a view the page draws, or null; command(page, address): runs a page command;
 *   maps(large): puts the map pane named large ('map2d' or 'map3d') in the large area and returns {large, small},
 *     the elements that hold the large and the small map; classic(on): the page as written, without the workspace;
 *   chatPane(body): the chat in a pane's body, or back in its dock with null; log(level, ...): developer lines.
 * Without a workspace read, in an AI tool's frame or before a project is chosen, the page stays as written.
 *
 * The arrangement that is the page as written, the Default one, is drawn by the page as written: one map in the main
 * area, and at one side the other map over a group of the node's tabs (Object, Brief, Provenance, Prompt), with the
 * board, the settings and What the agent sees as the page's own windows. The workspace then adds its toolbar and its
 * Window menu and leaves the page's own column, splitters, tabs and windows to work as they always have, `classicFrame`;
 * which map takes the large area stays this browser's choice there, as Swap made it. Any other arrangement, a pane
 * opened beside them or a tab moved, is drawn in the workspace's areas, `grid`, with the maps where this browser had
 * them. */
'use strict';

const AREAS = ['left', 'main', 'right', 'bottom'];
const NARROW = '(max-width: 820px)';
const MAPS = {'web.map2d': 'map2d', 'web.map3d': 'map3d'};
const CLASSIC_TABS = new Set(['object', 'brief', 'provenance', 'prompt']);  // the side column's tabs as the page is written
const WINDOWS = new Set(['board', 'settings', 'agent-view']);  // the page's own windows, opened by their own buttons

export function createWorkspace(host) {
  const {h, fill} = host;
  const WS = {state: null, toolbar: null, layout: null, on: false, groups: new Map(), panes: new Map(),
    floats: new Map(), saving: null, project: null, generation: 0, drag: null, showing: [],
    grid: false, framed: false, homes: new Map()};
  const $ = selector => document.querySelector(selector);
  const byId = id => (WS.state?.panes || []).find(one => one.id === id) || null;
  const toolById = id => (WS.state?.items || []).find(one => one.id === id) || null;
  const copy = value => JSON.parse(JSON.stringify(value));
  const narrow = () => matchMedia(NARROW).matches;

  /* ---------- reading and saving ---------- */
  async function load() {
    const project = host.project(), generation = ++WS.generation;
    if (!project) return false;
    let found;
    try { found = await host.getJson(`/api/workspace?project=${encodeURIComponent(project)}`); }
    catch (error) { host.log('info', 'workspace: not read, the page stays as written', error.message); return false; }
    if (generation !== WS.generation) return WS.on;
    WS.view = found.view || {};
    if (found.view?.panes === false) {  // web_panes off: the page as written, with the view settings still read
      if (WS.on) { WS.on = false; leave(); }
      return false;
    }
    adopt(found, project);
    return true;
  }
  function adopt(found, project = host.project()) {
    WS.state = found;
    WS.project = project;
    WS.toolbar = copy(found.toolbar);
    WS.layout = copy(found.layout);
    if (!WS.on) { WS.on = true; host.classic(false); }
    render();
  }
  /* Save what the person left: the toolbar, the layout or both, after a short pause, so a drag saves once. */
  function save(part) {
    WS.saving = WS.saving || new Set();
    WS.saving.add(part);
    clearTimeout(save.timer);
    save.timer = setTimeout(async () => {
      const parts = WS.saving; WS.saving = null;
      const body = {project: WS.project};
      if (parts.has('toolbar')) body.toolbar = WS.toolbar;
      if (parts.has('layout')) body.layout = WS.layout;
      const done = await host.wrote('/api/workspace/arrangement', body);
      if (done) { WS.state = done; host.log('verbose', 'workspace: saved', [...parts]); }
    }, 250);
  }
  async function act(path, body, said) {
    const done = await host.wrote(`/api/workspace/${path}`, {project: WS.project, ...body});
    if (!done) return false;
    adopt(done);
    if (said) host.toast(said);
    return true;
  }

  /* ---------- the page as written: where each element the workspace moves came from, and going back there ---------- */
  /* Before the workspace first moves an element of the page, a mark is left where it stood, so it can go back. */
  function home(element) {
    if (!element || WS.homes.has(element) || !element.parentNode) return;
    const mark = document.createComment(' a pane of the workspace stands here in the page as written ');
    element.before(mark);
    WS.homes.set(element, mark);
  }
  /* Every element moved goes back to its place, undocked, for the page as written. */
  function restoreHomes() {
    for (const pane of WS.state?.panes || []) {
      if (pane.content.kind !== 'page' || MAPS[pane.id]) continue;
      const element = host.view(pane.content.page)?.el;
      if (element?.classList.contains('docked')) dockedOff(pane, element);
    }
    for (const [element, mark] of WS.homes) {
      if (!mark.isConnected) continue;
      mark.after(element);
      element.classList.remove('wstab');
      delete element.dataset.wsShown;
      if (element.matches('main, #small')) element.hidden = false;
    }
  }
  /* The workspace off: the page as written, with no toolbar and no Window menu. */
  function leave() {
    for (const id of [...WS.floats.keys()]) closeFloat(id);
    restoreHomes();
    WS.grid = false; WS.framed = false;
    $('.app').classList.remove('wsclassic');
    host.classic(true);
    $('#windowPick').hidden = true;
    dispatchEvent(new Event('resize'));
  }
  const pageOf = pane => (pane?.content.kind === 'page' ? pane.content.page : null);
  const windowed = pane => Boolean(pane && WINDOWS.has(pageOf(pane)) && host.view(pageOf(pane)));
  const classicTab = pane => CLASSIC_TABS.has(pageOf(pane));
  /* A window of the page that floats is the page's own window, in either drawing: no second frame around it. */
  const ownWindow = id => windowed(byId(id)) && (!where(id) || where(id).area === 'float');
  /* The arrangement as the page as written draws it, or null: see the header. */
  function classicShape() {
    const shown = area => (WS.layout.areas[area]?.groups || []).filter(group => shownTabs(group).length);
    const main = shown('main');
    if (main.length !== 1 || shown('bottom').length) return null;
    const large = shownTabs(main[0]);
    if (large.length !== 1 || !MAPS[large[0]]) return null;
    const left = shown('left'), right = shown('right');
    if (left.length && right.length) return null;
    const groups = left.length ? left : right;
    if (groups.length !== 2) return null;
    const small = shownTabs(groups[0]);
    if (small.length !== 1 || !MAPS[small[0]] || small[0] === large[0]) return null;
    if (!shownTabs(groups[1]).every(id => classicTab(byId(id)))) return null;
    // a tab of the side column or a map floating is not the page as written; another pane floats over it as it does
    if (WS.layout.floating.some(one => isOn(one.pane) && (MAPS[one.pane] || classicTab(byId(one.pane))))) return null;
    return {side: left.length ? 'left' : 'right', group: groups[1]};
  }
  function renderClassic(shape) {
    WS.grid = false; WS.framed = true;
    restoreHomes();
    const app = $('.app');
    app.classList.remove('ws');
    app.classList.add('wsclassic');
    host.classicFrame({side: shape.side, panes: new Map(WS.state.panes.map(pane => [pane.id, pane])), tabs: shape.group.tabs,
      off: new Set(WS.layout.off)});
    for (const pane of WS.state.panes) if (classicTab(pane)) classicTabMenu(pane);
    // a floating pane that is not one of the page's own windows floats over the page as written
    const drawn = new Set();
    for (const one of WS.layout.floating) {
      const pane = byId(one.pane);
      if (!pane || !isOn(one.pane) || !usable(pane) || windowed(pane)) continue;
      drawFloat(pane, one, {}, drawn);
    }
    for (const id of [...WS.floats.keys()]) if (!drawn.has(id)) closeFloat(id);
    for (const pane of WS.state.panes) if (windowed(pane)) watchWindow(pane);
    drawToolbar();
    drawWindowMenu();
    host.log('verbose', 'workspace: the page as written', WS.layout);
    dispatchEvent(new Event('resize'));
    const showing = WS.showing.splice(0);
    for (const show of showing) show();
  }
  /* A tab of the page as written opens the workspace's tab menu too, Move to and Close, the way to another arrangement. */
  const menued = new WeakSet();
  function classicTabMenu(pane) {
    const tab = host.tab?.(pageOf(pane));
    if (!tab || menued.has(tab)) return;
    menued.add(tab);
    tab.addEventListener('contextmenu', event => {
      if (!WS.on) return;
      event.preventDefault();
      tabMenu(pane.id, event.clientX, event.clientY);
    });
  }
  /* The toolbar's pressed tool and the Window menu's check follow a window of the page opening and closing. */
  const watched = new WeakSet();
  function watchWindow(pane) {
    const element = host.view(pageOf(pane))?.el;
    if (!element || watched.has(element)) return;
    watched.add(element);
    new MutationObserver(() => { if (WS.on) { drawToolbar(); drawWindowMenu(); } })
      .observe(element, {attributes: true, attributeFilter: ['hidden']});
  }
  /* In the page as written a tab of the side column turns on and off in its strip, and a window of the page opens and
   * closes as its own button does; true when that is what the pane is. */
  function classicAct(id, on) {
    const pane = byId(id);
    if (!pane) return false;
    if (windowed(pane)) {
      const element = host.view(pageOf(pane)).el;
      if (on && element.hidden) host.openWindow(pageOf(pane));
      else if (!on && !element.hidden) (element.querySelector('.bar .close, .close') || {click: () => { element.hidden = true; }}).click();
      return true;
    }
    if (!classicTab(pane) || !where(id) || where(id).area === 'float') return false;
    const off = new Set(WS.layout.off);
    if (on) {
      off.delete(id);
      WS.layout.off = [...off];
      render();
      host.showTab(pageOf(pane));
    } else {
      off.add(id);
      WS.layout.off = [...off];
      if (host.tabOpen(pageOf(pane))) {  // the tab on view goes: the first tab left opens
        const next = shownTabs(where(id).group).find(one => one !== id);
        if (next) host.showTab(pageOf(byId(next)));
      }
      render();
    }
    save('layout');
    return true;
  }
  /* Out of the page as written into the workspace's areas: the maps keep the places this browser had them in. */
  function enterGrid() {
    if (WS.framed && largeMap() !== host.largeMap()) {
      const two = where('web.map2d'), three = where('web.map3d');
      if (two?.group && three?.group) {
        two.group.tabs[two.group.tabs.indexOf('web.map2d')] = 'web.map3d';
        three.group.tabs[three.group.tabs.indexOf('web.map3d')] = 'web.map2d';
        for (const group of [two.group, three.group]) {
          group.active = group.active === 'web.map2d' ? 'web.map3d' : group.active === 'web.map3d' ? 'web.map2d' : group.active;
        }
        save('layout');
      }
    }
    WS.grid = true; WS.framed = false;
    $('.app').classList.remove('wsclassic');
  }
  /* The side column dragged to the other side of the page as written moves the layout's side with it. */
  new MutationObserver(() => {
    if (!WS.on || WS.grid || !WS.layout) return;
    const right = $('.app').classList.contains('side-right'), from = right ? 'left' : 'right', to = right ? 'right' : 'left';
    const moving = WS.layout.areas[from]?.groups || [];
    if (!moving.some(group => shownTabs(group).length)) return;
    const area = WS.layout.areas[to] || (WS.layout.areas[to] = {size: null, groups: []});
    area.groups = [...moving, ...area.groups];
    WS.layout.areas[from].groups = [];
    save('layout');
  }).observe($('.app'), {attributes: true, attributeFilter: ['class']});

  /* ---------- panes: what each shows ---------- */
  const shownTabs = group => group.tabs.filter(id => byId(id) && !WS.layout.off.includes(id) && usable(byId(id)));
  /* A pane is drawn when the page carries its view, or the server serves its content. */
  function usable(pane) {
    if (pane.content.kind === 'page') return Boolean(MAPS[pane.id] || host.view(pane.content.page));
    return true;
  }
  function where(id) {
    for (const area of AREAS) for (const group of WS.layout.areas[area]?.groups || []) {
      if (group.tabs.includes(id)) return {area, group};
    }
    const floating = WS.layout.floating.find(one => one.pane === id);
    return floating ? {area: 'float', floating} : null;
  }
  const isOn = id => !WS.layout.off.includes(id);
  /* Shown: on, and its group's open tab, or floating. */
  function isShown(id) {
    if (WS.on && ownWindow(id)) return !host.view(pageOf(byId(id))).el.hidden;
    if (WS.on && !WS.grid) {  // the page as written: a map is always shown, a tab while open, a window while open
      const pane = byId(id);
      if (windowed(pane)) return !host.view(pageOf(pane)).el.hidden;
      if (!pane || !isOn(id)) return false;
      if (MAPS[id]) return true;
      if (classicTab(pane)) return host.tabOpen(pageOf(pane));
      return WS.floats.has(id);
    }
    if (!isOn(id)) return false;
    const found = where(id);
    if (!found) return false;
    if (found.area === 'float') return true;
    return activeOf(found.group) === id;
  }
  function activeOf(group) {
    const shown = shownTabs(group);
    return shown.includes(group.active) ? group.active : shown[0] || null;
  }
  /* The element that holds a pane's content: a view of the page, or a pane of the workspace's own, made once. */
  function contentOf(pane, maps) {
    if (MAPS[pane.id]) return MAPS[pane.id] === maps.largeName ? maps.large : maps.small;
    if (pane.content.kind === 'page') return host.view(pane.content.page)?.el || null;
    if (!WS.panes.has(pane.id)) WS.panes.set(pane.id, makePane(pane));
    return WS.panes.get(pane.id).el;
  }

  /* ---------- the frame ---------- */
  function frame() {
    let root = $('#ws');
    if (root) return root;
    root = h('div', {id: 'ws', class: 'ws'});
    for (const area of AREAS) {
      root.append(h('section', {class: 'wsarea', 'data-area': area, 'aria-label': `${area} area`}));
      if (area !== 'main') root.append(splitter(area));
    }
    root.append(h('div', {id: 'wsHold', hidden: true}));
    $('.app').append(root);
    return root;
  }
  /* The large map: the map pane open in the main area, else the 3D map; the other map is the small one. */
  function largeMap() {
    for (const group of WS.layout.areas.main?.groups || []) {
      const open = activeOf(group);
      if (MAPS[open]) return MAPS[open];
    }
    for (const group of WS.layout.areas.main?.groups || []) for (const id of shownTabs(group)) if (MAPS[id]) return MAPS[id];
    return isOn('web.map3d') ? 'map3d' : 'map2d';
  }
  function render() {
    if (!WS.on) return;
    const shape = classicShape();
    if (shape) return renderClassic(shape);
    if (!WS.grid) enterGrid();
    const root = frame(), hold = $('#wsHold');
    const app = $('.app');
    app.classList.add('ws');
    for (const area of AREAS) {
      const size = WS.layout.areas[area]?.size;
      // an area the person has not sized: the right one is as wide as the side column of the page as written
      if (area !== 'main') app.style.setProperty(`--ws-${area}`, size ? `${Math.round(size)}px`
        : area === 'right' ? 'var(--side-width, max(320px, 25vw))' : `${area === 'bottom' ? 280 : 360}px`);
    }
    const largeName = largeMap();
    const maps = {largeName, ...host.maps(largeName)};
    const placed = new Set();
    for (const area of AREAS) {
      const box = root.querySelector(`.wsarea[data-area="${area}"]`);
      const groups = (WS.layout.areas[area]?.groups || []).filter(group => shownTabs(group).length);
      const kept = [];
      groups.forEach((group, index) => {
        if (index) kept.push(groupSplitter(area, index));
        kept.push(drawGroup(group, area, maps, placed));
      });
      keepChildren(box, kept);
      box.classList.toggle('empty', !groups.length);
      root.querySelector(`.wssplit[data-area="${area}"]`)?.toggleAttribute('hidden', !groups.length);
      box.style.flexDirection = area === 'bottom' && !narrow() ? 'row' : 'column';
    }
    for (const one of WS.layout.floating) {
      const pane = byId(one.pane);
      if (!pane || !isOn(one.pane) || !usable(pane) || windowed(pane)) { closeFloat(one.pane); continue; }
      drawFloat(pane, one, maps, placed);
    }
    for (const pane of WS.state.panes) if (windowed(pane)) watchWindow(pane);
    for (const id of [...WS.floats.keys()]) if (!WS.layout.floating.some(one => one.pane === id)) closeFloat(id);
    // what is not placed goes back where the page as written keeps it, so the chat's own dock and the page's windows
    // still work with their pane off; a pane's own content waits, out of sight, for its pane to come back on
    for (const pane of WS.state.panes) {
      if (placed.has(pane.id) || !usable(pane)) continue;
      const element = contentOf(pane, maps);
      if (!element || (MAPS[pane.id] && placedElement(element, placed, maps))) continue;
      const mark = WS.homes.get(element);
      if (mark?.isConnected) {
        if (mark.nextSibling === element) continue;
        dockedOff(pane, element);
        element.classList.remove('wstab');
        mark.after(element);
      } else if (element.parentElement !== hold && !(pane.content.kind === 'page' && !MAPS[pane.id])) {
        hold.append(element);
      }
    }
    drawToolbar();
    drawWindowMenu();
    host.log('verbose', 'workspace: drawn', WS.layout);
    dispatchEvent(new Event('resize'));
    // each pane that has just come on view draws itself now that it stands in the page
    const showing = WS.showing.splice(0);
    for (const show of showing) show();
  }
  function placedElement(element, placed, maps) {
    return [...placed].some(id => MAPS[id] && contentOf(byId(id), maps) === element);
  }
  /* Children in this order, moving only those not already in place, so a map's canvas or an editor is not rebuilt. */
  function keepChildren(box, kids) {
    for (const child of [...box.children]) if (!kids.includes(child)) child.remove();
    kids.forEach((kid, index) => { if (box.children[index] !== kid) box.insertBefore(kid, box.children[index] || null); });
  }
  function drawGroup(group, area, maps, placed) {
    let made = WS.groups.get(group.id);
    if (!made) {
      const strip = h('div', {class: 'wstabs', role: 'tablist', 'aria-label': `${group.id} panes`});
      const body = h('div', {class: 'wsbody'});
      made = {el: h('div', {class: 'wsgroup', 'data-group': group.id}, strip, body), strip, body};
      strip.addEventListener('keydown', event => tabKeys(event, group.id));
      WS.groups.set(group.id, made);
    }
    made.el.dataset.area = area;
    made.el.style.flex = group.size ? `${group.size} 1 0` : '1 1 0';
    const tabs = shownTabs(group), open = activeOf(group);
    group.active = open;
    const strip = tabs.map(id => tabButton(byId(id), group, id === open));
    fill(made.strip, ...strip);
    const bodies = [];
    for (const id of tabs) {
      const pane = byId(id), element = contentOf(pane, maps);
      if (!element) continue;
      placed.add(id);
      const shown = id === open;
      if (element.parentElement !== made.body) {
        home(element);
        dockedOn(pane, element);
        made.body.append(element);
      }
      bodies.push(element);
      showContent(pane, element, shown);
    }
    for (const child of [...made.body.children]) if (!bodies.includes(child)) $('#wsHold').append(child);
    // a map alone in a group at a side is as tall as the small map of the page as written, until the person shares it
    made.el.classList.toggle('mapalone', area !== 'main' && tabs.length === 1 && Boolean(MAPS[tabs[0]]) && !group.size);
    made.el.style.minWidth = `${Math.min(...tabs.map(id => byId(id).min_width || 0), 600)}px`;
    return made.el;
  }
  const tabs = new Map();
  /* A pane's tab, made once: the page's own tab for a view that has one, such as the node's Object and Brief, so what
   * opens that tab opens the pane; otherwise a tab of its own. */
  function tabButton(pane, group, open) {
    let button = tabs.get(pane.id);
    if (!button) {
      const own = pane.content.kind === 'page' ? host.tab?.(pane.content.page) : null;
      home(own);
      button = own || h('button', {type: 'button', onclick: () => activate(pane.id)});
      button.classList.add('wstab');
      Object.assign(button.dataset, {pane: pane.id});
      button.setAttribute('role', 'tab');
      if (!menued.has(button)) {
        menued.add(button);
        button.addEventListener('contextmenu', event => { event.preventDefault(); tabMenu(pane.id, event.clientX, event.clientY); });
      }
      button.addEventListener('pointerdown', event => { if (WS.grid) startDrag(event, pane.id); });
      button.addEventListener('keydown', event => {
        if ((event.shiftKey && event.key === 'F10') || event.key === 'ContextMenu') {
          event.preventDefault();
          const at = button.getBoundingClientRect();
          tabMenu(pane.id, at.left, at.bottom);
        }
      });
      tabs.set(pane.id, button);
    }
    button.hidden = false;
    button.title = pane.description;
    button.setAttribute('aria-selected', String(open));
    button.tabIndex = open ? 0 : -1;
    fill(button, icon(pane), h('span', {class: 'lbl'}, pane.title));
    return button;
  }
  function tabKeys(event, groupId) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = [...WS.groups.get(groupId).strip.querySelectorAll('[role=tab]')];
    const at = tabs.indexOf(document.activeElement);
    if (at < 0) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : (at + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    activate(tabs[next].dataset.pane);
    requestAnimationFrame(() => document.querySelector(`.wstab[data-pane="${CSS.escape(tabs[next].dataset.pane)}"]`)?.focus());
  }
  /* A pane's content shows when its tab is open; a view of the page is told to draw itself as it shows. */
  function showContent(pane, element, shown) {
    const was = !element.hidden && element.dataset.wsShown === 'true';
    element.dataset.wsShown = String(shown);
    if (pane.content.kind !== 'page' || MAPS[pane.id]) {
      element.hidden = !shown;
      if (shown && !was && !MAPS[pane.id]) WS.showing.push(() => WS.panes.get(pane.id)?.read());
      return;
    }
    const view = host.view(pane.content.page);
    element.hidden = !shown;
    if (shown && !was && view?.show) WS.showing.push(() => view.show());
  }
  /* A window of the page shown as a pane takes its body's room and leaves the overlay stack; back out, it is a window
   * again. Its own close button turns the pane off. */
  function dockedOn(pane, element) {
    if (pane.content.kind !== 'page' || MAPS[pane.id]) return;
    host.view(pane.content.page)?.docked?.(true, element.parentElement);
    element.classList.add('docked');
    watchClose(pane, element);
  }
  function dockedOff(pane, element) {
    if (pane.content.kind !== 'page' || MAPS[pane.id]) return;
    if (!element.classList.contains('docked')) return;
    element.classList.remove('docked');
    element.hidden = true;
    host.view(pane.content.page)?.docked?.(false, null);
  }
  const closing = new WeakSet();
  function watchClose(pane, element) {
    if (closing.has(element) || !element.classList.contains('window')) return;
    closing.add(element);
    new MutationObserver(() => {
      if (!element.classList.contains('docked') || !element.hidden) return;
      const id = [...(WS.state?.panes || [])].find(one => one.content.kind === 'page'
        && host.view(one.content.page)?.el === element)?.id;
      if (id && element.dataset.wsShown === 'true' && isShown(id)) setOn(id, false);
    }).observe(element, {attributes: true, attributeFilter: ['hidden']});
  }

  /* ---------- a pane's own content: a verb's result or a module's file ---------- */
  function makePane(pane) {
    const body = h('div', {class: 'wscontent'});
    const el = h('section', {class: 'pane wspane', 'data-pane': pane.id, 'aria-label': pane.title, tabindex: '-1'}, body);
    const made = {el, body, generation: 0, read: () => readPane(pane, made)};
    return made;
  }
  async function readPane(pane, made) {
    const generation = ++made.generation;
    if (pane.content.kind === 'resource') {
      if (pane.content.type.startsWith('text/html')) {
        fill(made.body, h('iframe', {class: 'wsframe', sandbox: '', src: `${pane.content.url}?project=${encodeURIComponent(WS.project)}`,
          title: pane.title}));
        return;
      }
      try {
        const response = await fetch(`${pane.content.url}?project=${encodeURIComponent(WS.project)}`);
        const text = await response.text();
        if (generation === made.generation) fill(made.body, h('pre', {class: 'wstext'}, text));
      } catch (error) { fill(made.body, h('p', {class: 'empty'}, error.message)); }
      return;
    }
    const address = host.selection();
    if (pane.selection && !address) {
      fill(made.body, h('p', {class: 'empty'}, `${pane.title} follows the selection: select a node on the map.`));
      return;
    }
    if (!made.body.childElementCount) fill(made.body, h('p', {class: 'loading'}, `Reading ${pane.title}…`));
    const query = new URLSearchParams({project: WS.project, pane: pane.id, ...(address && pane.selection ? {selection: address} : {}),
      ...host.layers()});
    let found;
    try { found = await host.getJson(`/api/workspace/pane?${query}`); }
    catch (error) {
      if (generation === made.generation) fill(made.body, h('div', {class: 'failed', role: 'alert'}, h('p', {}, error.message),
        error.body?.next ? h('p', {class: 'next'}, 'Next: ', h('code', {}, error.body.next)) : null));
      return;
    }
    if (generation !== made.generation) return;
    fill(made.body, h('div', {class: 'wsmeta'}, h('span', {class: 'eyebrow'}, pane.title),
      h('span', {class: 'chars', title: 'The length of the result an agent is handed for this read'}, `${Number(found.chars).toLocaleString('en')} characters, as an agent reads it`)),
      result(found.result),
      h('details', {class: 'raw'}, h('summary', {}, 'As an agent reads it'), h('pre', {class: 'wstext'}, JSON.stringify(found.result, null, 2))));
  }
  /* A verb's result as every surface shows it: text as text, a list as a list, an object as its fields. */
  function result(value, depth = 0) {
    if (value === null || value === undefined || value === '') return h('span', {class: 'none'}, '—');
    if (typeof value !== 'object') {
      const text = String(value);
      return text.includes('\n') ? h('pre', {class: 'wstext'}, text) : h('span', {}, text);
    }
    if (Array.isArray(value)) {
      if (!value.length) return h('span', {class: 'none'}, 'none');
      if (depth > 3) return h('code', {}, JSON.stringify(value));
      return h('ol', {class: 'wslist'}, value.slice(0, 200).map(one => h('li', {}, result(one, depth + 1))),
        value.length > 200 ? h('li', {class: 'none'}, `and ${value.length - 200} more`) : null);
    }
    if (depth > 3) return h('code', {}, JSON.stringify(value));
    return h('dl', {class: 'wsfields'}, Object.entries(value).flatMap(([key, one]) => [h('dt', {}, key.replace(/_/g, ' ')),
      h('dd', {}, result(one, depth + 1))]));
  }
  /* The panes that follow the selection or the map read again when either changes. */
  function refresh(selectionMoved = false) {
    if (!WS.on) return;
    for (const pane of WS.state.panes) {
      if (pane.content.kind !== 'verb' || !isShown(pane.id)) continue;
      if (selectionMoved && !pane.selection) continue;
      WS.panes.get(pane.id)?.read();
    }
    drawToolbar();
  }

  /* ---------- turning panes on and off, and moving them ---------- */
  function setOn(id, on) {
    if ((ownWindow(id) || !WS.grid) && classicAct(id, on)) return;
    const off = new Set(WS.layout.off);
    on ? off.delete(id) : off.add(id);
    WS.layout.off = [...off];
    if (on && !where(id)) placeDefault(id);
    render();
    save('layout');
  }
  function placeDefault(id) {
    const pane = byId(id);
    if (pane.area === 'float') { WS.layout.floating.push({pane: id, x: null, y: null, w: null, h: null}); return; }
    const area = WS.layout.areas[pane.area] || (WS.layout.areas[pane.area] = {size: null, groups: []});
    const group = area.groups.find(one => one.id === pane.group);
    if (group) group.tabs.push(id); else area.groups.push({id: pane.group, tabs: [id], active: id, size: null});
  }
  /* The pane open where it is: turned on, its tab the open one, a floating one brought to the front. */
  function activate(id) {
    if (!WS.on || !byId(id)) return false;
    if ((ownWindow(id) || !WS.grid) && classicAct(id, true)) return true;
    let changed = false;
    if (!isOn(id)) { WS.layout.off = WS.layout.off.filter(one => one !== id); changed = true; }
    if (!where(id)) { placeDefault(id); changed = true; }
    const found = where(id);
    if (found.area !== 'float' && found.group.active !== id) { found.group.active = id; changed = true; }
    render();
    if (found.area === 'float') WS.floats.get(id)?.box && host.overlay && WS.floats.get(id).box.focus?.();
    if (changed) save('layout');
    return true;
  }
  /* Whether a page view is shown as a pane: then its opener shows the pane instead of its window. */
  function reveal(page) {
    if (!WS.on || !WS.grid) return false;  // the page as written opens its own windows and tabs
    const pane = WS.state.panes.find(one => one.content.kind === 'page' && one.content.page === page);
    if (!pane || ownWindow(pane.id)) return false;  // a floating window of the page opens as itself
    activate(pane.id);
    return true;
  }
  function paneOfPage(page) {
    return WS.on && WS.grid ? WS.state.panes.find(one => one.content.kind === 'page' && one.content.page === page) || null : null;
  }
  function detach(id) {
    for (const area of AREAS) for (const group of WS.layout.areas[area]?.groups || []) {
      group.tabs = group.tabs.filter(one => one !== id);
      if (group.active === id) group.active = null;
    }
    for (const area of AREAS) if (WS.layout.areas[area]) WS.layout.areas[area].groups = WS.layout.areas[area].groups.filter(group => group.tabs.length);
    WS.layout.floating = WS.layout.floating.filter(one => one.pane !== id);
  }
  let groupsMade = 0;
  /* Move a pane: into a group at a place among its tabs, into a new group of an area, or floating at a point. */
  function moveTo(id, target) {
    const before = where(id);
    detach(id);
    if (target.kind === 'group') {
      const group = AREAS.flatMap(area => WS.layout.areas[area]?.groups || []).find(one => one.id === target.group);
      if (!group) return moveTo(id, {kind: 'area', area: target.area || 'right'});
      group.tabs.splice(Math.min(target.index ?? group.tabs.length, group.tabs.length), 0, id);
      group.active = id;
    } else if (target.kind === 'area') {
      const area = WS.layout.areas[target.area] || (WS.layout.areas[target.area] = {size: null, groups: []});
      if (!area.size && target.area !== 'main') area.size = target.area === 'bottom' ? 280 : 360;
      const name = `${byId(id).group}-${Date.now().toString(36)}${++groupsMade}`;
      area.groups.splice(target.first ? 0 : area.groups.length, 0, {id: name, tabs: [id], active: id, size: null});
    } else {
      const was = before?.floating;
      WS.layout.floating.push({pane: id, x: Math.round(target.x ?? was?.x ?? 0) || null, y: Math.round(target.y ?? was?.y ?? 0) || null,
        w: was?.w ?? null, h: was?.h ?? null});
    }
    WS.layout.off = WS.layout.off.filter(one => one !== id);
    render();
    save('layout');
  }
  /* Swap, the button on each map: the two maps exchange their places. */
  function swapMaps() {
    if (!WS.on || !WS.grid) return false;  // the page as written swaps as it always has, kept in this browser
    const two = where('web.map2d'), three = where('web.map3d');
    if (!two || !three) return false;
    const spot = found => found.area === 'float' ? {floating: found.floating} : {group: found.group, at: found.group.tabs.indexOf(found.group === two.group ? 'web.map2d' : 'web.map3d')};
    if (two.area === 'float' || three.area === 'float') return false;
    const a = spot(two), b = spot(three);
    if (a.group === b.group) return false;
    a.group.tabs[a.group.tabs.indexOf('web.map2d')] = 'web.map3d';
    b.group.tabs[b.group.tabs.indexOf('web.map3d')] = 'web.map2d';
    if (a.group.active === 'web.map2d') a.group.active = 'web.map3d';
    if (b.group.active === 'web.map3d') b.group.active = 'web.map2d';
    render();
    save('layout');
    return true;
  }
  function tabMenu(id, x, y) {
    const box = menuBox();
    const found = where(id);
    const choices = [['left', 'Move to Left'], ['main', 'Move to Main'], ['right', 'Move to Right'], ['bottom', 'Move to Bottom']]
      .map(([area, words]) => h('button', {type: 'button', role: 'menuitem', disabled: found?.area === area && found.group.tabs.length === 1,
        onclick: () => { box.hidden = true; moveTo(id, {kind: 'area', area}); }}, words));
    fill(box, h('div', {class: 'label'}, byId(id).title), ...choices,
      h('button', {type: 'button', role: 'menuitem', disabled: found?.area === 'float', onclick: () => { box.hidden = true; moveTo(id, {kind: 'float'}); }}, 'Float'),
      h('div', {class: 'sep', role: 'separator'}),
      h('button', {type: 'button', role: 'menuitem', onclick: () => { box.hidden = true; setOn(id, false); }}, 'Close'));
    showMenuAt(box, x, y);
  }
  function menuBox() {
    let box = $('#wsmenu');
    if (!box) {
      box = h('div', {id: 'wsmenu', class: 'menu wsfloatmenu', role: 'menu', hidden: true});
      document.body.append(box);
      host.overlay(box, {kind: 'menu'});
    }
    return box;
  }
  function showMenuAt(box, x, y) {
    box.hidden = false;
    const size = box.getBoundingClientRect();
    box.style.left = `${Math.max(8, Math.min(x, innerWidth - size.width - 8))}px`;
    box.style.top = `${Math.max(8, Math.min(y, innerHeight - size.height - 8))}px`;
  }

  /* ---------- floating panes ---------- */
  function drawFloat(pane, spot, maps, placed) {
    let made = WS.floats.get(pane.id);
    if (!made) {
      const body = h('div', {class: 'wsbody'});
      const box = h('div', {class: 'window wsfloat', role: 'dialog', 'aria-label': pane.title, 'data-pane': pane.id},
        h('div', {class: 'bar'}, h('span', {class: 'title'}, pane.title),
          h('button', {class: 'btn icon sm quiet', type: 'button', 'aria-label': `Dock ${pane.title}`, title: 'Dock it in its place',
            onclick: () => { detach(pane.id); placeDefaultDocked(pane.id); render(); save('layout'); }}, h('i', {class: 'i i-dock', 'aria-hidden': 'true'})),
          h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close',
            onclick: () => setOn(pane.id, false)}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}))),
        body);
      document.body.append(box);
      host.movable(box, {end: () => {
        const one = WS.layout.floating.find(entry => entry.pane === pane.id);
        if (!one) return;
        one.x = Math.round(parseFloat(box.style.left) || 0); one.y = Math.round(parseFloat(box.style.top) || 0);
        save('layout');
      }});
      new ResizeObserver(() => {
        const one = WS.layout.floating.find(entry => entry.pane === pane.id);
        if (!one || box.hidden || !box.style.width) return;
        const w = Math.round(box.offsetWidth), hh = Math.round(box.offsetHeight);
        if (one.w === w && one.h === hh) return;
        one.w = w; one.h = hh;
        save('layout');
        dispatchEvent(new Event('resize'));
      }).observe(box);
      made = {box, body};
      WS.floats.set(pane.id, made);
    }
    const {box, body} = made;
    box.hidden = false;
    box.style.minWidth = `${Math.min(pane.min_width || 240, innerWidth - 16)}px`;
    box.style.minHeight = `${Math.min(pane.min_height || 160, innerHeight - 16)}px`;
    if (spot.w) box.style.width = `${spot.w}px`;
    if (spot.h) box.style.height = `${spot.h}px`;
    if (spot.x !== null && spot.y !== null && spot.x !== undefined) {
      box.style.left = `${Math.max(0, Math.min(spot.x, innerWidth - 60))}px`;
      box.style.top = `${Math.max(0, Math.min(spot.y, innerHeight - 40))}px`;
    } else if (!box.style.left) host.place(box);
    const element = contentOf(pane, maps);
    if (!element) return;
    placed.add(pane.id);
    if (element.parentElement !== body) { home(element); dockedOn(pane, element); body.append(element); }
    showContent(pane, element, true);
  }
  function placeDefaultDocked(id) {
    const pane = byId(id);
    const area = pane.area === 'float' ? 'right' : pane.area;
    const groups = WS.layout.areas[area]?.groups || [];
    const group = groups.find(one => one.id === pane.group) || groups[0];
    if (group) { group.tabs.push(id); group.active = id; } else moveTo(id, {kind: 'area', area});
  }
  function closeFloat(id) {
    const made = WS.floats.get(id);
    if (!made) return;
    for (const child of [...made.body.children]) {
      const pane = byId(id);
      if (pane) dockedOff(pane, child);
      $('#wsHold').append(child);
    }
    made.box.remove();
    WS.floats.delete(id);
  }

  /* ---------- dragging a tab: onto a group, an area's edge, or away to float ---------- */
  function startDrag(event, id) {
    if (event.button !== 0 || narrow()) return;
    const from = [event.clientX, event.clientY];
    let ghost = null, mark = null, target = null;
    const move = moved => {
      if (!ghost) {
        if (Math.hypot(moved.clientX - from[0], moved.clientY - from[1]) < 6) return;
        ghost = h('div', {class: 'wsghost'}, byId(id).title);
        mark = h('div', {class: 'wsdrop', hidden: true});
        document.body.append(ghost, mark);
        document.body.classList.add('ws-dragging');
        showZones(true);
      }
      ghost.style.left = `${moved.clientX + 12}px`; ghost.style.top = `${moved.clientY + 8}px`;
      target = moved.ctrlKey ? {kind: 'float', x: moved.clientX - 40, y: moved.clientY - 16} : dropAt(moved.clientX, moved.clientY, id);
      const rect = target.rect;
      mark.hidden = !rect;
      if (rect) Object.assign(mark.style, {left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`});
    };
    const end = () => {
      removeEventListener('pointermove', move); removeEventListener('pointerup', end); removeEventListener('pointercancel', end);
      if (!ghost) return;
      ghost.remove(); mark.remove(); showZones(false);
      document.body.classList.remove('ws-dragging');
      if (target) moveTo(id, target);
    };
    addEventListener('pointermove', move);
    addEventListener('pointerup', end);
    addEventListener('pointercancel', end);
  }
  function showZones(on) {
    for (const zone of document.querySelectorAll('.wszone')) zone.remove();
    if (!on) return;
    const root = $('#ws').getBoundingClientRect();
    const band = 40;
    const zones = {left: {left: root.left, top: root.top, width: band, height: root.height},
      right: {left: root.right - band, top: root.top, width: band, height: root.height},
      bottom: {left: root.left, top: root.bottom - band, width: root.width, height: band}};
    for (const [area, rect] of Object.entries(zones)) {
      document.body.append(h('div', {class: 'wszone', 'data-area': area, style: {left: `${rect.left}px`, top: `${rect.top}px`,
        width: `${rect.width}px`, height: `${rect.height}px`}}));
    }
  }
  function dropAt(x, y, id) {
    const root = $('#ws').getBoundingClientRect(), band = 40;
    const inside = x >= root.left && x <= root.right && y >= root.top && y <= root.bottom;
    if (inside) {
      if (x < root.left + band) return {kind: 'area', area: 'left', first: true, rect: {left: root.left, top: root.top, width: band * 3, height: root.height}};
      if (x > root.right - band) return {kind: 'area', area: 'right', rect: {left: root.right - band * 3, top: root.top, width: band * 3, height: root.height}};
      if (y > root.bottom - band) return {kind: 'area', area: 'bottom', rect: {left: root.left, top: root.bottom - band * 3, width: root.width, height: band * 3}};
    }
    for (const [groupId, made] of WS.groups) {
      if (!made.el.isConnected) continue;
      const strip = made.strip.getBoundingClientRect(), body = made.el.getBoundingClientRect();
      if (x < body.left || x > body.right || y < body.top || y > body.bottom) continue;
      const group = AREAS.flatMap(area => WS.layout.areas[area]?.groups || []).find(one => one.id === groupId);
      if (!group) continue;
      if (group.tabs.length === 1 && group.tabs[0] === id) return {kind: 'none'};
      const tabs = [...made.strip.querySelectorAll('[role=tab]')];
      let index = group.tabs.length;
      if (y <= strip.bottom) {
        const after = tabs.findIndex(tab => x < tab.getBoundingClientRect().left + tab.offsetWidth / 2);
        if (after >= 0) index = group.tabs.indexOf(tabs[after].dataset.pane);
      }
      return {kind: 'group', group: groupId, index, area: made.el.dataset.area, rect: y <= strip.bottom
        ? {left: strip.left, top: strip.top, width: strip.width, height: strip.height} : {left: body.left, top: body.top, width: body.width, height: body.height}};
    }
    return {kind: 'float', x: x - 40, y: y - 16, rect: null};
  }

  /* ---------- splitters: an area's size and a group's share ---------- */
  function splitter(area) {
    const handle = h('div', {class: 'wssplit', 'data-area': area, role: 'separator', tabindex: '0',
      'aria-orientation': area === 'bottom' ? 'horizontal' : 'vertical', 'aria-label': `The ${area} area's size`,
      title: 'Drag to resize; double-click to reset'});
    const set = pixels => {
      const most = area === 'bottom' ? innerHeight * 0.7 : innerWidth * 0.6;
      WS.layout.areas[area].size = Math.round(Math.max(160, Math.min(most, pixels)));
      $('.app').style.setProperty(`--ws-${area}`, `${WS.layout.areas[area].size}px`);
      dispatchEvent(new Event('resize'));
    };
    handle.addEventListener('pointerdown', event => {
      event.preventDefault();
      handle.classList.add('dragging');
      const root = $('#ws').getBoundingClientRect();
      const move = moved => set(area === 'left' ? moved.clientX - root.left : area === 'right' ? root.right - moved.clientX : root.bottom - moved.clientY);
      const end = () => { handle.classList.remove('dragging'); removeEventListener('pointermove', move); removeEventListener('pointerup', end); save('layout'); };
      addEventListener('pointermove', move);
      addEventListener('pointerup', end);
    });
    handle.addEventListener('dblclick', () => {
      const declared = WS.state.defaults.layout.areas[area]?.size;
      set(declared || 320); save('layout');
    });
    handle.addEventListener('keydown', event => {
      const grow = {left: ['ArrowRight', 'ArrowLeft'], right: ['ArrowLeft', 'ArrowRight'], bottom: ['ArrowUp', 'ArrowDown']}[area];
      const by = event.key === grow[0] ? 24 : event.key === grow[1] ? -24 : 0;
      if (!by) return;
      event.preventDefault();
      set((WS.layout.areas[area].size || 320) + by);
      save('layout');
    });
    return handle;
  }
  function groupSplitter(area, index) {
    const across = area === 'bottom' && !narrow();
    const handle = h('div', {class: `wsgsplit${across ? ' across' : ''}`, role: 'separator',
      'aria-orientation': across ? 'vertical' : 'horizontal', title: 'Drag to share the room between the panes'});
    handle.addEventListener('pointerdown', event => {
      event.preventDefault();
      const groups = (WS.layout.areas[area].groups || []).filter(group => shownTabs(group).length);
      const one = groups[index - 1], two = groups[index];
      const els = [WS.groups.get(one.id).el, WS.groups.get(two.id).el];
      const rects = els.map(el => el.getBoundingClientRect());
      const total = across ? rects[0].width + rects[1].width : rects[0].height + rects[1].height;
      const start = across ? rects[0].left : rects[0].top;
      const shares = groups.map(group => group.size || 1), pair = shares[index - 1] + shares[index];
      const move = moved => {
        const first = Math.max(0.1, Math.min(0.9, ((across ? moved.clientX : moved.clientY) - start) / total));
        one.size = +(pair * first).toFixed(3); two.size = +(pair * (1 - first)).toFixed(3);
        els[0].style.flex = `${one.size} 1 0`; els[1].style.flex = `${two.size} 1 0`;
        dispatchEvent(new Event('resize'));
      };
      const end = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', end); save('layout'); };
      addEventListener('pointermove', move);
      addEventListener('pointerup', end);
    });
    return handle;
  }

  /* ---------- the toolbar ---------- */
  function icon(record) {
    if (record.icon_url) return h('img', {class: 'i img', src: `${record.icon_url}?project=${encodeURIComponent(WS.project || '')}`, alt: '', 'aria-hidden': 'true'});
    return h('i', {class: `i i-${record.icon || 'tool'}`, 'aria-hidden': 'true'});
  }
  /* A tool is left out when the page carries neither its pane nor its command. */
  function offered(tool) {
    if (!tool) return false;
    const action = tool.action;
    if (action.kind === 'pane') return Boolean(byId(action.pane) && usable(byId(action.pane)));
    if (action.kind === 'page') return host.hasCommand(action.page);
    return true;
  }
  function pressed(tool) {
    return tool.action.kind === 'pane' && isShown(tool.action.pane);
  }
  function usableNow(tool) {
    return !tool.selection || Boolean(host.selection());
  }
  function drawToolbar() {
    const bar = $('#toolbar');
    if (!bar) return;
    bar.hidden = false;
    const slots = WS.toolbar.toolbar.map(slot => slot.map(toolById).filter(offered)).filter(slot => slot.length);
    const extra = WS.toolbar.extra.map(toolById).filter(offered);
    const buttons = slots.map((slot, index) => slotButton(slot, index));
    buttons.push(h('button', {class: 'btn sm quiet wsslot more', type: 'button', 'aria-haspopup': 'menu', 'aria-label': 'Extra tools',
      title: 'Extra tools, and Edit Toolbar…', onclick: event => extraMenu(event.currentTarget, extra)}, h('span', {}, '…')));
    fill(bar, ...buttons);
  }
  function slotButton(slot, index) {
    const tool = slot[0];
    const press = pressed(tool);
    const button = h('button', {class: `btn sm quiet wsslot${slot.length > 1 ? ' grouped' : ''}`, type: 'button', 'data-tool': tool.id,
      title: tool.description + (tool.shortcut ? ` (${tool.shortcut})` : ''), 'aria-label': tool.title,
      'aria-keyshortcuts': tool.shortcut || null, 'aria-pressed': tool.action.kind === 'pane' ? String(press) : null,
      'aria-haspopup': slot.length > 1 ? 'menu' : null, disabled: !usableNow(tool),
      onclick: () => run(tool),
      oncontextmenu: event => { event.preventDefault(); slot.length > 1 ? flyout(slot, index, event.currentTarget) : toolbarMenu(event.clientX, event.clientY); }},
    icon(tool), h('span', {class: 'lbl'}, tool.title));
    let held = null;
    button.addEventListener('pointerdown', () => {
      if (slot.length < 2) return;
      held = setTimeout(() => { held = 'opened'; flyout(slot, index, button); }, 500);
    });
    const letGo = () => { if (held && held !== 'opened') clearTimeout(held); };
    button.addEventListener('pointerup', event => { if (held === 'opened') event.preventDefault(); letGo(); });
    button.addEventListener('pointerleave', letGo);
    button.addEventListener('click', event => { if (held === 'opened') { event.stopImmediatePropagation(); held = null; } }, true);
    return button;
  }
  function flyout(slot, index, anchor) {
    const box = menuBox();
    fill(box, slot.map(tool => h('button', {type: 'button', role: 'menuitemradio', 'aria-checked': String(tool === slot[0]),
      title: tool.description, disabled: !usableNow(tool), onclick: () => {
        box.hidden = true;
        const ids = WS.toolbar.toolbar.find(one => one.includes(tool.id));
        if (ids) { ids.splice(ids.indexOf(tool.id), 1); ids.unshift(tool.id); save('toolbar'); drawToolbar(); }
        run(tool);
      }}, h('span', {class: 'wsitem'}, icon(tool), tool.title), tool.shortcut ? h('kbd', {}, tool.shortcut) : null)),
    h('div', {class: 'sep', role: 'separator'}), h('button', {type: 'button', role: 'menuitem', onclick: () => { box.hidden = true; editToolbar(); }}, 'Edit Toolbar…'));
    const at = anchor.getBoundingClientRect();
    showMenuAt(box, at.left, at.bottom + 4);
  }
  function extraMenu(anchor, extra) {
    const box = menuBox();
    fill(box, extra.length ? extra.map(tool => h('button', {type: 'button', role: 'menuitem', title: tool.description, disabled: !usableNow(tool),
      onclick: () => { box.hidden = true; run(tool); }}, h('span', {class: 'wsitem'}, icon(tool), tool.title), tool.shortcut ? h('kbd', {}, tool.shortcut) : null))
      : h('div', {class: 'label'}, 'No extra tools'),
    h('div', {class: 'sep', role: 'separator'}), h('button', {type: 'button', role: 'menuitem', onclick: () => { box.hidden = true; editToolbar(); }}, 'Edit Toolbar…'));
    const at = anchor.getBoundingClientRect();
    showMenuAt(box, at.left, at.bottom + 4);
  }
  function toolbarMenu(x, y) {
    const box = menuBox();
    fill(box, h('button', {type: 'button', role: 'menuitem', onclick: () => { box.hidden = true; editToolbar(); }}, 'Edit Toolbar…'),
      h('button', {type: 'button', role: 'menuitem', onclick: async () => { box.hidden = true; await act('reset', {part: 'toolbar'}, 'The toolbar is back as the workspace saved it.'); }}, 'Reset the toolbar'));
    showMenuAt(box, x, y);
  }
  /* What a tool does: show or hide its pane, run the page's command, run its verb, after its form when it has one,
   * or open its link. */
  async function run(tool) {
    const action = tool.action, address = host.selection();
    host.log('info', 'tool', tool.id, action);
    if (tool.selection && !address) return host.toast(`${tool.title} acts on the selected node: select one first.`);
    if (action.kind === 'pane') {
      if (isShown(action.pane)) setOn(action.pane, false); else activate(action.pane);
      return;
    }
    if (action.kind === 'page') return host.command(action.page, address);
    if (action.kind === 'link') {
      const url = action.url.startsWith('/api/') ? `${action.url}?project=${encodeURIComponent(WS.project)}` : action.url;
      if (url.startsWith('metaform://')) return host.openAddress(url);
      return void window.open(url, '_blank', 'noopener');
    }
    if ((action.form || []).length) return openForm(tool, address);
    return runVerb(tool, address, {});
  }
  async function runVerb(tool, address, values, confirm = false) {
    const body = {project: WS.project, item: tool.id, ...(tool.selection ? {selection: address} : {}), values, ...(confirm ? {confirm: true} : {})};
    let response;
    try {
      response = await fetch('/api/workspace/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    } catch (error) { host.toast(error.message); return false; }
    const found = await response.json().catch(() => ({}));
    if (response.status === 409 && found.confirm && !confirm) {
      if (!await host.confirmAct({title: `${tool.title}?`, text: found.error, verb: tool.title, cancel: 'Cancel'})) return false;
      return runVerb(tool, address, values, true);
    }
    if (!response.ok) { host.toast([found.error, found.next ? `Next: ${found.next}` : ''].filter(Boolean).join(' ')); return false; }
    showResult(tool, found.result);
    refresh();
    return true;
  }
  function showResult(tool, value) {
    const box = windowBox('wsresult', tool.title);
    fill(box.querySelector('.body'), result(value),
      h('details', {class: 'raw'}, h('summary', {}, 'As every surface shows it'), h('pre', {class: 'wstext'}, JSON.stringify(value, null, 2))));
    box.hidden = false;
  }
  function windowBox(id, title, {dialog = false} = {}) {
    let box = document.getElementById(id);
    if (!box) {
      box = h('div', {id, class: `window${dialog ? ' dialog' : ' movable'} wswindow`, hidden: true, role: 'dialog', 'aria-modal': dialog ? 'true' : null,
        'aria-labelledby': `${id}Title`},
      h('div', {class: 'bar'}, h('span', {class: 'title', id: `${id}Title`}),
        h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close (Escape)',
          onclick: () => { box.hidden = true; }}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}))),
      h('div', {class: 'body'}), h('div', {class: 'foot acts'}));
      document.body.append(box);
      host.overlay(box, {kind: dialog ? 'dialog' : 'window', close: () => { box.hidden = true; }});
      if (!dialog) host.movable(box);
    }
    box.querySelector('.title').textContent = title;
    fill(box.querySelector('.foot'));
    return box;
  }
  /* A small form for a tool whose verb takes more than its fixed arguments: each field typed as the verb declares it,
   * its help beside it. */
  function openForm(tool, address) {
    const box = windowBox('wsform', tool.title, {dialog: true});
    const fields = tool.action.form.map(field => {
      const id = `wsf-${field.name}`;
      let input;
      if (field.choices) input = h('select', {id, name: field.name}, field.required ? null : h('option', {value: ''}, '—'),
        field.choices.map(one => h('option', {value: one}, one)));
      else if (field.kind === 'bool') input = h('input', {id, name: field.name, type: 'checkbox'});
      else if (field.kind === 'int') input = h('input', {id, name: field.name, type: 'number', step: '1'});
      else if (field.kind === 'json' || field.many) input = h('textarea', {id, name: field.name, rows: field.many ? 3 : 4});
      else input = h('input', {id, name: field.name, type: 'text', autocomplete: 'off'});
      if (field.required) input.setAttribute('aria-required', 'true');
      return {field, input, row: h('label', {class: 'field wsfield', for: id},
        h('span', {}, field.name.replace(/_/g, ' '), field.required ? h('small', {}, ' · required') : null), input,
        h('small', {class: 'hint'}, field.help))};
    });
    const go = h('button', {class: 'btn primary', type: 'submit'}, tool.title);
    const form = h('form', {class: 'wsformbody', onsubmit: async event => {
      event.preventDefault();
      const values = {};
      for (const {field, input} of fields) {
        let value = input.type === 'checkbox' ? input.checked : input.value.trim();
        if (field.kind === 'int' && value !== '') value = Number(value);
        if (field.kind === 'json' && value) { try { value = JSON.parse(value); } catch { return host.toast(`${field.name} is not JSON.`); } }
        if (field.many && typeof value === 'string' && value) value = value.split('\n').map(one => one.trim()).filter(Boolean);
        if (field.required && (value === '' || value === false)) { input.focus(); return host.toast(`${field.name} is needed.`); }
        if (value !== '' && value !== false) values[field.name] = value;
      }
      go.disabled = true;
      const done = await runVerb(tool, address, values);
      go.disabled = false;
      if (done) box.hidden = true;
    }}, tool.selection && address ? h('p', {class: 'hint'}, `At ${address}`) : null, fields.map(one => one.row),
    h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => { box.hidden = true; }}, 'Cancel'), go));
    fill(box.querySelector('.body'), form);
    box.hidden = false;
  }

  /* ---------- Edit Toolbar… ---------- */
  function editToolbar() {
    const box = windowBox('wsedit', 'Edit Toolbar', {dialog: true});
    let draft = copy(WS.toolbar);
    const lists = {};
    const row = (id, list, slotIndex, inSlot) => {
      const tool = toolById(id);
      const item = h('li', {class: `wsedititem${inSlot ? ' inslot' : ''}`, tabindex: '-1', 'data-id': id, draggable: 'true',
        title: tool?.description || id},
      tool ? icon(tool) : null, h('span', {class: 'name'}, tool?.title || id), h('small', {class: 'why'}, tool?.description || ''));
      item.addEventListener('dragstart', event => { event.dataTransfer.setData('text/plain', id); item.classList.add('dragging'); });
      item.addEventListener('dragend', () => item.classList.remove('dragging'));
      item.addEventListener('dragover', event => { event.preventDefault(); item.classList.add('over'); });
      item.addEventListener('dragleave', () => item.classList.remove('over'));
      item.addEventListener('drop', event => {
        event.preventDefault(); event.stopPropagation();
        const dragged = event.dataTransfer.getData('text/plain');
        if (!dragged || dragged === id) return draw();
        remove(dragged);
        if (list === 'toolbar') draft.toolbar[draft.toolbar.findIndex(slot => slot.includes(id))]?.push(dragged);  // shares the slot
        else draft.extra.splice(draft.extra.indexOf(id), 0, dragged);
        draw(dragged);
      });
      item.addEventListener('keydown', event => keys(event, id, list));
      return item;
    };
    const remove = id => {
      draft.toolbar = draft.toolbar.map(slot => slot.filter(one => one !== id)).filter(slot => slot.length);
      draft.extra = draft.extra.filter(one => one !== id);
    };
    const flat = () => [...draft.toolbar.flatMap(slot => slot.map(id => ['toolbar', id])), ...draft.extra.map(id => ['extra', id])];
    function keys(event, id, list) {
      const all = flat();
      const at = all.findIndex(([, one]) => one === id);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (event.altKey) {
          if (list === 'toolbar') {
            const slot = draft.toolbar.findIndex(one => one.includes(id)), by = event.key === 'ArrowDown' ? 1 : -1;
            const to = slot + by;
            if (to >= 0 && to < draft.toolbar.length) [draft.toolbar[slot], draft.toolbar[to]] = [draft.toolbar[to], draft.toolbar[slot]];
          } else {
            const index = draft.extra.indexOf(id), to = index + (event.key === 'ArrowDown' ? 1 : -1);
            if (to >= 0 && to < draft.extra.length) [draft.extra[index], draft.extra[to]] = [draft.extra[to], draft.extra[index]];
          }
          return draw(id);
        }
        const next = all[(at + (event.key === 'ArrowDown' ? 1 : -1) + all.length) % all.length];
        return focusItem(next[1]);
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        remove(id);
        if (list === 'toolbar') draft.extra.unshift(id); else draft.toolbar.push([id]);
        draw(id);
      }
    }
    const focusItem = id => box.querySelector(`li[data-id="${CSS.escape(id)}"]`)?.focus();
    const zone = (name, title) => {
      const list = h('ol', {class: 'wseditlist', 'aria-label': title});
      list.addEventListener('dragover', event => event.preventDefault());
      list.addEventListener('drop', event => {
        event.preventDefault();
        const dragged = event.dataTransfer.getData('text/plain');
        if (!dragged) return;
        remove(dragged);
        if (name === 'toolbar') draft.toolbar.push([dragged]); else draft.extra.push(dragged);
        draw(dragged);
      });
      lists[name] = list;
      return h('section', {class: 'wseditcol'}, h('h3', {class: 'eyebrow'}, title), list);
    };
    function draw(focus = null) {
      fill(lists.toolbar, draft.toolbar.map((slot, index) => h('li', {class: 'wseditslot'},
        h('ol', {}, slot.map((id, at) => {
          const item = row(id, 'toolbar', index, at > 0);
          if (at > 0) item.append(h('button', {class: 'btn sm quiet', type: 'button', title: 'Give it a slot of its own',
            onclick: () => { remove(id); draft.toolbar.splice(index + 1, 0, [id]); draw(id); }}, 'Own slot'));
          return item;
        })))));
      fill(lists.extra, draft.extra.map(id => row(id, 'extra')));
      for (const item of box.querySelectorAll('li[data-id]')) item.tabIndex = -1;
      const first = box.querySelector('li[data-id]');
      if (first) first.tabIndex = 0;
      if (focus) focusItem(focus);
    }
    fill(box.querySelector('.body'), h('p', {class: 'hint'}, 'Drag a tool between the lists or within them; drop it on another tool to share its slot. '
      + 'With the keyboard: Up and Down move the focus, Alt with Up or Down moves the tool, Enter moves it to the other list.'),
    h('div', {class: 'wseditcols'}, zone('toolbar', 'Toolbar'), zone('extra', 'Extra tools')));
    fill(box.querySelector('.foot'),
      h('button', {class: 'btn', type: 'button', onclick: () => { draft = copy(WS.state.defaults.toolbar); draw(); }}, 'Restore Defaults'),
      h('button', {class: 'btn', type: 'button', onclick: () => { draft = {toolbar: [], extra: flat().map(([, id]) => id)}; draw(); }}, 'Clear Tools'),
      h('span', {class: 'grow'}),
      h('button', {class: 'btn keep', type: 'button', onclick: () => { box.hidden = true; }}, 'Cancel'),
      h('button', {class: 'btn primary', type: 'button', onclick: () => {
        WS.toolbar = draft; box.hidden = true; drawToolbar(); save('toolbar'); host.toast('The toolbar is saved.');
      }}, 'Done'));
    draw();
    box.hidden = false;
  }

  /* ---------- the Window menu ---------- */
  function drawWindowMenu() {
    const box = $('#windowbox');
    if (!box) return;
    $('#windowPick').hidden = false;
    const panes = [...WS.state.panes].filter(usable).sort((a, b) => a.title.localeCompare(b.title));
    fill(box, h('div', {class: 'label'}, 'Panes'),
      panes.map(pane => {
        const checked = (!WS.grid && windowed(pane)) || ownWindow(pane.id) ? isShown(pane.id) : isOn(pane.id);  // a window: while open
        return h('button', {type: 'button', role: 'menuitemcheckbox', 'aria-checked': String(checked), title: pane.description,
          onclick: () => { setOn(pane.id, !checked); drawWindowMenu(); }},
      h('span', {class: 'wsitem'}, h('i', {class: 'i i-check wscheck', 'aria-hidden': 'true'}), pane.title));
      }),
      h('div', {class: 'sep', role: 'separator'}),
      h('button', {type: 'button', role: 'menuitem', 'aria-haspopup': 'menu', id: 'workspacesBtn', onclick: event => workspacesMenu(event.currentTarget),
        onkeydown: event => { if (event.key === 'ArrowRight') { event.preventDefault(); workspacesMenu(event.currentTarget); } }},
      h('span', {}, 'Workspaces'), h('b', {}, WS.state.workspace)),
      h('button', {type: 'button', role: 'menuitem', onclick: () => { box.hidden = true; editToolbar(); }}, 'Edit Toolbar…'));
  }
  function workspacesMenu(anchor) {
    const box = $('#wsworkspaces');
    const active = WS.state.workspace;
    fill(box, WS.state.workspaces.map(name => h('button', {type: 'button', role: 'menuitemradio', 'aria-checked': String(name === active),
      onclick: async () => { closeMenus(); await act('select', {name}, `Workspace ${name}.`); }},
    h('span', {class: 'wsitem'}, h('i', {class: 'i i-check wscheck', 'aria-hidden': 'true'}), name))),
    h('div', {class: 'sep', role: 'separator'}),
    h('button', {type: 'button', role: 'menuitem', onclick: () => { closeMenus(); newWorkspace(); }}, 'New Workspace…'),
    h('button', {type: 'button', role: 'menuitem', onclick: async () => { closeMenus(); await act('reset', {}, `${active} is back as it was saved.`); }}, `Reset ${active}`),
    h('button', {type: 'button', role: 'menuitem', disabled: WS.state.workspaces.length < 2, onclick: () => { closeMenus(); deleteWorkspace(); }}, 'Delete Workspace…'));
    box.hidden = false;
    const at = anchor.getBoundingClientRect(), size = box.getBoundingClientRect();
    const left = at.right + size.width + 8 < innerWidth ? at.right + 2 : Math.max(8, at.left - size.width - 2);
    Object.assign(box.style, {left: `${left}px`, top: `${Math.max(8, Math.min(at.top, innerHeight - size.height - 8))}px`});
  }
  function closeMenus() { $('#wsworkspaces').hidden = true; $('#windowbox').hidden = true; }
  function newWorkspace() {
    const box = windowBox('wsask', 'New Workspace', {dialog: true});
    const name = h('input', {type: 'text', maxlength: '40', 'data-autofocus': '', 'aria-label': 'The workspace\'s name', placeholder: 'Reading, Review…'});
    const form = h('form', {onsubmit: async event => {
      event.preventDefault();
      const named = name.value.trim();
      if (!named) return name.focus();
      if (named.toLowerCase() === 'default') return host.toast('Default is the declared defaults; choose another name.');
      if (WS.state.workspaces.includes(named) && !await host.confirmAct({title: `Replace ${named}?`, text: `${named} is saved over with the toolbar and panes as they are now.`, verb: 'Replace', danger: false})) return;
      if (await act('save', {name: named}, `Saved as ${named}, now the active workspace.`)) box.hidden = true;
    }}, h('label', {class: 'field'}, h('span', {}, 'Name'), name),
    h('p', {class: 'hint'}, 'The toolbar and the panes as they are now, under this name. Every project opens with the active workspace.'),
    h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => { box.hidden = true; }}, 'Cancel'),
      h('button', {class: 'btn primary', type: 'submit'}, 'Save')));
    fill(box.querySelector('.body'), form);
    box.hidden = false;
  }
  function deleteWorkspace() {
    const box = windowBox('wsask', 'Delete Workspace', {dialog: true});
    const names = WS.state.workspaces.filter(name => name !== 'Default');
    const pick = h('select', {'aria-label': 'The workspace to delete', 'data-autofocus': ''}, names.map(name => h('option', {value: name}, name)));
    fill(box.querySelector('.body'), h('label', {class: 'field'}, h('span', {}, 'Workspace'), pick),
      h('p', {class: 'hint'}, 'Default cannot be deleted: it is what the modules declare.'),
      h('div', {class: 'acts'}, h('button', {class: 'btn keep', type: 'button', onclick: () => { box.hidden = true; }}, 'Cancel'),
        h('button', {class: 'btn danger', type: 'button', onclick: async () => {
          const name = pick.value;
          box.hidden = true;
          if (!await host.confirmAct({title: `Delete ${name}?`, lost: [`The workspace ${name}`], kept: ['The toolbar and panes as they are now', 'Default and every other workspace'], verb: 'Delete'})) return;
          await act('delete', {name}, `Deleted ${name}.`);
        }}, 'Delete')));
    box.hidden = false;
  }

  /* ---------- the tools' keys: each tool a module gives a shortcut runs from the keyboard ----------
   * A key with Alt, Ctrl or Meta as the tool declares it, such as Alt+B, by the key's place, so a Mac's Option, which
   * types characters, works too; a bare key such as / or ? is the page's own and is left to it. Not while a field or
   * a window over the page holds the keys. */
  function toolKeys() {
    if (!WS.on) return [];
    const placed = new Set([...WS.toolbar.toolbar.flat(), ...WS.toolbar.extra]);
    return WS.state.items.filter(tool => tool.shortcut && placed.has(tool.id) && offered(tool));
  }
  const codeOf = key => /^[A-Z]$/i.test(key) ? `Key${key.toUpperCase()}` : /^[0-9]$/.test(key) ? `Digit${key}` : null;
  addEventListener('keydown', event => {
    if (!WS.on || event.defaultPrevented || event.isComposing) return;
    if (!(event.altKey || event.ctrlKey || event.metaKey)) return;
    const target = event.target instanceof Element ? event.target : document.body;
    if (target.closest('input, textarea, select, .CodeMirror, [contenteditable="true"]') || host.overlayHolds?.(target)) return;
    for (const tool of toolKeys()) {
      const parts = tool.shortcut.split('+'), key = parts.at(-1);
      const mods = new Set(parts.slice(0, -1));
      if (mods.has('Alt') !== event.altKey || mods.has('Ctrl') !== event.ctrlKey || mods.has('Meta') !== event.metaKey
        || mods.has('Shift') !== event.shiftKey) continue;
      if (codeOf(key) ? event.code !== codeOf(key) : event.key !== key) continue;
      event.preventDefault();
      run(tool);
      return;
    }
  });

  /* ---------- a narrow screen: the areas stack, main first ---------- */
  matchMedia(NARROW).addEventListener('change', () => render());
  addEventListener('resize', () => { for (const [, made] of WS.floats) if (!made.box.hidden) keepInView(made.box); });
  function keepInView(box) {
    const at = box.getBoundingClientRect();
    if (at.left > innerWidth - 60) box.style.left = `${Math.max(0, innerWidth - 120)}px`;
    if (at.top > innerHeight - 40) box.style.top = `${Math.max(0, innerHeight - 80)}px`;
  }

  return {load, render, refresh, activate, reveal, paneOfPage, swapMaps, setOn, isShown, isOn,
    // on: the page laid out in the workspace's areas; active: the workspace read, its toolbar and Window menu drawn,
    // in the page as written too
    get on() { return WS.on && WS.grid; }, get active() { return WS.on; }, grid: () => WS.on && WS.grid, state: () => WS.state, view: () => WS.view || WS.state?.view || {}, layout: () => WS.layout, toolbar: () => WS.toolbar, toolKeys,
    edit: editToolbar, moveTo, where: id => { const found = where(id); return found ? {area: found.area, group: found.group?.id || null} : null; },
    reset() { WS.on = false; leave(); }};
}
