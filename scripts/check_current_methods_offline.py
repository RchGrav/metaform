"""Offline unit harness; dependencies at service boundaries are controlled substitutes."""
import hashlib
import importlib
import importlib.resources
import importlib.util
import sys
import types
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1] / 'src'


def module(name, **attributes):
    value = types.ModuleType(name)
    value.__dict__.update(attributes)
    sys.modules[name] = value
    return value


def package(name, path):
    value = module(name)
    value.__path__ = [str(path)]
    value.__spec__ = importlib.util.spec_from_loader(name, loader=None, is_package=True)
    return value


class Stop(Exception):
    def __init__(self, message, next_step=''):
        self.next_step = next_step
        super().__init__(message)


package('metaform', root / 'metaform')
package('metaform.modules', root / 'metaform/modules')
package('metaform.modules.orchestration', root / 'metaform/modules/orchestration')
module('metaform.errors', Stop=Stop)
module('metaform.home', home=lambda: Path('/tmp'), mkdir_private=lambda p: None, file_lock=lambda p: None)
prompts = module('metaform.data.prompts', prompt_version=lambda name: None)
module('metaform.data', prompts=prompts)
module('metaform.prompt_files',
       address=lambda owner, name: f'prompt.{owner}:{name}' if owner != 'skill' else f'prompt.skill.{name}',
       resolve=lambda name: {}, resolve_text=lambda name, body: {'name': name, 'text': body},
       component=lambda name, text: {'name': name, 'text': text},
       rendered=lambda body: body)
module('metaform.module', Context=object, Stop=Stop, agent_context_collecting=lambda: False,
       prepare_agent_context=lambda *args, **kwargs: {}, record_agent_context=lambda *args, **kwargs: {},
       held_role=lambda ctx: None, provided=lambda *args: [])
module('metaform.modules.orchestration.state',
       SERVICE=types.SimpleNamespace(assignment=lambda ctx: None, runtime=lambda *args: {}),
       service=lambda *args: None, own=lambda ctx: None,
       fingerprint=lambda text: hashlib.sha256(text.encode()).hexdigest())
module('metaform.modules.orchestration.runtime', TASKS={'coding': 'Implement'}, choose=lambda *a, **k: None,
       rejection_reason=lambda *a: None, strengths_of=lambda *a: {})
original_files = importlib.resources.files
importlib.resources.files = lambda name: root / 'metaform' if name == 'metaform' else original_files(name)
try:
    importlib.import_module('metaform.skills')
finally:
    importlib.resources.files = original_files
raise SystemExit(pytest.main([
    '--noconftest', '-q', '-o', 'addopts=', '-o', 'markers=kind(value): fixture classification',
    str(root / 'metaform/modules/orchestration/tests/test_current_methods.py'), *sys.argv[1:]]))
