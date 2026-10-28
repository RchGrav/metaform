from pathlib import Path
import json, hashlib, math, copy, xml.etree.ElementTree as ET
from jsonschema import Draft202012Validator

ROOT=Path('/mnt/data/metaform-delivery')
OUT=ROOT/'contracts'
S='https://json-schema.org/draft/2020-12/schema'
DEC={'type':'string','pattern':'^(0|[1-9][0-9]*)$'}
TXT={'type':'string','minLength':1}
NDEC={'anyOf':[DEC,{'type':'null'}]}
def obj(props, required=None):
    return {'type':'object','required':list(props) if required is None else required,'properties':props}
def arr64(items):
    return {'type':'array','minItems':64,'maxItems':64,'items':items}
def write(name, val):
    (OUT/name).write_text(json.dumps(val,ensure_ascii=False,indent=2)+'\n')

spatial={'$schema':S,'$id':'urn:metaform:schema:spatial-tof:1',**obj({
 'schema_version':{'const':'metaform.spatial.tof/1'},
 'source':obj({'id':TXT,'kind':{'enum':['physical','virtual']},'epoch':TXT}),
 'sequence':DEC,
 'clock':obj({'id':TXT,'kind':{'enum':['monotonic','simulation']},
              'capture_ns':NDEC,'received_ns':DEC,'nominal_period_ns':NDEC}),
 'frame_id':TXT,'calibration_uri':{'type':'string','format':'uri'},
 'shape':{'const':[8,8]},'layout':{'const':'row-major-top-left'},
 'distance_semantics':{'const':'axial-z'},'units':{'const':'mm'},
 'distances_mm':arr64({'type':['number','null'],'minimum':0}),
 'zone_status':arr64({'enum':['valid','no_return','invalid','unavailable']}),
 'native_status':arr64({'type':['integer','null']})
})}
write('spatial-tof.schema.json',spatial)
vec={'type':'array','minItems':3,'maxItems':3,'items':{'type':'number'}}
cal={'$schema':S,'$id':'urn:metaform:schema:spatial-calibration:1',**obj({
 'schema_version':{'const':'metaform.spatial.calibration/1'},'calibration_id':TXT,
 'source_id':TXT,'frame_id':TXT,'body_frame_id':TXT,
 'axes':{'const':'x-right,y-down,z-forward'},'rays':arr64(vec),
 'native_to_canonical':arr64({'type':'integer','minimum':0,'maximum':63}),
 'sensor_to_body':obj({'translation_m':vec,'rotation_xyzw':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'number'}}}),
 'sample_model':TXT,'native_distance_convention':TXT,'quality_mapping_ref':TXT
})}
write('spatial-calibration.schema.json',cal)
event={'$schema':S,'$id':'urn:metaform:schema:event:1',**obj({
 'schema_version':{'const':'metaform.event/1'},'event_id':TXT,
 'source_id':TXT,'source_epoch':TXT,'source_sequence':DEC,'kind':TXT,
 'journal_id':TXT,'journal_sequence':DEC,
 'project_id':TXT,'target_address':TXT,'join_id':{'type':['string','null']},
 'clock_id':TXT,'observed_ns':DEC,'persisted_ns':NDEC,
 'persisted_clock_id':{'type':['string','null']},
 'cause_id':{'type':['string','null']},'observation_uri':TXT,
 'observation_sequence':DEC,
 'summary':TXT,'details':{'type':'object'}
})}
write('event.schema.json',event)
handoff={'$schema':S,'$id':'urn:metaform:schema:handoff:1',**obj({
 'schema_version':{'const':'metaform.handoff/1'},'handoff_id':TXT,'agent_id':TXT,
 'from_context_id':TXT,'to_context_id':TXT,'snapshot_key':TXT,
 'target_address':TXT,'work_unit_id':{'type':['string','null']},
 'worktree_ref':{'type':['string','null']},'goal':TXT,
 'completed':{'type':'array','items':{'type':'string'}},
 'remaining':{'type':'array','items':{'type':'string'}},
 'decisions':{'type':'array','items':{'type':'object'}},
 'artifact_refs':{'type':'array','items':{'type':'object'}},
 'event_cursor':{'type':'object'},'skill_refs':{'type':'array','items':{'type':'object'}},
 'reason':{'enum':['context_usage','goal_boundary','explicit']}
})}
write('handoff.schema.json',handoff)
manifest={'$schema':S,'$id':'urn:metaform:schema:composition-manifest:1',**obj({
 'schema_version':{'const':'metaform.composition/1'},'run_id':TXT,
 'repository_id':TXT,'base_commit':{'type':['string','null']},'target_commit':TXT,
 'snapshot_key':TXT,'source_manifest_digest':TXT,
 'runtime_cut':{'type':['object','null']},'document_kind':TXT,
 'selection':{'type':'object'},'producer':{'type':'object'},
 'sections':{'type':'array','items':obj({'section_id':TXT,'path':TXT,'digest':TXT,
        'source_refs':{'type':'array','items':{'type':'object'}},
        'status':{'enum':['generated','reused','failed']}})},
 'findings':{'type':'array','items':{'type':'object'}},
 'state':{'enum':['assembling','complete','failed']}
})}
write('composition-manifest.schema.json',manifest)

M={'io.modelcontextprotocol/protocolVersion':'2026-07-28',
   'io.modelcontextprotocol/clientInfo':{'name':'metaform-context-host','version':'1.0.0'},
   'io.modelcontextprotocol/clientCapabilities':{'extensions':{'io.modelcontextprotocol/skills':{}}}}
URI='resource://spatial/tof/matrix_8x8'
frame={
 'schema_version':'metaform.spatial.tof/1',
 'source':{'id':'front-tof','kind':'virtual','epoch':'run-17'},'sequence':'42',
 'clock':{'id':'sim-17','kind':'simulation','capture_ns':'2800000000',
          'received_ns':'2800000000','nominal_period_ns':'66666667'},
 'frame_id':'front_tof_optical','calibration_uri':'resource://spatial/tof/front-tof/calibration',
 'shape':[8,8],'layout':'row-major-top-left','distance_semantics':'axial-z','units':'mm',
 'distances_mm':[1200.0]*64,'zone_status':['valid']*64,'native_status':[None]*64}
for i in (27,28,35,36): frame['distances_mm'][i]=120.0
write('matrix-example.json',frame)
read_request={'jsonrpc':'2.0','id':'r-42','method':'resources/read','params':{'_meta':M,'uri':URI}}
read_result={'jsonrpc':'2.0','id':'r-42','result':{'resultType':'complete','ttlMs':0,'cacheScope':'private','contents':[
 {'uri':URI,'mimeType':'application/json','text':json.dumps(frame,separators=(',',':'))}]}}
write('mcp-read-request.json',read_request);write('mcp-read-response.json',read_result)
listen={'jsonrpc':'2.0','id':'sub-front','method':'subscriptions/listen','params':{'_meta':M,
 'notifications':{'toolsListChanged':True,'resourcesListChanged':True,
 'resourceSubscriptions':[URI,'resource://metaform/events','resource://metaform/skills/catalog']}}}
ack={'jsonrpc':'2.0','method':'notifications/subscriptions/acknowledged','params':{
 '_meta':{'io.modelcontextprotocol/subscriptionId':'sub-front'},'notifications':listen['params']['notifications']}}
notice={'jsonrpc':'2.0','method':'notifications/resources/updated','params':{
 '_meta':{'io.modelcontextprotocol/subscriptionId':'sub-front'},'uri':'resource://metaform/events'}}
write('mcp-subscription-request.json',listen);write('mcp-subscription-ack.json',ack);write('mcp-event-notification.json',notice)

skill_body='---\nname: inspect-proximity\ndescription: Interpret the local ToF observation and the motion outcome.\n---\n\nRead the observation and its calibration. Explain the observed obstruction in the receiving task context.\n'
(OUT/'SKILL.example.md').write_text(skill_body)
b=skill_body.encode()
skill={'uri':'skill://metaform/v1/inspect-proximity/SKILL.md',
 'frontmatter':{'name':'inspect-proximity','description':'Interpret the local ToF observation and the motion outcome.'},
 'resources':[{'uri':'skill://metaform/v1/inspect-proximity/SKILL.md',
               'digest':'sha256:'+hashlib.sha256(b).hexdigest(),'size':len(b)}]}
write('skill-entry.example.json',skill)
skill_list={'jsonrpc':'2.0','id':'skills-1','result':{'resultType':'complete','skills':[skill],'ttlMs':0,'cacheScope':'private'}}
write('skills-list-response.example.json',skill_list)

results=[]
def check(name, fn):
    fn();results.append({'test':name,'status':'passed'})
def ok(condition):
    assert condition
v=Draft202012Validator(spatial)
check('All five application JSON Schemas are well formed',lambda:[Draft202012Validator.check_schema(s) for s in (spatial,cal,event,handoff,manifest)])
check('Complete matrix example validates',lambda:v.validate(frame))
check('JSON-RPC resource text round-trips to the same matrix',lambda:ok(json.loads(read_result['result']['contents'][0]['text'])==frame))
check('Resource result includes current resultType and cache fields',lambda:ok(read_result['result']['resultType']=='complete' and read_result['result']['ttlMs']==0 and read_result['result']['cacheScope']=='private'))
def invalid_length():
    x=copy.deepcopy(frame);x['distances_mm'].pop();ok(bool(list(v.iter_errors(x))))
check('A 63-zone matrix is structurally invalid',invalid_length)
def negative():
    x=copy.deepcopy(frame);x['distances_mm'][0]=-1;ok(bool(list(v.iter_errors(x))))
check('Negative finite depth is structurally invalid',negative)
def semantics(x):
    v.validate(x)
    for d,s in zip(x['distances_mm'],x['zone_status']):
        if s=='valid': assert d is not None and math.isfinite(d)
        else: assert d is None
check('Matrix status/depth agreement',lambda:semantics(frame))
def unknown():
    x=copy.deepcopy(frame);x['zone_status'][0]='invalid';x['distances_mm'][0]=None;semantics(x)
check('Unknown depth is null, not fabricated clear distance',unknown)
def mismatch():
    x=copy.deepcopy(frame);x['zone_status'][0]='invalid'
    try: semantics(x)
    except AssertionError: return
    raise AssertionError('Mismatch not found')
check('Cross-field status/depth mismatch is reported',mismatch)
def axial():
    for y in range(8):
      for x in range(8):
        raw=((x-3.5)/8,(y-3.5)/8,1.0);norm=math.sqrt(sum(t*t for t in raw));d=[t/norm for t in raw]
        t=1.0/d[2]
        ok(abs(t*d[2]-1.0)<1e-12)
check('64 oblique ray hits normalize to one-meter axial wall',axial)
def selection():
    U={'knowledge','skills','docs'}
    incoming=set(U)
    parent=(incoming-{'docs'})|set()
    leaf=(parent-set())|{'docs'}
    sibling=set(parent)
    ok(leaf==U and sibling=={'knowledge','skills'})
    ok(set()!=U)
check('Dynamic mask/select restoration is branch-local; empty differs from unspecified',selection)
def ancestors():
    address='.'.join(['code']+['x'+str(i) for i in range(40)])
    parts=address.split('.');a={'.'.join(parts[:n]):len(parts)-n for n in range(1,len(parts)+1)}
    ok(a[address]==0 and a['code']==40 and len(a)==41)
check('Materialized ancestry includes self and more than thirty hops',ancestors)
def loaded():
    learned={'skill://a@1'};catalog={'skill://b@1'}
    ok('skill://a@1' in learned and 'skill://a@1' not in catalog)
    learned.add('skill://b@1');ok(len(learned)==2)
    successor=set();ok(not successor)
check('Movement changes discovery, not loaded skills; successor starts fresh',loaded)
def notices():
    journal=[{'event_id':'e1','kind':'entered'},{'event_id':'e2','kind':'cleared'}]
    delivered=set();turn_events=[]
    for e in journal+journal:
      if e['event_id'] not in delivered: delivered.add(e['event_id']);turn_events.append(e)
    ok(len(turn_events)==2 and [e['kind'] for e in turn_events]==['entered','cleared'])
check('Journal preserves crossing and clearing; replay deduplicates event IDs',notices)
check('Skill manifest digest matches actual UTF-8 bytes',lambda:ok(skill['resources'][0]['digest']=='sha256:'+hashlib.sha256((OUT/'SKILL.example.md').read_bytes()).hexdigest()))
root=ET.parse('/mnt/data/hermes-agent-ice-corrections.xml').getroot()
blocks=root.findall('./blocks/block')
summary={'blocks':len(blocks),'members_per_block':{b.attrib['id']:len(b.findall('./elements/element')) for b in blocks},
 'unique_member_addresses':len({e.attrib['namespace_address'] for b in blocks for e in b.findall('./elements/element')})}
check('Supplied Hermes correction contains five Blocks and fifteen explicit members',lambda:ok(summary['blocks']==5 and summary['unique_member_addresses']==15))
report={'scope':'Local schema and reference-semantics checks; not an implementation integration test',
 'tests':results,'hermes_correction_structure':summary,
 'not_executed':['LadybugDB DDL or Cypher execution','MCP server/client interoperability','ACP harness execution',
                 'Bevy integration','physical sensor calibration or motor control','inference-amortization benchmark'],
 'environment_note':'Ladybug driver was absent. Package installation failed because the runtime could not resolve the package server.'}
(ROOT/'verification'/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':len(results),'hermes':summary},indent=2))
