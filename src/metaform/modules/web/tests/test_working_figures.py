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
        figures[0].glance = {other: figures[1].id, until: figures[0].clock + 1000};
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
        f.glance = null;
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


@pytest.mark.req('VIEW-005')
def test_the_agent_view_ends_a_met_sign_and_sees_from_the_eyes_near_plane(
        run, web, mapped, browser):  # noqa: F811 -- imported fixtures keep their names for discovery
    """Stretched label, code.interface.graphical#63: a sign met before V was drawn over the map at the rectangle its
    corners project to from the agent's eyes, a stretched strip of its name, and the meeting's near plane hid all that
    stood before the eyes. The agent view ends the meeting, takes the eyes' near plane, and gives the person's back."""
    import time

    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Check the label')
    store.take_work(ticket.id, by='claude')
    live_session(ticket.id, 'claude')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.figures().length === 1', timeout=30000)
    state = """async () => {
        const THREE = await import('three');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {tags, MET} = await import('/page/app/map3d/labels.js');
        const {MEET} = await import('/page/app/camera/fly3d.js');
        const {EYE} = await import('/page/app/figures/eyes.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const camera = G.camera(), tag = tags.get(MEET.back?.id), figure = [...ROAM.figures.values()][0];
        const shown = Boolean(MET.box && !MET.box.hidden && tag);
        let stretch = null;
        if (shown) {  // the met name's box on the screen against the name as painted: 1 when seen square on
            tag.sprite.updateMatrixWorld();
            const xs = [], ys = [];
            for (const [x, y] of [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) {
                const at = tag.sprite.localToWorld(new THREE.Vector3(x, y, 0));
                const seen = G.graph2ScreenCoords(at.x, at.y, at.z);
                xs.push(seen.x); ys.push(seen.y);
            }
            stretch = (Math.max(...xs) - Math.min(...xs)) / (Math.max(...ys) - Math.min(...ys))
                / (tag.width / tag.height);
        }
        return {meet: MEET.on, shown, stretch, near: camera.near, own: MEET.own, eyeNear: EYE.camera.near,
            view: EYE.view, settled: EYE.k >= 1, saved: Boolean(EYE.saved), body: figure.mesh.visible,
            walking: ['arriving', 'going'].includes(figure.stage)};
    }"""

    def until(check, seconds=30):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            now = page.evaluate(state)
            if check(now):
                return now
            time.sleep(0.1)
        pytest.fail(f'never came: {page.evaluate(state)}')

    until(lambda now: not now['walking'])
    page.evaluate('window.metaform.mode3d("zoom")')  # a met sign is Zoom's; Work frames the node with its agent
    page.evaluate("""async () => {
        const {S} = await import('/page/app/core/reads.js');
        const {select} = await import('/page/app/selection/select.js');
        select([...S.elements.values()].find(one => one.element.address === 'code.alarm.audible').element.id, true);
    }""")
    # met: its name drawn over the map square on, and the near plane eased out to just short of the sign
    met = until(lambda now: now['meet'] and now['shown'] and now['near'] > now['own'])
    assert abs(met['stretch'] - 1) < 0.05, met
    page.evaluate("""async () => {
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {followFigure, agentView} = await import('/page/app/figures/eyes.js');
        followFigure([...ROAM.figures.values()][0]);
        agentView();
    }""")
    seen = until(lambda now: now['view'] and now['settled'])
    time.sleep(0.5)
    seen = page.evaluate(state)
    # no met name drawn over the map from the eyes, stretched or not, and nothing before the eyes cut away
    assert not seen['meet'] and not seen['shown'], seen
    assert seen['near'] == pytest.approx(seen['eyeNear']) and not seen['body'], seen
    page.evaluate("async () => (await import('/page/app/figures/eyes.js')).agentView()")
    back = until(lambda now: not now['view'] and not now['saved'])
    assert back['near'] == pytest.approx(back['own']) and back['body'] and not back['shown'], back
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_speech_bubbles_stay_in_view_apart_dimmed_by_distance_and_the_watched_agent_speaks_at_the_bottom(
        run, web, mapped, browser):  # noqa: F811 -- imported fixtures keep their names for discovery
    """code.interface.graphical#81: bubbles stacked only upward, off the top of the view, and were dimmed by how far
    the stack pushed them; in the agent view the watched agent's words were hidden with its body; and leaving the
    view held the person's controls until the way back ended. Agents near the top of the view now talk inside it,
    apart, each as bright as its agent is near; the watched agent's words are at the bottom of its view; and V off
    gives the controls back at once."""
    import time

    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    run('set', '--web-bubble-seconds=120')
    store = Store('proj')
    places = ['code.alarm.audible', 'code.alarm.audible', 'code.loop.tick']
    tickets = [store.add_work(Node('element', address), 'broken', task='Check it') for address in places]
    for ticket, glyph in zip(tickets, ('owl', 'moth', 'beetle')):
        run('map', 'work', 'op=edit', f'id={ticket.id}', f'glyph={glyph}', cwd=mapped)
        store.take_work(ticket.id, by='claude')
        live_session(ticket.id, 'claude')
    with Store('proj', module='dispatch').tables() as tx:
        for n, ticket in enumerate(tickets):
            tx.insert('session_lines', {'session_id': f's-{ticket.id}', 'name': 'l1', 'work_id': ticket.id,
                                'kind': 'agent_message_chunk', 'seq': 1,
                                'text': f'Reading part {n} of the code to see where each speech bubble goes'})
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.figures().length === 3', timeout=30000)
    bubbles = """async () => {
        const THREE = await import('three');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {bubbles3d} = await import('/page/app/figures/bubble3d.js');
        const {eyeOf} = await import('/page/agents3d.js');
        const {EYE} = await import('/page/app/figures/eyes.js');
        const camera = G.camera(), at = new THREE.Vector3(), gaze = new THREE.Vector3();
        bubbles3d();
        const shown = [];
        G.scene().traverse(o => { if (o.isMesh && o.renderOrder >= 1000 && o.material.map && o.visible) {
            o.updateMatrixWorld();
            const a = new THREE.Vector3(-0.5, -0.5, 0).applyMatrix4(o.matrixWorld).project(camera);
            const b = new THREE.Vector3(0.5, 0.5, 0).applyMatrix4(o.matrixWorld).project(camera);
            shown.push({box: [a.x, a.y, b.x, b.y], bright: o.material.color.r});
        }});
        const heads = [...ROAM.figures.values()].filter(f => f.mesh !== EYE.mesh).map(f => {
            eyeOf(f.mesh, at, gaze); return at.distanceTo(camera.position); });
        return {shown, heads, walking: [...ROAM.figures.values()].some(f => ['arriving', 'going'].includes(f.stage))};
    }"""
    end = time.monotonic() + 30
    while (now := page.evaluate(bubbles))['walking'] or len(now['shown']) < 3:
        assert time.monotonic() < end, now
        time.sleep(0.2)
    # the camera held, and moved down so the agents stand near the top of the view, where bubbles stacked up went off
    page.evaluate("""async () => {
        const THREE = await import('three');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        window.metaform.pause3d(true);
        const camera = G.camera(), mid = new THREE.Vector3(), figures = [...ROAM.figures.values()];
        for (const f of figures) mid.add(f.mesh.position);
        const seen = mid.divideScalar(figures.length).applyMatrix4(camera.matrixWorldInverse);
        const down = 0.8 * -seen.z * Math.tan(camera.fov * Math.PI / 360) - seen.y;
        camera.position.addScaledVector(new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion), -down);
        camera.updateMatrixWorld();
    }""")
    placed = page.evaluate(bubbles)
    boxes = [one['box'] for one in placed['shown']]
    assert len(boxes) == 3, placed
    assert all(-1 <= x0 and -1 <= y0 and x1 <= 1 and y1 <= 1 for x0, y0, x1, y1 in boxes), placed
    assert not any(a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
                   for n, a in enumerate(boxes) for b in boxes[n + 1:]), placed
    # each as bright as its agent is near, against the nearest one talking, however far it was moved apart
    nearest = min(placed['heads'])
    assert sorted(one['bright'] for one in placed['shown']) == pytest.approx(
        sorted(max(1 / 3, (nearest / head) ** 1.5) for head in placed['heads']), abs=0.01), placed
    page.evaluate("""async () => {
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {followFigure, agentView} = await import('/page/app/figures/eyes.js');
        window.metaform.pause3d(false);
        followFigure([...ROAM.figures.values()][0]);
        agentView();
    }""")
    page.wait_for_function("""async () => { const {EYE} = await import('/page/app/figures/eyes.js');
        return EYE.view && EYE.k >= 1; }""", timeout=30000)
    page.evaluate('window.metaform.pause3d(true)')
    watched = page.evaluate(bubbles)
    # its body hidden, its words at the bottom of the view, in its middle, over the others
    bottom = min(watched['shown'], key=lambda one: one['box'][1])
    assert -1 <= bottom['box'][1] < -0.9 and abs(bottom['box'][0] + bottom['box'][2]) < 0.05, watched
    assert bottom['bright'] == 1, watched
    off = page.evaluate("""async () => {
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {agentView, EYE} = await import('/page/app/figures/eyes.js');
        window.metaform.pause3d(false);
        agentView();
        return {controls: G.controls().enabled, saved: Boolean(EYE.saved)};
    }""")
    assert off == {'controls': True, 'saved': True}, off  # the person's camera at once, while the view eases back
    page.wait_for_function("""async () => !(await import('/page/app/figures/eyes.js')).EYE.saved""", timeout=30000)
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_the_work_camera_shows_a_node_with_its_agents_and_all_the_work_each_in_view_and_apart(
        run, web, mapped, browser):  # noqa: F811 -- imported fixtures keep their names for discovery
    """Work, the 3D map's default mode: a selected node is shown with the agents working on it, and with nothing
    selected every node at work with its agents, from the angle where each of them, the node and its name are on the
    screen, nothing of the map stands in front of them, and none hides behind another."""
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    places = ['code.alarm.audible', 'code.alarm.audible', 'code.loop.tick']
    tickets = [store.add_work(Node('element', address), 'broken', task='Check it') for address in places]
    for ticket, glyph in zip(tickets, ('owl', 'moth', 'beetle')):
        run('map', 'work', 'op=edit', f'id={ticket.id}', f'glyph={glyph}', cwd=mapped)
        store.take_work(ticket.id, by='codex')
        live_session(ticket.id, 'codex')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.figures().length === 3', timeout=30000)
    shot = """async focus => {
        const {ROAM, ballOf} = await import('/page/app/figures/agents.js');
        const {roam3d} = await import('/page/app/figures/roam3d.js');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {tags, layered} = await import('/page/app/map3d/labels.js');
        const {V3, flight} = await import('/page/app/camera/flight.js');
        const {S} = await import('/page/app/core/reads.js');
        const {select} = await import('/page/app/selection/select.js');
        const {shownNode} = await import('/page/app/map3d/light.js');
        window.metaform.pause3d(true);
        const data = G.graphData(), figures = [...ROAM.figures.values()], camera = G.camera();
        for (const node of data.nodes) { node.fx = node.x; node.fy = node.y; node.fz = node.z; }
        if (!figures[0].settled) {
            for (const f of figures) {
                const node = data.nodes.find(n => n.id === f.target);
                Object.assign(f, {stage: 'circling', clock: 0, nextAct: 1e9, nextGlance: 1e9, act: null, glance: null,
                    settled: true});
                f.pos.set(node.x + 10, node.y, node.z + 10); f.mesh.position.copy(f.pos); f.vel.set(0, 0, 0);
            }
            for (let n = 0; n < 200; n++) {
                for (const f of figures) f.nextAct = 1e9;
                layered(); ROAM.last = performance.now() / 1000 - .05; roam3d(data);
            }
        }
        const id = focus && [...S.elements.values()].find(one => one.element.address === focus).element.id;
        // the camera starts on the line through two of the agents, so from where it stands one hides the other
        const [near, far] = figures.filter(f => !id || f.target === id), there = near.mesh.position;
        const along = there.clone().sub(far.mesh.position).normalize();
        G.controls().target.copy(there);
        camera.position.copy(there).addScaledVector(along, 300);
        camera.lookAt(there); camera.updateMatrixWorld();
        if (id) select(id, true); else { (await import('/page/app/camera/fly3d.js')).workShot(null); }
        flight(performance.now() + 1e7);  // the flight's end, where the shot is taken
        layered();
        const box = G.renderer().domElement.getBoundingClientRect();
        const work = figures.filter(f => !id || f.target === id), nodes = new Set(work.map(f => f.target));
        const points = work.map(f => ({what: f.id, at: f.mesh.position, r: 0}));
        for (const node of data.nodes.filter(n => nodes.has(n.id))) {
            points.push({what: node.id, at: {x: node.x, y: node.y, z: node.z}, r: 0});
            const sign = tags.get(node.id)?.sprite;
            if (sign?.visible) points.push({what: 'sign ' + node.id, at: sign.position, r: 0});
        }
        const eye = camera.position, out = [], hidden = [];
        for (const p of points) {
            const seen = G.graph2ScreenCoords(p.at.x, p.at.y, p.at.z);
            if (seen.x < 0 || seen.y < 0 || seen.x > box.width || seen.y > box.height) out.push(p.what);
            const vx = p.at.x - eye.x, vy = p.at.y - eye.y, vz = p.at.z - eye.z, long = vx * vx + vy * vy + vz * vz;
            for (const node of data.nodes) {
                if (node.x === undefined || nodes.has(node.id) || !shownNode(node)) continue;
                const s = ((node.x - eye.x) * vx + (node.y - eye.y) * vy + (node.z - eye.z) * vz) / long;
                if (s <= 0 || s >= 0.97) continue;
                const gap = Math.hypot(eye.x + vx * s - node.x, eye.y + vy * s - node.y, eye.z + vz * s - node.z);
                if (gap < ballOf(node) * 0.85) { hidden.push(p.what + ' behind ' + node.id); break; }
            }
            p.screen = seen;
        }
        // each two agents seen side by side: the angle between the line through them and the eye's line to them
        let apart = 90;
        for (const one of work) for (const two of work) if (one !== two) {
            const a = one.mesh.position, b = two.mesh.position, pair = a.clone().sub(b);
            const ray = a.clone().add(b).multiplyScalar(0.5).sub(eye);
            const angle = pair.angleTo(ray) * 180 / Math.PI;
            apart = Math.min(apart, Math.min(angle, 180 - angle));
        }
        return {mode: V3.mode, out, hidden, apart, agents: work.length};
    }"""
    one = page.evaluate(shot, 'code.alarm.audible')
    assert one['mode'] == 'work' and one['agents'] == 2, one
    assert one['out'] == [] and one['hidden'] == [], one
    assert one['apart'] > 30, one  # the two agents side by side, not one behind the other
    every = page.evaluate(shot, None)
    assert every['agents'] == 3 and every['out'] == [] and every['hidden'] == [], every
    assert every['apart'] > 30, every
    assert problems == []
