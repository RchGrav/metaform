import json,glob,re,os,sys
T="/tmp/claude-1000/-home-rich-metaform/adfc5f6a-d5c7-4dfe-88d2-e0b87bbededd/scratchpad/phototest"; files=set(os.listdir(T+"/n/photos"))
for L in sys.argv[1:]:
    print("####",L)
    for f in sorted(glob.glob(T+"/v/%s/stream-*.jsonl"%L)):
        i=f[-7]; reads=set(); r=""; meta={}; seq=""
        for line in open(f):
            try:o=json.loads(line)
            except: continue
            if o.get("type")=="assistant":
                for b in (o.get("message") or {}).get("content") or []:
                    if b.get("type")=="tool_use":
                        seq+={"Read":"r","Glob":"G","Write":"W","Edit":"E"}.get(b["name"],"?")
                        if b["name"]=="Read": reads.add(os.path.basename(b["input"].get("file_path","")))
            if o.get("type")=="result":
                r=o.get("result") or ""; u=o.get("usage") or {}; mu=o.get("modelUsage") or {}
                meta=dict(err=o.get("is_error"),sec=round(o.get("duration_ms",0)/1000),out=u.get("output_tokens"),think=sum((m.get("thinkingTokens") or 0) for m in mu.values()),cost=round(o.get("total_cost_usd") or 0,2))
        open(f.replace("stream-","answer-").replace(".jsonl",".txt"),"w").write(r)
        m=re.search(r"```json\s*(.*?)```",r,re.S); s=m.group(1) if m else r
        photos=len([x for x in reads if x in files])
        writes=re.sub(r"r{4,}",lambda mm:"r(%d)"%len(mm.group(0)),seq)
        try: d=json.loads(s)
        except Exception as e: print(" run",i,meta,"| opened",photos,"| JSON did not parse:",str(e)[:50]); continue
        top=d
        while isinstance(top,dict) and len(top)==1 and not any("." in k for k in top) and isinstance(next(iter(top.values())),dict): top=next(iter(top.values()))
        keys=[k for k in top if isinstance(top[k],dict)] if isinstance(top,dict) else []
        fn_ok=0; fn_bad=[]; uri_bad=[]; deps=0; depfields=set(); ifd=set(); badpe=[]
        for k in keys:
            e=top[k]; rev=" ".join(reversed(k.split("."))).replace("_"," "); fn=(e.get("functional_name") or "")
            if fn and (rev==fn or rev.startswith(fn+" ")): fn_ok+=1
            else: fn_bad.append((k,fn))
            u=str(e.get("uri") or ""); b=os.path.basename(u.rstrip("/"))
            if u and b not in files and not u.rstrip("/").endswith("photos") and u not in (".","./"): uri_bad.append(u[-30:])
            dd=e.get("dependencies") or []
            if isinstance(dd,dict): dd=[dict(v,pe=kk) for kk,v in dd.items() if isinstance(v,dict)]
            for x in dd:
                if isinstance(x,dict):
                    deps+=1; depfields|=set(x.keys()); ifd.add(x.get("ifd") or x.get("direction"))
                    if x.get("pe") not in top: badpe.append(x.get("pe"))
        roles={}
        for k in keys: roles.setdefault(top[k].get("role"),[]).append(k)
        print(" run",i,meta,"| opened",photos,"| calls",writes)
        print("    elements",len(keys),"| dependencies",deps,"fields",sorted(depfields),"ifd",sorted(str(x) for x in ifd),"| pe not in map:",badpe[:3])
        print("    functional_name ok",fn_ok,"of",len(keys),"bad:",fn_bad[:3],"| uri not real:",uri_bad[:3])
        for ro in ("AUE","DE","SE","NE","CQU","UD","DD"):
            if ro in roles: print("     ",ro,roles[ro])
        other={k:v for k,v in roles.items() if k not in ("AUE","DE","SE","NE","CQU","UD","DD")}
        if other: print("      other roles:",other)
