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
