        """Every message from the agent, seen before the SDK reads it: a subagent's start and end, P016, which the
                # Connection observers run after transport.send succeeds, before any returned MCP call can read.
                # Queuing, resolving a resource or merely constructing a prompt never acknowledges delivery.
                self.context_delivered()
E       AssertionError: assert ('Understand t...\nFirst task.' == 'Understand t...\nFirst task.'
The test passes without the wait too, so it doesn't prove the ordering. Slowing the compaction's first step to make the race deterministic.
1 failed, 12 deselected in 2.66s
1 passed, 12 deselected in 2.66s