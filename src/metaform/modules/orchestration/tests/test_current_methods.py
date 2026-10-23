"""Current-context procedure and expertise behavior with controlled service boundaries.

These are unit contracts, not native model or ACP process measurements.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metaform import skills
from metaform.module import Stop
from metaform.modules.orchestration import facilitation, methods

pytestmark = pytest.mark.kind('fixture')


def component(name: str, text: str, version: str = 'v1') -> dict[str, Any]:
    return {'name': name, 'text': text, 'actual_version_id': version, 'selected_version_id': version,
            'source': {'kind': 'test'}}


@dataclass
class Call:
    folder: Path
    nouns: dict[str, Any] = field(default_factory=dict[str, Any])
    project: str = 'project'
    session: str | None = 'informed'
    surface: str = 'mcp'
    queued: list[Any] = field(default_factory=list[Any])

    def queue_context(self, components, epoch):
        self.queued.append((copy.deepcopy(components), epoch))


class Delivery:
    """Controlled receipt boundary: preparation does not imply acceptance."""
    def __init__(self):
        self.epoch = 0
        self.accepted = set()

    def prepare(self, folder, session, components, **kwargs):
        due, seen = [], set()
        for one in components:
            digest = hashlib.sha256(one['text'].encode()).hexdigest()
            key = (session, self.epoch, digest)
            if key not in self.accepted and key not in seen:
                due.append(copy.deepcopy(one))
                seen.add(key)
        return {'epoch': self.epoch, 'components': due}

    def record(self, folder, session, components, *, epoch, **kwargs):
        if epoch != self.epoch:
            return
        for one in components:
            self.accepted.add((session, epoch, hashlib.sha256(one['text'].encode()).hexdigest()))


@pytest.fixture
def setup(monkeypatch, tmp_path):
    delivery = Delivery()
    monkeypatch.setattr(methods, 'prepare_agent_context', delivery.prepare)
    monkeypatch.setattr(methods, 'record_agent_context', delivery.record)
    monkeypatch.setattr(methods, 'agent_context_collecting', lambda: False)
    monkeypatch.setattr(methods.prompt_files, 'resolve', lambda name: component(name, 'Scoped method.'))
    monkeypatch.setattr(methods.SERVICE, 'assignment', lambda ctx: None)
    return Call(tmp_path), delivery


def test_preparation_is_not_delivery_and_accepted_content_is_shared(setup):
    ctx, delivery = setup
    body = component('role:one', 'Exact reusable instructions.')
    first = methods.deliver(ctx, [body])
    assert first['instructions'][0]['text'] == body['text']
    assert ctx.queued[0][0][0]['delivered_value'] == body['text']
    assert methods.deliver(ctx, [body])['instructions']
    delivery.record(ctx.folder, ctx.session, ctx.queued[0][0], epoch=0)
    assert methods.deliver(ctx, [body])['instructions'] == []
    assert methods.deliver(ctx, [component('alias', body['text'])])['instructions'] == []
    assert methods.deliver(ctx, [component('role:one', 'Changed instructions.', 'v2')])['instructions']
    delivery.epoch += 1
    assert methods.deliver(ctx, [body])['instructions']


def test_cli_records_complete_return_without_a_model_call(setup):
    ctx, _ = setup
    ctx.surface = 'cli'
    body = component('role:one', 'Read precisely.')
    assert methods.deliver(ctx, [body])['instructions']
    assert methods.deliver(ctx, [body])['instructions'] == []
    assert not ctx.queued


def test_pinned_assignment_retains_its_exact_selected_components(setup, monkeypatch):
    ctx, _ = setup
    pinned = component('prompt.orchestration:planner', 'Pinned wording.', 'pinned-v')
    assignment = {'assignment_id': 'existing', 'authored_role_uri': 'metaform://role/planner',
                  'role_snapshot': {'components': [pinned]}}
    before = copy.deepcopy(assignment)
    monkeypatch.setattr(methods.SERVICE, 'assignment', lambda ctx: assignment)
    monkeypatch.setattr(methods, 'service', lambda *a: pytest.fail('pinned body must not resolve newest source'))
    ctx.nouns = {'name': 'metaform://role/planner', 'task': 'Preserve THIS exception; exactly.'}
    result = methods.apply(ctx)
    assert result['source'] == 'assignment_snapshot'
    assert result['task'] == ctx.nouns['task']
    assert result['instructions'][-1] == pinned
    assert assignment == before


def test_supplementary_method_keeps_shared_pinned_guidance(setup, monkeypatch):
    ctx, _ = setup
    common = component('prompt.orchestration:common', 'Pinned common.', 'old')
    assigned = {'assignment_id': 'work', 'authored_role_uri': 'metaform://role/gc',
                'role_snapshot': {'components': [common]}}
    monkeypatch.setattr(methods.SERVICE, 'assignment', lambda ctx: assigned)
    registry = SimpleNamespace(resolve=lambda *args: {'components': [
        component('prompt.orchestration:common', 'New common.', 'new'), component('reviewer', 'Review method.')]})
    monkeypatch.setattr(methods, 'service', lambda *args: registry)
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    monkeypatch.setenv('METAFORM_AUTHORED_ROLE', 'metaform://role/gc')
    ctx.nouns = {'name': 'metaform://role/reviewer'}
    result = methods.apply(ctx)
    assert [one['text'] for one in result['instructions']] == ['Scoped method.', 'Pinned common.', 'Review method.']
    assert os.environ['METAFORM_ROLE'] == 'worker'
    assert os.environ['METAFORM_AUTHORED_ROLE'] == 'metaform://role/gc'
    assert result['assignment'] == 'work'


def test_selected_skill_components_use_the_same_delivery_boundary(setup, monkeypatch):
    ctx, _ = setup
    monkeypatch.setattr(methods.skills, 'get', lambda name: SimpleNamespace(name='example'))
    monkeypatch.setattr(methods.skills, 'components', lambda name: [component('prompt.skill.example', 'User edit.')])
    ctx.nouns = {'name': 'example'}
    assert methods.apply(ctx)['instructions'][-1]['text'] == 'User edit.'


def test_explicit_role_uri_never_resolves_same_named_skill(setup, monkeypatch):
    ctx, _ = setup
    monkeypatch.setattr(methods.skills, 'get', lambda name: pytest.fail('explicit role is not a native skill'))
    monkeypatch.setattr(methods, 'service', lambda *args: SimpleNamespace(
        resolve=lambda *args: {'components': [component('facilitator', 'Selected Facilitator.')]}))
    ctx.nouns = {'op': 'use', 'role': 'facilitator'}
    assert facilitation.facilitate(ctx)['instructions'][-1]['text'] == 'Selected Facilitator.'


def test_missing_method_surfaces_real_source_problem(setup, monkeypatch):
    ctx, _ = setup
    monkeypatch.setattr(methods, 'service', lambda *args: SimpleNamespace(
        resolve=lambda *args: {'missing': True, 'problems': ['Missing provider.']}))
    ctx.nouns = {'name': 'metaform://role/unavailable'}
    with pytest.raises(Stop, match='Missing provider'):
        methods.apply(ctx)
    assert not ctx.queued


class Registry:
    def __init__(self):
        self.entries = {}
        self.writes = []

    def resolve(self, ctx, name):
        return copy.deepcopy(self.entries.get(name, {'missing': True}))

    def publish(self, ctx, name, purpose, duty, source):
        self.writes.append((name, purpose, duty, source))
        self.entries[name] = {'name': name, 'purpose': purpose, 'uri': f'metaform://role/{name}',
                              'version_id': 'created', 'specialist': True, 'text': duty}
        return self.resolve(ctx, name)

    def specialists(self, ctx):
        return [{'name': name, 'purpose': value['purpose']} for name, value in self.entries.items()]


@pytest.fixture
def registry_setup(setup, monkeypatch):
    ctx, delivery = setup
    registry = Registry()
    monkeypatch.setattr(facilitation, '_registry', lambda ctx: registry)
    monkeypatch.setattr(facilitation, 'held_role', lambda ctx: None)
    monkeypatch.setattr(facilitation.home, 'home', lambda: ctx.folder)
    monkeypatch.setattr(facilitation.home, 'mkdir_private', lambda path: path.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(facilitation.home, 'file_lock', lambda path: contextlib.nullcontext())
    return ctx, registry


def test_expertise_creation_needs_no_creator_assignment_and_reuses_user_edit(registry_setup):
    ctx, registry = registry_setup
    ctx.nouns = {'op': 'publish', 'role': 'domain_expert', 'purpose': 'Domain expertise.', 'duty': 'Exact method.'}
    first = facilitation.facilitate(ctx)
    assert first['source'] == 'created' and first['assignment_changed'] is False
    assert registry.writes[0][3]['caller_session_id'] == 'informed'
    assert registry.writes[0][3]['caller_assignment_id'] is None
    registry.entries['domain_expert']['text'] = 'Subsequent user edit.'
    assert facilitation.facilitate(ctx)['source'] == 'existing'
    assert len(registry.writes) == 1
    assert registry.entries['domain_expert']['text'] == 'Subsequent user edit.'


def test_registry_creation_retains_actual_owner_without_completing_it(registry_setup, monkeypatch):
    ctx, registry = registry_setup
    assignment = {'assignment_id': 'parent', 'state': 'running'}
    monkeypatch.setattr(methods.SERVICE, 'assignment', lambda ctx: assignment)
    ctx.nouns = {'role': 'expert', 'purpose': 'Expertise.', 'duty': 'Reusable method.'}
    facilitation.publish(ctx)
    assert registry.writes[0][3]['caller_assignment_id'] == 'parent'
    assert assignment['state'] == 'running'


def test_dynamic_blacklist_is_not_bypassed_by_skill_publication(registry_setup, monkeypatch):
    ctx, registry = registry_setup
    monkeypatch.setattr(facilitation, 'held_role', lambda ctx: 'user_configured_role')
    ctx.nouns = {'role': 'expert', 'purpose': 'Expertise.', 'duty': 'Reusable method.'}
    with pytest.raises(Stop, match='user_configured_role'):
        facilitation.publish(ctx)
    assert not registry.writes


def test_find_ranks_without_hiding_specialties_or_reading_bodies(registry_setup):
    ctx, registry = registry_setup
    registry.entries = {'other': {'purpose': 'Graphics.'}, 'storage': {'purpose': 'SQLite concurrency.'}}
    ctx.nouns = {'query': 'SQLite'}
    result = facilitation.find(ctx)
    assert [row['name'] for row in result['specialists']] == ['storage', 'other']
    assert all(set(row) == {'name', 'purpose'} for row in result['specialists'])
    assert registry.writes == []


def test_runtime_choice_preserves_explicit_overrides_without_commission(setup, monkeypatch):
    ctx, _ = setup
    kept = {'agent': 'codex', 'model': 'selected', 'decision': {'decider': 'person'}}
    catalog = {'codex': {'models': {'selected': 'Available'}, 'efforts': []}}
    saved = []
    transport = SimpleNamespace(runtime_catalog=lambda *args: catalog, runtime_settings=lambda *args: kept,
                                keep_runtime=lambda ctx, work, choice: saved.append(choice) or choice)
    monkeypatch.setattr(facilitation, 'provided', lambda *args: [('dispatch', transport)])
    monkeypatch.setattr(facilitation, 'held_role', lambda ctx: None)
    monkeypatch.setattr(facilitation, 'own', lambda ctx: SimpleNamespace(
        ticket=lambda work: SimpleNamespace(work=SimpleNamespace(task='Exact task.'))))
    observed = []

    def choose(ctx, record, catalog, *, fallback, overrides):
        observed.append(overrides)
        return dict(fallback)

    monkeypatch.setattr(facilitation, 'choose', choose)
    ctx.nouns = {'work': 'ticket', 'choice': {'agent': 'codex', 'model': 'selected', 'effort': None,
                                            'task_type': 'coding', 'confidence': 1, 'reason': 'Fits.'}}
    result = facilitation.runtime(ctx)
    assert result['state'] == 'selected'
    assert observed == [{'agent': 'codex', 'model': 'selected'}]
    assert len(saved) == 1 and saved[0]['source']['caller_session_id'] == 'informed'
    assert saved[0]['task_fingerprint'] == hashlib.sha256(b'Exact task.').hexdigest()


def test_runtime_rejection_returns_catalog_and_leaves_configuration_unchanged(setup, monkeypatch):
    ctx, _ = setup
    monkeypatch.setattr(facilitation, 'held_role', lambda ctx: None)
    transport = SimpleNamespace(runtime_catalog=lambda *args: {}, runtime_settings=lambda *args: {},
                                keep_runtime=lambda *args: pytest.fail('invalid choice must not be stored'))
    monkeypatch.setattr(facilitation, 'provided', lambda *args: [('dispatch', transport)])
    monkeypatch.setattr(facilitation, 'own', lambda ctx: SimpleNamespace(
        ticket=lambda work: SimpleNamespace(work=SimpleNamespace(task='Work.'))))
    monkeypatch.setattr(facilitation, 'choose', lambda *args, **kwargs: None)
    monkeypatch.setattr(facilitation, 'rejection_reason', lambda *args: 'model unavailable')
    monkeypatch.setattr(facilitation, 'strengths_of', lambda *args: {})
    ctx.nouns = {'work': 'ticket', 'choice': {'model': 'unavailable'}}
    assert facilitation.runtime(ctx)['reason'] == 'model unavailable'


def test_method_families_cover_procedures_without_cataloging_every_specialty():
    names = [name for group in methods.FAMILIES.values() for name in group]
    assert len(names) == len(set(names)) == 16
    assert len(set(names) | set(methods.RESPONSIBILITIES) | {'facilitator', 'role_creator'}) == 23
    assert 'context_delivery_engineer' not in names


def test_native_families_use_the_existing_registry_and_deploy_selected_procedure(monkeypatch):
    names = {'facilitator', *methods.FAMILIES}
    available = {one.name: one for one in skills.catalog()}
    assert names <= set(available)
    for name in names:
        skill = available[name]
        assert skill.discover and skill.requires == ()
        assert 'references/procedure.axiom' in skills.deployment_files(skill)
    monkeypatch.setattr(skills, 'selected_procedure', lambda name: 'Exact selected user procedure.')
    deployed = skills.deployment_files(available['facilitator'])
    assert deployed['references/procedure.axiom'] == b'Exact selected user procedure.\n'


def test_skill_components_preserve_selected_source_and_only_actual_library_sections(monkeypatch):
    skill = SimpleNamespace(name='example')
    monkeypatch.setattr(skills, 'get', lambda name: skill)
    monkeypatch.setattr(skills, 'procedure', lambda name: 'shipped procedure')
    selected = component('prompt.skill.example', 'edited procedure', 'edited-v')
    monkeypatch.setattr(skills.prompt_files, 'resolve_text', lambda *args: selected)
    monkeypatch.setattr(skills, 'libraries', lambda one: {'lib_axiom': 'wrapper actual-section end'})
    monkeypatch.setattr(skills, 'SECTIONS', ('used', 'unused'))
    monkeypatch.setattr(skills.prompts, 'prompt_version', lambda name: SimpleNamespace(
        text='actual-section' if name.endswith('used') and not name.endswith('unused') else 'not-delivered',
        format='text', version_id=name))
    parts = skills.components('example')
    assert parts[-1] == selected
    assert parts[0]['text'] == 'wrapper actual-section end'
    assert len(parts[0]['source']['sections']) == 1
    assert parts[0]['source']['sections'][0]['name'].endswith('used')
