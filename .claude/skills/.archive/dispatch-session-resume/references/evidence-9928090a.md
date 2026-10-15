        for _ in range(2):
            assert module.stay_connected(ctx, dispatch.store) == {'legacy': 's1', 'next': 'metaform dispatch system'}
    assert started == [], 'nothing automatic resumes it'