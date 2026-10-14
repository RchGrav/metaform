"""A working figure holds its place and shares its label gaze with its own camera."""
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


def test_working_figures_hold_separate_places_face_the_label_and_resume_after_an_act(
        run, web, mapped, browser):  # noqa: F811 -- imported fixtures keep their names for discovery
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    tickets = [store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Check the label')
               for _ in range(2)]
    for ticket, glyph in zip(tickets, ('owl', 'moth')):
        run('map', 'work', 'op=edit', f'id={ticket.id}', f'glyph={glyph}', cwd=mapped)
        store.take_work(ticket.id, by='codex')
        live_session(ticket.id, 'codex')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.figures().length === 2', timeout=30000)
    found = page.evaluate("""async () => {
        const THREE = await import('three');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {roam3d} = await import('/page/app/figures/roam3d.js');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {tags, layered} = await import('/page/app/map3d/labels.js');
        const {eyeOf, orientAgent} = await import('/page/agents3d.js');
        const {D} = await import('/page/app/agents/dispatch.js');
        window.metaform.pause3d(true);
        const data = G.graphData(), figures = [...ROAM.figures.values()];
        // Hold the actual map layout. Only the figures' own motion is under examination.
        for (const node of data.nodes) { node.fx = node.x; node.fy = node.y; node.fz = node.z; }
        for (const f of figures) {
            const node = data.nodes.find(n => n.id === f.target);
            Object.assign(f, {stage: 'circling', clock: 0, nextAct: 1e9, nextGlance: 1e9, act: null, glance: null});
            f.pos.set(node.x + 10, node.y, node.z + 10);
            f.mesh.position.copy(f.pos); f.vel.set(0, 0, 0);
        }
        const step = count => {
            for (let n = 0; n < count; n++) {
                for (const figure of figures) figure.nextAct = 1e9;
                layered(); ROAM.last = performance.now() / 1000 - .05; roam3d(data);
            }
        };
        step(200);
        const places = figures.map(f => f.mesh.position.clone()), radius = [0, 0], angles = [], eyes = [];
        for (let n = 0; n < 200; n++) {
            step(1);
            for (const [i, f] of figures.entries()) {
                radius[i] = Math.max(radius[i], f.mesh.position.distanceTo(places[i]));
                const label = tags.get(f.target).sprite.getWorldPosition(new THREE.Vector3());
                const forward = f.mesh.getWorldDirection(new THREE.Vector3());
                angles.push(forward.angleTo(label.clone().sub(f.mesh.position).normalize()) * 180 / Math.PI);
                const at = new THREE.Vector3(), dir = new THREE.Vector3(); eyeOf(f.mesh, at, dir);
                eyes.push(dir.angleTo(label.clone().sub(at).normalize()) * 180 / Math.PI);
            }
        }
        const f = figures[0], before = f.mesh.position.clone();
        f.act = {kind: 'peek', at: f.clock, long: 1, hit: false};
        step(10);
        const departure = f.mesh.position.distanceTo(before);
        step(200);
        const returned = f.mesh.position.distanceTo(before), act = f.act;
        const other = data.nodes.find(n => n.t === 'el' && n.id !== f.target);
        f.lookAt = {node: other.id, until: f.clock + 1};
        step(15);
        const lookAngle = f.mesh.getWorldDirection(new THREE.Vector3()).angleTo(
            new THREE.Vector3(other.x, other.y, other.z).sub(f.mesh.position)) * 180 / Math.PI;
        step(200);
        f.reach = {to: other.id, at: f.clock}; step(13);
        const reachDeparture = f.mesh.position.distanceTo(before); step(200);
        const reachReturned = f.mesh.position.distanceTo(before);
        f.drive = {point: before.clone().add(new THREE.Vector3(60, 10, 20)), top: 70, accel: 70};
        f.stage = 'driven'; step(100);
        const driven = f.mesh.position.distanceTo(f.drive.point);
        f.drive = null; step(200);
        const driveReturned = f.mesh.position.distanceTo(before);
        const session = D.sessions.find(one => one.work_id === f.id);
        session.activity = 'waiting'; step(200); const waiting = f.mood;
        session.activity = 'working';
        D.signals = [{session_id: session.session_id, signal: 'spinning-time', active: true}];
        step(200); const restless = f.mood, restlessAt = f.mesh.position.clone(); step(40);
        const restlessMoved = f.mesh.position.distanceTo(restlessAt);
        D.signals = []; step(200);
        const mover = figures[1], node = data.nodes.find(n => n.id === mover.target);
        Object.assign(mover, {stage: 'going', clock: 0, u: 0, speed: 0});
        mover.way = [{point: new THREE.Vector3(node.x - 180, node.y, node.z)}, {id: mover.target}];
        mover.mesh.position.copy(mover.way[0].point); mover.pos.copy(mover.mesh.position); mover.vel.set(0, 0, 0);
        mover.heading.set(1, 0, 0); orientAgent(mover.mesh, mover.heading, 1);
        let travel = 0, samples = 0;
        for (let n = 0; n < 300 && mover.stage === 'going'; n++) {
            const before = mover.mesh.position.clone(); step(1);
            const velocity = mover.mesh.position.clone().sub(before);
            if (n > 3 && mover.stage === 'going' && velocity.length() > .001) {
                travel = Math.max(travel, mover.mesh.getWorldDirection(new THREE.Vector3())
                    .angleTo(velocity.normalize()) * 180 / Math.PI);
                samples++;
            }
        }
        return {radius, angles: Math.max(...angles), eyes: Math.max(...eyes), travel, samples,
            lookAngle, reachDeparture, reachReturned, driven, driveReturned, waiting, restless, restlessMoved,
            separation: places[0].distanceTo(places[1]), sizes: figures.map(f => f.mesh.scale.x),
            departure, returned, act};
    }""")
    assert all(radius < size * .05 for radius, size in zip(found['radius'], found['sizes'])), found
    assert found['angles'] < 10 and found['eyes'] < 10, found
    assert found['separation'] > min(found['sizes']), found
    assert found['departure'] > found['sizes'][0] * .2, found
    assert found['returned'] < found['sizes'][0] * .05 and found['act'] is None, found
    assert found['lookAngle'] < 10, found
    assert found['reachDeparture'] > found['sizes'][0] * .2 and found['reachReturned'] < .01, found
    assert found['driven'] < 1 and found['driveReturned'] < .01, found
    assert found['waiting'] == 'waiting' and found['restless'] == 'restless' and found['restlessMoved'] > 1, found
    assert found['samples'] > 20 and found['travel'] < 20, found
    assert problems == []


def test_thread_messages_reach_the_figures_shared_bubble_without_private_or_tool_lines(
        run, web, mapped, browser, tmp_path):  # noqa: F811 -- shared fixtures
    import json

    from metaform import relay
    from metaform.data import Node, Store
    from metaform.modules.web.tests.test_web import ACTIVITY

    run('enable', 'dispatch')
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Check the visible update')
    store.take_work(ticket.id, by='codex')
    run('map', 'work', 'op=edit', f'id={ticket.id}', 'glyph=owl', cwd=mapped)
    live_session(ticket.id, 'codex')
    session = f's-{ticket.id}'
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 1', timeout=30000)
    page.evaluate("""async () => {
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {roam3d} = await import('/page/app/figures/roam3d.js');
        const {layered} = await import('/page/app/map3d/labels.js');
        window.metaform.pause3d(true);
        const data = G.graphData(), f = [...ROAM.figures.values()][0];
        for (const node of data.nodes) { node.fx = node.x; node.fy = node.y; node.fz = node.z; }
        Object.assign(f, {stage: 'circling', clock: 0, nextGlance: 1e9, act: null});
        f.pos.copy(f.mesh.position); f.vel.set(0, 0, 0);
        for (let n = 0; n < 200; n++) {
            f.nextAct = 1e9; layered(); ROAM.last = performance.now() / 1000 - .05; roam3d(data);
        }
        G.camera().position.copy(f.mesh.position).add({x: 25, y: 20, z: 80});
        G.camera().lookAt(f.mesh.position); G.camera().updateMatrixWorld(true);
        G.controls().target.copy(f.mesh.position); layered();
        G.renderer().render(G.scene(), G.camera());
    }""")
    selector = f'.agent-thought[data-map="3d"][data-session="{session}"]'

    def line(seq, kind, text):
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('lines', {'session_id': session, 'work_id': ticket.id, 'name': f'flow:{seq}',
                                'kind': kind, 'text': text, 'seq': seq})
        relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch',
                                      'dispatch_tables': ['dispatch.lines']})

    def shows(text):
        # The event makes the browser read the server's actual session summary. Only placement is stepped by hand.
        page.wait_for_function("""async ([session, text, selector]) => {
            const {D} = await import('/page/app/agents/dispatch.js');
            if (D.sessions.find(one => one.session_id === session)?.latest_message?.text !== text) return false;
            const {placeThoughts3d} = await import('/page/app/figures/thoughts.js');
            placeThoughts3d();
            const el = document.querySelector(selector);
            const {thoughtText} = await import('/page/app/figures/thoughts.js');
            return el?.classList.contains('on')
                && el.querySelector('.agent-thought-words')?.textContent === thoughtText(text);
        }""", arg=[session, text, selector], timeout=15000)

    short = 'Checking the current view.'
    line(1, 'agent_message_chunk', short)
    shows(short)
    cloud = page.locator(f'{selector} .agent-thought-cloud')
    words = page.locator(f'{selector} .agent-thought-words')
    assert words.text_content() == short
    short_box = cloud.bounding_box()
    assert short_box and short_box['width'] <= 340
    page.wait_for_timeout(250)
    short_picture = tmp_path / 'thread-thought-short.png'
    page.screenshot(path=str(short_picture))

    for seq, kind, text in [(2, 'tool_call', 'TOOL OUTPUT SHOULD STAY PRIVATE'),
                            (3, 'agent_thought_chunk', 'THINKING SHOULD STAY PRIVATE'),
                            (4, 'stderr', 'STDERR SHOULD STAY PRIVATE')]:
        line(seq, kind, text)
    page.wait_for_function("""async session => {
        const {D} = await import('/page/app/agents/dispatch.js');
        return D.sessions.find(one => one.session_id === session)?.latest_message?.complete === true;
    }""", arg=session, timeout=15000)
    shows(short)
    assert words.text_content() == short
    assert not any(text in page.locator(selector).inner_text() for text in ['TOOL OUTPUT', 'THINKING', 'STDERR'])

    long = ('Checking that the graphical interface keeps the node label centred while a working figure rests beside '
            'its node, and that a longer public update wraps into a readable bubble above its own name.')
    line(5, 'agent_message_chunk', long)
    shows(long)
    displayed = words.text_content()
    long_box = cloud.bounding_box()
    assert len(displayed) <= 140 and displayed.endswith('…') and displayed.startswith('Checking that the graphical')
    assert long_box and long_box['height'] > short_box['height'] and long_box['width'] <= 340
    assert page.locator(f'{selector} .agent-thought-name').inner_text() == 'codex'
    page.wait_for_timeout(250)
    long_picture = tmp_path / 'thread-thought-long.png'
    page.screenshot(path=str(long_picture))

    anchored = page.evaluate("""async ([work, selector, text]) => {
        const THREE = await import('three');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {eyeOf} = await import('/page/agents3d.js');
        const {speechBubble} = await import('/page/app/figures/bubble.js');
        const {placeThoughts3d} = await import('/page/app/figures/thoughts.js');
        const bubble = speechBubble(text), canvas = document.querySelector(selector + ' canvas');
        const head = new THREE.Vector3();
        const measure = () => {
            placeThoughts3d();
            eyeOf(ROAM.figures.get(work).mesh, head, new THREE.Vector3());
            head.project(G.camera());
            const area = G.renderer().domElement.getBoundingClientRect(), box = canvas.getBoundingClientRect();
            const x = area.left + (head.x + 1) * area.width / 2;
            const y = area.top + (1 - head.y) * area.height / 2;
            return {width: box.width, height: box.height,
                error: Math.hypot(box.left + bubble.tip[0] - x, box.top + bubble.tip[1] - y)};
        };
        const before = measure();
        G.camera().position.lerp(G.controls().target, -.5);
        G.camera().updateMatrixWorld(true);
        return {before, after: measure()};
    }""", [ticket.id, selector, displayed])
    assert max(anchored['before']['error'], anchored['after']['error']) < 1, anchored
    assert anchored['before']['width'] == anchored['after']['width'], anchored
    assert anchored['before']['height'] == anchored['after']['height'], anchored

    ACTIVITY[session] = 'waiting'
    relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})
    page.wait_for_function("""async ([session, selector]) => {
        const {D} = await import('/page/app/agents/dispatch.js');
        if (D.sessions.find(one => one.session_id === session)?.activity !== 'waiting') return false;
        const {placeThoughts3d} = await import('/page/app/figures/thoughts.js'); placeThoughts3d();
        return !document.querySelector(selector)?.classList.contains('on');
    }""", arg=[session, selector], timeout=15000)
    page.wait_for_function('selector => getComputedStyle(document.querySelector(selector)).opacity === "0"',
                           arg=f'{selector} .agent-thought-cloud')
    assert page.locator(f'{selector} .agent-thought-name').inner_text() == 'codex'
    assert problems == []
    print(json.dumps({'short': str(short_picture), 'long': str(long_picture), 'short_box': short_box,
                      'long_box': long_box, 'displayed': displayed}))
