    said = run('map', 'item', f'item={item}', cwd=mapped).stdout
    structured = json.loads(run('map', 'item', f'item={item}', '--json', cwd=mapped).stdout)