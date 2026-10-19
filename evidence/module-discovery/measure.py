"""Measure MCP manifests against the source on PYTHONPATH.

Run with a fresh METAFORM_HOME and one output JSON path; no models are called.
For comparison, run separately against each revision with equivalent fresh homes.
"""
import json
import os
import sys
from pathlib import Path

from metaform.cli import main

folder=Path(os.environ['METAFORM_HOME']).parent/'project'
folder.mkdir(parents=True,exist_ok=True)
assert main(['add','project','probe',str(folder)]) == 0
for name in ('dispatch','orchestration'):
    assert main(['enable',name]) == 0
from metaform.modules.mcp import server

out={}
for role in ('worker','system','person'):
    os.environ['METAFORM_ROLE']='' if role=='person' else role
    available=server.listing(folder)
    for scope in ('session','stateless'):
        names=server.listed_names(folder, f'measure-{role}' if scope=='session' else None)
        tools=[]
        for name in names:
            if name=='metaform_catalog':
                tools.append({'name':name,'description':'','inputSchema':server.catalog_schema(folder,scope=='stateless')})
            else:
                tool=available[name]
                tools.append({'name':name,'description':tool.description,'inputSchema':tool.schema()})
        out[f'{role}_{scope}']={'tools':len(tools),'manifest_bytes':len(json.dumps(tools,ensure_ascii=False).encode())}
Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+'\n')
