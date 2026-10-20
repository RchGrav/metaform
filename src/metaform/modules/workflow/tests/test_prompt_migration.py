"""Legacy store copies retain prompt identities, source text and saved revisions."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from metaform import loader
from metaform.data import Column, Node, Store, Table, Tables
from metaform.data import tables as storage
from metaform.modules.workflow import catalog
from metaform.modules.workflow.migration import MARKER, portable, prepare_store
from tests.storekit import small_map, store_file

pytestmark = [pytest.mark.req('CTX-080'), pytest.mark.kind('fixture')]
ADDRESS = 'prompt.workflow.migration'
TEXT = 'Keep logic in authored text exactly.\n{logic} := PARAM\n'


def legacy_copy(run, store, home):
    run('enable', 'workflow')
    small_map(store)
    layer = store.layer('procedures', 'workflow', 'Reusable workflow logic.', mutable=True, hideable=True, ready=True)
    owner = store.add_element(layer.name, 'workflow.migration', name_length=2)
    item = store.add_item(layer.name, Node('element', owner.id),
                          {'type': 'logic', 'name': 'review', 'content': TEXT}, refs=[('path', 'review.axiom')])
    old = Tables(version=6, compatible_from=1, tables=(
        Table('logic_versions', key=('logic_id', 'number'), columns=(
            Column('logic_id', required=True), Column('number', 'int', required=True),
            Column('name', required=True), Column('content', required=True)),
            on_remove=(('item', 'logic_id', 'delete'),)),))
    path = store_file(home, store)
    with sqlite3.connect(path) as db:
        storage._create(db, 'workflow', old.tables[0])
        storage._record(db, 'workflow', old.recorded('metaform'))
        db.executemany('INSERT INTO "workflow.logic_versions" VALUES (?,?,?,?)',
                       [(item.id, 1, 'review', TEXT), (item.id, 2, 'review', TEXT + 'RETURN TRUE\n')])
    source = path.with_name('legacy-source.sqlite3')
    with sqlite3.connect(path) as db, sqlite3.connect(source) as saved:
        db.backup(saved)
    # The registered working file is explicitly restored from the legacy source copy.
    with sqlite3.connect(source) as saved, sqlite3.connect(path) as db:
        saved.backup(db)
    return Store(store.project_id, module='workflow'), item, path, source


def test_legacy_copy_reads_saved_prompt_and_preserves_history(run, store, home):
    owned, item, path, source = legacy_copy(run, store, home)
    with sqlite3.connect(source) as db:
        old_ops = db.execute('SELECT * FROM ops ORDER BY seq').fetchall()
    prepare_store(owned)
    prompt, _ = catalog.lookup(owned, ADDRESS, 'review')
    assert (prompt.prompt_id, prompt.content, prompt.type) == (item.id, TEXT, 'prompt')
    assert [row['content'] for row in catalog.history(owned, ADDRESS, 'review', 'procedures')] == [
        TEXT, TEXT + 'RETURN TRUE\n']
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM ops ORDER BY seq LIMIT ?', (len(old_ops),)).fetchall() == old_ops
        assert db.execute('SELECT name FROM sqlite_master WHERE name="workflow.logic_versions"').fetchone() is None
        assert json.loads(db.execute('SELECT value FROM meta WHERE key="module:workflow"').fetchone()[0])[
            'compatible_from'] == 7
        before = db.execute('SELECT COUNT(*) FROM ops').fetchone()[0]
    prepare_store(owned)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM ops').fetchone()[0] == before
    with sqlite3.connect(source) as db:
        assert db.execute('SELECT * FROM ops ORDER BY seq').fetchall() == old_ops
        assert db.execute('SELECT COUNT(*) FROM "workflow.logic_versions"').fetchone()[0] == 2
    assert loader.get('workflow').module.tables.oldest == 7


def test_migration_rolls_back_and_retries(run, store, home, monkeypatch):
    owned, item, _path, _ = legacy_copy(run, store, home)
    from metaform.data.session import Tx
    emit = Tx.emit
    def fail(self, *args, **kwargs):
        emit(self, *args, **kwargs)
        raise RuntimeError('interrupted migration')
    monkeypatch.setattr(Tx, 'emit', fail)
    with pytest.raises(RuntimeError, match='interrupted migration'):
        prepare_store(owned)
    with owned.tables(write=False) as tx:
        assert tx.get('migrations', {'name': MARKER}) is None
    assert store.element('workflow.migration', raw=True).id
    monkeypatch.setattr(Tx, 'emit', emit)
    prepare_store(owned)
    assert catalog.lookup(owned, ADDRESS, 'review')[0].prompt_id == item.id


def test_concurrent_preparation_converts_once(run, store, home):
    owned, item, path, _ = legacy_copy(run, store, home)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: prepare_store(Store(owned.project_id, module='workflow')), range(2)))
    assert catalog.lookup(owned, ADDRESS, 'review')[0].prompt_id == item.id
    with sqlite3.connect(path) as db:
        changed = [json.loads(row[0]) for row in db.execute('SELECT data FROM ops WHERE id=?', (item.id,))]
    assert sum(json.loads(one.get('value', '{}')).get('type') == 'prompt' for one in changed) == 1


def test_portable_v1_preserves_prompt_text_and_user_fields():
    old = {'format': 'metaform-workflow:1', 'workflow': {'address': 'workflow.example'},
           'logic': [{'logic_id': 'stable', 'type': 'logic', 'name': 'review', 'content': TEXT}],
           'versions': {'stable': [{'number': 1, 'name': 'review', 'content': TEXT}]}}
    new = portable(old)
    assert new['prompt'][0] == {'prompt_id': 'stable', 'type': 'prompt', 'name': 'review', 'content': TEXT}
    assert new['versions'] == old['versions']
    assert old['format'] == 'metaform-workflow:1'


def test_legacy_run_frames_upgrade_without_rewriting_user_values(run, store, home):
    run('enable', 'workflow')
    small_map(store)
    from metaform.modules.workflow import runs
    path = storage.project_store(store.project_id, 'workflow')
    path.parent.mkdir(parents=True, exist_ok=True)
    old = Tables(version=6, compatible_from=1, tables=(runs.TABLE,))
    call = {'address': 'workflow.example', 'logic': {'type': 'logic', 'logic_id': 'kept',
            'name': 'review', 'content': TEXT}, 'arguments': {'logic': 'user data'}}
    frame = {'call': call, 'variables': {'logic': 'user variable'}}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.executemany('INSERT INTO meta VALUES (?,?)', [('schema_version', '1'), ('compatible_from', '1')])
        storage._create(db, 'workflow', runs.TABLE)
        storage._record(db, 'workflow', old.recorded('project'))
        db.execute('INSERT INTO "workflow.runs" (run_id,kind,state,created,seq,frames,branches,result) '
                   'VALUES (?,?,?,?,?,?,?,?)', ('legacy', 'call', 'running', '2026-10-01', 1,
                   json.dumps([frame]), json.dumps({'child': frame}), json.dumps({'logic': 'user result'})))
    with Store(store.project_id, module='workflow').tables(write=False) as tx:
        saved = tx.get('runs', {'run_id': 'legacy'})
    assert saved['frames'][0]['call']['prompt']['prompt_id'] == 'kept'
    assert saved['frames'][0]['call']['address'] == 'prompt.workflow.example'
    assert saved['frames'][0]['call']['prompt']['content'] == TEXT
    assert saved['frames'][0]['variables'] == {'logic': 'user variable'}
    assert saved['branches']['child']['call']['arguments'] == {'logic': 'user data'}
    assert saved['result'] == {'logic': 'user result'}


def test_address_conflict_preserves_both_records(run, store, home):
    owned, item, path, _ = legacy_copy(run, store, home)
    conflict = store.add_element('procedures', ADDRESS, name_length=2)
    with sqlite3.connect(path) as db:
        before = db.execute('SELECT * FROM ops ORDER BY seq').fetchall()
    from metaform.data import StoreError
    with pytest.raises(StoreError, match='would overwrite'):
        prepare_store(owned)
    assert store.element('workflow.migration', raw=True).id != conflict.id
    assert store.element(ADDRESS, raw=True).id == conflict.id
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM ops ORDER BY seq').fetchall() == before
    with owned.tables(write=False) as tx:
        assert tx.get('migrations', {'name': MARKER}) is None
        assert [one['prompt_id'] for one in tx.rows('prompt_versions', limit=0).results] == [item.id, item.id]
