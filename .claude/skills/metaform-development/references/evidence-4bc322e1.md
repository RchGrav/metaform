  agent.start('hold', 'system=true', FAKE_ACP_LOAD='1')
    session = agent.session().extra['session_id']
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:  # ended sessions the person never stopped
        for index, how in enumerate(('it failed: x', 'cancelled by the person')):
            tx.insert('sessions', {'session_id': f'other-ended-{index}', 'work_id': f'other-work-{index}',
                                   'agent': 'claude', 'state': 'ended', 'how': how,
                                   'started': '2026-10-01T00:00:00Z', 'seq': index + 1})
Memory note recorded on code.interface.graphical: "Resume and the .stopped-agent class are only on stopped-by-person rows, because dispatch-resume refuses failed sessions with a 400. A failed or ended session shows Continue (.again) in the thread bar."