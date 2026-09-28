"""The sealed container of a packet, PROJ-027, carried over from Tempo's `tempo.data`, version 3.

A packet is a plain ZIP. Its work is visible. Its `.metaform/` folder holds two files: `manifest`, in plain text, which
indexes the visible work and nothing else, and `metaform.data`, an AES-256-GCM envelope around an inner ZIP of the
provenance and the data. The key is derived from the manifest, so the work and what is sealed are bound to each other:
a changed work file fails the manifest's hashes, and a manifest changed to match derives another key.

The write order is fixed: the work, then the manifest, then the key, then the seal.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import struct
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

FOLDER = '.metaform/'
MANIFEST, SEALED = FOLDER + 'manifest', FOLDER + 'metaform.data'
MAGIC = b'METAFORM-DATA-V1\x00'
ENVELOPE_SCHEMA = 'metaform.data-envelope.v1'
MANIFEST_SCHEMA = 'metaform.packet-manifest.v1'
SALT, INFO = b'metaform', b'Metaform metaform.data v1'
ROOT_PARENT = '0' * 64
# The evidence every copy of Metaform holds, so every copy opens every packet: the seal shows tampering and keeps no
# one out. Someone who needs secrecy seals with evidence of their own, the `packet_evidence` setting.
SHIPPED_EVIDENCE = b'Metaform tamper seal: every copy of the tool opens every packet.'


class Tampered(Exception):
    """The packet was changed after it was sealed; `where` names what no longer matches."""

    def __init__(self, where: str) -> None:
        super().__init__(where)
        self.where = where


class OtherEvidence(Exception):
    """The packet was sealed with evidence this tool does not hold. It is not a sign of tampering."""


class Malformed(Exception):
    """The packet is not built as a packet is."""


@dataclass(frozen=True)
class Opened:
    manifest: dict[str, Any]
    work: dict[str, bytes]
    data: dict[str, bytes]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def fingerprint(evidence: bytes) -> str:
    return hashlib.sha256(evidence).hexdigest()


def derive_key(evidence: bytes, origin: bytes, manifest: bytes, parent: str, wave: int) -> bytes:
    """The key of one packet at one place in its lineage: the tool's evidence, the origin's digest, this packet's
    manifest's digest, its parent's manifest's digest, all zeroes at the root, and the wave number."""
    if len(evidence) < 32:
        raise Malformed('The evidence a packet is sealed with holds 32 bytes or more.')
    material = b''.join((evidence, hashlib.sha256(origin).digest(), hashlib.sha256(manifest).digest(),
                         bytes.fromhex(parent), struct.pack('>Q', wave)))
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=SALT, info=INFO).derive(material)


def zipped(files: Mapping[str, bytes]) -> bytes:
    held = io.BytesIO()
    with zipfile.ZipFile(held, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            archive.writestr(name, files[name])
    return held.getvalue()


def unzipped(data: bytes, what: str) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    except zipfile.BadZipFile:
        raise Malformed(f'{what} is not a ZIP.') from None


def write(work: Mapping[str, bytes], data: Mapping[str, bytes], *, evidence: bytes, packet_id: str, created: str,
          origin: str = '', parent: bytes | None = None, nonce: bytes) -> bytes:
    """A packet's bytes. `origin` names the work file the packet is grounded in; `parent` is the manifest of the
    packet this one was made from."""
    inside = [name for name in work if name.startswith(FOLDER)]
    if inside:
        raise Malformed(f'Work is never kept in {FOLDER}: {inside[0]}.')
    wave, parent_digest = 0, ROOT_PARENT
    if parent is not None:
        wave = int(json.loads(parent)['wave_number']) + 1
        parent_digest = hashlib.sha256(parent).hexdigest()
    manifest = canonical({
        'schema': MANIFEST_SCHEMA, 'packet_id': packet_id, 'created': created, 'origin_artifact': origin,
        'wave_number': wave, 'parent_manifest_sha256': parent_digest,
        'work': [{'path': name, 'sha256': hashlib.sha256(work[name]).hexdigest(), 'size': len(work[name])}
                 for name in sorted(work)]})
    key = derive_key(evidence, work.get(origin, b''), manifest, parent_digest, wave)
    header = canonical({'schema': ENVELOPE_SCHEMA, 'nonce': base64.urlsafe_b64encode(nonce).decode('ascii'),
                        'wave_number': wave, 'origin_artifact': origin,
                        'system_evidence_fingerprint': fingerprint(evidence)})
    sealed = MAGIC + struct.pack('>I', len(header)) + header + AESGCM(key).encrypt(nonce, zipped(data), header)
    return zipped({**work, MANIFEST: manifest, SEALED: sealed})


def read(packet: bytes, *, evidence: bytes) -> Opened:
    """The packet's work and data, once its build, its manifest and its seal have each been checked."""
    held = unzipped(packet, 'The packet')
    own = sorted(name for name in held if name.startswith(FOLDER))
    if own != [MANIFEST, SEALED]:
        raise Malformed(f'{FOLDER} holds exactly two files, manifest and metaform.data; this one holds '
                        f'{", ".join(name[len(FOLDER):] for name in own) or "none"}.')
    work = {name: body for name, body in held.items() if not name.startswith(FOLDER)}
    try:
        manifest = json.loads(held[MANIFEST])
        records = {str(record['path']): record for record in manifest['work']}
        wave, parent, origin = int(manifest['wave_number']), str(manifest['parent_manifest_sha256']), str(
            manifest['origin_artifact'])
    except (ValueError, KeyError, TypeError):
        raise Tampered('the manifest') from None
    for name in sorted(set(records) | set(work)):
        if name not in work or name not in records or hashlib.sha256(work[name]).hexdigest() != records[name].get(
                'sha256'):
            raise Tampered(name)
    sealed = held[SEALED]
    if not sealed.startswith(MAGIC) or len(sealed) < len(MAGIC) + 4:
        raise Malformed('metaform.data does not begin as a sealed file does.')
    size = struct.unpack('>I', sealed[len(MAGIC):len(MAGIC) + 4])[0]
    header, cipher = sealed[len(MAGIC) + 4:len(MAGIC) + 4 + size], sealed[len(MAGIC) + 4 + size:]
    try:
        stated = json.loads(header)
        nonce = base64.urlsafe_b64decode(stated['nonce'])
        mine = stated['system_evidence_fingerprint'] == fingerprint(evidence)
    except (ValueError, KeyError, TypeError):
        raise Tampered('metaform.data') from None
    try:
        inner = AESGCM(derive_key(evidence, work.get(origin, b''), held[MANIFEST], parent, wave)).decrypt(
            nonce, cipher, header)
    except (InvalidTag, ValueError):
        if not mine:
            raise OtherEvidence() from None
        raise Tampered('metaform.data') from None
    return Opened(manifest, work, unzipped(inner, 'What is sealed'))
