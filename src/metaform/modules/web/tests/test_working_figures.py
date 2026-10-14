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
