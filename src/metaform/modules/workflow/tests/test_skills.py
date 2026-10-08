"""The workflow agent's libs and skills are served from prompts.xml and the prompt store, MCP-034."""
import asyncio
import json
import re

import pytest

from metaform import nonce, prompt_files
from metaform.data import prompts
from metaform.modules.mcp.server import enter
from metaform.modules.workflow import MODULE, PACKAGE, SKILLS, _about, executor
from metaform.modules.workflow.binding import Logic
from metaform.modules.workflow.element import ElementValue

pytestmark = [pytest.mark.req('MCP-034'), pytest.mark.kind('fixture')]


@pytest.fixture(autouse=True)
def enabled_workflow(run):
    run('enable', 'workflow')


def read(run, folder, *words):
    return json.loads(run(*words, '--json', cwd=folder).stdout)


def test_lib_serves_the_newest_stored_shared_section(run, project_folder):
    served = run('workflow', 'lib', 'lib_metaform', cwd=project_folder).stdout
    stored = prompts.prompt_version('metaform-tools')
    assert stored.text in served and 'metaform workflow submit' in served
    assert '<<TO FILL:' not in served, 'no tool is left as a placeholder; the section only states the rule for one'
    edited = stored.text + '\nAn edit saved in the prompt store.'
    prompts.add_prompt_version('metaform-tools', edited, stored.number)
    assert edited in run('workflow', 'lib', 'lib_metaform', cwd=project_folder).stdout


def test_skills_list_the_libs_their_requires_line_names(run, project_folder):
    listed = {one['name']: one['requires'] for one in read(run, project_folder, 'workflow', 'skills')}
    assert listed == {
        'scan': [],
        'write_workflow': ['lib_axiom', 'lib_metaform', 'lib_workflow'],
        'import_workflow': ['lib_axiom', 'lib_metaform', 'lib_workflow'],
        'workflow_efficiency': ['lib_axiom', 'lib_metaform', 'lib_workflow', 'lib_quality'],
        'prompt_efficiency': ['lib_axiom', 'lib_quality'],
        'workflow_builder': ['lib_axiom', 'lib_metaform', 'lib_workflow'],
        'workflow_evaluator': ['lib_axiom', 'lib_metaform', 'lib_workflow'],
        'sentinel': ['lib_metaform'],
    }


def test_skills_list_what_each_skill_header_says(run, project_folder):
    for one in read(run, project_folder, 'workflow', 'skills'):
        flat = ' '.join(prompt_files.required(PACKAGE, one['name']).replace('#', ' ').split())
        assert one['about'] and f"skill: {one['name']} · {one['about']} requires:" in flat


def test_assignment_serves_each_lib_once_then_skill_then_input_and_closes(run, project_folder):
    markers = {one['name']: one['marker'] for one in read(run, project_folder, 'workflow', 'libs')}
    given = 'Write a workflow that reviews the kitchen timer.'
    word = read(run, project_folder, 'workflow', 'assign', 'write_workflow', f'input={given}')['nonce']
    served = run(word, cwd=project_folder).stdout
    skill = prompt_files.required(PACKAGE, 'write_workflow')
    head = served[:served.index(skill)]
    places = [head.index(markers[name]) for name in ('lib_axiom', 'lib_metaform', 'lib_workflow')]
    assert places == sorted(places)
    assert all(head.count(markers[name]) == 1 for name in ('lib_axiom', 'lib_metaform', 'lib_workflow'))
    assert markers['lib_quality'] not in head
    assert served.index(given) > served.index(skill)

    failed, blocks = asyncio.run(enter(project_folder, 'workflow', {'command': 'resume', 'arguments': {'nonce': word}}))
    assert not failed and skill in blocks[-1] and given in blocks[-1]

    run(word, 'complete', cwd=project_folder)
    gone = run(word, cwd=project_folder, ok=False)
    assert gone.returncode != 0 and gone.stderr.strip() == 'Error: Invalid or Unknown Nonce'


def test_complete_on_a_call_without_return_is_refused_with_a_next_step(run, project_folder):
    script = '@STATE_INIT:\n {target} := PARAM\n'
    word = executor.start('{ok} := workflow.quality.code.review(target=this)', {},
                          ElementValue({'address': 'code.timer'}),
                          lambda address, name: (Logic('logic', name, name, script), ElementValue({'address': address})),
                          {'project': 'proj', 'folder': str(project_folder), 'metaform': None, 'layers': []})
    refused = run(word, 'complete', cwd=project_folder, ok=False)
    assert refused.returncode != 0
    assert 'Next: metaform workflow complete "RETURN' in refused.stderr
    assert nonce.read(word).open


def test_each_skill_is_a_slash_command_running_skill():
    commands = [(tag, attributes) for tag, attributes, *_ in prompt_files.commands(PACKAGE)
                if attributes.get('verb') == 'skill']
    assert sorted(attributes['name'] for _, attributes in commands) == sorted(SKILLS)
    assert all(tag == attributes['name'] for tag, attributes in commands)


@pytest.mark.req('MCP-032')
def test_each_skill_command_summary_is_its_skill_header():
    summaries = {attributes['name']: attributes.get('summary') for _, attributes, *_ in prompt_files.commands(PACKAGE)
                 if attributes.get('verb') == 'skill'}
    assert summaries == {name: _about(name) for name in SKILLS}


def test_every_workflow_verb_the_instructions_name_is_a_verb():
    text = prompt_files.required(PACKAGE, 'instructions')
    named = {word for pair in re.findall(r'\bworkflow (?!is active)(\w+)(?: and (\w+))?', text) for word in pair if word}
    assert named and named <= {verb.name for verb in MODULE.verbs}


@pytest.mark.req('BASE-055')
@pytest.mark.parametrize('name', ['workflow_builder', 'workflow_evaluator'])
def test_role_assignment_carries_only_its_role_and_closes(run, project_folder, name):
    given = json.dumps({'request': 'Assess the timer change', 'criteria': 'It preserves the alarm purpose'})
    word = read(run, project_folder, 'workflow', 'assign', name, f'input={given}')['nonce']
    served = run(word, cwd=project_folder).stdout
    own = run('workflow', 'skill', name, cwd=project_folder).stdout.strip()
    other = 'workflow_evaluator' if name == 'workflow_builder' else 'workflow_builder'
    unrelated = run('workflow', 'skill', other, cwd=project_folder).stdout.strip()
    assert own in served and unrelated not in served
    assert given in served
    assert nonce.read(word).value['skill'] == name
    run(word, 'complete', cwd=project_folder)
    assert not nonce.read(word).open


def test_workflow_lib_names_built_transport_without_the_kit_unbuilt_claim(run, project_folder):
    served = run('workflow', 'lib', 'lib_workflow', cwd=project_folder).stdout
    tools = run('workflow', 'lib', 'lib_metaform', cwd=project_folder).stdout
    assert 'not built' not in served.lower()
    for verb in ('list', 'submit', 'add_logic', 'export', 'run', 'call', 'handoff', 'parallel', 'complete', 'fail'):
        assert f'metaform workflow {verb}' in tools
