rep("""            after = max((int(one['seq']) for one in self.events), default=0)
            with Store('proj', module='roundtables').tables(write=False) as tx:
                fresh = [dict(one) for one in tx.rows('events', limit=0).results if int(one['seq']) > after]
""", """            seen = {(one['table_id'], int(one['seq'])) for one in self.events}  # each table counts its own seq
            with Store('proj', module='roundtables').tables(write=False) as tx:
                fresh = [dict(one) for one in tx.rows('events', limit=0).results
                         if (one['table_id'], int(one['seq'])) not in seen]
""")
rep("""    held = serve(monkeypatch, stubbed(pace=0.4))
    try:
        for stop in ('sigterm', 'stop-all'):""", """    held = serve(monkeypatch, stubbed(pace=2.0))  # slow enough that each stop lands while the table discusses
    try:
        for stop in ('sigterm', 'stop-all'):""")
Result: AssertionError: the follower ended it, the table did not