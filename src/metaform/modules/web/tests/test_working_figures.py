"""A working figure holds its place and shares its label gaze with its own camera."""
import sys

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
        D.signals = [{session_id: session.session_id, signal: 'spinning-calls', active: true}];
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


def test_a_paper_plane_keeps_its_wings_level_flying_straight_banks_into_a_turn_and_noses_along_its_path(
        run, web, mapped, browser):  # noqa: F811 -- imported fixtures keep their names for discovery
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.loaded()')
    found = page.evaluate("""async () => {
        const THREE = await import('three');
        const {createAgent, orientAgent, motionOf} = await import('/page/agents3d.js');
        const dt = 1 / 60, roll = new THREE.Euler(0, 0, 0, 'YXZ'), q = new THREE.Quaternion();
        const p = new THREE.Vector3(), dir = new THREE.Vector3();
        // the body's drawn roll, pitch and height over 8 s of a path, after 2 s to settle
        const fly = path => {
            const agent = createAgent('plane'); agent.userData.motion = motionOf('plane', 'probe');
            const body = agent.children[0].children[0].children[0].children[0];
            const seen = {roll: [Infinity, -Infinity], pitch: [Infinity, -Infinity], high: [Infinity, -Infinity]};
            for (let i = 0; i < 600; i++) {
                const t = i * dt, aligned = path(t, agent.position, dir);
                orientAgent(agent, dir, aligned ? 1 : .16, dt, aligned);
                agent.updateMatrixWorld(true);
                agent.userData.update(dt, {move: {speed: 1, stride: t, state: 'travel'}});
                agent.updateMatrixWorld(true);
                if (i < 120) continue;
                body.getWorldQuaternion(q); roll.setFromQuaternion(q, 'YXZ'); body.getWorldPosition(p);
                for (const [key, value] of [['roll', roll.z], ['pitch', roll.x], ['high', p.y - agent.position.y]]) {
                    seen[key][0] = Math.min(seen[key][0], value); seen[key][1] = Math.max(seen[key][1], value);
                }
            }
            return Object.fromEntries(Object.entries(seen).map(([key, [lo, hi]]) =>
                [key, key === 'high' ? [lo, hi] : [lo * 180 / Math.PI, hi * 180 / Math.PI]]));
        };
        const lap = 2 * Math.PI / 12;  // circling its node: a right turn, lap 12 s
        return {
            straight: fly((t, at, d) => { at.set(0, 0, t * 2); d.set(0, 0, 1); return true; }),
            turn: fly((t, at, d) => { at.set(Math.cos(lap * t) * 3, 0, Math.sin(lap * t) * 3);
                d.set(-Math.sin(lap * t), 0, Math.cos(lap * t)); return false; }),
            descent: fly((t, at, d) => { d.set(0, -Math.tan(.26), 1).normalize(); at.copy(d).multiplyScalar(t * 2);
                return true; }),
        };
    }""")
    straight, turn, descent = found['straight'], found['turn'], found['descent']
    # flying straight: wings level, nose on the path, no bob
    assert max(map(abs, straight['roll'] + straight['pitch'])) < .5, found
    assert straight['high'][1] - straight['high'][0] < 1e-3, found
    # in a steady turn: a steady bank into the turn, right wing down
    assert 10 < turn['roll'][0] and turn['roll'][1] - turn['roll'][0] < .5, found
    # in a descent: the nose follows the path down, 15 degrees
    assert all(abs(one - 14.9) < 1 for one in descent['pitch']), found
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
def test_word_bubbles_point_at_their_speakers_stay_apart_in_view_and_the_watched_agent_speaks_at_the_bottom(
        run, web, mapped, browser):  # noqa: F811 -- imported fixtures keep their names for discovery
    """code.interface.graphical#c7: an agent's bubble was a picture in the scene with its tail drawn at one corner, so
    once it was moved apart or into the view its tail pointed at another figure, and the mascot's had a fixed tail too.
    Every bubble is now SVG over the maps, its tail drawn each frame to its speaker's head on the screen: two agents
    side by side each have a tail on their own head, no bubble covers another, a speaker turned out of the view keeps
    its bubble in it with the tail toward it, a short line goes after its bubbleSeconds while a long one stays, and
    the mascot's web_say bubble points at the mascot. Carried over from #81: bubbles stay in view, each as bright as
    its agent is near, and the watched agent's words are at the bottom of the agent view."""
    import math
    import time

    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    run('set', '--web-bubble-seconds=60')
    run('set', '--web-mascot=seahorse')
    store = Store('proj')
    places = ['code.alarm.audible', 'code.alarm.audible', 'code.loop.tick']  # two agents close together
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
    # the person's system agent, in a conversation, so its mascot, the seahorse, is on the map to speak
    system = store.add_work(Node('element', 'code.alarm.audible'), None, task='Conversation with the system agent',
                            held=True)
    live_session(system.id)
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.figures().length === 3 && window.metaform.mascot().shown',
                           timeout=30000)
    # the bubbles as drawn after `frames` frames: each one's speaker, its tail's tip and its body's box on the page,
    # its brightness, and its speaker's head on the page as the bubbles measure it, by LOOK.lift
    bubbles = """async frames => {
        const THREE = await import('three');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {MASCOT} = await import('/page/app/figures/mascot.js');
        const {bubbles3d, LOOK} = await import('/page/app/figures/bubble3d.js');
        const {placeBubble} = await import('/page/app/figures/cut.js');
        const {eyeOf} = await import('/page/agents3d.js');
        for (let n = 0; n < frames; n++) {
            await new Promise(requestAnimationFrame);
            placeBubble(); bubbles3d();
        }
        const camera = G.camera(), area = G.renderer().domElement.getBoundingClientRect();
        const at = new THREE.Vector3(), gaze = new THREE.Vector3();
        const head = mesh => {
            eyeOf(mesh, at, gaze);
            at.y += LOOK.lift * mesh.scale.x;
            const far = at.distanceTo(camera.position);
            at.project(camera);
            return {x: area.left + (at.x + 1) / 2 * area.width, y: area.top + (1 - at.y) / 2 * area.height, far};
        };
        const shown = [...document.querySelectorAll('#bubbles .wbubble')].filter(el => el.style.display !== 'none')
          .map(el => {
            const tail = el.querySelector('[id^="wbubble-tail-"]'), body = el.querySelector('[id^="wbubble-body-"]');
            const m = (tail.getAttribute('d') || '').match(/^M(-?[0-9.]+),(-?[0-9.]+)/);
            const tip = m ? new DOMPoint(Number(m[1]), Number(m[2])).matrixTransform(tail.getScreenCTM()) : null;
            const box = body.getBoundingClientRect(), who = el.dataset.who;
            const mesh = who === 'mascot' ? MASCOT.mesh : ROAM.figures.get(who)?.mesh;
            return {who, tip: tip && [tip.x, tip.y], box: [box.left, box.top, box.right, box.bottom],
                head: mesh ? head(mesh) : null, opacity: Number(el.style.opacity),
                bright: Number(el.querySelector('.paper').getAttribute('fill').match(/[0-9]+/)[0]) / 255,
                said: el.querySelector('.said').textContent,
                lines: [...el.querySelectorAll('.words text')].map(one => one.textContent)};
          });
        return {shown, area: [area.left, area.top, area.right, area.bottom],
            walking: [...ROAM.figures.values()].some(f => ['arriving', 'going'].includes(f.stage))};
    }"""
    end = time.monotonic() + 30
    while (now := page.evaluate(bubbles, 1))['walking'] or len(now['shown']) < 3:
        assert time.monotonic() < end, now
        time.sleep(0.2)
    # the camera held, and moved down so the agents stand high in the view, their bubbles kept inside it
    page.evaluate("""async () => {
        const THREE = await import('three');
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const {LOOK} = await import('/page/app/figures/bubble3d.js');
        const {eyeOf} = await import('/page/agents3d.js');
        window.metaform.pause3d(true);
        const camera = G.camera(), tan = Math.tan(camera.fov * Math.PI / 360), at = new THREE.Vector3();
        // the highest head two thirds of the way up from the middle of the view
        let down = Infinity;
        for (const f of ROAM.figures.values()) {
            eyeOf(f.mesh, at, new THREE.Vector3());
            at.y += LOOK.lift * f.mesh.scale.x;
            const seen = at.applyMatrix4(camera.matrixWorldInverse);
            down = Math.min(down, 0.65 * -seen.z * tan - seen.y);
        }
        camera.position.addScaledVector(new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion), -down);
        camera.updateMatrixWorld();
        window.__kept = {position: camera.position.clone(), quaternion: camera.quaternion.clone()};
    }""")

    def overlap(a, b):
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    def apart_in_view(placed):
        left, top, right, bottom = placed['area']
        boxes = [one['box'] for one in placed['shown']]
        assert all(left <= x0 and top <= y0 and x1 <= right and y1 <= bottom for x0, y0, x1, y1 in boxes), placed
        assert not any(overlap(a, b) for n, a in enumerate(boxes) for b in boxes[n + 1:]), placed

    def on_head(one, area):
        left, top, right, bottom = area
        assert left < one['head']['x'] < right and top < one['head']['y'] < bottom, one
        assert one['tip'] and math.dist(one['tip'], (one['head']['x'], one['head']['y'])) < 6, one

    placed = page.evaluate(bubbles, 40)
    assert len(placed['shown']) == 3, placed
    apart_in_view(placed)
    # every tail's tip on its own speaker's head, the two side by side included
    for one in placed['shown']:
        on_head(one, placed['area'])
    # each as bright as its agent is near, against the nearest one talking, however far it was moved apart
    nearest = min(one['head']['far'] for one in placed['shown'])
    for one in placed['shown']:
        assert one['bright'] == pytest.approx(max(0.33, (nearest / one['head']['far']) ** 1.5), abs=0.01), one
    # code.interface.graphical#149: the bubbles belong to the maps, over the map and its figures but under every
    # window. An agent's bubble takes no pointer, so the probe lets it take one to be found at its own centre: there it
    # is the topmost element over the map, and a window opened over it is the topmost instead
    stacked = page.evaluate("""async ([who, x, y]) => {
        const svg = [...document.querySelectorAll('#bubbles .wbubble')].find(el => el.dataset.who === who)
            .querySelector('svg');
        svg.style.pointerEvents = 'auto';
        const before = document.elementFromPoint(x, y)?.closest('svg') === svg;
        (await import('/page/app/keys/keys.js')).openHelp();
        const help = document.querySelector('#help'), box = help.getBoundingClientRect();
        Object.assign(help.style, {transform: 'none', left: `${x - box.width / 2}px`, top: `${y - box.height / 2}px`});
        const over = document.elementFromPoint(x, y)?.closest('.window')?.id || null;
        help.hidden = true; help.style.transform = help.style.left = help.style.top = svg.style.pointerEvents = '';
        return {before, over};
    }""", [placed['shown'][0]['who'], (placed['shown'][0]['box'][0] + placed['shown'][0]['box'][2]) / 2,
           (placed['shown'][0]['box'][1] + placed['shown'][0]['box'][3]) / 2])
    assert stacked == {'before': True, 'over': 'help'}, stacked

    # the camera turned until the agent on its own node is off the right of the view: its bubble stays in the view,
    # and its tail runs to the view's right edge, toward it
    alone = tickets[2].id
    page.evaluate("""async alone => {
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {ROAM} = await import('/page/app/figures/agents.js');
        const camera = G.camera(), seen = ROAM.figures.get(alone).mesh.position.clone()
            .applyMatrix4(camera.matrixWorldInverse);
        const half = Math.atan(Math.tan(camera.fov * Math.PI / 360) * camera.aspect);
        camera.rotateY(half + 0.2 - Math.atan2(seen.x, -seen.z));
        camera.updateMatrixWorld();
    }""", alone)
    turned = page.evaluate(bubbles, 40)
    left, top, right, bottom = turned['area']
    off = next(one for one in turned['shown'] if one['who'] == alone)
    assert off['head']['x'] > right, off
    apart_in_view(turned)
    middle = ((off['box'][0] + off['box'][2]) / 2, (off['box'][1] + off['box'][3]) / 2)
    toward = math.atan2(off['head']['y'] - middle[1], off['head']['x'] - middle[0])
    aimed = math.atan2(off['tip'][1] - middle[1], off['tip'][0] - middle[0])
    assert off['tip'][0] > right - 8 and abs(toward - aimed) < math.radians(5), off

    # a short line goes after its bubbleSeconds, on auto; a longer one stays until its own time is up
    page.evaluate("""async () => {
        const {G} = await import('/page/app/map3d/graph3d.js');
        const camera = G.camera();
        camera.position.copy(window.__kept.position); camera.quaternion.copy(window.__kept.quaternion);
        camera.updateMatrixWorld();
        window.metaform.pause3d(false);
    }""")
    lines = {tickets[0].id: 'Done.', tickets[1].id: 'Now reading the tests as well, then the page that draws them all. '
             'I will also check the timing while both agents keep working.'}
    times = page.evaluate("""async lines => {
        const {D} = await import('/page/app/agents/dispatch.js');
        const {takeBubbleSeconds} = await import('/page/app/workspace/workspace.js');
        const {bubbleSeconds} = await import('/page/app/figures/bubble.js');
        takeBubbleSeconds('auto');
        for (const [work, text] of Object.entries(lines)) {
            const session = D.sessions.find(one => one.work_id === work);
            session.said = {...session.said, text, seq: (session.said?.seq || 1) + 1};
        }
        return Object.fromEntries(Object.entries(lines).map(([work, text]) => [work, bubbleSeconds(text, 'auto')]));
    }""", lines)
    said = time.monotonic()
    short, long = times[tickets[0].id], times[tickets[1].id]
    assert short + 1 < long, times

    def showing():
        return {one['who']: one['said'] for one in page.evaluate(bubbles, 1)['shown'] if one['opacity'] > 0.5}

    time.sleep(max(0, said + short - 1 - time.monotonic()))
    assert showing().get(tickets[0].id) == 'Done.', showing()  # still up just before its time
    time.sleep(max(0, said + short + 0.6 - time.monotonic()))
    now = showing()
    assert tickets[0].id not in now and now.get(tickets[1].id) == lines[tickets[1].id], now
    time.sleep(max(0, said + long + 0.6 - time.monotonic()))
    assert tickets[1].id not in showing(), showing()
    # code.interface.graphical#14c: a view switch to 2D and back, the 3D map without an area meanwhile as when the 2D
    # tab is shown in its place, brings no line back whose time had passed; the next line, below, shows again once
    # its said.seq changes
    page.evaluate("""async () => {
        const {placeBubble} = await import('/page/app/figures/cut.js');
        const {bubbles3d} = await import('/page/app/figures/bubble3d.js');
        for (const hidden of [true, false]) {
            document.querySelector('#big3d').style.display = hidden ? 'none' : '';
            for (let n = 0; n < 10; n++) { await new Promise(requestAnimationFrame); placeBubble(); bubbles3d(); }
        }
    }""")
    assert not set(lines) & set(showing()), showing()

    # the mascot's status is in the accessibility tree between its lines, apart from its drawn bubble, which comes and
    # goes, and takes each line said
    status = page.locator('#bubbles').get_by_role('status')
    assert status.count() == 1 and status.evaluate('el => getComputedStyle(el).display') != 'none'

    # the mascot's web_say: its bubble's tail on the seahorse's head
    page.evaluate("""async work => {
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {MASCOT} = await import('/page/app/figures/mascot.js');
        const {mascotEvent} = await import('/page/app/figures/attention.js');
        const {S} = await import('/page/app/core/reads.js');
        window.metaform.pause3d(true);
        const camera = G.camera(), ahead = camera.getWorldDirection(MASCOT.mesh.position.clone());
        // in front of the eye, below the middle of the view, where its bubble has room above it
        MASCOT.mesh.position.copy(camera.position).addScaledVector(ahead, 40 * MASCOT.mesh.scale.x);
        MASCOT.mesh.updateMatrixWorld();
        mascotEvent({project: S.project, act: 'say', text: 'Over here, look at this one!'});
        // and an agent says a new line, to be clicked
        const {D} = await import('/page/app/agents/dispatch.js');
        const session = D.sessions.find(one => one.work_id === work);
        session.said = {...session.said, text: 'Looking at the alarm again', seq: session.said.seq + 1};
    }""", tickets[0].id)
    spoke = page.evaluate(bubbles, 20)
    mascot = next(one for one in spoke['shown'] if one['who'] == 'mascot')
    assert mascot['said'] == '' and mascot['opacity'] > 0.5, mascot  # told once, by the status
    assert status.text_content() == 'Over here, look at this one!'
    on_head(mascot, spoke['area'])
    # a click on an agent's bubble picks that agent, and a click on the mascot's does what it was said with
    agent = next(one for one in spoke['shown'] if one['who'] != 'mascot')
    picked = page.evaluate("""async ([x, y]) => (await import('/page/app/figures/ask.js')).figureAt(x, y)""",
                           [(agent['box'][0] + agent['box'][2]) / 2, (agent['box'][1] + agent['box'][3]) / 2])
    assert picked == agent['who'], (picked, agent)
    page.evaluate("""async () => (await import('/page/app/figures/cut.js'))
        .say('Click me', 5, () => { window.__clicked = true; })""")
    clickable = next(one for one in page.evaluate(bubbles, 20)['shown'] if one['who'] == 'mascot')
    page.mouse.click((clickable['box'][0] + clickable['box'][2]) / 2, (clickable['box'][1] + clickable['box'][3]) / 2)
    assert page.evaluate('window.__clicked') is True
    assert 'mascot' not in [one['who'] for one in page.evaluate(bubbles, 20)['shown'] if one['opacity'] > 0.5]
    assert status.count() == 1 and status.text_content() == 'Click me'
    # code.interface.graphical#14a: a line longer than three lines hold grows the bubble, at the least font size, and
    # shows every word as said; the status tells the whole line
    long = ('The alarm on the scheduler fired twice because the second runner read the old lease before the first '
            'one wrote it back, so both took the same ticket and started')
    assert len(long) == 160
    page.evaluate("""async line => (await import('/page/app/figures/cut.js')).say(line, 5)""", long)
    grown = next(one for one in page.evaluate(bubbles, 20)['shown'] if one['who'] == 'mascot')
    assert len(grown['lines']) > 3 and ' '.join(grown['lines']) == long, grown['lines']
    assert status.text_content() == long
    apart_in_view(page.evaluate(bubbles, 1))
    # a line too long even for the grown bubble ends its last shown line with an ellipsis, never silently, and a click
    # on it opens the whole line in the chat
    longer = ' '.join([long] * 4)
    page.evaluate("""async line => (await import('/page/app/figures/cut.js')).say(line, 5)""", longer)
    cut = next(one for one in page.evaluate(bubbles, 20)['shown'] if one['who'] == 'mascot')
    shown = ' '.join(cut['lines'])
    assert shown.endswith('…') and longer.startswith(shown[:-1].rstrip()) and len(shown) < len(longer), cut['lines']
    page.mouse.click((cut['box'][0] + cut['box'][2]) / 2, (cut['box'][1] + cut['box'][3]) / 2)
    page.wait_for_function("""line => !document.querySelector('#helpdesk').hidden
        && document.querySelector('#helpdesk .log').textContent.includes(line)""", arg=longer, timeout=10000)

    page.evaluate("""async alone => {
        const {ROAM} = await import('/page/app/figures/agents.js');
        const eyes = await import('/page/app/figures/eyes.js');
        window.__eyes = eyes;  // read by the synchronous waits below; an async predicate ends a wait at once
        window.metaform.pause3d(false);
        eyes.followFigure(ROAM.figures.get(alone));
        eyes.agentView();
    }""", alone)
    page.wait_for_function('() => window.__eyes.EYE.view && window.__eyes.EYE.k >= 1', timeout=30000)
    page.evaluate('window.metaform.pause3d(true)')
    watched = page.evaluate(bubbles, 20)
    # its body hidden, its words at the bottom of the view, in its middle, at full brightness, the tail to the edge
    left, top, right, bottom = watched['area']
    own = next(one for one in watched['shown'] if one['who'] == alone)
    assert bottom - own['box'][3] < 0.1 * (bottom - top) / 2, own
    assert abs((own['box'][0] + own['box'][2]) / 2 - (left + right) / 2) < 0.05 * (right - left) / 2, own
    assert own['bright'] == 1 and own['tip'][1] > bottom - 4, own
    off = page.evaluate("""async () => {
        const {G} = await import('/page/app/map3d/graph3d.js');
        const {agentView, EYE} = await import('/page/app/figures/eyes.js');
        window.metaform.pause3d(false);
        agentView();
        return {controls: G.controls().enabled, saved: Boolean(EYE.saved)};
    }""")
    assert off == {'controls': True, 'saved': True}, off  # the person's camera at once, while the view eases back
    page.wait_for_function('() => !window.__eyes.EYE.saved', timeout=30000)
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


ROUNDTABLE_PROBE = """async () => {
    const THREE = await import('three');
    const {stageView, TABLE} = await import('/page/app/roundtable/stage.js');
    const {LOOK} = await import('/page/app/figures/bubble3d.js');
    const {eyeOf} = await import('/page/agents3d.js');
    await new Promise(requestAnimationFrame);
    const view = stageView(), camera = view.camera, [left, top, right, bottom] = view.area;
    const at = new THREE.Vector3(), gaze = new THREE.Vector3(), forward = new THREE.Vector3();
    const toScreen = point => {
        const seen = point.clone().project(camera);
        return [left + (seen.x + 1) / 2 * (right - left), top + (1 - seen.y) / 2 * (bottom - top)];
    };
    const seats = view.meshes.map((mesh, n) => {
        eyeOf(mesh, at, gaze);
        at.y += LOOK.lift * mesh.scale.x;
        mesh.getWorldDirection(forward);
        const toward = camera.position.clone().sub(mesh.position).normalize();
        const el = [...document.querySelectorAll('#bubbles .wbubble')].find(one => one.dataset.who === view.speakers[n].id
            && one.style.display !== 'none');
        let tip = null;
        if (el) {
            const tail = el.querySelector('[id^="wbubble-tail-"]');
            const m = (tail.getAttribute('d') || '').match(/^M(-?[0-9.]+),(-?[0-9.]+)/);
            const point = m && new DOMPoint(Number(m[1]), Number(m[2])).matrixTransform(tail.getScreenCTM());
            tip = point ? [point.x, point.y] : null;
        }
        return {name: view.names[n], middle: toScreen(mesh.position), head: toScreen(at),
            facing: forward.angleTo(toward) * 180 / Math.PI, visible: mesh.visible && Boolean(mesh.parent),
            want: view.speakers[n].want, tip, opacity: el ? Number(el.style.opacity) : 0,
            words: el ? el.querySelector('.said').textContent : ''};
    });
    return {seats, area: view.area, floor: TABLE.floor, next: TABLE.next, state: TABLE.state,
        hands: [...document.querySelectorAll('.rt-seat.hand')].length};
}"""


@pytest.mark.req('VIEW-035')
@pytest.mark.timeout(600)
def test_the_roundtable_stage_sinks_the_map_and_shows_the_table_debate_the_question_until_it_is_answered(
        run, web, mapped, browser, monkeypatch):  # noqa: F811 -- imported fixtures keep their names for discovery
    """code.interface.graphical#131: a table opened from the selected part, run by the Roundtable 2 engine with its own
    fakes (its stub OpenRouter and Jev, its fake ACP agent), as the roundtables module's tests run it. The map sinks
    back and the seats stand in an arc facing the person; the floor's bubble points at its head; a veto fades; the
    ideas, rankings and summary grow above the arc as they come; the stage asks the person nothing once the question
    is asked; leaving puts the map back."""
    import itertools
    import math
    import time

    from metaform.modules.roundtables.tests import test_roundtables as rt
    for key, value in {'ROUNDTABLE_HOME': str(mapped.parent / 'engine'), 'OPENROUTER_API_KEY': 'stub-key',
                       'ROUNDTABLE_AGENT_CLAUDE': f'{sys.executable} {rt.FAKE_AGENT}',
                       'ROUNDTABLE_AGENT_WAIT': '30', 'ROUNDTABLE_MIN_ROUNDS': '1', 'ROUNDTABLE_ROUNDS': '4',
                       'ROUNDTABLE_REPORT_MODEL': 'stub/reporter',
                       'FAKE_ACP_LOG': str(mapped.parent / 'fake-acp.log')}.items():
        monkeypatch.setenv(key, value)
    held = rt.serve(monkeypatch, rt.stubbed(pace=1.0))
    try:
        run('enable', 'dispatch', cwd=mapped)
        run('set', '--jev', cwd=mapped)
        run('set', '--roundtables-seats=stub/vega,claude/haiku,stub/orion', cwd=mapped)
        started(run)
        page, problems, _ = opened(browser, web, plain=True)
        page.wait_for_function('() => window.metaform.figures !== undefined')
        page.evaluate("""async () => {
            const {S} = await import('/page/app/core/reads.js');
            const {select} = await import('/page/app/selection/select.js');
            const id = [...S.elements.values()].find(one => one.element.address === 'code.alarm.audible').element.id;
            select(id, true);
        }""")
        # the camera at rest on the selected part, the layout held, so what leaving gives back can be compared
        page.evaluate("async () => (await import('/page/app/map3d/graph3d.js')).pauseLayout()")
        assert page.evaluate("""async () => {
            const {G} = await import('/page/app/map3d/graph3d.js');
            const {FLIGHT} = await import('/page/app/camera/flight.js');
            for (let tries = 0; tries < 60; tries++) {
                const at = G.camera().position.clone();
                await new Promise(resolve => setTimeout(resolve, 500));
                if (!FLIGHT.on && at.distanceTo(G.camera().position) < 1e-6) return true;
            }
            return false;
        }"""), 'the camera came to rest'
        before = page.evaluate("""async () => {
            const {G} = await import('/page/app/map3d/graph3d.js');
            const at = G.camera().position;
            return {camera: [at.x, at.y, at.z], filter: getComputedStyle(document.querySelector('#stage')).filter};
        }""")
        # the ideas, the rankings and the answer noted as each first shows, above the arc
        page.evaluate("""() => {
            window.__arrived = [];
            new MutationObserver(() => {
                for (const name of ['ideas', 'rankings', 'answer']) {
                    const box = document.querySelector(`.rt-${name}`);
                    if (box && !box.hidden && !window.__arrived.includes(name)) window.__arrived.push(name);
                }
            }).observe(document.body, {subtree: true, attributes: true, attributeFilter: ['hidden'], childList: true});
        }""")
        page.wait_for_selector('#work .roundtablebtn')
        page.evaluate("() => document.querySelector('#work .roundtablebtn').click()")  # the panel redraws as it loads
        page.wait_for_function('() => [...document.querySelectorAll(".rt-setup .rt-model input")]'
                               '.some(one => one.value === "stub/orion")')
        sunk = page.evaluate("""() => ({sunk: document.querySelector('#big3d').classList.contains('roundtable'),
            filter: getComputedStyle(document.querySelector('#stage')).filter})""")
        assert sunk['sunk'] and 'blur' in sunk['filter'] and 'brightness' in sunk['filter'], sunk
        assert 'blur' not in before['filter'], before
        page.fill('.rt-setup textarea', 'How should the alarm tell the cook the dish is ready?')
        # each frame Vega has the floor with its vetoed turn: how much its bubble wants to show, and shows
        page.evaluate("""async () => {
            window.__stage = await import('/page/app/roundtable/stage.js');
            const {SEATS} = await import('/page/app/figures/bubble3d.js'), {TABLE} = window.__stage;
            window.__veto = [];
            const frame = () => {
                const n = TABLE.names.indexOf('Vega');
                if (n >= 0 && TABLE.floor === n && document.querySelector('.rt-transcript .vetoed')) {
                    const el = [...document.querySelectorAll('#bubbles .wbubble')].find(one =>
                        one.dataset.who === SEATS.list[n].id);
                    window.__veto.push([SEATS.list[n].want,
                        el && el.style.display !== 'none' ? Number(el.style.opacity) : 0]);
                }
                if (!TABLE.ended) requestAnimationFrame(frame);
            };
            requestAnimationFrame(frame);
        }""")
        page.click('.rt-setup .rt-start')  # the default seats, roundtables_seats

        # three figures in an arc in view, facing the person; the floor's bubble tail on its head
        page.wait_for_function('() => window.__stage.TABLE.floor >= 0', timeout=120000)
        time.sleep(0.6)  # the floor's step forward and its bubble eased into place
        probe = page.evaluate(ROUNDTABLE_PROBE)
        left, top, right, bottom = probe['area']
        assert [one['name'] for one in probe['seats']] == ['Vega', 'Haiku', 'Orion'], probe
        for one in probe['seats']:
            assert one['visible'] and left < one['middle'][0] < right and top < one['middle'][1] < bottom, one
            assert one['facing'] < 25, one
        xs = [one['middle'][0] for one in probe['seats']]
        assert xs == sorted(xs) and xs[-1] - xs[0] > (right - left) * 0.5, xs  # across the screen
        speaking = probe['seats'][probe['floor']]
        assert speaking['tip'] and math.dist(speaking['tip'], speaking['head']) < 6, speaking
        assert speaking['words'], speaking

        # the person only watches: nothing on the stage takes their input once the question is asked
        assert page.evaluate("""() => [...document.querySelectorAll('#roundtable input, #roundtable button')]
            .filter(one => !one.closest('.rt-setup') && !one.classList.contains('rt-leave')).length""") == 0

        # Vega's second turn is vetoed: struck in the transcript, and it fades from its bubble while Vega has the floor,
        # recorded frame by frame since the table opened
        page.wait_for_function('() => window.__veto.length > 2 && window.__veto.at(-1)[0] < 0.5', timeout=120000)
        faded = page.evaluate("() => window.__veto")
        assert len(faded) > 2 and all(b[0] <= a[0] for a, b in itertools.pairwise(faded)), faded
        assert faded[-1][0] < 0.5 < faded[0][0] and faded[-1][1] < faded[0][1], faded
        assert page.evaluate("() => document.querySelector('.rt-transcript .vetoed').textContent").startswith('Vega')

        # the ideas, then each seat's ranking, then the host's summary, which answers the question; the table ends
        page.wait_for_function('() => document.querySelector("#roundtable").dataset.state === "ended"', timeout=180000)
        board = page.evaluate("""() => ({arrived: window.__arrived,
            ideas: [...document.querySelectorAll('.rt-ideas li')].map(li => li.dataset.id),
            rankings: [...document.querySelectorAll('.rt-rankings li')].map(li => li.dataset.seat),
            answer: document.querySelector('.rt-answertext').textContent,
            transcript: document.querySelectorAll('.rt-transcript li').length})""")
        assert board['arrived'] == ['ideas', 'rankings', 'answer'], board
        assert board['ideas'][:2] == ['I1', 'I2'] and sorted(board['rankings']) == ['Haiku', 'Orion', 'Vega'], board
        assert 'summarises' in board['answer'] and board['transcript'] > 4, board

        # leaving puts the map back as it was
        page.click('.rt-leave')
        page.wait_for_function(f"() => getComputedStyle(document.querySelector('#stage')).filter === '{before['filter']}'")
        after = page.evaluate("""async () => {
            const {G} = await import('/page/app/map3d/graph3d.js');
            const {SEATS} = await import('/page/app/figures/bubble3d.js');
            const at = G.camera().position;
            return {camera: [at.x, at.y, at.z], filter: getComputedStyle(document.querySelector('#stage')).filter,
                sunk: document.querySelector('#big3d').classList.contains('roundtable'), on: SEATS.on,
                shown: !document.querySelector('#roundtable').hidden,
                seats: [...document.querySelectorAll('#bubbles .wbubble')].filter(one => (one.dataset.who || '').startsWith(
                    '\\u0000seat') && one.style.display !== 'none').length};
        }""")
        assert after == {'camera': after['camera'], 'filter': before['filter'], 'sunk': False, 'on': False,
                         'shown': False, 'seats': 0}, after
        assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(after['camera'], before['camera'])), after

        # a second table, its seats chosen, from the T key: it runs to its end with the person only watching
        page.focus('#stage')
        page.keyboard.press('t')
        page.wait_for_selector('.rt-setup:not([hidden])')
        page.fill('.rt-setup textarea', 'Is a second alarm needed?')
        for _ in range(2):  # the seats kept from the first table, less Claude's and Orion's
            page.click('.rt-pick:nth-child(2) [aria-label="Remove this seat"]')
        page.fill('.rt-pick:nth-child(1) .rt-model input', 'stub/vega, stub/orion')
        page.click('.rt-setup .rt-start')
        page.wait_for_function('() => document.querySelector("#roundtable").dataset.state === "running"',
                               timeout=120000)
        assert page.evaluate('async () => (await import("/page/app/roundtable/stage.js")).TABLE.names') == [
            'Vega', 'Orion']
        # leaving a table that runs and coming back to it shows its seats again: each figure in the stage's scene
        page.click('.rt-leave')
        page.wait_for_function("() => document.querySelector('#roundtable').hidden")
        page.focus('#stage')
        page.keyboard.press('t')
        page.wait_for_selector('#roundtable:not([hidden])')
        back = page.evaluate("""async () => {
            const {stageView} = await import('/page/app/roundtable/stage.js');
            await new Promise(requestAnimationFrame);
            const view = stageView();
            return {seats: view.meshes.length, inScene: view.meshes.every(mesh => mesh.parent !== null),
                labels: [...document.querySelectorAll('.rt-seat')].filter(one => !one.hidden).length,
                setup: !document.querySelector('.rt-setup').hidden};
        }""")
        assert back == {'seats': 2, 'inScene': True, 'labels': 2, 'setup': False}, back

        # a burst of the roundtables module's changes for another table reads nothing: no table, no map
        reads = []
        page.on('request', lambda sent: reads.append(sent.url) if '/api/' in sent.url else None)
        page.evaluate("""async () => {
            const {changed} = await import('/page/app/live/stream.js');
            const {S} = await import('/page/app/core/reads.js');
            for (let n = 0; n < 50; n++) await changed({topic: 'map.changed', payload: {project: S.project,
                tables: ['roundtables.events', 'roundtables.tables'], kinds: ['roundtables', 'roundtables:another']}});
        }""")
        page.wait_for_timeout(500)
        own = 'table=' + page.evaluate('async () => (await import("/page/app/roundtable/stage.js")).TABLE.id')
        assert not [url for url in reads if ('/api/roundtable' in url and own not in url) or '/api/layer' in url], reads
        page.wait_for_function('() => document.querySelector("#roundtable").dataset.state === "ended"', timeout=180000)
        page.keyboard.press('Escape')
        assert page.evaluate("() => document.querySelector('#roundtable').hidden"), 'Escape leaves the stage'
        assert problems == []
    finally:
        held.shutdown()
