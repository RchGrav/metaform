"""packet: a project's work in a plain ZIP with its provenance and data sealed inside, PROJ-027.

The tests follow those of Tempo's packet writer, from which the container comes: the round trip, the two files of
`.metaform/`, and each way a packet can be changed after it is written.
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def made(run, tmp_path):
    """The packet module enabled, a folder of work and a folder of data, and a packet written from them."""
    run('enable', 'packet')
    work, data = tmp_path / 'work', tmp_path / 'data'
    (work / 'game').mkdir(parents=True)
    (work / 'game' / 'pong.py').write_text('print("pong")\n', encoding='utf-8')
    (work / 'report.md').write_text('# Report\n', encoding='utf-8')
    (work / 'origin.zip').write_bytes(b'PK\x05\x06' + bytes(18))
    (data / 'provenance').mkdir(parents=True)
    (data / 'provenance' / 'journal').write_text('made by a test\n', encoding='utf-8')
    (data / 'store.sqlite3').write_bytes(b'SQLite format 3\x00' + bytes(64))
    packet = tmp_path / 'proj.zip'
    run('packet', 'seal', f'work={work}', f'data={data}', f'file={packet}', cwd=tmp_path)
    return tmp_path, packet


def entries(packet):
    with zipfile.ZipFile(packet) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def rewritten(packet, target, change):
    """The packet written again with its entries changed, as someone editing the ZIP would."""
    held = change(entries(packet))
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, body in held.items():
            archive.writestr(name, body)
    return target


def check(run, packet, cwd, ok=True):
    return run('packet', 'check', str(packet), '--json', cwd=cwd, ok=ok)


@pytest.mark.req('PROJ-027')
def test_a_packet_is_a_plain_zip_with_the_work_visible_and_two_files_in_its_metaform_folder(run, made):
    folder, packet = made
    held = entries(packet)
    assert held['game/pong.py'] == b'print("pong")\n' and held['report.md'] == b'# Report\n'
    assert sorted(name for name in held if name.startswith('.metaform/')) == ['.metaform/manifest',
                                                                              '.metaform/metaform.data']
    manifest = json.loads(held['.metaform/manifest'])
    assert sorted(record['path'] for record in manifest['work']) == ['game/pong.py', 'origin.zip', 'report.md']
    assert (manifest['wave_number'], manifest['parent_manifest_sha256']) == (0, '0' * 64)
    sealed = held['.metaform/metaform.data']
    assert sealed.startswith(b'METAFORM-DATA-V1\x00')
    assert b'made by a test' not in sealed and b'SQLite format 3' not in sealed  # the data is inside the seal
    assert json.loads(check(run, packet, folder).stdout)['sealed'] == 'intact'


@pytest.mark.req('PROJ-027')
def test_opening_a_packet_gives_back_the_work_and_the_data_as_they_were(run, made):
    folder, packet = made
    run('packet', 'open', str(packet), f'into={folder / "out"}', cwd=folder)
    out = folder / 'out'
    assert (out / 'work' / 'game' / 'pong.py').read_text(encoding='utf-8') == 'print("pong")\n'
    assert (out / 'data' / 'provenance' / 'journal').read_text(encoding='utf-8') == 'made by a test\n'
    assert (out / 'data' / 'store.sqlite3').read_bytes().startswith(b'SQLite format 3\x00')
    assert not (out / 'work' / '.metaform').exists()


@pytest.mark.req('PROJ-027')
def test_a_changed_work_file_is_caught_by_the_manifest(run, made):
    folder, packet = made
    changed = rewritten(packet, folder / 'changed.zip', lambda held: {**held, 'report.md': b'# Report, edited\n'})
    found = check(run, changed, folder, ok=False)
    assert found.returncode != 0 and 'tampered' in found.stdout + found.stderr
    assert 'report.md' in found.stdout + found.stderr


@pytest.mark.req('PROJ-027')
def test_work_and_manifest_changed_together_no_longer_open_the_seal(run, made):
    """The key comes from the manifest, so a manifest rewritten to match edited work derives another key."""
    import hashlib
    folder, packet = made

    def both(held):
        body = b'# Report, edited\n'
        manifest = json.loads(held['.metaform/manifest'])
        for record in manifest['work']:
            if record['path'] == 'report.md':
                record.update(sha256=hashlib.sha256(body).hexdigest(), size=len(body))
        return {**held, 'report.md': body,
                '.metaform/manifest': json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode('utf-8')}
    found = check(run, rewritten(packet, folder / 'both.zip', both), folder, ok=False)
    assert found.returncode != 0 and 'tampered' in found.stdout + found.stderr


@pytest.mark.req('PROJ-027')
def test_one_changed_byte_of_the_sealed_file_is_caught(run, made):
    folder, packet = made

    def flipped(held):
        sealed = bytearray(held['.metaform/metaform.data'])
        sealed[-1] ^= 1
        return {**held, '.metaform/metaform.data': bytes(sealed)}
    found = check(run, rewritten(packet, folder / 'flipped.zip', flipped), folder, ok=False)
    assert found.returncode != 0 and 'tampered' in found.stdout + found.stderr


@pytest.mark.req('PROJ-027')
def test_a_third_file_in_the_metaform_folder_is_refused(run, made):
    folder, packet = made
    extra = rewritten(packet, folder / 'extra.zip', lambda held: {**held, '.metaform/journal': b'loose'})
    found = check(run, extra, folder, ok=False)
    assert found.returncode != 0 and 'exactly two files' in found.stdout + found.stderr


@pytest.mark.req('PROJ-027')
def test_a_packet_sealed_with_other_evidence_is_told_apart_from_a_tampered_one(run, made):
    """Someone who needs secrecy seals with evidence of their own; a tool without it says so, and does not call the
    packet tampered."""
    folder = made[0]
    secret = folder / 'evidence.bin'
    secret.write_bytes(bytes(range(48)))
    private = folder / 'private.zip'
    run('packet', 'seal', f'work={folder / "work"}', f'data={folder / "data"}', f'file={private}',
        '--packet-evidence', str(secret), cwd=folder)
    assert json.loads(run('packet', 'check', str(private), '--packet-evidence', str(secret), '--json',
                          cwd=folder).stdout)['sealed'] == 'intact'
    found = check(run, private, folder, ok=False)
    said = found.stdout + found.stderr
    assert found.returncode != 0 and 'other evidence' in said and 'tampered' not in said


@pytest.mark.req('PROJ-027')
def test_a_packet_made_from_another_takes_the_next_place_in_its_lineage(run, made):
    folder, packet = made
    import hashlib
    parent = entries(packet)['.metaform/manifest']
    child = folder / 'child.zip'
    run('packet', 'seal', f'work={folder / "work"}', f'data={folder / "data"}', f'file={child}', f'parent={packet}',
        cwd=folder)
    manifest = json.loads(entries(child)['.metaform/manifest'])
    assert manifest['wave_number'] == 1
    assert manifest['parent_manifest_sha256'] == hashlib.sha256(parent).hexdigest()
    assert json.loads(check(run, child, folder).stdout)['sealed'] == 'intact'


@pytest.mark.req('PROJ-027')
def test_the_work_opens_with_any_zip_reader(made):
    _, packet = made
    assert zipfile.is_zipfile(packet)
    with zipfile.ZipFile(io.BytesIO(packet.read_bytes())) as archive:
        assert archive.testzip() is None
