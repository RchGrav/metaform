    for base in Store(store.project_id).bases(limit=0).results:
        key, path = (store.project_id, base.id), home.store_file(store.project_id, base.name)
        if key in _CARRIED and _CARRIED[key] == _store_stamp(path):
            continue
        held = Store(store.project_id, base=base.id, module='dispatch')
        ...
        _CARRIED[key] = _store_stamp(path)

Agent note on the same ticket: "Stamp the -wal too: stores run PRAGMA journal_mode=WAL, so a late legacy `spend` write lands in the log and leaves the main file's mtime alone."