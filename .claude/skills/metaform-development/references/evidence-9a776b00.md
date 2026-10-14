    sys.stdin = io.TextIOWrapper(io.BytesIO((given or '').encode('utf-8')), encoding='utf-8')
    sys.stdout, sys.stderr = out, err
Agent: "The fixture swaps `sys.stderr` during the call, so the trace went into the captured output. Printing that captured output instead."
Memory note: "(2) An in-process CLI call can reload metaform.modules.mcp.a2a_out, so a test's monkeypatched a2a_out.TRANSPORT does not reach the subscription inside run(...)."