"""A store at layout 7 is updated to layout 8 when it is opened, never refused or thrown away, STORE-029, LAYER-025."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from metaform.data import StoreError
from metaform.data.session import open_store

pytestmark = [pytest.mark.kind("fixture"), pytest.mark.req("STORE-029", "LAYER-025")]

LAYOUT_7 = (Path(__file__).parent / 'fixtures' / 'store-v7.sql').read_text(encoding='utf-8')
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
    assert version == '8'
    assert [tuple(layer) for layer in layers] == [(INTAKE, 'intake', 'intake'), (MEMORY, 'memory', 'memory')]
    assert [tuple(row) for row in versions] == [(1, INTAKE, 'the first purpose'), (2, INTAKE, 'the refined purpose')]
    assert current == 2
    assert [tuple(row) for row in elements] == [('E1', 1), ('E2', 2)]
    assert 'correction_stack' not in tables
    assert broken == []
    backups = list((home / 'backups' / 'upgrade-8').glob('*/*/main.metaform.sqlite3'))
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
