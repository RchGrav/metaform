"""The shared roster contains names and never overwrites participant-authored content."""
import pytest

from metaform.module import Stop
from metaform.modules.roundtables.roundtable.identity import write_roster

pytestmark = pytest.mark.kind('simulation')
NAMES = ['StableComet', 'ActiveAgent']


def test_roster_is_readable_names_only_in_the_session_folder(tmp_path):
    folder = tmp_path / 'session'
    path = write_roster(folder, NAMES)
    assert path == folder / 'participants.md'
    assert path.read_text(encoding='utf-8') == '# Participants\n\n- StableComet\n- ActiveAgent\n'
    assert not any(private in path.read_text(encoding='utf-8').casefold()
                   for private in ('claude', 'codex', 'opus', 'profile_key', 'identity', 'model', 'provider', 'score'))
    assert [entry.name for entry in folder.iterdir()] == ['participants.md']


def test_identical_retry_reuses_the_roster_without_rewriting_even_when_read_only(tmp_path):
    path = write_roster(str(tmp_path), NAMES)
    path.chmod(0o444)
    before = path.stat()
    try:
        assert write_roster(tmp_path, NAMES) == path
        after = path.stat()
        assert after.st_mtime_ns == before.st_mtime_ns
        assert after.st_mode == before.st_mode
        assert path.read_bytes() == b'# Participants\n\n- StableComet\n- ActiveAgent\n'
    finally:
        path.chmod(0o644)


def test_an_edited_existing_roster_is_not_clobbered(tmp_path):
    path = write_roster(tmp_path, NAMES)
    edited = '# Participants\n\n- StableComet\n\n## Participant notes\nKeep these edits.\n'
    path.write_text(edited, encoding='utf-8')
    before = path.stat().st_mtime_ns
    with pytest.raises(Stop, match='already has different content'):
        write_roster(tmp_path, NAMES)
    assert path.read_text(encoding='utf-8') == edited
    assert path.stat().st_mtime_ns == before


def test_a_different_participant_list_cannot_replace_the_existing_roster(tmp_path):
    path = write_roster(tmp_path, NAMES)
    before = path.read_bytes()
    with pytest.raises(Stop, match='already has different content'):
        write_roster(tmp_path, ['OtherParticipant'])
    assert path.read_bytes() == before


@pytest.mark.parametrize('names', [[], [''], ['StableComet\nprivate model metadata'], ['ActiveAgent\rmetadata']])
def test_roster_rejects_empty_or_multiline_names_before_creating_a_file(tmp_path, names):
    with pytest.raises(Stop, match='nonempty single-line names'):
        write_roster(tmp_path, names)
    assert not (tmp_path / 'participants.md').exists()
