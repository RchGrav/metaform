    settings.assign('report', False, tmp_path, glue=True)
    assert cli.main(['config', '--show', f'folder={tmp_path}']) == 0
    for key in ('debug', 'report', 'layers', 'modules'):