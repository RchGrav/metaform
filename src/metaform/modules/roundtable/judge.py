"""Jev's judgment of each seat submission, BASE-066: four nouls asked in one request over the same state.

The state names every field and never relies on a list position: the opening, the discussion as it entered, each
turn under `T01` and on with its seat and text, and the contribution judged. A vetoed submission's text is never in
it, so a later contribution is judged against what was actually said. Over 24,000 tokens the oldest entries are
dropped first, and the drop is logged.

The roundtable asks Jev through `metaform.jev`'s own client, its endpoint, model, `Question` and answer checks, but
not through `jev.ask`: the setting `jev` governs the decisions Metaform makes by itself, and a roundtable is opened
on purpose, so the switch does not hold it back. Jev failing is never a fallback here: the table pauses and says why,
since nothing enters unjudged.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from metaform import jev, settings

from .render import said, turn, who
from .store import NOULS

log = logging.getLogger(__name__)

STATE_TOKENS = 24_000  # past this the oldest entries leave Jev's state, well inside its 32,000-token limit


class Failed(Exception):
    """Jev gave no usable answer; the message says why."""


def questions() -> dict[str, jev.Question]:
    """The four nouls, each one condition phrased so that true means keep, from the module's prompts."""
    return {name: jev.Question('noul', said(f'jev_{name}'),
                               {'true': said(f'jev_{name}_true'), 'false': said(f'jev_{name}_false')})
            for name in NOULS}


def state(opening: str, entered: Sequence[Mapping[str, Any]], seat: str, text: str) -> dict[str, Any]:
    """Jev's state: the opening, what entered the discussion by turn, and the contribution; the oldest entries are
    dropped first while it is over STATE_TOKENS."""
    held = list(entered)
    while True:
        built = {'opening': opening,
                 'discussion': {turn(int(row['number'])): {'seat': who(row), 'text': row['text']} for row in held},
                 'contribution': {'seat': seat, 'text': text}}
        if jev.tokens(built) <= STATE_TOKENS or not held:
            return built
        log.info('Roundtable: turn %s left Jev\'s state, which was over %s tokens.', held[0]['number'], STATE_TOKENS)
        held = held[1:]


def config(folder: Path) -> jev.Config:
    """The endpoint and model the person chose for Jev, with its key, whatever the `jev` switch says."""
    endpoint = jev.ENDPOINTS[str(settings.value('jev_endpoint', folder))]
    model = str(settings.value('jev_model', folder) or '').strip() or endpoint.model
    key = os.environ.get(endpoint.key, '').strip()
    if not key:
        raise Failed(f'{endpoint.key} is not set in the environment.')
    return jev.Config(endpoint, model, key, STATE_TOKENS)


def ask(folder: Path, given: Mapping[str, Any]) -> dict[str, float]:
    """The four nouls for the contribution in `given`, by name; Failed when Jev does not answer usably."""
    cfg = config(folder)
    asked = questions()
    body = {'model': cfg.model, 'state': dict(given),
            'questions': {name: question.payload() for name, question in asked.items()}}
    try:
        reply = jev.post(cfg, body)
        raw: Any = reply['answers']
        return {name: float(jev.checked(question, raw[name], cfg.model).value) for name, question in asked.items()}
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        raise Failed(str(error) or type(error).__name__) from None
