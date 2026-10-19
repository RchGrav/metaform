E       AttributeError: 'types.SimpleNamespace' object has no attribute 'typed'

Edit: if not typed:  # the person's words reach the agent as they wrote them  →  if not typed or compacted:  # the person's words reach the agent as they wrote them
Edit: compacted = self.recompacted  # the agent lost its context, so even the person's turn has it
Edit (test_user_control.py): queues = ('pending', 'prompt_versions', 'prompt_contexts', 'voiced', 'peered', 'worded') → queues = ('pending', 'prompt_versions', 'prompt_contexts', 'voiced', 'peered', 'worded', 'typed')