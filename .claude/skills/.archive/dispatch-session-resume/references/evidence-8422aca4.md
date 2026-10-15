    module, ctx, held, started = stay_connected(dispatch, run, monkeypatch, {'load': True})
    ...
    """A system conversation recorded before sessions kept their origin: stay connected leaves it, telling the person
    once that Call resumes it, and their Call does; one stamped by another home is never resumed by Call."""
    -> docstring added to resumed_conversation: "`person` is the person's own Call or talk: it resumes a conversation recorded before sessions kept their origin, which nothing automatic does; one stamped by another home is never resumed here."