import json,sys,re,os,glob
T,L=sys.argv[1:3]; files=set(os.listdir(T+"/n/photos"))
print("##",L,"| procedure bytes",os.path.getsize(T+"/v/"+L+"/prompt.txt"))
for f in sorted(glob.glob(T+"/v/%s/stream-*.jsonl"%L)):
    reads=set(); r=""; err=None; secs=None; inline=[]
    for line in open(f):
        try:o=json.loads(line)
        except: continue
        if o.get("type")=="assistant":
            for b in (o.get("message") or {}).get("content") or []:
                if b.get("type")=="tool_use" and b["name"]=="Read": reads.add(os.path.basename(b["input"].get("file_path","")))
        if o.get("type")=="result": r=o.get("result") or ""; err=o.get("is_error"); secs=round((o.get("duration_ms") or 0)/1000)
        if o.get("type")=="assistant":
            for b in (o.get("message") or {}).get("content") or []:
                if b.get("type")=="text": inline.append(b["text"])
    open(f.replace("stream-","answer-").replace(".jsonl",".txt"),"w").write(r)
    els=re.findall(r'"namespace_address"\s*:\s*"([^"]+)"',r)
    role={}
    for m in re.finditer(r'\{[^{}]*?"namespace_address"\s*:\s*"([^"]+)"[^{}]*?\}',r):
        mm=re.search(r'"role"\s*:\s*"([^"]+)"',m.group(0))
        if mm: role[m.group(1)]=mm.group(1)
    for m in re.finditer(r'"namespace_address"\s*:\s*"([^"]+)"[^{}\[\]]*?"role"\s*:\s*"([^"]+)"',r): role.setdefault(m.group(1),m.group(2))
    for m in re.finditer(r'"role"\s*:\s*"([^"]+)"[^{}\[\]]*?"namespace_address"\s*:\s*"([^"]+)"',r): role.setdefault(m.group(2),m.group(1))
    uris=re.findall(r'"uri"\s*:\s*"([^"]*)"',r)
    bad=[u for u in uris if os.path.basename(u.rstrip("/")) not in files and u not in (".","./","") and not u.rstrip("/").endswith("photos")]
    allp=set(os.path.basename(p) for p in re.findall(r'[\w.]+\.jpg',r)); fake=sorted(p for p in allp if p not in files)
    cqu=sorted(a for a,ro in role.items() if ro=="CQU"); de=sorted(a for a,ro in role.items() if ro=="DE")
    print("- run",os.path.basename(f)[7:-6],"| err",err,"| sec",secs,"| opened",len(reads),"| elements",len(set(els)),"| uris",len(uris),"bad",bad,"| fake names",fake)
    print("   CQU:",cqu); print("   DE:",de); print("   other:",sorted(a for a in set(els) if a not in cqu and a not in de))
    it="\n".join(inline); ip=set(os.path.basename(p) for p in re.findall(r"[\w.]+\.jpg",it)); print("   inline text chars",len(it),"| distinct file names written in line",len(ip),"| fake in line",sorted(p for p in ip if p not in files))
    ps=re.findall(r'"purpose"\s*:\s*"([^"]+)"',r)
    print("   purposes(%d):"%len(ps)," | ".join(p[:70] for p in ps[:4]))
