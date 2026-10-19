E       AssertionError: the writer is not told of its own write
E       assert ['other', 'worker'] == ['other']
E         
E         Left contains one more item: 'worker'
# code comment written in memory/delivery.py:
    # a receipt changes no map and no one listens for it, so it is announced by no event: noted, it would strip the
    # write's own concerns, the sessions and kinds every other recipient filters on
    events.quietly(record_agent_context, ctx.folder, ctx.session, ...)