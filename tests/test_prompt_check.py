"""The structural prompt check flags what a prompt's structure lacks and passes a complete prompt, MCP-035, BASE-057."""
from importlib import resources

import pytest

from metaform import axiom, prompt_files

pytestmark = [pytest.mark.req('MCP-035'), pytest.mark.req('BASE-057'), pytest.mark.kind('fixture')]

COMPLETE = '''@STATE_INIT:
  {target} := PARAM
@CONSTRAINT:
  +> Acceptance: the target has been checked.
@CONDITION (DONE):
  ?IF ( TRUE ) -> RETURN TRUE
@ROUTER:
  EXECUTE_PIPELINE( Review )
@EXECUTE_PIPELINE (Review):
  [STEP 1]: RETURN TRUE.
@VERIFY:
  [V1] Was it checked? NO -> RECURSE Review.
'''


def test_a_one_line_prompt_is_flagged():
    found = axiom.incomplete('Use Metaform for all task assignment.')
    assert 'It is one line.' in found
    assert '@VERIFY is missing.' in found


def test_a_prompt_with_no_verify_is_flagged_for_it_alone():
    text = COMPLETE[:COMPLETE.index('@VERIFY')]
    assert axiom.incomplete(text) == ['@VERIFY is missing.']


def test_a_prompt_with_no_acceptance_is_flagged():
    text = COMPLETE.replace('  +> Acceptance: the target has been checked.\n', '').replace(
        '  [V1] Was it checked? NO -> RECURSE Review.\n', '')
    assert axiom.incomplete(text) == ['It states no acceptance.']


def test_a_complete_prompt_passes():
    assert axiom.incomplete(COMPLETE) == []


def test_dispatch_handoff_prompt_passes_unchanged():
    text = prompt_files.required(resources.files('metaform.modules.dispatch'), 'handoff', work_id='abc')
    assert axiom.incomplete(text) == []
