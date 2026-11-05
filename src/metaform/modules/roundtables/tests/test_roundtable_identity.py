"""Generated participant identities reuse public naming and preserve private score history."""
import re
import uuid

import pytest

from metaform.module import Stop, provided
from metaform.modules.dispatch.names import is_name, session_name
from metaform.modules.roundtables.roundtable import identity, render, store

pytestmark = pytest.mark.kind('simulation')

CLAUDE = {'kind': 'acp', 'agent': 'claude', 'model': 'opus', 'id': 'acp:claude/opus'}
CODEX = {'kind': 'acp', 'agent': 'codex', 'model': 'sol', 'id': 'acp:codex/sol'}


@pytest.fixture
def engine(home, tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    return tmp_path


def test_registered_participants_reuse_existing_generator_and_keep_legacy_scores(
        engine, project_folder, run):
    run('enable', 'dispatch', cwd=project_folder)
    maker = provided(project_folder, 'agent.name')
    assert len(maker) == 1 and maker[0][0] == 'dispatch'
    assert maker[0][1]('a') == session_name('a') == 'StableComet'
    with store.connect() as db:
        db.execute('INSERT INTO profiles VALUES (?,?,?,?,?,?)', ('claude/opus', 'Opus', 83.5, 7, 3, 'earlier'))
        first = identity.assign(db, project_folder, [CLAUDE, CODEX, CLAUDE])
        reordered = identity.assign(db, project_folder, [CODEX, CLAUDE, CLAUDE])
        assert reordered == [first[1], first[0], first[2]]
        assert first[0]['profile_key'] == 'claude/opus'
        assert first[2]['profile_key'] != first[0]['profile_key']
        assert first[0]['identity'] != first[2]['identity']
        assert len({one['name'].casefold() for one in first}) == 3
        assert all(is_name(one['name']) for one in first)
        assert all(one['name'].casefold() not in ('claude', 'codex', 'opus', 'sol') for one in first)
        assert all(uuid.UUID(str(one['identity'])).hex == one['identity'] for one in first)
        profile = dict(db.execute('SELECT * FROM profiles WHERE agent=?', ('claude/opus',)).fetchone())
        assert profile == {'agent': 'claude/opus', 'name': 'Opus', 'score': 83.5,
                           'ratings': 7, 'sessions': 3, 'updated': 'earlier'}
    with store.connect() as db:
        assert identity.assign(db, project_folder, [CLAUDE, CODEX, CLAUDE]) == first


def test_unregistered_engine_uses_public_names_and_writes_a_persistent_roster(engine, run):
    run('enable', 'dispatch', cwd=engine)
    maker = provided(engine, 'agent.name')
    assert len(maker) == 1 and maker[0][0] == 'dispatch'
    with store.connect() as db:
        db.execute('INSERT INTO profiles VALUES (?,?,?,?,?,?)', ('claude/opus', 'Opus', 83.5, 7, 3, 'earlier'))
        first = identity.assign(db, engine, [CLAUDE, CODEX, CLAUDE])
        assert first[0]['profile_key'] == 'claude/opus'
        assert first[2]['profile_key'] != first[0]['profile_key']
        assert all(is_name(one['name']) and one['identity'] for one in first)
        assert all(one['name'].casefold() not in ('claude', 'codex', 'opus', 'sol') for one in first)
        assert identity.assign(db, engine, [CLAUDE, CODEX, CLAUDE]) == first

    number = store.opened({'subject': 'Next step', 'opening': 'Choose the next useful step.', 'folder': str(engine),
                           'chair_key': None, 'chair_token': 'fixture', 'reporter': CLAUDE['id'],
                           'rounds': 0, 'spend': 0}, [CLAUDE, CODEX], judging=False)
    names = [seat['name'] for seat in store.seats(number)]
    roster = engine / 'docs' / 'roundtables' / f'{number}-notes' / 'participants.md'
    assert roster.read_text() == '# Participants\n\n' + ''.join(f'- {name}\n' for name in names)
    profile = store.profile('claude/opus')
    assert profile is not None and profile['score'] == 83.5 and profile['ratings'] == 7


def test_existing_alias_survives_without_a_provider_and_old_record_is_unchanged(
        engine, project_folder, run, monkeypatch):
    run('enable', 'dispatch', cwd=engine)
    earlier = store.opened({'subject': 'Earlier session', 'opening': 'Keep the old record.', 'folder': str(engine),
                            'chair_key': None, 'chair_token': 'fixture', 'reporter': CLAUDE['id'],
                            'rounds': 0, 'spend': 0}, [CLAUDE], judging=False)
    with store.connect() as db:
        old_name = db.execute('SELECT name FROM seats WHERE discussion=?', (earlier,)).fetchone()[0]
        db.execute('UPDATE seats SET name=? WHERE discussion=?', ('Opus', earlier))
        monkeypatch.setattr(identity, 'provided', lambda folder, kind: [])
        assert identity.assign(db, project_folder, [CLAUDE]) == [
            {'identity': db.execute('SELECT identity FROM profile_aliases WHERE source=? AND occurrence=0',
                                    ('claude/opus',)).fetchone()[0],
             'name': old_name, 'profile_key': 'claude/opus'}]
        assert db.execute('SELECT name FROM seats WHERE discussion=?', (earlier,)).fetchone()[0] == 'Opus'


@pytest.mark.parametrize('staged', [False, True])
def test_opened_roster_and_captured_rules_use_persistent_names_without_peer_model_brands(
        engine, project_folder, run, staged):
    run('enable', 'dispatch', cwd=project_folder)
    number = store.opened({'subject': 'Next step', 'opening': 'Choose the next useful step.',
                           'folder': str(project_folder), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': CLAUDE['id'], 'rounds': 0, 'spend': 0,
                           'synthesizer': {**CLAUDE, 'name': 'Opus'},
                           'host': {**CODEX, 'id': 'acp:codex/gpt-6', 'model': 'gpt-6', 'name': 'GPT-6'}},
                          [CLAUDE, CODEX],
                          [{'name': 'one', 'title': 'Next step', 'text': 'Choose a useful step.'}] if staged else [],
                          judging=True)
    found, seats = store.discussion(number), store.seats(number)
    names = [seat['name'] for seat in seats]
    assert all(is_name(name) for name in names)
    for name in names:
        prompt = render.system(found, names, name)
        assert all(person in prompt for person in names)
        assert not re.search(r'\b(?:claude|codex|opus|sol)\b|0\.70|70%', prompt, re.IGNORECASE)
    if not staged:
        assert all(name in render.captured(found)['rules'] for name in names)
    assert found['synthesizer']['name'] == names[0]
    assert found['host']['name'] == 'Host'
    if staged:
        for role, stage, position in [('synthesizer', 'synthesis', store.SYNTHESIZER),
                                       ('host', 'host_summary', store.HOST)]:
            store.stage_record(number, {'topic': 0, 'stage': stage, 'position': position,
                                        'seat': found[role]['id'], 'name': found[role]['name'],
                                        'text': 'A useful conclusion.',
                                        'ideas': [{'id': 'I1', 'name': 'One idea', 'summary': 'A useful idea.'}]})
        digest = render.digest(number, 1)
        assert names[0] in digest and 'Host' in digest
        assert all(brand not in digest for brand in ('Opus', 'GPT-6', 'claude', 'codex', 'acp:'))


def test_registered_projects_require_the_naming_provider_instead_of_model_label_fallback(
        engine, project_folder, monkeypatch):
    monkeypatch.setattr(identity, 'provided', lambda folder, kind: [])
    with store.connect() as db:
        with pytest.raises(Stop, match='shared agent naming service'):
            identity.assign(db, project_folder, [CLAUDE])
        assert db.execute('SELECT COUNT(*) FROM profile_aliases').fetchone()[0] == 0


def test_unregistered_engine_also_requires_the_naming_provider(engine, monkeypatch):
    monkeypatch.setattr(identity, 'provided', lambda folder, kind: [])
    with store.connect() as db:
        with pytest.raises(Stop, match='shared agent naming service'):
            identity.assign(db, engine, [CLAUDE])
        assert db.execute('SELECT COUNT(*) FROM profile_aliases').fetchone()[0] == 0


def test_name_collisions_get_a_fresh_opaque_identity_and_remain_normal_names(
        engine, project_folder, monkeypatch):
    identities = iter([uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=3)])
    named = {uuid.UUID(int=1).hex: 'StableComet', uuid.UUID(int=2).hex: 'StableComet',
             uuid.UUID(int=3).hex: 'ActiveAgent'}
    monkeypatch.setattr(identity.uuid, 'uuid4', lambda: next(identities))
    monkeypatch.setattr(identity, 'provided', lambda folder, kind: [('fixture', named.__getitem__)])
    with store.connect() as db:
        found = identity.assign(db, project_folder, [CLAUDE, CODEX])
        assert [one['name'] for one in found] == ['StableComet', 'ActiveAgent']
        assert [one['identity'] for one in found] == [uuid.UUID(int=1).hex, uuid.UUID(int=3).hex]
        assert all(is_name(one['name']) for one in found)
