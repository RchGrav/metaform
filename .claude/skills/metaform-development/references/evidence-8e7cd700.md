E       KeyError: 'results'

src/metaform/modules/roundtables/tests/test_roundtables.py:231: KeyError

Command that failed: ticket = json.loads(run('map', 'work', f'id={adopted["ticket"]}', '--json', cwd=folder).stdout)['results'][0]

Fixed by dropping the index: ticket = json.loads(run('map', 'work', f'id={adopted["ticket"]}', '--json', cwd=folder).stdout)
Then: 1 passed, 2 deselected in 8.62s