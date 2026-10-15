source = Path(restarter.__file__)
    kept = source.stat()
    os.utime(source, ns=(kept.st_atime_ns, kept.st_mtime_ns + 1_000_000_000))  # a code change, by its stamp
    try:
        assert json.loads(run('web', 'restart', '--json').stdout)['state'] == 'restarted'
    finally:
        os.utime(source, ns=(kept.st_atime_ns, kept.st_mtime_ns))