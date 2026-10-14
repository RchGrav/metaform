"""The 2D figure rests beside its work and uses the shared public-message bubble."""
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
    page.wait_for_function("""async () => {
        const {ROAM2D} = await import('/page/app/figures/roam2d.js'); return ROAM2D.figures.size === 2;
    }""")
    found = page.evaluate("""async () => {
        const {ROAM2D, again2d, spot2d} = await import('/page/app/figures/roam2d.js');
        const {M} = await import('/page/app/map2d/build.js');
        const {D} = await import('/page/app/agents/dispatch.js');
        const {updateThoughts} = await import('/page/app/figures/thoughts.js');
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
            D.signals = [{session_id: session.session_id, signal: 'spinning-time', active: true}];
            step(30); const restless = {x: f.x, y: f.y}; step(20);
            const restlessMoved = Math.hypot(f.x - restless.x, f.y - restless.y);
            D.signals = []; step(40);
            updateThoughts({sessions: [{...session, latest_message: {session_id: session.session_id,
                kind: 'agent_message_chunk', name: 'work:1', seq: 1,
                text: 'Checking the current work.', complete: true}}]});
            step(1);
            const bubble = document.querySelector('.agent-thought[data-map="2d"][data-work="' + f.id + '"]');
            const bubbleOn = Boolean(bubble?.classList.contains('on') && bubble.querySelector('canvas'));
            const bubbleText = bubble?.querySelector('.agent-thought-words')?.textContent;
            for (const one of figures) { one.stage = 'leaving'; one.clock = 2; }
            step(1);
            const removedBubble = !document.querySelector('.agent-thought[data-map="2d"].on');
            return {radius, separation: Math.hypot(places[0].x - places[1].x, places[0].y - places[1].y),
                sizes: figures.map(f => f.size), lift: Math.max(...lift.map(Math.abs)),
                beside: places.every(p => Math.abs(p.x - target.x) > target.w / 2),
                actDeparture, actReturn, reachDeparture, reachReturn, waitingDrift, restlessMoved,
                bubbleOn, bubbleText, removedBubble};
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
    assert found['bubbleOn'] and found['bubbleText'] == 'Checking the current work.', found
    assert found['removedBubble'], found
    assert problems == []
