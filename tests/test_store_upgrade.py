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


LAYOUT_19_JOIN = ('row', 'join_id', 'layer_id', 'type', 'receiver', 'purpose', 'ef', 'ifd', 'op', 'reason', 'evidence')


def renamed(row: dict) -> dict:
    """A join row as the current layout reads it: from layout 18 the join type require is purpose again, and from
    layout 19 a join holds only Rich's fields, Rich 2026-10-04."""
    row = {key: row.get(key) for key in LAYOUT_19_JOIN}
    return {**row, 'type': 'purpose'} if row.get('type') == 'require' else row


def layer_names(db) -> set[str]:
    """The layers a store holds: a layout 19 update makes the sources layer and no other, Rich 2026-10-04: "I want all
    of that fucikiong  shit gone"."""
    return {str(row[0]) for row in db.execute('SELECT name FROM layers')}


def element_names(db) -> dict[str, str | None]:
    """Each current element's name: a join's or a subtype join's name is the name of the element it holds after a
    layout 19 update, Rich 2026-10-04: "the name on the join was the name for the element"."""
    return {str(row[0]): row[1] for row in db.execute(
        'SELECT c.element_id, e.name FROM current_elements c JOIN elements e ON e.row = c.row ORDER BY c.element_id')}


def sources(db) -> list[tuple]:
    """The items of the sources layer, each with its node and its refs, in order."""
    return [tuple(row) for row in db.execute(
        "SELECT i.target_kind, i.target_id, r.key, r.value FROM current_items c JOIN items i ON i.row = c.row "
        "JOIN layers l ON l.layer_id = i.layer_id JOIN refs r ON r.owner = 'item' AND r.owner_row = i.row "
        "WHERE l.name = 'sources' ORDER BY i.row, r.position")]
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
        element = opened.execute("SELECT name FROM elements WHERE element_id='E1'").fetchone()
        joined = opened.execute('SELECT ifd FROM joins WHERE row=1').fetchone()
        layers = layer_names(opened)
        anywhere = [row[0] for row in opened.execute('SELECT value FROM items') if 'colour' in str(row[0])]
    assert element[0] == 'kitchen timer daemon'
    assert joined[0] == 'receives'
    # What else the extra held is not kept in the store, layout 19, Rich 2026-10-04; the backup made first holds it.
    assert 'intake details' not in layers and anywhere == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    kept = sqlite3.connect(backups[0])
    assert 'colour' in kept.execute("SELECT extra FROM elements WHERE element_id='E1'").fetchone()[0]
    kept.close()


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
    before = [renamed(dict(row)) for row in raw.execute('SELECT * FROM joins WHERE parent IS NULL ORDER BY row')]
    raw.close()
    with open_store(path, write=False) as db:
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        columns = [row[1] for row in db.execute('PRAGMA table_info(joins)')]
        after = [{key: row[key] for key in row.keys()} for row in db.execute('SELECT * FROM joins ORDER BY row')]
        current = db.execute('SELECT join_id, row FROM current_joins').fetchall()
        held = db.execute('SELECT element_id FROM join_elements WHERE join_row=3 ORDER BY position').fetchall()
        refs = sources(db)
        layers = layer_names(db)
        names = element_names(db)
        broken = db.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION
    assert 'perspective' not in columns
    # the join's name is the element's it holds, and so is the subtype join's; nothing else of them is kept
    assert names == {'E1': None, 'E2': 'engine', 'E3': 'tick'}
    assert 'intake details' not in layers
    assert after[:1] == before  # layout 12 adds each join's newest version, its ef the old relation, MAP-020
    assert [row['ef'] for row in after[1:]] == ['runs the code each frame']  # the subtype join is gone, layout 19
    moving = ('row', 'ef', 'op', 'reason', 'evidence')
    assert {key: value for key, value in after[1].items() if key not in moving} == \
        {key: value for key, value in before[0].items() if key not in moving}
    assert [tuple(row) for row in current] == [('J1', 3)] and [row[0] for row in held] == ['E2', 'E3']
    assert refs == [('element', 'E2', 'path', 'src/engine.c')]  # the join's refs are the element's it holds
    assert broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    kept = sqlite3.connect(backups[0])
    assert kept.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '10'
    assert kept.execute('SELECT perspective FROM joins ORDER BY row').fetchall() == [('Encounter',), ('Function',)]
    assert kept.execute('SELECT verb, non_goal, extra FROM joins WHERE row=1').fetchone() == (
        'runs', 'No threads.', '{"colour": "red"}')  # what the store no longer keeps, the backup holds
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
    before = [renamed(dict(row)) for row in raw.execute('SELECT * FROM joins WHERE parent IS NULL ORDER BY row')]
    raw.close()
    with open_store(path, write=False) as db:
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        columns = [row[1] for row in db.execute('PRAGMA table_info(joins)')]
        rows = [{key: row[key] for key in row.keys()} for row in db.execute('SELECT * FROM joins ORDER BY row')]
        current = db.execute('SELECT join_id, row FROM current_joins').fetchall()
        refs = sources(db)
        layers = layer_names(db)
        names = element_names(db)
        elements = db.execute('SELECT element_id, row FROM current_elements ORDER BY element_id').fetchall()
        kept = (db.execute('SELECT work_id, target_id FROM work').fetchall(),
                db.execute('SELECT message_id, target_id FROM messages').fetchall(),
                db.execute('SELECT item_id, target_id FROM current_items WHERE layer_id=?', (MEMORY,)).fetchall())
        join_ids = (db.execute('SELECT join_id FROM join_ids ORDER BY join_id').fetchall(),
                    db.execute("SELECT id FROM identities WHERE kind='join' ORDER BY id").fetchall())
        texts = [str(value) for table, in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                 for row in db.execute(f'SELECT * FROM "{table}"').fetchall() for value in row if isinstance(value, str)]
        broken = db.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION
    # each element keeps its own name, and nothing else of the joins' old fields is kept, layout 19
    assert names == {'E1': 'code', 'E2': 'engine', 'E3': 'tick', 'E4': None} and 'intake details' not in layers
    assert [[row[0] for row in held] for held in join_ids] == [['J1', 'J2', 'J3'], ['J1', 'J2', 'J3']]
    for observation in ('One loop.', 'One loop, in engine.c.', 'One interrupt.', 'Removed.'):
        assert not any(observation in text for text in texts), observation  # kept only in the backup
    assert 'relation' not in columns and 'observation' not in columns and 'ef' in columns and 'verb' not in columns
    assert rows[:4] == before  # every earlier version is kept, the old ef in it; the subtype join is gone, layout 19
    newest = {row['join_id']: row for row in rows[4:]}
    assert sorted(newest) == ['J1']  # the removed join gets no new version
    assert newest['J1']['ef'] == 'runs the code each frame'
    assert {key: value for key, value in newest['J1'].items() if key not in ('row', 'ef', 'op', 'reason', 'evidence')} \
        == {key: value for key, value in before[1].items() if key not in ('row', 'ef', 'op', 'reason', 'evidence')}
    assert (newest['J1']['op'], newest['J1']['reason']) == ('change', EF_REASON)
    assert [tuple(row) for row in current] == [('J1', newest['J1']['row'])]
    # the current versions' refs, each at the element the join or subtype join held, one sources item per element
    assert refs == [('element', 'E2', 'path', 'src/engine.c'), ('element', 'E2', 'spec', 'MAP-020'),
                    ('element', 'E3', 'path', 'src/tick.c')]
    assert [tuple(row) for row in elements] == [('E1', 1), ('E2', 2), ('E3', 3), ('E4', 4)]
    # what was at the subtype join is at the element it held, layout 19
    assert [[tuple(row) for row in table] for table in kept] == [[('W1', 'J1')], [('Q1', 'E3')], [('I1', 'J1')]]
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
def test_a_layout_12_store_opens_with_every_purpose_join_still_typed_purpose_and_nothing_else_changed(home: Path,
                                                                                                      tmp_path: Path):
    """Rich, 2026-10-04: "well I think we need to go back to purpose for semantics". Every version of every join of
    type purpose still reads as type purpose; a subtype join keeps its type, and every other field and row is kept.
    The store is backed up first."""
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
        layers = layer_names(opened)
        names = element_names(opened)
        held = opened.execute("SELECT e.element_id FROM join_elements e JOIN current_joins c ON c.row = e.join_row "
                              "WHERE c.join_id='J1' ORDER BY e.position").fetchall()
    assert version == SCHEMA_VERSION == '19'
    assert [row[0] for row in held] == ['E2', 'E3']
    # each element keeps its own name; the joins' verb, non_goal and the subtype join's own fields are not kept
    assert names == {'E1': 'code', 'E2': 'engine', 'E3': 'tick'} and 'intake details' not in layers
    assert [row['type'] for row in after] == ['purpose', 'purpose']  # the subtype join is gone, layout 19
    assert after == [renamed(row) for row in before if row['parent'] is None]
    assert broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1
    copy = sqlite3.connect(backups[0])
    assert copy.execute("SELECT type FROM joins ORDER BY row").fetchall() == [('purpose',), ('purpose',), ('subtype',)]
    assert copy.execute('SELECT verb, non_goal FROM joins WHERE row=2').fetchone() == ('runs', 'No threads.')


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
    assert version == SCHEMA_VERSION == '19'
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
    assert version == SCHEMA_VERSION == '19'
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
    assert version == SCHEMA_VERSION == '19'
    assert after == [{**row, 'read_first': 0, 'always_show': 0} for row in before]
    assert [tuple(row) for row in current] == [('I1', 2)] and broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1


LAYOUT_16 = (Path(__file__).parent / 'fixtures' / 'store-v16.sql').read_text(encoding='utf-8')


@pytest.mark.req('MAP-054')
@pytest.mark.req('STORE-010')
def test_a_layout_16_store_opens_with_every_join_kept_and_naming_no_element(home: Path, tmp_path: Path):
    """Layout 17, MAP-054, Rich 2026-10-02, D112: a promoted join names the element written for it by its address.
    A store at layout 16 is backed up, and the joins table gains its element column, empty on every join; nothing
    else changes."""
    path = tmp_path / 'main.metaform.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_16)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '16');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01');
        INSERT INTO types(address) VALUES ('code'), ('code.b');
        INSERT INTO element_ids(element_id) VALUES ('E1'), ('E2');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE'), (2, 'E2', '{INTAKE}', 'code.b', 1, 'b', 'SE');
        INSERT INTO current_elements(element_id, row, address, role)
          VALUES ('E1', 1, 'code', 'DE'), ('E2', 2, 'code.b', 'SE');
        INSERT INTO address_elements(address, element_id) VALUES ('code', 'E1'), ('code.b', 'E2');
        INSERT INTO join_ids(join_id) VALUES ('J1');
        INSERT INTO identities(id, kind) VALUES ('E1', 'element'), ('E2', 'element'), ('J1', 'join');
        INSERT INTO joins(row, join_id, layer_id, type, receiver, provider, name, purpose, ef, ifd, verb, non_goal)
          VALUES (1, 'J1', '{INTAKE}', 'require', 'E1', 'E2', 'b', 'Need b.', 'serves b', 'receives', 'serves', 'n'),
                 (2, 'J1', '{INTAKE}', 'require', 'E1', 'E2', 'b', 'Need b now.', 'serves b', 'receives', 'serves', 'n');
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J1', 2, 'E1', 'E2');
    """)
    db.commit()
    db.row_factory = sqlite3.Row
    before = [dict(row) for row in db.execute('SELECT * FROM joins ORDER BY row')]
    db.close()
    with open_store(path, write=False) as opened:
        version = opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        after = [{key: row[key] for key in row.keys()} for row in opened.execute('SELECT * FROM joins ORDER BY row')]
        current = opened.execute('SELECT join_id, row FROM current_joins').fetchall()
        broken = opened.execute('PRAGMA foreign_key_check').fetchall()
    assert version == SCHEMA_VERSION == '19'
    assert after == [renamed(row) for row in before]
    assert [row['type'] for row in after] == ['purpose', 'purpose']  # require is purpose again, Rich 2026-10-04
    assert [tuple(row) for row in current] == [('J1', 2)] and broken == []
    backups = list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/main.metaform.sqlite3'))
    assert len(backups) == 1


@pytest.mark.req('STORE-029')
@pytest.mark.req('STORE-010')
def test_a_layout_16_store_opens_in_richs_shape_with_nothing_it_held_lost(home: Path, tmp_path: Path):
    """Rich, 2026-10-04: "we are reverting the data shape back to my original original design, no added field
    nothing...   that can all go to a knowledge layer"; "the name on the join was the name for the element"; "I want
    all of that fucikiong  shit gone". A join holds its provider, and its subtype join's element is held by it too; a
    join's name is the name of the element it holds when that element has none; each element's refs, with those of the
    joins that held it, are its one item of the sources layer; a ticket, a message and an item at the subtype join move
    to its element. The current version is what moves. Nothing else of the old shape is kept in the store, and the copy
    kept first holds all of it. The metaform keeps only Rich's fields."""
    path = tmp_path / 'main.metaform.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(LAYOUT_16)
    db.executescript(f"""
        INSERT INTO meta(key, value) VALUES ('schema_version', '16');
        INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, created, ready)
          VALUES ('{INTAKE}', 'M', 'intake', 'intake', 'v', 0, 0, 'intake', '2026-10-01', '2026-10-01'),
                 ('{MEMORY}', 'M', 'memory', 'memory', 'v', 1, 1, 'memory', '2026-10-01', '2026-10-01');
        INSERT INTO types(address) VALUES ('code'), ('code.b'), ('code.c'), ('code.loop'), ('code.loop.tick');
        INSERT INTO element_ids(element_id) VALUES ('E1'), ('E2'), ('E3'), ('E4');
        INSERT INTO identities(id, kind) VALUES ('E1', 'element'), ('E2', 'element'), ('E3', 'element'),
                                                ('E4', 'element'), ('J1', 'join'), ('J2', 'join'), ('J3', 'join'),
                                                ('I1', 'item');
        INSERT INTO elements(row, element_id, layer_id, address, name_length, name, role, extra)
          VALUES (1, 'E1', '{INTAKE}', 'code', 1, 'code', 'DE', '{{"kept": "aside"}}'),
                 (2, 'E2', '{INTAKE}', 'code.b', 1, 'b', 'SE', NULL),
                 (3, 'E3', '{INTAKE}', 'code.loop.tick', 2, 'tick', 'SE', NULL),
                 (4, 'E4', '{INTAKE}', 'code.c', 1, NULL, 'NE', NULL);
        INSERT INTO current_elements(element_id, row, address, role)
          VALUES ('E1', 1, 'code', 'DE'), ('E2', 2, 'code.b', 'SE'), ('E3', 3, 'code.loop.tick', 'SE'),
                 ('E4', 4, 'code.c', 'NE');
        INSERT INTO address_elements(address, element_id)
          VALUES ('code', 'E1'), ('code.b', 'E2'), ('code.loop.tick', 'E3'), ('code.c', 'E4');
        INSERT INTO join_ids(join_id) VALUES ('J1'), ('J2'), ('J3');
        INSERT INTO joins(row, join_id, layer_id, type, parent, receiver, provider, name, purpose, ef, ifd, verb, non_goal,
                          extra, op)
          VALUES (1, 'J1', '{INTAKE}', 'require', NULL, 'E1', 'E2', 'old bee', 'Need b once.', 'served b', 'sends',
                  'served', 'No d.', NULL, 'add'),
                 (2, 'J2', '{INTAKE}', 'subtype', 'J1', NULL, 'E3', NULL, 'Keep time.', 'ticks once a frame', 'sends',
                  'ticks', NULL, NULL, 'add'),
                 (3, 'J1', '{INTAKE}', 'require', NULL, 'E1', 'E2', 'bee', 'Need b.', 'serves b', 'receives', 'serves',
                  'No c.', NULL, 'change'),
                 (4, 'J3', '{INTAKE}', 'require', NULL, 'E1', 'E4', 'cee', 'Need c.', 'serves c', 'receives', NULL,
                  NULL, '{{"weight": 2}}', 'add');
        INSERT INTO current_joins(join_id, row, receiver, provider) VALUES ('J1', 3, 'E1', 'E2'), ('J3', 4, 'E1', 'E4');
        INSERT INTO current_subtypes(join_id, row, parent, provider) VALUES ('J2', 2, 'J1', 'E3');
        INSERT INTO refs(owner, owner_row, position, key, value)
          VALUES ('element', 1, 0, 'path', 'src/code'), ('join', 1, 0, 'path', 'src/old.c'),
                 ('join', 3, 0, 'path', 'src/b.c'), ('join', 2, 0, 'path', 'src/tick.c');
        INSERT INTO item_ids(item_id, layer_id) VALUES ('I1', '{MEMORY}');
        INSERT INTO items(row, item_id, layer_id, target_kind, target_id, value)
          VALUES (1, 'I1', '{MEMORY}', 'join', 'J2', '"ticks drift"');
        INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id) VALUES ('I1', 1, '{MEMORY}', 'join', 'J2');
        INSERT INTO work(work_id, target_kind, target_id, condition, created) VALUES ('W1', 'join', 'J2', 'broken', '2026-10-01');
        INSERT INTO messages(message_id, target_kind, target_id, kind, created) VALUES ('Q1', 'join', 'J2', 'question', '2026-10-01');
    """)
    db.commit()
    elements_before = db.execute('SELECT element_id, address, name_length, name, role FROM elements ORDER BY row').fetchall()
    db.close()
    with open_store(path, write=False) as opened:
        q = lambda sql, *args: [tuple(row) for row in opened.execute(sql, args)]  # noqa: E731
        version = q("SELECT value FROM meta WHERE key='schema_version'")[0][0]
        elements_after = q('SELECT element_id, address, name_length, name, role FROM elements ORDER BY row')
        held = {join_id: [row[0] for row in q('SELECT e.element_id FROM join_elements e JOIN current_joins c '
                                              'ON c.row = e.join_row WHERE c.join_id=? ORDER BY e.position', join_id)]
                for join_id in ('J1', 'J3')}
        current = q('SELECT c.join_id, j.type, j.receiver, j.purpose, j.ef, j.ifd FROM current_joins c '
                    'JOIN joins j ON j.row = c.row ORDER BY c.join_id')
        joins = q('SELECT join_id FROM joins ORDER BY row')
        layer = {name: layer_id for layer_id, name in q('SELECT layer_id, name FROM layers')}
        layers = layer_names(opened)
        items = q('SELECT i.layer_id, i.target_kind, i.target_id, i.value, r.key, r.value FROM current_items c '
                  "JOIN items i ON i.row = c.row LEFT JOIN refs r ON r.owner = 'item' AND r.owner_row = i.row "
                  'ORDER BY i.row, r.position')
        moved = q('SELECT target_kind, target_id FROM work UNION ALL SELECT target_kind, target_id FROM messages')
        refs = q("SELECT owner FROM refs WHERE owner <> 'item'")
        broken = q('PRAGMA foreign_key_check')
    assert version == SCHEMA_VERSION == '19'
    # J1's name is not E2's, which has its own; J3's is E4's, which had none; the rest of every element is kept
    assert elements_after == [tuple(row) if row[0] != 'E4' else (*row[:3], 'cee', row[4]) for row in elements_before]
    assert held == {'J1': ['E2', 'E3'], 'J3': ['E4']}
    assert current == [('J1', 'purpose', 'E1', 'Need b.', 'serves b', 'receives'),
                       ('J3', 'purpose', 'E1', 'Need c.', 'serves c', 'receives')]
    assert 'J2' not in [row[0] for row in joins]  # the subtype join is gone, its element held by J1
    sources = layer['sources']
    assert 'intake details' not in layers  # nothing of the old shape is kept beside the metaform
    # The current version is what moves: J1's refs from its change row, at E2, the element J1 holds.
    assert items == [
        (MEMORY, 'element', 'E3', '"ticks drift"', None, None),
        (sources, 'element', 'E1', '"code"', 'path', 'src/code'),
        (sources, 'element', 'E2', '"code.b"', 'path', 'src/b.c'),
        (sources, 'element', 'E3', '"code.loop.tick"', 'path', 'src/tick.c'),
    ]
    assert moved == [('element', 'E3'), ('element', 'E3')]
    assert refs == [] and broken == []
    # Earlier versions' fields and refs remain in the copy kept first.
    backups = list((home / 'backups' / 'upgrade-19').glob(f'*/{tmp_path.name}/main.metaform.sqlite3'))
    assert len(backups) == 1
    kept = sqlite3.connect(backups[0])
    assert kept.execute("SELECT value FROM refs WHERE owner='join' AND owner_row=1").fetchall() == [('src/old.c',)]
    # what the store no longer keeps, the copy holds: J1's name, verb and non_goal, J3's extra, E1's extra, and the
    # subtype join's own purpose and ef
    assert kept.execute('SELECT name, verb, non_goal FROM joins WHERE row=3').fetchone() == ('bee', 'serves', 'No c.')
    assert kept.execute('SELECT extra FROM joins WHERE row=4').fetchone() == ('{"weight": 2}',)
    assert kept.execute("SELECT extra FROM elements WHERE element_id='E1'").fetchone() == ('{"kept": "aside"}',)
    assert kept.execute('SELECT purpose, ef FROM joins WHERE row=2').fetchone() == ('Keep time.', 'ticks once a frame')
    kept.close()
