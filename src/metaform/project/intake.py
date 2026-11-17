"""The intake procedure, as Markdown sections, ported from the Rust form (`core/metaform/rust/crates/metaform-core/build.rs`
and `src/procedure.rs`).

The procedure is the folder `procedure/` beside this file: one Markdown file for each section, and `sections.md`, which
names the sections in reading order, marks the required ones, and says when to read a section that applies to one kind
of artifact only. The files are the founder's, copied unchanged from `core/metaform/intake/procedure/`.

The procedure is sliced because much of its context is reused by other operations. It is delivered two ways from the
same files (the founder, 2026-11-17): an agent performing an intake, a clean-context agent with that one purpose, is
given the whole procedure inline, `whole`; any other agent reads the sections it needs by address, each one a resource
at `metaform://intake/<section>` and the answer to `{"help": "intake/<section>"}`, so a section named by several tools
is read once in a context.

This module names no section and knows nothing of what a section holds, so a change to the procedure is a change to that
folder. Nothing fails because of how the folder is edited: a section that `sections.md` names with no file is left out,
and a file it does not name is served after the listed sections, in name order. No test reads the sections' names or
text.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable

INDEX = 'sections.md'
URI = 'metaform://intake/'  # the start of each section's address; the section's name follows


@dataclass(frozen=True)
class Section:
    """One section: its name, its Markdown, whether it is required reading, and when to read it, in the words of
    `sections.md`, empty when it gives none."""
    name: str
    text: str
    required: bool
    when: str


def _folder() -> Traversable:
    return resources.files(__package__ or 'metaform.project') / 'procedure'


def _listed(index: str) -> list[tuple[str, bool, str]]:
    """The sections `sections.md` names, in order. A line is "- name", "- name (required)" or "- name (when ...)"; words
    in brackets other than "required" say when an agent reads the section and are passed on as written."""
    listed: list[tuple[str, bool, str]] = []
    for line in index.splitlines():
        if not line.startswith('- '):
            continue
        entry = line[2:].strip()
        opened = entry.find('(')
        name, note = (entry[:opened].strip(), entry[opened + 1:-1].strip()) if opened >= 0 and entry.endswith(')') \
            else (entry, '')
        required = note == 'required'
        listed.append((name, required, '' if required else note))
    return listed


def sections() -> list[Section]:
    """The sections of the intake procedure, in reading order."""
    folder = _folder()
    try:
        index = (folder / INDEX).read_text(encoding='utf-8')
    except OSError:
        index = ''
    files = sorted(entry.name[:-3] for entry in folder.iterdir() if entry.name.endswith('.md') and entry.name != INDEX)
    listed = [entry for entry in _listed(index) if entry[0] in files]
    known = {name for name, _, _ in listed}
    listed += [(name, False, '') for name in files if name not in known]
    return [Section(name, (folder / f'{name}.md').read_text(encoding='utf-8').strip(), required, when)
            for name, required, when in listed]


def section(name: str) -> Section | None:
    """The section with this name, if the procedure has one."""
    return next((one for one in sections() if one.name == name), None)


def whole() -> str:
    """The whole procedure for an agent performing an intake, inline: each section under its name, in reading order,
    its text as the file holds it. Empty when the folder holds no section."""
    found = sections()
    return '\n\n'.join(f'## {one.name}\n\n{one.text}' for one in found) + '\n' if found else ''


def listing() -> dict[str, object]:
    """`{"help": "intake"}`'s answer, as the Rust form gives it (`metaform-core/src/contract.rs`)."""
    found = sections()
    return {'sections': [one.name for one in found],
            'required': [one.name for one in found if one.required],
            'when': {one.name: one.when for one in found if one.when},
            'read': 'These sections are the intake procedure. Read them to perform an intake: every section in this '
                    'order, except a section listed under when, which you read only if its condition holds. Read one '
                    'section with {"help": "intake/<section>"}. For other work on the map you need none of them.'}
