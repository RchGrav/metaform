"""The structural check of a prompt, MCP-035 and BASE-057: what code can count, never whether the prompt says what to
do, how, how it works and when, which the orchestrator judges. A flagged prompt is still stored and sent, BASE-044."""
from __future__ import annotations

import re

# The six modules every Axiom script has, in order, as the axiom-language section of the workflow module's
# prompts.xml defines them; Axiom-OS 2.0 requires the same six.
MODULES = ('@STATE_INIT', '@CONSTRAINT', '@CONDITION', '@ROUTER', '@EXECUTE_PIPELINE', '@VERIFY')
SIGNAL = 'incomplete prompt'


def _module(text: str, name: str) -> re.Match[str] | None:
    return re.search(rf'^[ \t]*{name}\b', text, re.MULTILINE)


def incomplete(text: str) -> list[str]:
    """What the prompt's structure lacks, one sentence each; empty when nothing is. Acceptance is an `Acceptance:`
    statement or a check under @VERIFY, the yes/no checks run before the result is used."""
    found: list[str] = []
    if sum(1 for line in text.splitlines() if line.strip()) <= 1:
        found.append('It is one line.')
    found += [f'{name} is missing.' for name in MODULES if not _module(text, name)]
    verify = _module(text, '@VERIFY')
    # The checks under @VERIFY run to the next module that starts a line, or to the end.
    checks = '' if verify is None else re.split(r'^@', text[verify.end():].lstrip(':'), maxsplit=1,
                                                 flags=re.MULTILINE)[0]
    if not checks.strip() and not re.search(r'\bacceptance\s*:', text, re.IGNORECASE):
        found.append('It states no acceptance.')
    return found


def notices(where: str, text: str) -> list[dict[str, str]]:
    """The check's findings as notices on `where`, BASE-044."""
    return [{'where': where, 'message': f'Incomplete prompt: {message}'} for message in incomplete(text)]
