"""packet: a project's work in a plain ZIP, its provenance and data sealed inside it, PROJ-027.

The seal is a tamper seal. It shows whether a packet was changed after it was written, and it keeps no one out:
every copy of Metaform opens every packet. The container is Tempo's, in `seal.py`.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from metaform import settings
from metaform.module import Context, Module, Noun, Stop, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('cryptography>=42',)
SHIPS_DISABLED = True
REMOTE_AGENT = False  # sealing needs the compiled cryptography package, which a direct run does not carry

settings.text('packet_evidence', '', help='A file of 32 bytes or more to seal and open packets with, for someone who '
                                          'needs secrecy. Empty means the evidence every copy of Metaform holds.')
EVIDENCE = ('packet_evidence',)
# What is never part of the source, PROJ-029: git's own files, and what is built from the source.
LEFT_OUT = ('.git', '__pycache__', '.metaform')


def _evidence(ctx: Context) -> bytes:
    from . import seal
    named = str(ctx.setting('packet_evidence') or '')
    if not named:
        return seal.SHIPPED_EVIDENCE
    path = _path(ctx, named)
    if not path.is_file():
        raise Stop(f'No evidence file at {path}.', 'metaform unset --packet-evidence')
    return path.read_bytes()


def _path(ctx: Context, given: Any) -> Path:
    path = Path(str(given))
    return path if path.is_absolute() else ctx.folder / path


def _files(folder: Path) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in sorted(folder.rglob('*'))
            if path.is_file() and not set(path.relative_to(folder).parts) & set(LEFT_OUT)
            and path.suffix not in ('.pyc', '.pyo')}


def _folder(ctx: Context, name: str) -> Path:
    path = _path(ctx, ctx.nouns[name])
    if not path.is_dir():
        raise Stop(f'No folder at {path}.', 'metaform help packet seal')
    return path


def _opened(ctx: Context) -> Any:
    from . import seal
    path = _path(ctx, ctx.nouns['packet'])
    if not path.is_file():
        raise Stop(f'No packet at {path}.', 'metaform help packet check')
    try:
        return seal.read(path.read_bytes(), evidence=_evidence(ctx))
    except seal.Tampered as found:
        raise Stop(f'This packet was tampered with: {found.where} is not as it was sealed.',
                   'metaform help packet') from None
    except seal.OtherEvidence:
        raise Stop('This packet was sealed with other evidence than this tool holds.',
                   'metaform help packet_evidence') from None
    except seal.Malformed as found:
        raise Stop(str(found), 'metaform help packet') from None


def seal_(ctx: Context) -> Any:
    """Write a packet: the work visible, the data sealed."""
    from . import seal
    for name in ('work', 'data', 'file'):
        if not ctx.nouns.get(name):
            raise Stop(f'packet seal needs {name}=.', 'metaform help packet seal')
    work, parent = _files(_folder(ctx, 'work')), None
    if ctx.nouns.get('parent'):
        held = seal.unzipped(_path(ctx, ctx.nouns['parent']).read_bytes(), 'The parent packet')
        parent = held.get(seal.MANIFEST)
        if parent is None:
            raise Stop('The parent is not a packet: it has no manifest.', 'metaform help packet seal')
    origin = str(ctx.nouns.get('origin') or ('origin.zip' if 'origin.zip' in work else ''))
    if origin and origin not in work:
        raise Stop(f'The origin {origin} is not in the work.', 'metaform help packet seal')
    try:
        packet = seal.write(work, _files(_folder(ctx, 'data')), evidence=_evidence(ctx), packet_id=uuid.uuid4().hex,
                            created=datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), origin=origin, parent=parent,
                            nonce=secrets.token_bytes(12))
    except seal.Malformed as found:
        raise Stop(str(found), 'metaform help packet seal') from None
    target = _path(ctx, ctx.nouns['file'])
    target.write_bytes(packet)
    return {'written': str(target), 'work': len(work), 'size': len(packet)}


def check(ctx: Context) -> Any:
    """Say whether a packet is as it was sealed."""
    found = _opened(ctx)
    return {'sealed': 'intact', 'packet_id': found.manifest.get('packet_id'), 'created': found.manifest.get('created'),
            'wave_number': found.manifest.get('wave_number'), 'work': len(found.work), 'data': len(found.data)}


def open_(ctx: Context) -> Any:
    """Check a packet and write its work and its data out to a folder."""
    if not ctx.nouns.get('into'):
        raise Stop('packet open needs into=.', 'metaform help packet open')
    found, target = _opened(ctx), _path(ctx, ctx.nouns['into'])
    for part, files in (('work', found.work), ('data', found.data)):
        for name, body in files.items():
            path = (target / part / name).resolve()
            if not path.is_relative_to((target / part).resolve()):
                raise Stop(f'{name} would be written outside {target}.', 'metaform help packet open')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    return {'written': str(target), 'work': len(found.work), 'data': len(found.data)}


def _optional(name: str, help: str) -> Noun:
    return Noun(name, help, required=False)


MODULE = Module(
    id='packet',
    summary='Write a project as a packet, a plain ZIP with a tamper seal, and check or open one.',
    purpose='Writes work as a packet: a plain ZIP with the work visible and the provenance and data sealed inside '
            'it, so any change after it was written shows. Use it to carry work to another home and to check what '
            'arrives. Details: metaform help packet.',
    details='The seal is a tamper seal and keeps no one out: every copy of Metaform opens every packet.',
    verbs=(
        Verb('seal', seal_, 'Write a packet from a folder of work and a folder of data.',
             nouns=(_optional('work', 'The folder of work, visible in the packet.'),
                    _optional('data', 'The folder of provenance and data, sealed in the packet.'),
                    _optional('file', 'The packet to write.'),
                    _optional('origin', 'The work file the packet is grounded in; origin.zip when the work has one.'),
                    _optional('parent', 'The packet this one was made from, which sets its place in the lineage.')),
             switches=EVIDENCE, surfaces=('cli',)),
        Verb('check', check, 'Say whether a packet is as it was sealed.',
             nouns=(Noun('packet', 'The packet.'),), switches=EVIDENCE, surfaces=('cli',)),
        Verb('open', open_, 'Check a packet and write its work and its data out to a folder.',
             nouns=(Noun('packet', 'The packet.'), _optional('into', 'The folder to write to.')),
             switches=EVIDENCE, surfaces=('cli',)),
    ),
    subscriptions=(),
    start=None,
    stop=None,
    status=None,
)
