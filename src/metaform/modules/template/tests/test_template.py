"""template is hello's shape with nothing in it, BASE-019."""
from __future__ import annotations

import ast
import dataclasses
import importlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('fixture')

MODULES = Path(__file__).parents[2]


def declaration(name):
    return importlib.import_module(f'metaform.modules.{name}')


def literals(name):
    tree = ast.parse((MODULES / name / '__init__.py').read_text(encoding='utf-8'))
    declarations = {'SUPPORTED_OS', 'DEPENDENCIES', 'SHIPS_DISABLED', 'REQUIRES_CHASSIS', 'MODULE'}
    return {target.id for node in tree.body if isinstance(node, ast.Assign) for target in node.targets
            if isinstance(target, ast.Name) and target.id in declarations}


@pytest.mark.req('BASE-019')
def test_template_declares_every_field_hello_declares_with_nothing_in_it(home):
    assert literals('hello') <= literals('template')
    template = declaration('template').MODULE
    assert template.id == 'template'
    assert template.verbs == () and template.subscriptions == ()
    assert template.start is None and template.stop is None and template.status is None
    assert {field.name for field in dataclasses.fields(template)} == \
        {field.name for field in dataclasses.fields(declaration('hello').MODULE)}


@pytest.mark.req('BASE-019')
def test_a_copy_of_template_loads_once_enabled(run, home, module_row):
    import shutil
    shutil.copytree(MODULES / 'template', home / 'modules' / 'mine',
                    ignore=shutil.ignore_patterns('tests', '__pycache__'))
    init = home / 'modules' / 'mine' / '__init__.py'
    init.write_text(init.read_text(encoding='utf-8').replace("id='template'", "id='mine'"), encoding='utf-8')
    assert module_row('mine')[1] == 'off'
    run('enable', 'mine')
    assert module_row('mine')[1] == 'on'


@pytest.mark.req('BASE-035')
@pytest.mark.req('QUAL-016')
def test_template_declares_node_read_empty_and_hello_demonstrates_it(home):
    def keywords(name):
        tree = ast.parse((MODULES / name / '__init__.py').read_text(encoding='utf-8'))
        call = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'MODULE' for target in node.targets))
        return {keyword.arg: keyword.value for keyword in call.keywords}
    written = keywords('template')
    assert isinstance(written.get('node_read'), ast.Constant) and written['node_read'].value is None
    assert 'node_read' in keywords('hello') and declaration('hello').MODULE.node_read is not None
    assert isinstance(written.get('work_read'), ast.Constant) and written['work_read'].value is None
    assert 'work_read' in keywords('hello') and declaration('hello').MODULE.work_read is not None
