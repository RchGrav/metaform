"""The procedure actually delivered is required before intake construction."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys

import pytest

from metaform.module import context, prepare_agent_context
from metaform.modules import intake

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture(autouse=True)
def load_project_modules(project_folder):
    from metaform.module import surface
    surface(project_folder)


def test_procedure_component_retains_exact_source_and_ignores_focus_only_data(project_folder):
    ctx = context('intake', project_folder, nouns={'mode': 'fresh'})
    component = intake.procedure_component(ctx)
    for asked in ('Survey the timer.', 'Inspect its changed alarm.'):
        assert component['text'] in intake.served(ctx, asked)
    assert component['source']['sha256'] == hashlib.sha256(intake.RESOURCE.read_bytes()).hexdigest()
    assert component['source']['path'] == str(intake.RESOURCE)
    assert component['rendered_fingerprint'] == hashlib.sha256(component['text'].encode()).hexdigest()


def test_procedure_resource_unlocks_only_delivered_body_across_intake_mutations(project_folder):
    from metaform.modules.mcp import server

    component = intake.procedure_component(context('intake', project_folder))

    async def exercise():
        error, _, result = await server.answer(project_folder, 'intake_start', {}, session='intake-reader')
        assert error and result['error'] == 'instructions_required' and not result['executed']
        assert not context('intake', project_folder).require_store().intake_building().results
        assert component['name'] in {one['name'] for one in result['instructions']}
        body, _ = await server.read_resource_text(project_folder, intake.PROCEDURE_URI, session='intake-reader')
        assert component['text'] in body
        for tool in ('intake_start', 'intake_element', 'intake_purpose', 'intake_remove', 'intake_finish'):
            required = server.instruction_required(project_folder, tool, {}, 'intake-reader')
            assert required and component['name'] not in {one['name'] for one in required['instructions']}, tool
            guide, _ = await server.read_resource_text(project_folder, server.instruction_uri(tool),
                                                      session='intake-reader')
            assert component['text'] not in guide
            assert server.instruction_required(project_folder, tool, {}, 'intake-reader') is None
            if tool == 'intake_start':
                error, blocks, _ = await server.answer(project_folder, tool, {}, session='intake-reader')
                assert not error, blocks
    asyncio.run(exercise())


def test_custom_procedure_binding_is_not_receipted_when_its_empty_variant_was_not_delivered(
        run, project_folder, tmp_path):
    custom = tmp_path / 'procedure.xml'
    custom.write_text('<procedure><target type="" value=""/><prompt>{prompt}</prompt></procedure>')
    run('set', f'--intake-file={custom}', cwd=project_folder)
    ctx = context('intake', project_folder, nouns={'text': 'Preserve this exact request'}, session='custom-reader')
    component = intake.procedure_component(ctx)
    body = intake.prompt(ctx)
    assert 'Preserve this exact request' in body and component['text'] not in body
    assert ctx.context_receipts == []
    due = prepare_agent_context(project_folder, ctx.session, [component])
    assert due['components']
    empty = context('intake', project_folder, session='custom-reader')
    assert component['text'] in intake.prompt(empty)
    assert empty.context_receipts[0]['component'] == component
    custom.write_text(custom.read_text().replace('<procedure>', '<procedure revision="2">'))
    revised = intake.procedure_component(empty)
    assert revised['source']['sha256'] != component['source']['sha256']
    assert revised['rendered_fingerprint'] != component['rendered_fingerprint']


def test_custom_middle_prompt_during_active_launch_has_a_satisfiable_combined_guide_route(
        run, project_folder, tmp_path, monkeypatch):
    from metaform.modules.intake.tests.test_intake import _INTAKE_AGENT, _let_go
    from metaform.modules.mcp import server

    custom = tmp_path / 'procedure.xml'
    custom.write_text('<procedure><prompt>{prompt}</prompt><rules>Retain the exact namespace rules.</rules></procedure>')
    run('set', f'--intake-file={custom}', cwd=project_folder)
    launch = {'work': 'intake-x', 'mode': 'fresh', 'map': 'new', 'name': 'fresh-map'}
    held = subprocess.Popen([sys.executable, '-c', _INTAKE_AGENT.replace("Store('timer')", "Store('proj')"),
                             json.dumps(launch)], cwd=project_folder, text=True,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=dict(os.environ))
    assert held.stdout is not None and held.stdout.readline().strip() == 'holding'
    monkeypatch.setenv('METAFORM_WORK', 'intake-x')
    try:
        component = intake.procedure_component(context('intake', project_folder))
        assert 'read' not in component, 'The procedure URI inserts active mode data into the middle slot.'

        async def exercise():
            body, _ = await server.read_resource_text(project_folder, intake.PROCEDURE_URI, session='active-custom')
            assert 'Selected intake mode: fresh' in body and component['text'] not in body
            required = server.instruction_required(project_folder, 'intake_start', {}, 'active-custom')
            assert required and component['name'] in {one['name'] for one in required['instructions']}
            exact, _ = await server.read_resource_text(project_folder, required['read'], session='active-custom')
            assert component['text'] in exact
            assert server.instruction_required(project_folder, 'intake_start', {}, 'active-custom') is None
        asyncio.run(exercise())
    finally:
        _let_go(held)


@pytest.mark.parametrize('body', ['', '{prompt}'])
def test_empty_configured_procedure_keeps_api_guidance_without_an_unreceiptable_prerequisite(
        run, project_folder, tmp_path, body):
    from metaform.modules.mcp import server

    custom = tmp_path / 'procedure.txt'
    custom.write_text(body)
    run('set', f'--intake-file={custom}', cwd=project_folder)
    ctx = context('intake', project_folder, session='empty-reader')
    assert intake.tool_instructions(ctx, 'intake_start', None) == []
    intake.prompt(ctx)
    assert ctx.context_receipts == []

    async def exercise():
        required = server.instruction_required(project_folder, 'intake_start', {}, ctx.session)
        assert required and 'prompt.intake:procedure' not in {one['name'] for one in required['instructions']}
        await server.read_resource_text(project_folder, required['read'], session=ctx.session)
        assert server.instruction_required(project_folder, 'intake_start', {}, ctx.session) is None
    asyncio.run(exercise())


@pytest.mark.parametrize('invalid_utf8', [False, True])
def test_unreadable_configured_procedure_returns_the_ordinary_error_before_any_write(
        run, project_folder, tmp_path, invalid_utf8):
    from metaform.modules.mcp import server

    custom = tmp_path / 'unreadable-intake.txt'
    if invalid_utf8:
        custom.write_bytes(b'\xff')
    run('set', f'--intake-file={custom}', cwd=project_folder)
    error, blocks, result = asyncio.run(server.answer(project_folder, 'intake_start', {}, session='bad-source'))
    assert error and result is None
    assert ('is not UTF-8 text' if invalid_utf8 else 'No intake file') in '\n'.join(blocks)
    assert 'Next:' in '\n'.join(blocks)
    assert not context('intake', project_folder).require_store().intake_building().results


def test_dispatched_intake_records_exact_procedure_only_after_prompt_acceptance(store, project_folder):
    from metaform.modules.dispatch import runner

    async def exercise():
        ctx = context('dispatch', project_folder, nouns={'intake': True})
        held = runner.Session(ctx, store, None, 'codex', [], system=True, work_id='intake-procedure-test')
        held.runner = 'intake-context'
        component = intake.procedure_component(context('intake', project_folder))
        text = intake.served(context('intake', project_folder, nouns={'mode': 'fresh'}), 'Survey the timer.')
        outgoing = held.current_guidance(text, [])
        assert outgoing.count(component['text']) == 1
        assert component in held.inflight_context['components']
        assert prepare_agent_context(project_folder, held.runner, [component])['components']
        held.context_delivered()
        assert not prepare_agent_context(project_folder, held.runner, [component])['components']
        following = held.current_guidance('Continue the same intake.', [])
        assert component['text'] not in following
    asyncio.run(exercise())
