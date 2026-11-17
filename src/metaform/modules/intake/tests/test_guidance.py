"""The procedure actually delivered is required before intake construction."""
from __future__ import annotations

import asyncio
import hashlib

import pytest

from metaform.module import context
from metaform.modules import intake

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture(autouse=True)
def load_project_modules(project_folder):
    from metaform.module import surface
    surface(project_folder)


def test_procedure_component_retains_exact_source_and_ignores_focus_only_data(project_folder):
    ctx = context('intake', project_folder, nouns={'mode': 'fresh'})
    component = intake.procedure_component(ctx)
    # The served procedure holds its request in a slot of its own, so the component, which is the source without a
    # request, is the served text on both sides of what was asked.
    from metaform.project import intake as procedure
    source = procedure.whole()
    before, after = source.split('{prompt}', 1)
    assert component['text'].startswith(before + after.rstrip('\n'))
    for asked in ('Survey the timer.', 'Inspect its changed alarm.'):
        served = intake.served(ctx, asked)
        assert served.startswith(before) and after.rstrip('\n') in served and asked in served
    assert component['source']['sha256'] == hashlib.sha256(source.encode('utf-8')).hexdigest()
    assert component['rendered_fingerprint'] == hashlib.sha256(component['text'].encode()).hexdigest()


def test_dispatched_intake_records_exact_procedure_only_after_prompt_acceptance(store, project_folder):
    from metaform.modules.dispatch import runner

    async def exercise():
        ctx = context('dispatch', project_folder, nouns={'intake': True})
        held = runner.Session(ctx, store, None, 'codex', [], system=True, work_id='intake-procedure-test')
        held.runner = 'intake-context'
        component = intake.procedure_component(context('intake', project_folder))
        text = intake.served(context('intake', project_folder, nouns={'mode': 'fresh'}), 'Survey the timer.')
        outgoing = held.current_guidance(text, [])
        # The served procedure holds the request in a slot of its own, so the first turn carries it once, with the
        # request in place, and the source without a request is never recorded as delivered: it was not what was sent.
        from metaform.project import intake as procedure
        before = procedure.whole().split('{prompt}', 1)[0]
        assert outgoing.count(before) == 1 and 'Survey the timer.' in outgoing
        assert component not in held.inflight_context['components']
        held.context_delivered()
        following = held.current_guidance('Continue the same intake.', [])
        assert before not in following
    asyncio.run(exercise())
