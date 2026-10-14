src/metaform/cli.py:1038:    if verb.caution and not parsed.confirm:
tests/test_cli.py:1016: run('map', 'activate', 'main', cwd=project)  →  run('map', 'activate', 'main', '--confirm', cwd=project)
src/metaform/modules/map/tests/test_map.py: made = j(run, 'collapse', 'fresh', cwd=mapped)  →  made = j(run, 'collapse', 'fresh', '--confirm', cwd=mapped)
Step 6: "map add-base, activate and collapse now carry caution=BASE_SWITCH (map/__init__.py)... The CLI enforces caution too (cli.py:1038), so four existing CLI calls now pass --confirm"