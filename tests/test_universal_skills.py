"""One skill source serves native harnesses, MCP and Axiom calls, BASE-059."""
import json
import re

import pytest
import yaml

from metaform import skills
from metaform.data import prompts
from metaform.errors import Stop

pytestmark = [pytest.mark.req('BASE-059'), pytest.mark.kind('fixture')]


def test_skill_folders_declare_identity_and_separate_discovery_from_access():
    listed = skills.catalog()
    assert len(listed) == 9
    assert {one.name for one in listed if not one.discover} == {'sentinel', 'workflow-evaluator'}
    for one in listed:
        frontmatter = yaml.safe_load(skills.read(one.name, 'SKILL.md').split('---', 2)[1])
        assert frontmatter['name'] == one.name and 1 <= len(one.name) <= 64
        assert 1 <= len(frontmatter['description']) <= 1024
        assert all(isinstance(value, str) for value in frontmatter['metadata'].values())
        assert frontmatter['metadata']['ing.metaform.address'] == one.address
        assert frontmatter['metadata']['ing.metaform.discover'] == str(one.discover).lower()
        assert one.folder.name == one.name
        assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', one.name)
        assert one.address == f'logic.skill.{one.name}'
        loaded = skills.load(one.address)
        assert loaded == skills.load(one.name)
        assert loaded['procedure'].startswith('#! AXIOM/2.0')
        assert 'references/procedure.axiom' in loaded['files']
        assert set(loaded['libs']) == set(one.requires)
        assert loaded['version'] and loaded['tier']
    assert {one['name'] for one in skills.listing(discoverable=True)} == {
        one.name for one in listed if one.discover}
    assert skills.load('workflow_evaluator')['address'] == 'logic.skill.workflow-evaluator'


def test_load_and_deployment_use_current_prompt_store_libraries():
    first = skills.load('sentinel')
    held = prompts.prompt_version('metaform-tools')
    changed = held.text + '\nA current library edit.'
    prompts.add_prompt_version('metaform-tools', changed, held.number)
    assert changed in skills.load('logic.skill.sentinel')['libs']['lib_metaform']
    assert first['procedure'] == skills.load('sentinel')['procedure']
    one = next(one for one in skills.catalog() if one.name == 'code-links')
    deployed = skills.deployment_files(one)
    assert changed.encode() in deployed['references/lib_metaform.md']
    assert deployed['references/procedure.axiom'].decode().strip() == skills.load(one.name)['procedure']


@pytest.mark.parametrize('path', ['../SKILL.md', '/SKILL.md', 'references/../../SKILL.md',
                                 'references\\procedure.axiom', 'missing.md'])
def test_read_refuses_paths_outside_the_skills_files(path):
    with pytest.raises(Stop):
        skills.read('sentinel', path)


def test_read_returns_authored_frontmatter_and_procedure():
    assert 'ing.metaform.discover:' in skills.read('sentinel', 'SKILL.md')
    assert skills.read('sentinel', 'references/procedure.axiom').strip() == skills.load('sentinel')['procedure']
    with pytest.raises(Stop):
        skills.load('logic.skill.sentinel.v2')


def test_axiom_calls_skill_addresses_with_kebab_names_and_keeps_arguments(run, project_folder):
    run('enable', 'workflow')
    result = run('workflow', 'run',
                 '{verdict} := logic.skill.workflow-evaluator(Result="logic.skill.code-links()", Criteria="works")',
                 '--json', cwd=project_folder)
    called = json.loads(result.stdout)
    assert called['address'] == 'logic.skill.workflow-evaluator'
    assert called['arguments']['Result'] == 'logic.skill.code-links()'
    assert called['logic']['content'] == skills.load(called['address'])['procedure']
    assert set(called['libs']) == {'lib_axiom', 'lib_metaform', 'lib_workflow'}
    assert called['this']['address'] == called['address']
    completed = run('workflow', 'complete', 'RETURN TRUE', f'run={called["run"]}', '--json', cwd=project_folder)
    assert json.loads(completed.stdout)['variables']['verdict'] is True
