"""CLI and MCP use the same stored workflow and run-record call transport."""
import json
import re

import pytest

from metaform.data import Store
from metaform.modules.mcp.server import run_tool
from metaform.modules.workflow import catalog, runs
from tests.storekit import small_map

pytestmark = [pytest.mark.req('BASE-051'), pytest.mark.req('MCP-030'), pytest.mark.kind('fixture')]


@pytest.fixture(autouse=True)
def enabled_workflow(run):
    run('enable', 'workflow')

ADDRESS = 'prompt.workflow.quality.code'
SCRIPT = '''@STATE_INIT:
 {target} := PARAM
@CONSTRAINT:
 +> Acceptance: the target has been checked.
@CONDITION (DONE):
 ?IF ( TRUE ) -> RETURN TRUE
@ROUTER:
 EXECUTE_PIPELINE( Review )
@EXECUTE_PIPELINE (Review):
 [STEP 1]: RETURN ( TRUE, {target}.address ).
@VERIFY:
 [V1] Was it checked? NO -> RECURSE Review.
'''


def read(run, folder, *words):
    return json.loads(run(*words, '--json', cwd=folder).stdout)


def test_cli_stored_call_fresh_handoff_frozen_text_and_return(run, store, project_folder):
    small_map(store)
    read(run, project_folder, 'workflow', 'submit', ADDRESS, 'procedures', 'name=Code quality')
    read(run, project_folder, 'workflow', 'add_prompt', ADDRESS, 'procedures', 'improve', SCRIPT)
    read(run, project_folder, 'workflow', 'add_prompt', ADDRESS, 'procedures', 'review', SCRIPT)
    started = read(run, project_folder, 'workflow', 'run',
                   '({ok}, {address}) := prompt.workflow.quality.code.improve(target=code.timer.kitchen)')
    word = started['run']
    assert started['arguments']['target']['address'] == 'code.timer.kitchen'
    handed = read(run, project_folder, 'workflow', 'handoff',
                  '({ok}, {address}) := prompt.workflow.quality.code.review(target={target})', f'run={word}')
    child = handed['run']
    assert f'metaform workflow resume run={child} --project proj' in handed['handoff']
    read(run, project_folder, 'workflow', 'add_prompt', ADDRESS, 'procedures', 'review', SCRIPT + '# revised\n')
    elsewhere = project_folder.parent / 'fresh-agent'  # a fresh agent's own folder reaches the run by project
    redeemed = read(run, elsewhere, 'workflow', 'resume', f'run={child}', '--project', 'proj')
    assert redeemed['prompt']['content'] == SCRIPT
    assert 'frames' not in redeemed and 'parent' not in redeemed
    returned = read(run, project_folder, 'workflow', 'complete', 'RETURN (TRUE, {target}.address)', f'run={child}')
    assert returned['resume'] == word
    assert 'variables' not in returned and 'prompt' not in returned
    assert read(run, project_folder, 'workflow', 'resume', f'run={word}')['variables']['address'] == \
        'code.timer.kitchen'
    root = read(run, project_folder, 'workflow', 'complete', 'RETURN ({ok}, {address})', f'run={word}')
    assert root['value'] == [True, 'code.timer.kitchen']
    held = Store('proj', module='workflow')
    assert runs.read(held, word).state == runs.read(held, child).state == 'completed'
    assert runs.read(held, child).value['parent'] == word


def test_mcp_run_id_resumes_and_returns_the_same_call(store, project_folder):
    small_map(store)
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    catalog.submit_prompt(store, ADDRESS, 'procedures', 'review', SCRIPT)
    def invoke(name, args):
        import asyncio
        failed, blocks = asyncio.run(run_tool(project_folder, f'workflow_{name}', args))
        assert not failed, blocks
        return json.loads(blocks[-1])

    started = invoke('run', {'call': '( {ok}, {address} ) := prompt.workflow.quality.code.review(target=this)',
                            'element': 'code.timer.kitchen'})
    redeemed = invoke('resume', {'run': started['run']})
    assert redeemed['arguments']['target']['address'] == 'code.timer.kitchen'
    result = invoke('complete', {'run': started['run'], 'return': 'RETURN (TRUE, {target}.address)'})
    assert result['variables'] == {'ok': True, 'address': 'code.timer.kitchen'}


def test_shared_sections_are_shipped_to_the_prompt_store(run, project_folder):
    run('workflow', 'lib', 'lib_axiom', cwd=project_folder)
    language = run('prompt', 'prompt.skills:axiom-language', '1', cwd=project_folder).stdout
    assert 'The agent reading an Axiom script is its interpreter. There is no other runtime.' in language
    tools = run('prompt', 'prompt.skills:metaform-tools', '1', cwd=project_folder).stdout
    assert 'metaform workflow add_prompt' in tools and '<<TO FILL: record one prompt' not in tools


@pytest.mark.req('LAYER-017')
def test_lexicalize_serves_the_authored_script_with_the_prompt_and_owner_settings(run, project_folder):
    from metaform import prompt_files
    from metaform.modules.workflow import PACKAGE
    text = 'Review the timer and fix what the kitchen display shows.'
    script = prompt_files.required(PACKAGE, 'prompt-lexicalization').strip()
    served = read(run, project_folder, 'workflow', 'lexicalize', text)
    assert served['prompt'] == script
    inputs = served['inputs']
    owner = script.split('OWNER PLACEHOLDERS')[1].split('@CONSTRAINT')[0]
    assert set(inputs) == {'Prompt_Text', *re.findall(r'\{(\w+)\}\s*:=', owner)}
    assert inputs['Prompt_Text'] == text
    assert 'metaform map where' in inputs['MAP_READ']
    assert 'save_prompt' in inputs['PROMPT_STORE'] and 'metaform prompt save' in inputs['PROMPT_STORE']
    assert inputs['UNRESOLVED_POLICY'] == 'keep wording'
    assert inputs['ADDRESS_PLACEMENT'] == 'one block of name -> address'
    run('set', '--lexicalize-unresolved=mark missing', '--lexicalize-addresses=inline after each name',
        cwd=project_folder)
    inputs = read(run, project_folder, 'workflow', 'lexicalize', text)['inputs']
    assert inputs['UNRESOLVED_POLICY'] == 'mark missing'
    assert inputs['ADDRESS_PLACEMENT'] == 'inline after each name'


@pytest.mark.req('LAYER-017')
def test_preprocess_cli_mcp_and_setting_prepare_the_same_context(run, store, project_folder):
    import asyncio

    from metaform.data import Node, prompts
    from metaform.modules.mcp.server import run_tool
    from tests.storekit import PROVENANCE

    small_map(store)
    store.layer('practices', 'test', 'Task knowledge.', mutable=True, hideable=True,
                provenance=PROVENANCE, ready=True)
    store.add_item('practices', Node('element', 'code.timer.kitchen'), 'Timer practice.')
    store.add_item('practices', Node('element', 'code.alarm.audible'), 'Alarm practice.')
    text = 'Review the kitchen timer.\n'
    addresses = ['code.timer.kitchen']
    prepared = read(run, project_folder, 'workflow', 'preprocess', text, json.dumps(addresses))
    assert prepared['prompt'].startswith(text)
    assert 'Timer practice.' in prepared['prompt'] and 'Alarm practice.' not in prepared['prompt']
    assert prepared['scope'] == 'context'
    failed, blocks = asyncio.run(run_tool(project_folder, 'workflow_preprocess', {'text': text, 'addresses': addresses}))
    assert not failed, blocks
    assert json.loads(blocks[-1]) == prepared
    saved = json.loads(run('prompt', 'save', 'prepared-review', prepared['prompt'], '--json',
                          cwd=project_folder).stdout)
    assert prompts.prompt_version('prepared-review').text == prepared['prompt'] == saved['text']
    run('set', '--preprocess-knowledge=whole', cwd=project_folder)
    whole = read(run, project_folder, 'workflow', 'preprocess', text, json.dumps(addresses))
    assert whole['scope'] == 'whole' and 'Alarm practice.' in whole['prompt']
    assert whole['prompt'].endswith('kitchen timer -> code.timer.kitchen')


def test_cli_portable_file_runs_on_another_project(run, store, project_folder, tmp_path):
    small_map(store)
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    catalog.submit_prompt(store, ADDRESS, 'procedures', 'review', SCRIPT)
    path = tmp_path / 'code quality.metaform'
    read(run, project_folder, 'workflow', 'export', ADDRESS, 'procedures', f'file={path}')
    other_folder = tmp_path / 'other'
    other_folder.mkdir()
    run('add', 'project', 'other', str(other_folder), cwd=project_folder)
    other = Store('other')
    small_map(other)
    read(run, other_folder, 'workflow', 'import', str(path))
    started = read(run, other_folder, 'workflow', 'run',
                   'prompt.workflow.quality.code.review(target=this)', 'element=code.timer.kitchen')
    assert started['prompt']['content'] == SCRIPT
    assert started['context']['project'] == 'other'


def test_selected_knowledge_reaches_arguments_and_still_obeys_masks(run, store, project_folder):
    from metaform.data import Node
    layer, _, _ = small_map(store)
    catalog.ensure_layer(store, 'standards')
    store.add_item('standards', Node('element', 'code.timer.kitchen'), 'Keep time precisely.')
    catalog.submit_workflow(store, ADDRESS, 'procedures', layers=('standards',))
    catalog.submit_prompt(store, ADDRESS, 'procedures', 'review', SCRIPT)
    arguments = ('workflow', 'run', 'prompt.workflow.quality.code.review(target=this)',
                 'element=code.timer.kitchen', '--layers', f'{layer.name},procedures')
    visible = read(run, project_folder, *arguments)
    assert visible['arguments']['target']['items']['standards'][0]['value'] == 'Keep time precisely.'
    store.mask('code.timer', 'standards')
    masked = read(run, project_folder, *arguments)
    assert 'standards' not in masked['arguments']['target']['items']
    store.mask('prompt.workflow', 'procedures')
    failed = run(*arguments, cwd=project_folder, ok=False)
    assert failed.returncode != 0 and 'KeyError' in failed.stderr


def test_existing_prompt_versions_are_kept_and_libs_name_the_shipped_section_version(run, home, project_folder):
    from metaform.data import prompts
    old = prompts.add_prompt('prompt.skills:metaform-tools', 'text', 'old tool instructions', origin='shipped')
    served = run('workflow', 'lib', 'lib_metaform', cwd=project_folder).stdout
    latest = prompts.prompt_version('prompt.skills:metaform-tools')
    assert latest.number == 2 and 'metaform workflow add_prompt' in latest.text
    assert 'metaform-tools · version 2' in served and latest.text in served
    assert prompts.prompt_version('prompt.skills:metaform-tools', 1).text == old.text


def test_run_calls_remain_bound_when_active_metaform_changes(store, project_folder):
    from metaform.module import Context
    from metaform.modules.workflow import call, complete, run
    from metaform.modules.workflow.executor import view
    small_map(store)
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    catalog.submit_prompt(store, ADDRESS, 'procedures', 'improve', SCRIPT)
    catalog.submit_prompt(store, ADDRESS, 'procedures', 'review', SCRIPT)
    initial = run(Context('workflow', project_folder, store=store, nouns={
        'call': 'prompt.workflow.quality.code.improve(target=this)', 'element': 'code.timer.kitchen'}))
    old_metaform = initial['context']['metaform']
    store.add_base('other')
    bound = Store('proj', module='workflow', base=old_metaform)
    catalog.ensure_layer(bound, 'standards')
    catalog.submit_workflow(bound, ADDRESS, 'procedures', layers=('standards',))
    context = Context('workflow', project_folder, nouns={
        'run': initial['run'], 'call': '{ok} := prompt.workflow.quality.code.review(target={target})'})
    # Selecting accompanying knowledge must retain the original metaform.
    context.store = Store('proj', module='workflow')
    child = call(context)
    assert child['context']['metaform'] == old_metaform
    assert child['prompt']['content'] == SCRIPT
    context.nouns = {'run': initial['run'], 'return': 'RETURN TRUE'}
    complete(context)
    assert view(Store('proj', module='workflow'), initial['run'])['context']['metaform'] == old_metaform


def test_workflow_ships_and_runs_in_direct_wheel_without_other_feature_modules(run, home, project_folder):
    import os
    import subprocess
    import sys
    import zipfile
    from pathlib import Path
    catalog.submit_workflow(Store('proj'), ADDRESS, 'procedures')
    catalog.submit_prompt(Store('proj'), ADDRESS, 'procedures', 'review', SCRIPT)
    for module in ('map', 'mcp', 'memory', 'intake', 'web'):
        run('disable', module)
    built = run('build').stdout
    wheel = Path(next(line.split(':', 1)[1].strip() for line in built.splitlines() if line.startswith('Wheel:')))
    with zipfile.ZipFile(wheel) as archive:
        assert 'metaform/modules/workflow/resources/prompts.xml' in archive.namelist()
        assert not any('/workflow/tests/' in name for name in archive.namelist())
    result = subprocess.run([sys.executable, '-I', str(wheel), 'workflow', 'skill', 'write_workflow'],
                            cwd=project_folder, env={**os.environ, 'METAFORM_HOME': str(home)},
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert 'name=write_workflow' in result.stdout
    started = subprocess.run([sys.executable, '-I', str(wheel), 'workflow', 'run',
                              'prompt.workflow.quality.code.review(target=this)', f'element={ADDRESS}', '--json'],
                             cwd=project_folder, env={**os.environ, 'METAFORM_HOME': str(home)},
                             capture_output=True, text=True, check=False)
    assert started.returncode == 0, started.stderr
    assert json.loads(started.stdout)['arguments']['target']['address'] == ADDRESS


@pytest.mark.req('CLI-009')
def test_a_call_or_export_that_does_not_bind_is_the_callers_error_with_its_next_step(run, store, project_folder):
    import asyncio
    small_map(store)
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    catalog.submit_prompt(store, ADDRESS, 'procedures', 'review', SCRIPT)
    for arguments in (('workflow', 'run', f'{ADDRESS}.review()'), ('workflow', 'run', f'{ADDRESS}.absent(target=1)'),
                      ('workflow', 'export', ADDRESS, 'nolayer')):
        failed = run(*arguments, cwd=project_folder, ok=False)
        assert failed.returncode == 2, failed.stderr
        assert failed.stderr.count('\nNext: ') == 1 and 'StopIteration' not in failed.stderr
    failed, blocks = asyncio.run(run_tool(project_folder, 'workflow_run', {'call': f'{ADDRESS}.review()'}))
    assert failed and 'Missing required parameter: target' in blocks[-1] and 'feedback' not in blocks[-1]
