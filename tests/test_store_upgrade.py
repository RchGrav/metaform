"""A store at layout 7 is updated to layout 8 when it is opened, never refused or thrown away, STORE-029, LAYER-025."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from metaform.data import StoreError
from metaform.data.session import open_store
from metaform.data.upgrade import EF_REASON
from metaform.sqlite import SCHEMA_VERSION

pytestmark = [pytest.mark.kind("fixture"), pytest.mark.req("STORE-029", "LAYER-025")]

LAYOUT_7 = (Path(__file__).parent / 'fixtures' / 'store-v7.sql').read_text(encoding='utf-8')


def renamed(row: dict) -> dict:
    """A join row as layout 13 reads it: the join type purpose is require, Rich 2026-10-02."""
    return {**row, 'type': 'require'} if row.get('type') == 'purpose' else row
INTAKE, CORRECTION, MEMORY = 'L-intake', 'L-correction', 'L-memory'


def layout_7_store(path: Path) -> None:
    """An intake with one element and one join, and a correction layer that changed the join's purpose."""
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_7)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '7');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake-20261001T125705Z-2edfa0', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01'),
                 ('{CORRECTION}', 'M', 'refine-main-20261001', 'map', 'v', 0, 1, 'correction', '2026-10-02', '2026-10-02'),
                 ('{MEMORY}', 'M', 'memory', 'memory', 'v', 1, 1, 'memory', '2026-10-02', '2026-10-02');
        INSERT INTO layer_sources(layer_id, source_layer_id) VALUES ('{CORRECTION}', '{INTAKE}');
        INSERT INTO correction_stack(position, layer_id) VALUES (1, '{CORRECTION}');
        INSERT INTO types(address) VALUES ('code'), ('code.engine');
        INSERT INTO element_ids(element_id) VALUES ('E1'), ('E2');
        INSERT INTO elements(row, element_id, layer_id, address) VALUES (1, 'E1', '{INTAKE}', 'code'),
                                                                         (2, 'E2', '{INTAKE}', 'code.engine');
        INSERT INTO current_elements(element_id, row, address) VALUES ('E1', 1, 'code'), ('E2', 2, 'code.engine');
        INSERT INTO address_elements(address, element_id) VALUES ('code', 'E1'), ('code.engine', 'E2');
        INSERT INTO join_ids(join_id) VALUES ('J1');
        INSERT INTO joins(row, join_id, layer_id, receiver, provider, purpose)
          VALUES (1, 'J1', '{INTAKE}', 'E1', 'E2', 'the first purpose');
        INSERT INTO joins(row, join_id, layer_id, receiver, provider, purpose, op, reason)
          VALUES (2, 'J1', '{CORRECTION}', 'E1', 'E2', 'the refined purpose', 'change', 'it was wrong');
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J1', 2, 'E1', 'E2');
    """)
    db.commit()
    db.close()


def test_a_layout_7_store_opens_at_layout_8_with_its_corrections_folded_into_the_intake_layer(home: Path,
                                                                                              tmp_path: Path):
    path = tmp_path / 'main.metaform.sqlite3'
    layout_7_store(path)
    with open_store(path, write=False) as db:
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        layers = db.execute('SELECT layer_id, name, kind FROM layers ORDER BY created').fetchall()
        versions = db.execute("SELECT row, layer_id, purpose FROM joins WHERE join_id='J1' ORDER BY row").fetchall()
        current = db.execute("SELECT row FROM current_joins WHERE join_id='J1'").fetchone()[0]
        elements = db.execute('SELECT element_id, row FROM current_elements ORDER BY element_id').fetchall()
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        broken = db.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION
    assert [tuple(layer) for layer in layers] == [(INTAKE, 'intake', 'intake'), (MEMORY, 'memory', 'memory')]
    assert [tuple(row) for row in versions] == [(1, INTAKE, 'the first purpose'), (2, INTAKE, 'the refined purpose')]
    assert current == 2
    assert [tuple(row) for row in elements] == [('E1', 1), ('E2', 2)]
    assert 'correction_stack' not in tables
    assert broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    kept = sqlite3.connect(backups[0])
    assert kept.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '7'
    assert kept.execute('SELECT COUNT(*) FROM layers').fetchone()[0] == 3
    kept.close()


def test_a_store_older_than_layout_7_is_refused_and_left_unchanged(home: Path, tmp_path: Path):
    path = tmp_path / 'main.metaform.sqlite3'
    layout_7_store(path)
    db = sqlite3.connect(path)
    db.execute("UPDATE meta SET value='6' WHERE key='schema_version'")
    db.commit()
    db.close()
    before = path.read_bytes()
    with pytest.raises(StoreError, match='schema version 6'):
        with open_store(path, write=False):
            pass
    assert path.read_bytes() == before


def test_a_layout_9_store_moves_an_elements_name_and_a_joins_ifd_out_of_extra_into_their_own_fields(home, tmp_path):
    """Rich, 2026-10-01: extra should be gone; a name goes anywhere there is a namespace and name length, and the IFD is
    a field of the join. Layout 10 moves each out of the extra it was kept in."""
    path = tmp_path / 'main.metaform.sqlite3'
    layout_7_store(path)
    db = sqlite3.connect(path)
    db.executescript("""
        UPDATE elements SET extra='{"name": "kitchen timer daemon", "colour": "red"}' WHERE element_id='E1';
        UPDATE joins SET extra='{"ifd": "receives"}' WHERE row=1;
    """)
    db.commit()
    db.close()
    with open_store(path, write=False) as opened:
        assert opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == SCHEMA_VERSION
        element = opened.execute("SELECT name, extra FROM elements WHERE element_id='E1'").fetchone()
        joined = opened.execute('SELECT ifd, extra FROM joins WHERE row=1').fetchone()
    assert (element[0], element[1]) == ('kitchen timer daemon', '{"colour":"red"}')
    assert (joined[0], joined[1]) == ('receives', None)


LAYOUT_10 = (Path(__file__).parent / 'fixtures' / 'store-v10.sql').read_text(encoding='utf-8')


def layout_10_store(path: Path) -> None:
    """A layout 10 store whose join and subtype join carry a perspective and every other field of a join."""
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_10)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '10');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01');
        INSERT INTO types(address) VALUES ('code'), ('code.engine'), ('code.loop.tick');
        INSERT INTO element_ids(element_id) VALUES ('E1'), ('E2'), ('E3');
        INSERT INTO elements(row, element_id, layer_id, address) VALUES (1, 'E1', '{INTAKE}', 'code'),
                                                                         (2, 'E2', '{INTAKE}', 'code.engine'),
                                                                         (3, 'E3', '{INTAKE}', 'code.loop.tick');
        INSERT INTO current_elements(element_id, row, address) VALUES ('E1', 1, 'code'), ('E2', 2, 'code.engine'),
                                                                      ('E3', 3, 'code.loop.tick');
        INSERT INTO address_elements(address, element_id) VALUES ('code', 'E1'), ('code.engine', 'E2'),
                                                                 ('code.loop.tick', 'E3');
        INSERT INTO join_ids(join_id) VALUES ('J1'), ('J2');
        INSERT INTO joins(row, join_id, layer_id, type, parent, receiver, provider, name, purpose, ef, perspective, ifd,
                          relation, verb, observation, non_goal, extra, op, reason, evidence)
          VALUES (1, 'J1', '{INTAKE}', 'purpose', NULL, 'E1', 'E2', 'engine', 'Run it.', 'Runs each frame.', 'Encounter',
                  'receives', 'runs the code each frame', 'runs', 'One loop.', 'No threads.', '{{"colour": "red"}}', 'add',
                  NULL, NULL),
                 (2, 'J2', '{INTAKE}', 'subtype', 'J1', NULL, 'E3', 'tick', 'Keep time.', 'Ticks.', 'Function', 'sends',
                  'ticks once a frame', 'ticks', 'One interrupt.', NULL, NULL, 'change', 'it was wrong', 'the code');
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J1', 1, 'E1', 'E2');
        INSERT INTO current_subtypes(join_id, row, parent, provider) VALUES ('J2', 2, 'J1', 'E3');
        INSERT INTO refs(owner, owner_row, position, key, value) VALUES ('join', 1, 0, 'path', 'src/engine.c');
    """)
    db.commit()
    db.close()


@pytest.mark.req('MAP-020')
def test_a_layout_10_store_opens_with_no_perspective_and_every_other_field_of_every_join_kept(home: Path, tmp_path: Path):
    """Rich, 2026-10-02: "drop perspective drop the duality , EF infers fine". The update takes the joins' perspective
    column out, keeps every other field of every join and backs the store up first."""
    path = tmp_path / 'main.metaform.sqlite3'
    layout_10_store(path)
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    before = [renamed({key: row[key] for key in row.keys() if key not in ('perspective', 'relation', 'observation')})
              for row in raw.execute('SELECT * FROM joins ORDER BY row')]
    raw.close()
    with open_store(path, write=False) as db:
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        columns = [row[1] for row in db.execute('PRAGMA table_info(joins)')]
        after = [{key: row[key] for key in row.keys()} for row in db.execute('SELECT * FROM joins ORDER BY row')]
        current = (db.execute('SELECT join_id, row FROM current_joins').fetchall(),
                   db.execute('SELECT join_id, row, parent FROM current_subtypes').fetchall())
        refs = db.execute("SELECT owner, owner_row, key, value FROM refs").fetchall()
        broken = db.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION
    assert 'perspective' not in columns
    assert after[:2] == before  # layout 12 adds each join's newest version, its ef the old relation, MAP-020
    assert [row['ef'] for row in after[2:]] == ['runs the code each frame', 'ticks once a frame']
    moving = ('row', 'ef', 'op', 'reason', 'evidence')
    for base, newest in zip(before, after[2:]):
        assert {key: value for key, value in newest.items() if key not in moving} == \
            {key: value for key, value in base.items() if key not in moving}
    assert [[tuple(row) for row in rows] for rows in current] == [[('J1', 3)], [('J2', 4, 'J1')]]
    assert [tuple(row) for row in refs] == [('join', 1, 'path', 'src/engine.c'), ('join', 3, 'path', 'src/engine.c')]
    assert broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    kept = sqlite3.connect(backups[0])
    assert kept.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '10'
    assert kept.execute('SELECT perspective FROM joins ORDER BY row').fetchall() == [('Encounter',), ('Function',)]
    kept.close()


LAYOUT_11 = (Path(__file__).parent / 'fixtures' / 'store-v11.sql').read_text(encoding='utf-8')


def layout_11_store(path: Path) -> None:
    """A layout 11 store holding a join refined once, a subtype join, a removed join, a ticket, a question and a
    memory item, with every field of a join filled."""
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_11)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '11');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01'),
                 ('{MEMORY}', 'M', 'memory', 'memory', 'v', 1, 1, 'memory', '2026-10-02', '2026-10-02');
        INSERT INTO types(address) VALUES ('code'), ('code.engine'), ('code.loop.tick'), ('code.old');
        INSERT INTO element_ids(element_id) VALUES ('E1'), ('E2'), ('E3'), ('E4');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE'), (2, 'E2', '{INTAKE}', 'code.engine', 1, 'engine', 'SE'),
                 (3, 'E3', '{INTAKE}', 'code.loop.tick', 2, 'tick', 'SE'), (4, 'E4', '{INTAKE}', 'code.old', 1, NULL, 'SE');
        INSERT INTO current_elements(element_id, row, address, role)
          VALUES ('E1', 1, 'code', 'DE'), ('E2', 2, 'code.engine', 'SE'), ('E3', 3, 'code.loop.tick', 'SE'),
                 ('E4', 4, 'code.old', 'SE');
        INSERT INTO address_elements(address, element_id)
          VALUES ('code', 'E1'), ('code.engine', 'E2'), ('code.loop.tick', 'E3'), ('code.old', 'E4');
        INSERT INTO join_ids(join_id) VALUES ('J1'), ('J2'), ('J3');
        INSERT INTO identities(id, kind) VALUES ('J1', 'join'), ('J2', 'join'), ('J3', 'join');
        INSERT INTO joins(row, join_id, layer_id, type, parent, receiver, provider, name, purpose, ef, ifd,
                          relation, verb, observation, non_goal, extra, op, reason, evidence)
          VALUES (1, 'J1', '{INTAKE}', 'purpose', NULL, 'E1', 'E2', 'engine', 'Run it.', 'Runs the frame loop.', 'receives',
                  'runs the code each frame', 'runs', 'One loop.', 'No threads.', '{{"colour": "red"}}', 'add', NULL, NULL),
                 (2, 'J1', '{INTAKE}', 'purpose', NULL, 'E1', 'E2', 'engine', 'Run it now.', 'Runs each frame in C.',
                  'receives', 'runs the code each frame', 'runs', 'One loop, in engine.c.', 'No threads.',
                  '{{"colour": "red"}}', 'change', 'it was wrong', 'the code'),
                 (3, 'J2', '{INTAKE}', 'subtype', 'J1', NULL, 'E3', 'tick', 'Keep time.', 'Ticks from the timer ISR.',
                  'sends', 'ticks once a frame', 'ticks', 'One interrupt.', NULL, NULL, 'add', NULL, NULL),
                 (4, 'J3', '{INTAKE}', 'purpose', NULL, 'E1', 'E4', NULL, 'Gone.', 'Did a thing.', NULL,
                  'did a thing', 'did', 'Removed.', NULL, NULL, 'add', NULL, NULL),
                 (5, 'J3', '{INTAKE}', 'purpose', NULL, 'E1', 'E4', NULL, 'Gone.', 'Did a thing.', NULL,
                  'did a thing', 'did', 'Removed.', NULL, NULL, 'remove', 'not there', NULL);
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J1', 2, 'E1', 'E2');
        INSERT INTO current_subtypes(join_id, row, parent, provider) VALUES ('J2', 3, 'J1', 'E3');
        INSERT INTO refs(owner, owner_row, position, key, value)
          VALUES ('join', 1, 0, 'path', 'src/engine.c'), ('join', 2, 0, 'path', 'src/engine.c'),
                 ('join', 2, 1, 'spec', 'MAP-020'), ('join', 3, 0, 'path', 'src/tick.c');
        INSERT INTO item_ids(item_id, layer_id) VALUES ('I1', '{MEMORY}');
        INSERT INTO items(row, item_id, layer_id, target_kind, target_id, value)
          VALUES (1, 'I1', '{MEMORY}', 'join', 'J1', '"the loop drifts"');
        INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id)
          VALUES ('I1', 1, '{MEMORY}', 'join', 'J1');
        INSERT INTO work(work_id, target_kind, target_id, condition, note, created)
          VALUES ('W1', 'join', 'J1', 'broken', 'drifts', '2026-10-02');
        INSERT INTO messages(message_id, target_kind, target_id, kind, text, created)
          VALUES ('Q1', 'join', 'J2', 'question', 'Is the tick one second?', '2026-10-02');
    """)
    db.commit()
    db.close()


@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-029')
def test_a_layout_11_store_opens_with_ef_holding_the_old_relation_and_no_relation_or_observation(home: Path,
                                                                                                 tmp_path: Path):
    """Rich, 2026-10-02: "observation was not my design. I didn't ask for observation"; "Neither was relation"; "by
    placing permanent implementation details into the fucking metaform, you're fucking it all up". Every join and
    subtype join takes its old relation text as its ef, as its newest version, so its earlier versions keep the old
    ef; then the relation and observation columns are removed. The old observation text is kept only in the backup
    made first. Every element, join id, ticket, memory and question stays."""
    path = tmp_path / 'main.metaform.sqlite3'
    layout_11_store(path)
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    before = [renamed({key: row[key] for key in row.keys() if key not in ('relation', 'observation')})
              for row in raw.execute('SELECT * FROM joins ORDER BY row')]
    raw.close()
    with open_store(path, write=False) as db:
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        columns = [row[1] for row in db.execute('PRAGMA table_info(joins)')]
        rows = [{key: row[key] for key in row.keys()} for row in db.execute('SELECT * FROM joins ORDER BY row')]
        current = (db.execute('SELECT join_id, row FROM current_joins').fetchall(),
                   db.execute('SELECT join_id, row, parent FROM current_subtypes').fetchall())
        refs = db.execute("SELECT owner_row, position, key, value FROM refs WHERE owner='join' "
                          'ORDER BY owner_row, position').fetchall()
        elements = db.execute('SELECT element_id, row FROM current_elements ORDER BY element_id').fetchall()
        kept = (db.execute('SELECT work_id, target_id FROM work').fetchall(),
                db.execute('SELECT message_id, target_id FROM messages').fetchall(),
                db.execute('SELECT item_id, target_id FROM current_items').fetchall())
        join_ids = (db.execute('SELECT join_id FROM join_ids ORDER BY join_id').fetchall(),
                    db.execute("SELECT id FROM identities WHERE kind='join' ORDER BY id").fetchall())
        texts = [str(value) for table, in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                 for row in db.execute(f'SELECT * FROM "{table}"').fetchall() for value in row if isinstance(value, str)]
        broken = db.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION
    assert [[row[0] for row in held] for held in join_ids] == [['J1', 'J2', 'J3'], ['J1', 'J2', 'J3']]
    for observation in ('One loop.', 'One loop, in engine.c.', 'One interrupt.', 'Removed.'):
        assert not any(observation in text for text in texts), observation  # kept only in the backup
    assert 'relation' not in columns and 'observation' not in columns and 'ef' in columns and 'verb' in columns
    assert rows[:5] == before  # every earlier version is kept, the old ef in it
    newest = {row['join_id']: row for row in rows[5:]}
    assert sorted(newest) == ['J1', 'J2']  # the removed join gets no new version
    assert (newest['J1']['ef'], newest['J2']['ef']) == ('runs the code each frame', 'ticks once a frame')
    for join_id, base in (('J1', before[1]), ('J2', before[2])):
        assert {key: value for key, value in newest[join_id].items() if key not in ('row', 'ef', 'op', 'reason',
                                                                                    'evidence')} == \
            {key: value for key, value in base.items() if key not in ('row', 'ef', 'op', 'reason', 'evidence')}
        assert (newest[join_id]['op'], newest[join_id]['reason']) == ('change', EF_REASON)
    assert [[tuple(row) for row in held] for held in current] == [
        [('J1', newest['J1']['row'])], [('J2', newest['J2']['row'], 'J1')]]
    assert [tuple(ref) for ref in refs] == [
        (1, 0, 'path', 'src/engine.c'), (2, 0, 'path', 'src/engine.c'), (2, 1, 'spec', 'MAP-020'), (3, 0, 'path', 'src/tick.c'),
        *sorted([(newest['J1']['row'], 0, 'path', 'src/engine.c'), (newest['J1']['row'], 1, 'spec', 'MAP-020'),
                 (newest['J2']['row'], 0, 'path', 'src/tick.c')])]
    assert [tuple(row) for row in elements] == [('E1', 1), ('E2', 2), ('E3', 3), ('E4', 4)]
    assert [[tuple(row) for row in table] for table in kept] == [[('W1', 'J1')], [('Q1', 'J2')], [('I1', 'J1')]]
    assert broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    copy = sqlite3.connect(backups[0])
    assert copy.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '11'
    assert copy.execute('SELECT relation, observation FROM joins WHERE row=3').fetchone() == (
        'ticks once a frame', 'One interrupt.')
    copy.close()


LAYOUT_12 = (Path(__file__).parent / 'fixtures' / 'store-v12.sql').read_text(encoding='utf-8')


@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-029')
def test_a_layout_12_store_opens_with_every_purpose_join_typed_require_and_nothing_else_changed(home: Path,
                                                                                                tmp_path: Path):
    """Rich, 2026-10-02: "the join type for requirements is require, rename it across the board from purpose". Every
    version of every join of type purpose reads as type require; a subtype join keeps its type, and every other field
    and row is kept. The store is backed up first."""
    path = tmp_path / 'main.metaform.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_12)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '12');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01');
        INSERT INTO types(address) VALUES ('code'), ('code.engine'), ('code.loop.tick');
        INSERT INTO element_ids(element_id) VALUES ('E1'), ('E2'), ('E3');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE'), (2, 'E2', '{INTAKE}', 'code.engine', 1, 'engine', 'SE'),
                 (3, 'E3', '{INTAKE}', 'code.loop.tick', 2, 'tick', 'SE');
        INSERT INTO current_elements(element_id, row, address, role)
          VALUES ('E1', 1, 'code', 'DE'), ('E2', 2, 'code.engine', 'SE'), ('E3', 3, 'code.loop.tick', 'SE');
        INSERT INTO address_elements(address, element_id)
          VALUES ('code', 'E1'), ('code.engine', 'E2'), ('code.loop.tick', 'E3');
        INSERT INTO join_ids(join_id) VALUES ('J1'), ('J2');
        INSERT INTO identities(id, kind) VALUES ('J1', 'join'), ('J2', 'join');
        INSERT INTO joins(row, join_id, layer_id, type, parent, receiver, provider, name, purpose, ef, ifd, verb,
                          non_goal, extra, op, reason, evidence)
          VALUES (1, 'J1', '{INTAKE}', 'purpose', NULL, 'E1', 'E2', 'engine', 'Run it.', 'runs the loop', 'receives',
                  'runs', 'No threads.', NULL, 'add', NULL, NULL),
                 (2, 'J1', '{INTAKE}', 'purpose', NULL, 'E1', 'E2', 'engine', 'Run it now.', 'runs each frame',
                  'receives', 'runs', 'No threads.', NULL, 'change', 'it was wrong', NULL),
                 (3, 'J2', '{INTAKE}', 'subtype', 'J1', NULL, 'E3', 'tick', 'Keep time.', 'ticks once a frame', 'sends',
                  'ticks', NULL, NULL, 'add', NULL, NULL);
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J1', 2, 'E1', 'E2');
        INSERT INTO current_subtypes(join_id, row, parent, provider) VALUES ('J2', 3, 'J1', 'E3');
    """)
    db.commit()
    db.row_factory = sqlite3.Row
    before = [dict(row) for row in db.execute('SELECT * FROM joins ORDER BY row')]
    db.close()
    with open_store(path, write=False) as opened:
        version = opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        after = [{key: row[key] for key in row.keys()} for row in opened.execute('SELECT * FROM joins ORDER BY row')]
        broken = opened.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION == '16'
    assert [row['type'] for row in after] == ['require', 'require', 'subtype']
    assert after == [renamed(row) for row in before]
    assert broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    copy = sqlite3.connect(backups[0])
    assert copy.execute("SELECT type FROM joins ORDER BY row").fetchall() == [('purpose',), ('purpose',), ('subtype',)]


@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-029')
def test_a_join_with_no_relation_keeps_its_ef_through_the_layout_12_update(home: Path, tmp_path: Path):
    """Relation goes to ef only where there is a relation: a join with none keeps its ef and gets no new version, since
    an empty relation carries nothing to move."""
    path = tmp_path / 'main.metaform.sqlite3'
    layout_11_store(path)
    db = sqlite3.connect(path)
    db.executescript(f"""
        INSERT INTO join_ids(join_id) VALUES ('J4');
        INSERT INTO identities(id, kind) VALUES ('J4', 'join');
        INSERT INTO joins(row, join_id, layer_id, type, parent, receiver, provider, name, purpose, ef, ifd,
                          relation, verb, observation, non_goal, extra, op, reason, evidence)
          VALUES (6, 'J4', '{INTAKE}', 'purpose', NULL, 'E2', 'E3', NULL, 'Tick.', 'ticks the engine', 'receives',
                  NULL, 'ticks', NULL, NULL, NULL, 'add', NULL, NULL);
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J4', 6, 'E2', 'E3');
    """)
    db.commit()
    db.close()
    with open_store(path, write=False) as opened:
        rows = opened.execute("SELECT row, ef FROM joins WHERE join_id='J4' ORDER BY row").fetchall()
        current = opened.execute("SELECT row FROM current_joins WHERE join_id='J4'").fetchone()
    assert [tuple(row) for row in rows] == [(6, 'ticks the engine')] and current[0] == 6


LAYOUT_13 = (Path(__file__).parent / 'fixtures' / 'store-v13.sql').read_text(encoding='utf-8')


@pytest.mark.req('VIEW-040')
@pytest.mark.req('STORE-042')
def test_a_layout_13_store_opens_with_every_ticket_kept_and_no_glyph_column(home: Path, tmp_path: Path):
    """A store at layout 13 is backed up and opens at the current layout with every field of every ticket kept. The
    glyph column layout 14 added is gone again at layout 15, since a ticket's glyph is the map module's own field,
    STORE-045 and BASE-046."""
    path = tmp_path / 'main.metaform.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_13)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '13');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01');
        INSERT INTO types(address) VALUES ('code');
        INSERT INTO element_ids(element_id) VALUES ('E1');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE');
        INSERT INTO current_elements(element_id, row, address, role) VALUES ('E1', 1, 'code', 'DE');
        INSERT INTO address_elements(address, element_id) VALUES ('code', 'E1');
        INSERT INTO work(row, work_id, target_kind, target_id, condition, note, task, held, reviewed, created, done,
                         resolution, steps, steps_done, taken, taken_by, position)
          VALUES (1, 'W1', 'element', 'E1', 'missing', 'n', 'build it', 1, 0, '2026-10-01', NULL, NULL, NULL, 0, NULL,
                  NULL, 2),
                 (2, 'W2', 'element', 'E1', 'broken', NULL, 'fix it', 0, 1, '2026-10-02', '2026-10-03', 'fixed', 3, 3,
                  '2026-10-02', 'codex', 0);
        INSERT INTO work_steps(work_id, number, said, at) VALUES ('W2', 1, 'Traced it.', '2026-10-02');
    """)
    db.commit()
    db.row_factory = sqlite3.Row
    before = [dict(row) for row in db.execute('SELECT * FROM work ORDER BY row')]
    db.close()
    with open_store(path, write=False) as opened:
        version = opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        after = [{key: row[key] for key in row.keys()} for row in opened.execute('SELECT * FROM work ORDER BY row')]
        steps = opened.execute('SELECT work_id, number, said FROM work_steps').fetchall()
        broken = opened.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION == '16'
    assert after == before
    assert [tuple(row) for row in steps] == [('W2', 1, 'Traced it.')] and broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    copy = sqlite3.connect(backups[0])
    assert copy.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '13'
    copy.close()


LAYOUT_14 = (Path(__file__).parent / 'fixtures' / 'store-v14.sql').read_text(encoding='utf-8')


@pytest.mark.req('VIEW-040')
@pytest.mark.req('STORE-042')
@pytest.mark.req('STORE-045')
@pytest.mark.req('BASE-046')
def test_a_layout_14_store_opens_with_every_ticket_kept_and_the_glyph_column_dropped(home: Path, tmp_path: Path):
    """Layout 15, ticket 90430bba: a ticket's agent glyph is a feature's field, so it belongs in a module table keyed
    by the work id, and the chassis work table holds no glyph. A store at layout 14 is backed up, and the work table
    loses its glyph column; every other field of every ticket is kept, and the backup still holds the glyphs."""
    path = tmp_path / 'main.metaform.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_14)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '14');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01');
        INSERT INTO types(address) VALUES ('code');
        INSERT INTO element_ids(element_id) VALUES ('E1');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE');
        INSERT INTO current_elements(element_id, row, address, role) VALUES ('E1', 1, 'code', 'DE');
        INSERT INTO address_elements(address, element_id) VALUES ('code', 'E1');
        INSERT INTO work(row, work_id, target_kind, target_id, condition, note, task, held, reviewed, created, done,
                         resolution, steps, steps_done, taken, taken_by, position, glyph)
          VALUES (1, 'W1', 'element', 'E1', 'missing', 'n', 'build it', 1, 0, '2026-10-01', NULL, NULL, NULL, 0, NULL,
                  NULL, 2, 'moth'),
                 (2, 'W2', 'element', 'E1', 'broken', NULL, 'fix it', 0, 1, '2026-10-02', '2026-10-03', 'fixed', 3, 3,
                  '2026-10-02', 'codex', 0, NULL);
        INSERT INTO work_links(work_id, number, target_kind, target_id) VALUES ('W1', 0, 'element', 'E1');
        INSERT INTO work_steps(work_id, number, said, at) VALUES ('W2', 1, 'Traced it.', '2026-10-02');
    """)
    db.commit()
    db.row_factory = sqlite3.Row
    before = [dict(row) for row in db.execute('SELECT * FROM work ORDER BY row')]
    db.close()
    with open_store(path, write=False) as opened:
        version = opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        columns = [row[1] for row in opened.execute('PRAGMA table_info(work)')]
        after = [{key: row[key] for key in row.keys()} for row in opened.execute('SELECT * FROM work ORDER BY row')]
        links = opened.execute('SELECT work_id, number, target_id FROM work_links').fetchall()
        steps = opened.execute('SELECT work_id, number, said FROM work_steps').fetchall()
        broken = opened.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION == '16'
    assert 'glyph' not in columns
    assert after == [{key: value for key, value in row.items() if key != 'glyph'} for row in before]
    assert [tuple(row) for row in links] == [('W1', 0, 'E1')]
    assert [tuple(row) for row in steps] == [('W2', 1, 'Traced it.')] and broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    copy = sqlite3.connect(backups[0])
    assert copy.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '14'
    assert copy.execute('SELECT work_id, glyph FROM work ORDER BY row').fetchall() == [('W1', 'moth'), ('W2', None)]
    copy.close()


LAYOUT_15 = (Path(__file__).parent / 'fixtures' / 'store-v15.sql').read_text(encoding='utf-8')


@pytest.mark.req('LAYER-021')
@pytest.mark.req('STORE-015')
def test_a_layout_15_store_opens_with_every_item_kept_and_both_flags_false(home: Path, tmp_path: Path):
    """Layout 16, LAYER-021, Rich 2026-10-03, D91 and D92: a knowledge item carries read_first and always_show. A
    store at layout 15 is backed up, and the items table gains both columns, false on every item; nothing else
    changes."""
    path = tmp_path / 'main.metaform.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_15)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '15');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01'),
                 ('L2', 'M', 'critic', 'test', 'v', 1, 1, 'layer', '2026-10-02', '2026-10-02');
        INSERT INTO types(address) VALUES ('code');
        INSERT INTO element_ids(element_id) VALUES ('E1');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE');
        INSERT INTO current_elements(element_id, row, address, role) VALUES ('E1', 1, 'code', 'DE');
        INSERT INTO address_elements(address, element_id) VALUES ('code', 'E1');
        INSERT INTO identities(id, kind) VALUES ('E1', 'element'), ('I1', 'item');
        INSERT INTO item_ids(item_id, layer_id) VALUES ('I1', 'L2');
        INSERT INTO items(row, item_id, layer_id, target_kind, target_id, value, extra)
          VALUES (1, 'I1', 'L2', 'element', 'E1', '"first"', NULL),
                 (2, 'I1', 'L2', 'element', 'E1', '"second"', '{{"seen": 1}}');
        INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id) VALUES ('I1', 2, 'L2', 'element', 'E1');
    """)
    db.commit()
    db.row_factory = sqlite3.Row
    before = [dict(row) for row in db.execute('SELECT * FROM items ORDER BY row')]
    db.close()
    with open_store(path, write=False) as opened:
        version = opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        after = [{key: row[key] for key in row.keys()} for row in opened.execute('SELECT * FROM items ORDER BY row')]
        current = opened.execute('SELECT item_id, row FROM current_items').fetchall()
        broken = opened.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION == '16'
    assert after == [{**row, 'read_first': 0, 'always_show': 0} for row in before]
    assert [tuple(row) for row in current] == [('I1', 2)] and broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
