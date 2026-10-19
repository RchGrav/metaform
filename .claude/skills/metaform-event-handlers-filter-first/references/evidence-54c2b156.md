>       assert len(session.pending) == 1, 'Four notices for one node during a turn must wait as one turn, not four.'
E       AssertionError: Four notices for one node during a turn must wait as one turn, not four.
E       assert 4 == 1
        # the agent reads code.store.memory in the turn in flight, so the notice is stale when its turn comes
>       assert sent(monkeypatch, session) == [], 'A notice read empty by its turn must cost no turn.'
E       AssertionError: A notice read empty by its turn must cost no turn.
E       assert ['3 memories; 3 unread (a).'] == []
>       assert sent(monkeypatch, session) == [], f'A notice must start no turn once the {answered}.'
E       AssertionError: A notice must start no turn once the ticket done.
E       assert ['3 memories; 3 unread (a).'] == []