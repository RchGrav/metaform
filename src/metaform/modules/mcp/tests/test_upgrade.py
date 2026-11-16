"""Schema upgrades must not strand the host's live MCP connection, work 6efd6c19."""
import os
import shutil
import sys
from contextlib import closing
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from metaform import home as chassis_home
from metaform import sqlite
from metaform.data import Store

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('MCP-002'), pytest.mark.req('STORE-029')]


@pytest.fixture
def installation(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    layer = store.layer('intake', 'intake', 'The map.', kind='intake', ready=True, mutable=False, hideable=False)
    store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
    import metaform
    from metaform.sqlite import SCHEMA_VERSION
    copied = tmp_path / 'package' / 'metaform'
    shutil.copytree(Path(metaform.__file__).parent, copied, ignore=shutil.ignore_patterns('tests', '__pycache__'))
    parameters = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                       cwd=folder, env={**os.environ, 'METAFORM_HOME': str(home),
                                                        'PYTHONPATH': str(copied.parent)})
    database = chassis_home.project_folder('proj') / 'main.metaform.sqlite3'
    return folder, copied, parameters, database, SCHEMA_VERSION


def upgrade(installation, changed=True):
    _, copied, _, database, old = installation
    newer = str(int(old) + 1)
    if changed:
        source = copied / 'sqlite.py'
        source.write_text(source.read_text().replace(f"SCHEMA_VERSION = '{old}'", f"SCHEMA_VERSION = '{newer}'"))
        # Python bytecode validates whole-second mtimes, unlike the recovery fingerprint.
        state = source.stat()
        os.utime(source, (state.st_atime, state.st_mtime + 2))
    with closing(sqlite.connect(database)) as db:
        db.execute("UPDATE meta SET value=? WHERE key IN ('schema_version', 'compatible_from')", (newer,))


# One durable write an agent may make over the tool, MAP-050: a ticket is the person's to write, so the write under
# test is a tag on the intake layer, one op in the log.
REQUEST = {'layer': 'intake', 'tag': 'recovered'}
WRITTEN = "SELECT count(*) FROM ops WHERE data LIKE '%recovered%'"
