"""Compare production atlas ordering and frame costs against an earlier source file."""

import argparse
import base64
import json
import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FILE = "src/metaform/modules/web/page/app/map3d/nodes3d.js"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--software", action="store_true")
    args = parser.parse_args()
    baseline = (
        args.baseline.read_text()
        if args.baseline
        else subprocess.check_output(["git", "show", f"HEAD:{FILE}"], cwd=ROOT, text=True)
    )
    sources = {
        "baseline": baseline,
        "candidate": (ROOT / FILE).read_text(),
        "candidate_bank_limit": (ROOT / FILE).read_text(),
    }
    url = (
        "data:text/javascript;base64,"
        + base64.b64encode((ROOT / "src/metaform/modules/web/vendor/three.module.min.js").read_bytes()).decode()
    )
    environment = dict(os.environ)
    if not args.software:
        environment.update(DISPLAY=":0", MESA_LOADER_DRIVER_OVERRIDE="d3d12", GALLIUM_DRIVER="d3d12")
    with sync_playwright() as driver:
        browser = driver.chromium.launch(
            headless=True,
            env=environment,
            args=[
                "--use-angle=gl" if args.software else "--use-angle=gl-egl",
                "--ignore-gpu-blocklist",
                "--no-sandbox",
            ],
        )
        report = {
            "browser": browser.version,
            "viewport": [640, 480],
            "warmup": 30,
            "samples": 180,
            "timing": "CPU submission and RAF intervals, GPU queries when available",
            "variants": {},
        }
        for variant, source in sources.items():
            page = browser.new_page(viewport={"width": 640, "height": 480})
            page.on("pageerror", lambda error: print(str(error)))
            page.on("console", lambda message: print(message.text) if message.type == "error" else None)
            result = page.evaluate(
                JS, {"source": source[source.index("const PAGE = 2048") :].replace("export ", ""), "url": url, "bankLimit": variant == "candidate_bank_limit"}
            )
            report["variants"][variant] = result
            page.close()
        browser.close()
    print(json.dumps(report, indent=2))
    candidate = report["variants"]["candidate"]
    assert all(case["matches"] for case in report["variants"]["candidate_bank_limit"]["checks"])
    assert all(case["matches"] for case in candidate["checks"]), "Candidate differs from ordered reference"
    assert candidate["unpickable"], "Atlas must not intercept picking"
    if not args.software:
        assert candidate["hardwareIdentityAvailable"], "Hardware renderer identity unavailable"
        assert not any(word in candidate["renderer"].lower() for word in ("swiftshader", "llvmpipe", "software"))


JS = r"""async ({source,url,bankLimit}) => {
 const THREE=await import(url), renderer=new THREE.WebGLRenderer({preserveDrawingBuffer:true});
 renderer.setSize(640,480);document.body.append(renderer.domElement);
 const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera(60,4/3,.1,100);
 const G={scene:()=>scene,renderer:()=>renderer};
 if(bankLimit)renderer.capabilities.maxTextures=1;
 const atlas=new Function('THREE','G',source+';return {ATLAS,atlasPaint,atlasDraw,atlasDrop};')(THREE,G);
 const tags=[], references=[], reference=new THREE.Scene(), order=[];
 const pixel=new Uint8Array(4), expected=new Uint8Array(4), gl=renderer.getContext();
 const ext=gl.getExtension('WEBGL_debug_renderer_info');
 const timer=gl.getExtension('EXT_disjoint_timer_query_webgl2');
 const identity=gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER);
 function make(i, size) {
  const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
  const pen=canvas.getContext('2d');pen.fillStyle=['#ff0000','#0000ff','#00ff00'][i%3];
  pen.fillRect(0,0,size,size);
  const sprite=new THREE.Object3D();sprite.position.z=.5-i*.5;sprite.scale.set(2,2,1);
  sprite.material={opacity:1};
  const tag={texture:{image:canvas},sprite,slot:null,hidden:false,uv0:0,uv1:0,uvw:0,uvh:0};
  atlas.atlasPaint(tag);tags.push(tag);
  return tag;
 }
 for(let i=0;i<3;i++) {
  const tag=make(i,i===2?400:1500);
  const texture=new THREE.CanvasTexture(tag.texture.image);texture.colorSpace=THREE.SRGBColorSpace;
  texture.minFilter=texture.magFilter=THREE.LinearFilter;texture.generateMipmaps=false;
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:texture,
   side:THREE.DoubleSide,transparent:true,depthTest:true,depthWrite:false,alphaTest:.02,toneMapped:false,fog:false}));
  mesh.position.copy(tag.sprite.position);mesh.scale.copy(tag.sprite.scale);reference.add(mesh);references.push(mesh);
 }
 const blocker=new THREE.Mesh(new THREE.PlaneGeometry(.5,.5),new THREE.MeshBasicMaterial({color:0x808080}));
 blocker.position.z=.8;
 const other=blocker.clone();scene.add(blocker);reference.add(other);blocker.visible=other.visible=false;
 const checks=[];
 function draw(direction, target=scene) {
  camera.position.set(0,0,4*direction);camera.lookAt(0,0,0);camera.updateMatrixWorld();
  for(let i=0;i<3;i++) {order[i]=tags[direction===1?i:2-i];references[i].renderOrder=10+(direction===1?2-i:i);}
  atlas.atlasDraw(order,3,true);renderer.render(target,camera);
 }
 for(const mode of ['opaque','fade','alpha_edge','hole','occluder','hidden','off']) {
  for(let i=0;i<3;i++) {
   tags[i].sprite.material.opacity=references[i].material.opacity=mode==='fade'?.45:1;
   tags[i].hidden=mode==='hidden'&&i!==1;references[i].visible=!tags[i].hidden;
   if(mode==='alpha_edge'&&i!==1) {
    const canvas=tags[i].texture.image,pen=canvas.getContext('2d');pen.clearRect(0,0,canvas.width,canvas.height);
    pen.fillStyle=i?'rgba(0,255,0,.5)':'rgba(255,0,0,.5)';pen.fillRect(0,0,canvas.width/2,canvas.height);
    atlas.atlasPaint(tags[i]);references[i].material.map.needsUpdate=true;
   }
   if(mode==='hole'&&i!==1) {
    tags[i].texture.image.getContext('2d').clearRect(0,0,1500,1500);
    atlas.atlasPaint(tags[i]);references[i].material.map.needsUpdate=true;
   }
   // Restore opaque pixels after the alpha-hole case.
   if(mode==='occluder'&&i!==1) {
    const pen=tags[i].texture.image.getContext('2d');pen.fillStyle=i?'#00ff00':'#ff0000';pen.fillRect(0,0,1500,1500);
    atlas.atlasPaint(tags[i]);references[i].material.map.needsUpdate=true;
   }
  }
  blocker.visible=other.visible=mode==='occluder';
  for(const direction of [1,-1]) {
   draw(direction,reference);
   if(mode==='off') {for(const mesh of references)mesh.visible=false;renderer.render(reference,camera);}
   gl.readPixels(320,240,1,1,gl.RGBA,gl.UNSIGNED_BYTE,expected);
   draw(direction);
   if(mode==='off'){atlas.atlasDraw(order,3,false);renderer.render(scene,camera);}
   gl.readPixels(320,240,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
   checks.push({mode,direction,expected:Array.from(expected),pixel:Array.from(pixel),
    matches:pixel.every((v,i)=>Math.abs(v-expected[i])<=2),drawCalls:renderer.info.render.calls});
  }
 }
 const unpickable=scene.children.filter(mesh=>mesh!==blocker).every(mesh=>{
  const hits=[];mesh.raycast(new THREE.Raycaster(),hits);return hits.length===0;
 });
 blocker.visible=false;
 for(let i=0;i<3;i++){tags[i].hidden=false;tags[i].sprite.material.opacity=1;}
 const timing=[];
 for(const count of (bankLimit?[]:[3,1000])) {
  while(tags.length<count)make(tags.length,64);
  for(let i=0;i<count;i++) {
   const tag=tags[i];tag.sprite.position.set((i%20-10)*.18,(Math.floor(i/20)%20-10)*.18,-i*.001);
   tag.sprite.scale.set(.2,.2,1);order[i]=tag;
  }
  const cpu=[],raf=[],gpu=[],queries=[];let frame=0,last=0,calls=0,discarded=0;
  await new Promise(resolve=>{
   function tick(now) {
    if(last&&frame>=30)raf.push(now-last);last=now;
    for(let i=queries.length-1;i>=0;i--) {
     const query=queries[i];
     if(gl.getQueryParameter(query,gl.QUERY_RESULT_AVAILABLE)) {
      if(!gl.getParameter(timer.GPU_DISJOINT_EXT))gpu.push(gl.getQueryParameter(query,gl.QUERY_RESULT)/1e6);
      else discarded++;
      gl.deleteQuery(query);queries.splice(i,1);
     }
    }
    camera.position.set(Math.sin(frame*.01)*.1,0,4);camera.lookAt(0,0,0);camera.updateMatrixWorld();
    const query=timer&&frame>=30?gl.createQuery():null;
    if(query)gl.beginQuery(timer.TIME_ELAPSED_EXT,query);
    const start=performance.now();atlas.atlasDraw(order,count,true);renderer.render(scene,camera);
    const elapsed=performance.now()-start;
    if(query){gl.endQuery(timer.TIME_ELAPSED_EXT);queries.push(query);}
    if(frame>=30){cpu.push(elapsed);calls=renderer.info.render.calls;}
    if(++frame<210)requestAnimationFrame(tick);else resolve();
   }
   requestAnimationFrame(tick);
  });
  for(const query of queries)gl.deleteQuery(query);
  function quantiles(values){values.sort((a,b)=>a-b);return values.length?
   {median:values[Math.floor(values.length*.5)],p95:values[Math.floor(values.length*.95)],
    p99:values[Math.floor(values.length*.99)],count:values.length}:null;}
  timing.push({count,pages:atlas.ATLAS.pages.length,drawCalls:calls,cpu_ms:quantiles(cpu),raf_ms:quantiles(raf),
   gpu_ms:quantiles(gpu),disjoint_discarded:discarded});
 }
 return {renderer:identity,hardwareIdentityAvailable:!!ext,timer:!!timer,checks,unpickable,timing};
}"""

if __name__ == "__main__":
    main()
