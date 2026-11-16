"""MCP-024, the first working test: installer, instructions and delegation end to end, then shared memory.

Automated with a temporary Metaform home and user home, fake `claude` and
`codex` executables that record their arguments, a real Cursor config file,
the real `uv` and `uvx`, and the probe client of MCP-017 as the scripted host.
It needs network access or a warm uv cache for uvx to prepare the server.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('MCP-024')]

ROOT = Path(__file__).parents[1]
SPEC = ROOT / 'src' / 'metaform' / 'modules' / 'intake' / 'resources' / 'intake.xml'  # the served intake
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))
TOOLS = {'intake_prompt', 'intake_start', 'intake_element', 'intake_purpose', 'intake_remove',
         'intake_show', 'intake_finish', 'memory_create_entities', 'memory_open_nodes', 'map_select', 'map_mask',
         'map_clear', 'map_node', 'map_layers', 'map_tag', 'map_untag', 'map_knowledge', 'map_work', 'metaform_feedback',
         'metaform_list_reports', 'metaform_read_report', 'metaform_set'}
OWN = ('feedback', 'list_reports', 'read_report', 'set')  # the chassis's own commands, each the tool metaform_<name>


def asked(host, name, arguments, *, limit):
    """Run a command as an agent does, MCP-003: the tool named for it, with its arguments."""
    return host.call(f'metaform_{name}' if name in OWN else name, arguments, limit=limit)


def commands(host):
    """Every command the server offers: the tools it lists, one for each command."""
    return {tool['name'] for tool in host.request('tools/list', {}, deadline=_deadline())['tools']}


REPORT = 'The alarm pin is never released after stop.'
FEEDBACK = 'The join elements field repeats the provider address.'
CURSOR = {'mcpServers': {'other': {'command': 'other-server', 'args': ['--port', '1']}}}
LIMIT = 180.0


def texts(result):
    return [block['text'] for block in result.get('content', []) if block.get('type') == 'text']


def last_json(result):
    return json.loads(texts(result)[-1])


def memory_values(view):
    """The observations of the memories a node read shows, LAYER-013."""
    return [text for entity in view.get('memory', {}).get('entities', []) for text in entity['observations']]


def _deadline():
    import time
    return time.monotonic() + LIMIT
