"""Package the completed single real-model smoke run; no runtime mutation."""
from pathlib import Path
import collections
import hashlib
import json
import shutil
import subprocess

ROOT = Path('/tmp/metaform-review-live')
REPO = Path('/workspace/scratch/243b683ad142/metaform')
DEST = REPO / 'evidence/gc-orchestration-review/live-model'
DEST.mkdir(parents=True, exist_ok=True)
SOURCE_COMMIT = '03766976928aae6139563cdd9ec7075dd3541d7d'
SOURCE_TREE = 'f8dbc2419e340f98f951fbe1aef57f24975ace71'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip() == SOURCE_COMMIT
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=REPO,text=True).strip() == SOURCE_TREE
filters = collections.Counter()

def clean(value):
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v,dict) and (v.get('kind') == 'agent_thought_chunk' or v.get('type') == 'reasoning'):
                filters['thought_items_omitted'] += 1
                continue
            out.append(clean(v))
        return out
    if isinstance(value, dict):
        out = {}
        for k,v in value.items():
            if k == 'auth' and isinstance(v,dict):
                filters['auth_account_fields_omitted'] += int('account' in v)
                out[k] = {ak:clean(av) for ak,av in v.items() if ak!='account'}
            elif k == 'text' and value.get('kind') == 'state' and isinstance(v,str):
                try:
                    out[k] = json.dumps(clean(json.loads(v)),ensure_ascii=False)
                except ValueError:
                    out[k] = v
            else:
                out[k] = clean(v)
        return out
    return value

def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

runtime = clean(json.loads((ROOT/'runtime-records.json').read_text()))
runtime['filters'] += ['agent_thought_chunk omitted; auth.account also omitted from serialized state lines']
write(DEST/'runtime-records.json',runtime)
for snap in sorted((ROOT/'snapshots').iterdir()):
    for p in snap.glob('*.json'):
        write(DEST/'snapshots'/snap.name/p.name, clean(json.loads(p.read_text())))
for p in (ROOT/'harness').glob('*.json'):
    write(DEST/'harness'/p.name,clean(json.loads(p.read_text())))
shutil.copy2(ROOT/'harness/export.stderr',DEST/'harness/export.stderr')
for name in ('setup_journey.py','snapshot.py','export_harness.py','export_runtime.py','package_evidence.py',
             'ticket-task.txt','ticket.json','setup-commands.jsonl'):
    shutil.copy2(ROOT/name,DEST/name)
for name in ('label_tools.py','test_label_tools.py'):
    (DEST/'result').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'project'/name,DEST/'result'/name)

receipts=runtime['agents']['receipts']
session_map={x['session_id']:x['runner'] for x in runtime['orchestration']['sessions']}
PM='01a14e41-01da-7c92-86f8-0584d4d92209'
session_map[PM]='bd7c23d7095dce93'
actual=[]
for p in sorted((DEST/'harness').glob('01*.json')):
    t=json.loads(p.read_text())['thread']
    texts=[c.get('text','') for turn in t['turns'] for item in turn['items']
           if item['type']=='userMessage' for c in item.get('content',[]) if c.get('type')=='text']
    row={'session_id':t['id'],'runner':session_map[t['id']], 'model':t['model'],
         'model_provider':t['modelProvider'],'turn_count':len(t['turns']),
         'turn_statuses':dict(collections.Counter(x['status'] for x in t['turns'])),
         'components_observed_in_user_inputs':[]}
    for receipt in receipts:
        if receipt['session_id']!=row['runner']:
            continue
        if receipt['name'] in ('orchestration:common','orchestration:gc','orchestration:role_creator',
                              'orchestration:functionality','agents:generated_review_live_label_normalizer',
                              'dispatch:system') or receipt['name'].startswith('dispatch:user-update:'):
            row['components_observed_in_user_inputs'].append({
                'name':receipt['name'],'epoch':receipt['epoch'],
                'actual_version_id':receipt['actual_version_id'],
                'selected_version_id':receipt['selected_version_id'],
                'fingerprint':receipt['fingerprint'],'channel':receipt['channel'],
                'received_at':receipt['at'],
                'exact_text_occurrences':sum(text.count(receipt['component']['text']) for text in texts)})
    actual.append(row)
write(DEST/'recipient-evidence.json',actual)

threads={p.stem:json.loads(p.read_text())['thread'] for p in (DEST/'harness').glob('01*.json')}
pm_messages=[i['text'] for t in threads[PM]['turns'] for i in t['items'] if i['type']=='agentMessage']
(DEST/'pm-response.txt').write_text(pm_messages[-1]+'\n')
commands=[]
for sid,t in threads.items():
    for turn in t['turns']:
        for i in turn['items']:
            if i['type']=='commandExecution':
                commands.append({'session_id':sid,'turn_id':turn['id'],**i})
write(DEST/'model-command-results.json',commands)
capacity=[]
for p in sorted((DEST/'snapshots').iterdir()):
    capacity.append({'snapshot':p.name,**json.loads((p/'capacity.json').read_text())['slots']})
write(DEST/'capacity-observations.json',capacity)
notifications=[r for r in receipts if r['name'].startswith('dispatch:user-update:')]
write(DEST/'pm-notification-receipts.json',notifications)

summary={
 'status':'completed', 'source_candidate':SOURCE_COMMIT,'source_tree':SOURCE_TREE,
 'code_modified_during_journey':False, 'project':'review_live', 'root_ticket':'fcc7915d466e450eac7a45284cf63ddd',
 'model':'gpt-6.1-sol','provider':'openai','reasoning_effort':'low',
 'harness':{'adapter':'@agentclientprotocol/codex-acp','version':'2.2.2','codex_cli':'0.160.1','sdk':'1.9.0',
            'authentication':'normal existing Codex ChatGPT login, verified by official login status',
            'probe_is_separate':True,'actual_thread_export':'harness/manifest.json'},
 'sessions':[{k:v for k,v in x.items() if k!='components_observed_in_user_inputs'} for x in actual],
 'role_request':'faa7e55084e858488121b2dbabeb24df',
 'gc_assignment':'78d96dd251ca55b2abb943084b145a8d',
 'creator_assignment':'51357703485f49feae0338c96d5c21dd',
 'specialist_assignment':'d6b63545b4dc47e48e38424fea95a854',
 'generated_role':'metaform://role/label_normalizer',
 'generated_prompt':'agents:generated_review_live_label_normalizer',
 'generated_version':'27355977ddd54ff4b210b9aac6ca367e',
 'assessment_assignments':['a04354b70c9258b2b95169247ce63e74','a2afce9f50295a159b37f19471a1e43b'],
 'outcome':'Root delivered; specialist returned; both independent FQCs passed; PM consumed three actual notifications and reported complete.',
 'smoke_candidate':'label-normalizer-d6b63545',
 'files':[{'path':'result/'+p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((DEST/'result').iterdir())],
 'verification':[
    'Generated specialist ran python -m unittest -v: 11 tests passed, exit 0.',
    'GC independently ran python -m unittest -v: 11 tests passed, exit 0; six direct acceptance checks and exact hashes passed.',
    'FQC1 independently reran 11 tests and hashes; additional 29 Python Unicode whitespace and five idempotence checks passed.',
    'FQC2 independently reran 11 tests and hashes and inspected functional memory and typed API constraints.',
    'PM received three acp_prompt notification receipts at 2026-10-18T09:04:06Z and gave an actual status response.'
 ],
 'capacity':{'project_limit':1,'machine_limit':1,'max_observed_project_used':max(x['used'] for x in capacity),
             'max_observed_machine_used':max(x['machine_used'] for x in capacity),'final':capacity[-1],
             'scope':'Public capacity observations at each retained stage; durable suspend/relaunch transitions and same GC session show capacity-one progress.'},
 'runtime_counts':{m:{k:len(v) for k,v in runtime[m].items()} for m in ('agents','orchestration','memory')},
 'pm_session_stopped':True,'all_managed_sessions_ended':True,
 'observed_limitations':[
    'GC delivery automatically created FQC1. A later real GC orchestration_assess call during completion reconciliation created FQC2; both ran serially and passed.',
    'FQC1 called map_work done before submitting rich check-in. Its terminal assignment retains an empty evidence list; it preserved independent evidence in the root ticket note and actual harness commands.',
    'Two informational FQC pass-result sends to the already-ended GC remain pending. No corrective finding existed to create a corrective launch; PM actually received the results.',
    'The conversational PM attempted assignment check-in and was correctly rejected because it has no work assignment. It still consumed notification context and reported completion to the user.',
    'PM reported stale root waiting check-in, unbuilt condition and 2-of-3 progress counter alongside the authoritative completion/delivery records.',
    'Official Codex thread/read omits the in-flight commissioning MCP item when suspension interrupts its turn. Native Metaform transcript retains its in-progress tool id and suspension notice; durable creator launch/publication and real model continuation establish the transition.',
    'Adapter emitted a goals-feature-disabled notice after cancellation; the session resumed and completed. Original restricted-terminal settings refusal succeeded with identical public CLI command through normal unsandboxed terminal, without identity or store bypass.',
    'This single live journey required no specification adaptation, corrective work, second use of the generated role, peer interruption or context compaction. Broader fake-ACP process/contract evidence remains separate.'
 ],
 'evidence_filtering':dict(filters),
 'evidence_filter_policy':'Filtered operational exports omit reasoning/agent thought items and adapter auth account identity. Actual visible model text, task/role inputs, completed tool calls/results, commands, file edits and runtime identifiers are retained.'
}
write(DEST/'live-journey.json',summary)
prep=json.loads((DEST/'preparation.json').read_text())
prep['journey_status']='completed: GC self-request, commissioning, publication, generated specialist result, independent GC validation, two FQC passes, actual PM notification receipt and response; all managed leases released'
prep['journey_evidence']='live-journey.json'
prep['final_capacity']=capacity[-1]
write(DEST/'preparation.json',prep)
manifest=[]
for p in sorted(DEST.rglob('*')):
    if p.is_file() and p.name!='SHA256SUMS':
        manifest.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(DEST)))
(DEST/'SHA256SUMS').write_text('\n'.join(manifest)+'\n')
print(json.dumps({'status':'frozen','candidate':SOURCE_COMMIT,'files':len(manifest),
                  'destination':str(DEST),'capacity':capacity[-1],
                  'receipt_occurrences':[(x['session_id'],[(c['name'],c['exact_text_occurrences']) for c in x['components_observed_in_user_inputs']]) for x in actual]},indent=2))
