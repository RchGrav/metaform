"""Run reconstructed web variants together, PROJ-019."""
from __future__ import annotations

import http.client
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
from urllib.parse import urlsplit

import pytest

from metaform.data import Store

pytestmark = [pytest.mark.req('PROJ-019'), pytest.mark.kind('real')]


def get(address, path='/'):
    url = urlsplit(address)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


@pytest.mark.parametrize('selection', [('v000001', 'v000002'), ('all',), ('v000002',)])
def test_variants_serve_their_reconstructed_content_on_separate_ports_and_interrupt_cleans_up(
        home, project_folder, tmp_path, selection):
    source = project_folder / 'index.html'
    source.write_text('<h1>origin</h1>', encoding='utf-8')
    (project_folder / 'shared.txt').write_bytes(b'shared baseline file')
    store = Store('proj')
    origin = store.add_origin()
    expected = {}
    for name in ('first', 'second'):
        worker = tmp_path / name
        shutil.copytree(project_folder, worker)
        content = f'<h1>{name}</h1>'.encode()
        (worker / 'index.html').write_bytes(content)
        variant = store.add_variant(worker)
        expected[variant.variant_id] = content
        shutil.rmtree(worker)  # Serving must use history, rather than the collected folder.
    if selection != ('all',):
        expected = {identifier: content for identifier, content in expected.items() if identifier in selection}
    source.write_text('<h1>new origin</h1>', encoding='utf-8')
    store.add_origin()  # An explicit origin still serves the earlier variants.
    temporary = tmp_path / 'serving'
    temporary.mkdir()
    process = subprocess.Popen(
        [sys.executable, '-m', 'metaform', 'web', 'serve', *selection, f'origin={origin.mform_id}'],
        cwd=project_folder,
        env={**os.environ, 'METAFORM_HOME': str(home), 'TMPDIR': str(temporary),
             'TMP': str(temporary), 'TEMP': str(temporary)},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
        **({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}),
    )
    lines = queue.Queue()

    def read_lines():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=read_lines, daemon=True).start()
    try:
        addresses = {}
        for _ in expected:
            line = lines.get(timeout=10)
            assert line is not None, process.stderr.read()
            identifier, address = line.split()
            addresses[identifier] = address
        assert addresses.keys() == expected.keys()
        assert len({urlsplit(address).port for address in addresses.values()}) == len(expected)
        for identifier, address in addresses.items():
            assert urlsplit(address).hostname == '127.0.0.1'
            assert get(address) == (200, expected[identifier])
            assert get(address, '/shared.txt') == (200, b'shared baseline file')
        assert source.read_text(encoding='utf-8') == '<h1>new origin</h1>'
        assert not (home / 'run' / 'web.json').exists()  # No Metaform GUI is launched or replaced.
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGINT)
        process.wait(timeout=10)
        assert process.returncode == 0, process.stderr.read()
        assert list(temporary.iterdir()) == []
        for address in addresses.values():
            with pytest.raises(OSError):
                get(address)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()
