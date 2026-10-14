"""The shipped source and the tests name no person: decisions are recorded by their spec record, never by who made
them, and the wheel carries everything under src/metaform."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.req('QUAL-001'), pytest.mark.kind('real')]

ROOT = Path(__file__).resolve().parents[1]
OWNER = re.compile(r'\b' + 'R' + r'ich\b|\b' + 'r' + r'ichs\b|' + 'Gra' + 'ver')  # spelled apart so this file does not match itself
# The question form's third heading, which the page matches word for word against what agents write; it changes
# together with the form's text, which is not in this repository.
KEPT = {('src/metaform/modules/web/page/app/selection/select.js', '#3 Unexplained "' + 'R' + 'ich said":'),
        # the MCP Apps map view, built from the page's script by scripts/build_map_view.mjs, carries the same heading
        ('src/metaform/modules/mcp/resources/views/map.html', '#3 Unexplained "' + 'R' + 'ich said":'),
        # the official MCP Apps SDK, vendored unchanged in meaning, describes its host context in these words
        ('src/metaform/modules/mcp/resources/views/ext-apps.js', 'R' + 'ich context about the host environment.'),
        ('src/metaform/modules/mcp/resources/views/map.html', 'R' + 'ich context about the host environment.')}


def test_no_shipped_or_test_file_names_the_project_owner():
    found = []
    for top in (ROOT / 'src' / 'metaform', ROOT / 'tests'):
        for path in sorted(top.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue  # a binary file
            where = path.relative_to(ROOT).as_posix()
            for number, line in enumerate(text.splitlines(), 1):
                if OWNER.search(line) and not any(where == file and kept in line for file, kept in KEPT):
                    found.append(f'{where}:{number}: {line.strip()[:120]}')
    assert not found, '\n'.join(found)
