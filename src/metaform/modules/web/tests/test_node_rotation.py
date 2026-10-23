"""Distance-driven body turns preserve readable map interaction, VIEW-005."""
import json
import os
from pathlib import Path

import pytest

from metaform.modules.web.tests.test_web import (  # noqa: F401
    RETURNING,
    browser,
    mapped,
    opened,
    started,
    web,
)

pytestmark = [pytest.mark.browser, pytest.mark.kind('fixture'), pytest.mark.req('VIEW-005')]


@pytest.fixture
def motion_browser(request):
    if not os.environ.get('METAFORM_MOTION_GPU'):
        yield request.getfixturevalue('browser')
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        gpu = driver.chromium.launch(headless=True, args=['--use-angle=gl-egl', '--ignore-gpu-blocklist'],
                                     env={**os.environ, 'DISPLAY': ':0', 'MESA_LOADER_DRIVER_OVERRIDE': 'd3d12',
                                          'GALLIUM_DRIVER': 'd3d12'})
        new_page = gpu.new_page

        def returning(*args, **kwargs):
            if os.environ.get('METAFORM_MOTION_CAPTURE'):
                kwargs['record_video_dir'] = os.environ['METAFORM_MOTION_CAPTURE']
            page = new_page(*args, **kwargs)
            page.add_init_script(RETURNING)
            return page
        gpu.new_page = returning
        yield gpu
        gpu.close()


def test_a_pull_turns_the_body_and_keeps_momentum_without_turning_its_label(
        run, web, mapped, motion_browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(motion_browser, web, plain=True)
    found = page.evaluate("""async () => {
        const {G, FRAMES} = await import('/page/app/map3d/graph3d.js');
        const {FLIGHT, V3} = await import('/page/app/camera/flight.js');
        const {tags} = await import('/page/app/map3d/labels.js');
        window.metaform.pause3d(true);
        FLIGHT.on = false; V3.auto = false;
        const data = G.graphData();
        for (const n of data.nodes) { n.fx = n.x; n.fy = n.y; n.fz = n.z; }
        const node = data.nodes.find(n => n.t === 'el' && n.__threeObj);
        const object = node.__threeObj, before = object.quaternion.clone();
        const label = tags.get(node.id).sprite, labelBefore = label.quaternion.clone();
        const times = new Float64Array(90), intervals = new Float64Array(90);
        let previous = 0, at = 0;
        const frame = async () => {
            await new Promise(requestAnimationFrame);
            const now = performance.now();
            if (at < 90) intervals[at] = previous ? now - previous : 0;
            previous = now;
            G._animationCycle(); G.pauseAnimation();
            if (at < 90) times[at++] = performance.now() - now;
        };
        for (let i = 0; i < 30; i++) await frame();
        at = 0;
        G.d3ReheatSimulation(); G.onNodeDrag()(node);
        for (let i = 0; i < 30; i++) { node.x += .5; node.fx = node.x; await frame(); }
        G.onNodeDragEnd()(node);
        const released = object.quaternion.clone();
        for (let i = 0; i < 60; i++) await frame();
        const gl = G.renderer().getContext(), ext = gl.getExtension('WEBGL_debug_renderer_info');
        const percentile = (values, p) => Array.from(values).sort((a,b) => a-b)[Math.floor(89*p)];
        return {turn: before.angleTo(released), coast: released.angleTo(object.quaternion),
            labelTurn: labelBefore.angleTo(label.quaternion),
            cpu: [.5,.95,.99].map(p => percentile(times,p)),
            intervals: [.5,.95,.99].map(p => percentile(intervals,p)),
            calls: G.renderer().info.render.calls,
            renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown', frames: FRAMES.drawn};
    }""")
    print('NODE_ROTATION', json.dumps(found))
    assert found['turn'] > 1 and found['coast'] > .5, found
    assert found['labelTurn'] < 1e-6, found
    assert problems == []


def test_signed_distance_release_speed_decay_and_resets(run, web, mapped, motion_browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(motion_browser, web, plain=True)
    found = page.evaluate("""async () => {
        const THREE = await import('three');
        const {TURN, bindTurns, resetTurns, nodeTurnStart, nodeTurnEnd, turn3d, cameraTurnStart,
            cameraTurnEnd} = await import('/page/app/map3d/rotation.js');
        window.metaform.pause3d(true);
        const camera = new THREE.PerspectiveCamera(), target = new THREE.Vector3();
        const a = {x:0,y:0,z:0,__threeObj:new THREE.Object3D()},
            b = {x:0,y:0,z:0,__threeObj:new THREE.Object3D()};
        const nodes = [a,b];
        let time = 1000;
        const step = (dt, reduced=false, automatic=false) => {
            time += dt*1000; turn3d(time,camera,target,reduced,automatic);
        };
        const fresh = () => {
            a.x=b.x=0; a.__threeObj.quaternion.identity(); b.__threeObj.quaternion.identity();
            camera.quaternion.identity(); bindTurns(nodes, () => 1); step(1/60);
        };
        const pull = (frames, duration) => {
            fresh(); nodeTurnStart();
            for (let i=0;i<frames;i++) { a.x+=3/frames; b.x+=1.5/frames; step(duration/frames); }
            nodeTurnEnd();
            return {angle:2*Math.atan2(a.__threeObj.quaternion.y,a.__threeObj.quaternion.w),
                speed:TURN.wy[0], neighbor:2*Math.atan2(b.__threeObj.quaternion.y,b.__threeObj.quaternion.w)};
        };
        const slow=pull(120,2), fast=pull(15,.25);
        const released=fast.speed; step(2);
        const remaining=TURN.wy[0]/released;
        const decay = fps => {
            pull(30,.5);
            for(let i=0;i<fps*2;i++) step(1/fps);
            return [a.__threeObj.quaternion.y,a.__threeObj.quaternion.w,TURN.wy[0]];
        };
        const at30=decay(30), at144=decay(144);
        fresh(); bindTurns(nodes,n=>n===b?8:1); step(1/60); nodeTurnStart();
        a.x=b.x=3; step(.2);
        const radiusRatio=b.__threeObj.quaternion.angleTo(new THREE.Quaternion()) /
            a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        fresh(); nodeTurnStart(); a.x=3; step(.2); a.x=0; step(.2);
        const reversal=2*Math.atan2(a.__threeObj.quaternion.y,a.__threeObj.quaternion.w);
        nodeTurnEnd(); for(let i=0;i<600;i++) step(1/60);
        const settled=!TURN.moving, final=a.__threeObj.quaternion.clone(); step(10);
        const retained=final.angleTo(a.__threeObj.quaternion), upright=final.angleTo(new THREE.Quaternion());
        fresh(); a.x=300; step(.1);
        const initial=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        nodeTurnStart(); a.x+=3; step(.1);
        a.x+=30; step(.1,true); step(.1,true);
        const reduced=a.__threeObj.quaternion.angleTo(new THREE.Quaternion()), reducedSpeed=TURN.moving;
        step(.1); const resumed=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        a.__threeObj=new THREE.Object3D(); a.x=2000; step(.1);
        const replaced=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        resetTurns(); a.x=-2000; step(.1);
        const reset=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        fresh(); a.x=20; step(.1); cameraTurnStart(); camera.rotateY(.1); step(.1); cameraTurnEnd();
        const orbit=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        fresh(); a.x=20; step(.1); cameraTurnStart(); camera.rotateY(.1); step(.1,false,true);
        const flight=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        fresh(); cameraTurnStart(); camera.position.z=100; step(.1);
        const zoom=a.__threeObj.quaternion.angleTo(new THREE.Quaternion());
        return {slow,fast,remaining,at30,at144,radiusRatio,reversal,settled,retained,upright,initial,reduced,reducedSpeed,
            resumed,replaced,reset,orbit,flight,zoom};
    }""")
    print('ROTATION_LAWS', json.dumps(found))
    assert found['slow']['angle'] == pytest.approx(found['fast']['angle'], abs=1e-8)
    assert found['fast']['speed'] > found['slow']['speed'] * 5
    assert found['slow']['neighbor'] == pytest.approx(found['slow']['angle'] / 2)
    assert found['slow']['angle'] == pytest.approx(1)  # 6.25x the former 0.16-radian turn
    assert found['remaining'] == pytest.approx(2 ** (-2 / .65))
    assert found['at30'] == pytest.approx(found['at144'], abs=1e-8)
    assert found['radiusRatio'] == pytest.approx(.5)
    assert abs(found['reversal']) < 1e-8
    assert found['settled'] and found['retained'] < 1e-7 and found['upright'] < 1e-7
    for key in ('initial', 'reduced', 'resumed', 'replaced', 'reset', 'flight', 'zoom'):
        assert found[key] < 1e-7, (key, found)
    assert not found['reducedSpeed'] and found['orbit'] > .001
    assert problems == []


@pytest.mark.parametrize('plain', [True, False], ids=['glass', 'space'])
def test_pointer_gestures_pulled_neighbors_batches_picking_and_idle(
        run, web, mapped, motion_browser, plain):  # noqa: F811
    started(run)
    page, problems, _ = opened(motion_browser, web, plain=plain)
    setup = page.evaluate("""async () => {
        const {G, wake3d} = await import('/page/app/map3d/graph3d.js');
        const {FLIGHT, V3} = await import('/page/app/camera/flight.js');
        const {TURN} = await import('/page/app/map3d/rotation.js');
        window.nodeTurn = TURN;
        const {MASCOT} = await import('/page/app/figures/mascot.js');
        FLIGHT.on=false; V3.auto=false; MASCOT.job=null;
        const all=G.graphData(), a=all.nodes.find(n=>n.t==='el' && n.address==='code.timer.kitchen');
        const link=all.links.find(l=>l.source===a || l.target===a);
        const b=link.source===a ? link.target : link.source;
        const c={id:'rotation-check',t:'item',layer:a.layer,text:'Rotation check',
            x:0,y:-80,z:0,fx:0,fy:-80,fz:0};
        Object.assign(a,{x:-40,y:0,z:0,fx:-40,fy:0,fz:0,vx:0,vy:0,vz:0});
        Object.assign(b,{x:40,y:0,z:0,fx:40,fy:0,fz:0,vx:0,vy:0,vz:0});
        G.graphData({nodes:[a,b,c],links:[link,{source:a,target:c,k:'item',layer:a.layer}]}).d3AlphaDecay(.1);
        G.cameraPosition({x:0,y:0,z:300},{x:0,y:0,z:0},0);
        G.controls().target.set(0,0,0); G.controls().update(); wake3d();
        await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame);
        const box=document.querySelector('#stage').getBoundingClientRect(), p=G.graph2ScreenCoords(a.x,a.y,a.z);
        window.pullCheck={a,b,c,qa:a.__threeObj.quaternion.clone(),qb:b.__threeObj.quaternion.clone(),
            qc:c.__threeObj.quaternion.clone(),bx:b.x,by:b.y,bz:b.z,geometry:a.__threeObj.geometry,material:a.__threeObj.material};
        return {x:box.x+p.x,y:box.y+p.y,bgX:box.x+box.width*.85,bgY:box.y+box.height*.75};
    }""")
    capture = os.environ.get('METAFORM_MOTION_CAPTURE')

    def snapshot(name):
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            page.locator('#stage').screenshot(path=str(folder / f'{"glass" if plain else "space"}-{name}.png'))

    snapshot('01-rest')
    page.mouse.move(setup['x'], setup['y'])
    page.evaluate("window.pullCheck.b.fx=undefined; window.pullCheck.b.fy=undefined; window.pullCheck.b.fz=undefined")
    page.mouse.down()
    for i in range(1, 21):
        page.mouse.move(setup['x'] + i * 3, setup['y'] - i)
        page.evaluate('() => new Promise(requestAnimationFrame)')
    snapshot('02-pull-held')
    page.mouse.up()
    snapshot('03-pull-release')
    page.wait_for_function("() => !window.nodeTurn.layout")
    pulled = page.evaluate("""async () => {
        const {a,b,qa,qb,bx,by,bz,geometry,material}=window.pullCheck;
        const {G}=await import('/page/app/map3d/graph3d.js');
        const {nodeAt3d}=await import('/page/app/map3d/pick3d.js');
        const {BATCHES}=await import('/page/app/map3d/nodes3d.js');
        const box=document.querySelector('#stage').getBoundingClientRect(), p=G.graph2ScreenCoords(a.x,a.y,a.z);
        const batches=[...BATCHES.values()].flatMap(v=>v.ring).filter(m=>m.visible&&m.count>0);
        const matrices=batches.flatMap(m=>Array.from(m.instanceMatrix.array.slice(0,m.count*16)));
        return {turn:qa.angleTo(a.__threeObj.quaternion),neighborTurn:qb.angleTo(b.__threeObj.quaternion),
            neighborTravel:Math.hypot(b.x-bx,b.y-by,b.z-bz),picked:nodeAt3d(box.x+p.x,box.y+p.y)?.id===a.id,
            batches:batches.length,finite:matrices.every(Number.isFinite),
            sameLook:geometry===a.__threeObj.geometry && material===a.__threeObj.material};
    }""")
    print('POINTER_PULL', plain, json.dumps(pulled))
    assert pulled['turn'] > .03 and pulled['neighborTurn'] > .001 and pulled['neighborTravel'] > 1, pulled
    assert pulled['picked'] and pulled['batches'] > 0 and pulled['finite'] and pulled['sameLook'], pulled
    page.evaluate("""async () => {
        const {resetTurns}=await import('/page/app/map3d/rotation.js');
        const {a,b}=window.pullCheck;
        for(const n of [a,b]) { n.fx=n.x; n.fy=n.y; n.fz=n.z; }
        resetTurns(); window.pullCheck.orbitBefore=b.__threeObj.quaternion.clone();
    }""")
    page.mouse.move(setup['bgX'], setup['bgY'])
    page.mouse.down()
    for i in range(1, 16):
        page.mouse.move(setup['bgX'] - i * 7, setup['bgY'] - i * 3)
        page.evaluate('() => new Promise(requestAnimationFrame)')
    page.mouse.up()
    page.mouse.move(1, 1)
    snapshot('04-orbit-release')
    orbit = page.evaluate("""() => window.pullCheck.orbitBefore.angleTo(window.pullCheck.b.__threeObj.quaternion)""")
    print('POINTER_ORBIT', plain, orbit)
    assert orbit > .1, orbit
    page.wait_for_function("() => !window.nodeTurn.moving")
    snapshot('05-upright')
    landed = page.evaluate("""() => {
        const {a,b,c,qa,qb,qc}=window.pullCheck;
        return [qa.angleTo(a.__threeObj.quaternion),qb.angleTo(b.__threeObj.quaternion),
            qc.angleTo(c.__threeObj.quaternion)];
    }""")
    assert max(landed) < 1e-7, landed
    batched = page.evaluate("""async () => {
        const {BATCHES}=await import('/page/app/map3d/nodes3d.js');
        const object=window.pullCheck.c.__threeObj, expected=object.matrixWorld.elements;
        let found=false, error=Infinity;
        for(const batch of BATCHES.values()) for(const mesh of batch.ring) {
            if(!mesh.visible) continue;
            const m=mesh.instanceMatrix.array;
            for(let i=0;i<mesh.count;i++) {
                const at=i*16;
                if(Math.hypot(m[at+12]-expected[12],m[at+13]-expected[13],m[at+14]-expected[14])>.001) continue;
                let e=0; for(let k=0;k<16;k++) e=Math.max(e,Math.abs(m[at+k]-expected[k]));
                error=Math.min(error,e); found=true;
            }
        }
        return {found,error};
    }""")
    assert batched['found'] and batched['error'] < .0001, batched
    # A quiet map must be allowed to sleep once its angular motion ends. Ambient effects are the person's choices.
    page.emulate_media(reduced_motion='reduce')
    page.evaluate("""async () => {
        const {FRAMES,wake3d}=await import('/page/app/map3d/graph3d.js');
        FRAMES.rest=0; FRAMES.idle=0; window.rotationFrames=FRAMES; wake3d();
    }""")
    page.wait_for_function("() => window.rotationFrames.id===0")
    reduced = page.evaluate("""async () => {
        const {G}=await import('/page/app/map3d/graph3d.js');
        const a=window.pullCheck.a, q=a.__threeObj.quaternion.clone();
        G.d3ReheatSimulation(); G.onNodeDrag()(a); a.x+=10; a.fx=a.x;
        await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame);
        G.onNodeDragEnd()(a);
        return q.angleTo(a.__threeObj.quaternion);
    }""")
    assert reduced < 1e-7, reduced
    assert problems == []


def test_authored_upright_landing_is_continuous_interruptible_and_survives_rebinding(
        run, web, mapped, motion_browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(motion_browser, web, plain=True)
    found = page.evaluate("""async () => {
        const THREE=await import('three');
        const {TURN,bindTurns,resetTurns,nodeTurnStart,nodeTurnEnd,turn3d}=
            await import('/page/app/map3d/rotation.js');
        window.metaform.pause3d(true);
        const camera=new THREE.PerspectiveCamera(), target=new THREE.Vector3(), identity=new THREE.Quaternion();
        let a, rest, time=1000;
        const step=(dt,reduced=false)=>{time+=dt*1000;turn3d(time,camera,target,reduced,false);};
        const fresh=()=>{
            const object=new THREE.Object3D(); object.rotation.set(.4,-.7,.2);
            a={x:0,y:0,z:0,__threeObj:object}; rest=object.quaternion.clone();
            bindTurns([a],()=>1);step(1/60);
            nodeTurnStart();for(let i=0;i<30;i++){a.x+=.3;step(1/60);}nodeTurnEnd();
        };
        fresh();
        const released=a.__threeObj.quaternion.clone(), delta=new THREE.Quaternion(), prev=released.clone();
        step(.1);delta.copy(a.__threeObj.quaternion).multiply(prev.clone().invert());
        const forward=delta.y, first=prev.angleTo(a.__threeObj.quaternion);prev.copy(a.__threeObj.quaternion);
        step(.1);const second=prev.angleTo(a.__threeObj.quaternion);
        const coast=first>0 && forward>0 && second<first;
        const land=fps=>{
            fresh();const start=a.__threeObj.quaternion.clone(), prev=start.clone();
            let maxStep=0,lastStep=0;
            for(let i=0;i<fps*3.6;i++){
                step(1/fps);lastStep=prev.angleTo(a.__threeObj.quaternion);
                if(i>=fps*2)maxStep=Math.max(maxStep,lastStep);
                prev.copy(a.__threeObj.quaternion);
            }
            return {q:a.__threeObj.quaternion.toArray(),error:rest.angleTo(a.__threeObj.quaternion),maxStep,lastStep,
                moving:TURN.moving,exact:a.__threeObj.quaternion.equals(rest)};
        };
        const at30=land(30),at144=land(144);
        const middle=fps=>{fresh();for(let i=0;i<fps*2.5;i++)step(1/fps);return a.__threeObj.quaternion.toArray();};
        const mid30=middle(30),mid144=middle(144);
        fresh();step(2.5);const longMid=a.__threeObj.quaternion.toArray();step(1.2);
        const longRest=a.__threeObj.quaternion.equals(rest),longStopped=!TURN.moving;
        fresh();step(2.5);const landing=a.__threeObj.quaternion.clone();nodeTurnStart();step(1/60);
        const grab=landing.angleTo(a.__threeObj.quaternion);step(5);
        const held=landing.angleTo(a.__threeObj.quaternion);
        a.x+=1.5;step(.1);const renewed=landing.angleTo(a.__threeObj.quaternion);nodeTurnEnd();step(4);
        const interruptedRest=a.__threeObj.quaternion.equals(rest);
        fresh();step(.2);const spun=a.__threeObj.quaternion.clone();
        bindTurns([{x:a.x,y:a.y,z:a.z,__threeObj:a.__threeObj}],()=>1);step(1/60);
        const rebound=spun.angleTo(a.__threeObj.quaternion);step(4);
        const reboundRest=a.__threeObj.quaternion.equals(rest);
        // Replacing a theme/type object captures its own intentional tilt, never the former spun pose.
        const replacement=new THREE.Object3D();replacement.rotation.set(-.3,.9,-.5);
        const replacementRest=replacement.quaternion.clone();a=TURN.nodes[0];a.__threeObj=replacement;a.x+=1000;step(.1);
        const replacementInitial=replacement.quaternion.equals(replacementRest);
        nodeTurnStart();a.x+=3;step(.1);nodeTurnEnd();step(4);
        const replacementLanded=replacement.quaternion.equals(replacementRest);
        nodeTurnStart();a.x+=3;step(.1);nodeTurnEnd();step(2.5);step(.01,true);
        const reduced= replacement.quaternion.equals(replacementRest) && !TURN.moving;step(.1);
        const resumed=replacement.quaternion.equals(replacementRest) && !TURN.moving;
        nodeTurnStart();a.x+=3;step(.1);nodeTurnEnd();resetTurns();a.x+=1000;step(.1);step(4);
        const resetRest=replacement.quaternion.equals(replacementRest);
        return {coast,first,second,at30,at144,mid30,mid144,longMid,longRest,longStopped,grab,held,renewed,
            interruptedRest,rebound,reboundRest,replacementInitial,replacementLanded,reduced,resumed,resetRest,
            authoredTilt:rest.angleTo(identity)};
    }""")
    print('UPRIGHT_LANDING', json.dumps(found))
    assert found['coast'] and found['authoredTilt'] > .5, found
    for key in ('at30', 'at144'):
        assert found[key]['error'] < 1e-7 and found[key]['lastStep'] < .001, found[key]
        assert found[key]['maxStep'] < .15, found[key]
    assert found['mid30'] == pytest.approx(found['mid144'], abs=1e-8)
    assert found['mid30'] == pytest.approx(found['longMid'], abs=1e-8)
    assert found['grab'] < 1e-7 and found['held'] < 1e-7 and found['rebound'] < 1e-7, found
    assert found['renewed'] == pytest.approx(.5), found
    for key in ('longRest','longStopped','interruptedRest','reboundRest','replacementInitial','replacementLanded',
                'reduced','resumed','resetRest'):
        assert found[key], (key, found)
    assert problems == []
