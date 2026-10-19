"""The 2D figure rests beside its work and resumes after temporary motion."""
import pytest

from metaform.modules.web.tests.test_web import (  # noqa: F401 -- shared fixtures
    browser,
    live_session,
    mapped,
    opened,
    simulated_dispatch_control,
    started,
    web,
)

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-035')]


def test_working_2d_figures_hold_separate_places_and_resume_after_temporary_motion(
        run, web, mapped, browser):  # noqa: F811 -- shared fixtures
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    tickets = [store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Inspect the work')
               for _ in range(2)]
    for ticket, glyph in zip(tickets, ('slime', 'owl')):
        run('map', 'work', 'op=edit', f'id={ticket.id}', f'glyph={glyph}', cwd=mapped)
        store.take_work(ticket.id, by='codex')
        live_session(ticket.id, 'codex')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.evaluate("""async () => {
        const {swap} = await import('/page/app/camera/flight.js'); await swap(true);
    }""")
    # a predicate must be synchronous to be waited on: an async one is a promise, truthy at once
    page.evaluate("async () => { window.__roam2d = await import('/page/app/figures/roam2d.js'); }")
    page.wait_for_function('() => window.__roam2d.ROAM2D.figures.size === 2')
    found = page.evaluate("""async () => {
        const {ROAM2D, again2d, spot2d} = await import('/page/app/figures/roam2d.js');
        const {M} = await import('/page/app/map2d/build.js');
        const {D} = await import('/page/app/agents/dispatch.js');
        window.metaform.pause3d(true);
        const figures = [...ROAM2D.figures.values()], target = spot2d(M.base, figures[0].target);
        // Run the real frame callback at 50 ms intervals without waiting on wall-clock timing.
        const realFrame = window.requestAnimationFrame, realNow = performance.now.bind(performance);
        let tick, now = realNow();
        cancelAnimationFrame(ROAM2D.frame); ROAM2D.frame = 0;
        window.requestAnimationFrame = callback => {
            if (callback.name === 'roam2d') { tick = callback; return -1; }
            return realFrame(callback);
        };
        performance.now = () => now;
        again2d();
        const step = count => {
            for (let n = 0; n < count; n++) {
                now += 50;
                for (const f of figures) f.nextAct = 1e9;
                tick();
            }
        };
        try {
            for (const f of figures) Object.assign(f, {stage: 'circling', clock: 0, act: null, reach: null,
                x: target.x, y: target.y, from: {x: 0, y: 0}});
            step(60);
            const places = figures.map(f => ({x: f.x, y: f.y})), radius = [0, 0], lift = [];
            for (let n = 0; n < 200; n++) {
                step(1);
                figures.forEach((f, i) => {
                    radius[i] = Math.max(radius[i], Math.hypot(f.x - places[i].x, f.y - places[i].y));
                    // A resting hopper's feet cannot remain frozen above its resting spot.
                    if (f.motion.go === 'hop') {
                        const image = f.g.firstChild;
                        lift.push((f.y + f.size / 2 - Number(image.getAttribute('y')) - f.size) / f.size);
                    }
                });
            }
            const f = figures[0], before = {...places[0]};
            const away = () => Math.hypot(f.x - before.x, f.y - before.y);
            f.act = {kind: 'peek', at: f.clock, long: 1}; step(10);
            const actDeparture = away(); step(60); const actReturn = away();
            f.reach = {to: f.home, at: f.clock}; step(13);
            const reachDeparture = away(); step(60); const reachReturn = away();
            const session = D.sessions.find(one => one.work_id === f.id);
            session.activity = 'waiting'; step(30); const waiting = {x: f.x, y: f.y}; step(20);
            const waitingDrift = Math.hypot(f.x - waiting.x, f.y - waiting.y);
            session.activity = 'working';
            D.signals = [{session_id: session.session_id, signal: 'spinning-calls', active: true}];
            step(30); const restless = {x: f.x, y: f.y}; step(20);
            const restlessMoved = Math.hypot(f.x - restless.x, f.y - restless.y);
            D.signals = []; step(40);
            return {radius, separation: Math.hypot(places[0].x - places[1].x, places[0].y - places[1].y),
                sizes: figures.map(f => f.size), lift: Math.max(...lift.map(Math.abs)),
                beside: places.every(p => Math.abs(p.x - target.x) > target.w / 2),
                actDeparture, actReturn, reachDeparture, reachReturn, waitingDrift, restlessMoved};
        } finally {
            window.requestAnimationFrame = realFrame; performance.now = realNow;
            ROAM2D.frame = 0; ROAM2D.last = realNow() / 1000; again2d();
        }
    }""")
    assert max(found['radius']) < .1 and found['beside'], found
    assert found['separation'] > min(found['sizes']), found
    assert found['lift'] < .03, found
    assert found['actDeparture'] > 1 and found['actReturn'] < .1, found
    assert found['reachDeparture'] > 1 and found['reachReturn'] < .1, found
    assert found['waitingDrift'] < .1 and found['restlessMoved'] > 1, found
    assert problems == []


def test_a_click_on_an_agent_figure_opens_its_thread_in_3d_and_2d_and_a_drag_on_it_pans(
        run, web, mapped, browser):  # noqa: F811 -- shared fixtures
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Inspect the work')
    run('map', 'work', 'op=edit', f'id={ticket.id}', 'glyph=owl', cwd=mapped)
    store.take_work(ticket.id, by='claude')
    live_session(ticket.id)
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    work, session = ticket.id, f's-{ticket.id}'
    # the page's own state, held where a predicate can read it: wait_for_function does not await an async predicate
    page.evaluate("""async () => {
        const [{ROAM2D}, {M}] = await Promise.all([import('/page/app/figures/roam2d.js'),
            import('/page/app/map2d/build.js')]);
        window.figureCheck = {ROAM2D, M, figure: () => [...ROAM2D.figures.values()][0], centre: part => {
            const box = window.figureCheck.figure().g.querySelector(part).getBoundingClientRect();
            return {x: box.left + box.width / 2, y: box.top + box.height / 2};
        }};
    }""")
    centre = 'part => window.figureCheck.centre(part)'
    camera = '() => window.figureCheck.M.cam.x'
    resting = '() => window.figureCheck.M.to === null'

    def opens_and_closes(x, y):
        page.mouse.click(x, y)
        page.wait_for_selector('#helpdesk', state='visible', timeout=10000)
        assert page.evaluate('window.metaform.dock().on') == session
        page.click('#helpdesk .close')
        page.wait_for_selector('#helpdesk', state='hidden', timeout=10000)

    # 3D: the click at the figure is picked by its hit test, graph3d.js figureAt
    page.wait_for_function('() => window.metaform.figures().length === 1', timeout=30000)
    at = page.evaluate(f'window.metaform.figureOnScreen({work!r})')
    opens_and_closes(at['x'], at['y'])

    # 2D: the figure's group takes the pointer, roam2d.js, and the map's node picking leaves it out, wire.js offMap
    page.evaluate("async () => { const {swap} = await import('/page/app/camera/flight.js'); await swap(true); }")
    page.wait_for_function("""() => {
        const figure = window.figureCheck.figure();
        if (figure?.stage !== 'circling' || window.figureCheck.M.to !== null) return false;
        figure.nextAct = 1e9;  // no scheduled act moves it during the check
        // drawn on the 2D map, now in the large area, before its place is read
        const image = figure.g.querySelector('image').getBoundingClientRect();
        const map = document.querySelector('#map2d').getBoundingClientRect();
        return figure.g.isConnected && image.width > 0 && image.left >= map.left && image.right <= map.right;
    }""", timeout=30000)
    glyph = page.evaluate(centre, 'image')
    opens_and_closes(glyph['x'], glyph['y'])
    page.wait_for_function(resting, timeout=10000)  # opening the thread may move the camera
    name = page.evaluate(centre, 'text')
    opens_and_closes(name['x'], name['y'])

    # hovering over the figure says its agent in the 2D readout
    page.wait_for_function(resting, timeout=10000)
    glyph = page.evaluate(centre, 'image')
    page.mouse.move(glyph['x'], glyph['y'])
    words = page.evaluate("() => window.figureCheck.figure().g.querySelector('text').textContent")
    page.wait_for_function('words => (window.metaform.readout("2d") || "").includes(words)', arg=words,
                           timeout=10000)

    # a click just beside the figure, toward its node, picks the node; opening the thread chose the node already, so
    # another is chosen first
    home = page.evaluate('() => window.figureCheck.figure().home')
    page.evaluate('home => window.metaform.select(home)', home)
    page.wait_for_function('home => window.metaform.selected() === home', arg=home, timeout=10000)
    page.wait_for_function(resting, timeout=10000)
    near = page.evaluate("""() => {
        const figure = window.figureCheck.figure();
        const image = figure.g.querySelector('image').getBoundingClientRect();
        const box = document.querySelector(`#map2d svg g.node[data-key="${figure.target}"]`).getBoundingClientRect();
        const from = {x: image.left + image.width / 2, y: image.top + image.height / 2}, inset = 4;
        // the point of the node's box nearest the figure, just inside it
        const x = Math.min(box.right - inset, Math.max(box.left + inset, from.x));
        const y = Math.min(box.bottom - inset, Math.max(box.top + inset, from.y));
        const gap = Math.max(image.left - x, x - image.right, image.top - y, y - image.bottom);
        return {x, y, gap, target: figure.target};
    }""")
    assert 0 < near['gap'] < 40, near  # beside the figure, not on it
    page.mouse.click(near['x'], near['y'])
    page.wait_for_function('target => window.metaform.selected() === target', arg=near['target'], timeout=10000)
    assert page.locator('#helpdesk').is_hidden()

    # zoomed in, a drag that starts on the figure pans the map and opens nothing
    page.wait_for_function(resting, timeout=10000)
    glyph = page.evaluate(centre, 'image')
    page.mouse.move(glyph['x'], glyph['y'])
    for _ in range(6):
        page.mouse.wheel(0, -200)
    page.wait_for_function(resting, timeout=10000)
    glyph = page.evaluate(centre, 'image')
    before = page.evaluate(camera)
    page.mouse.move(glyph['x'], glyph['y'])
    page.mouse.down()
    for step in range(1, 11):
        page.mouse.move(glyph['x'] + 6 * step, glyph['y'])
    page.mouse.up()
    assert page.evaluate(camera) != before
    page.wait_for_timeout(300)  # a click the drag let through would have opened the dock by now
    assert page.locator('#helpdesk').is_hidden()
    assert problems == []
