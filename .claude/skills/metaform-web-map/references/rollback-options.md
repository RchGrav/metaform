# Rolling back to an earlier message

Three routes were found. None is chosen yet.

1. Standard ACP session/fork. It copies the session as it is now. ForkSessionRequest has only session_id, cwd, additional_directories, mcp_servers and field_meta. No from-this-message field exists.

2. Claude's adapter, claude-agent-acp 0.89.1 (dist/fork-session.js). It forks at an earlier message when the request carries _meta.jetbrains.air.fork with version 1, a messageId, a messageFingerprint and a messageOccurrence. The field is a JetBrains AIR vendor extension. It conflicts with the standard-ACP-only rule (acp-standard-signals-only) unless the person allows the exception.

3. Restart from here. Open a new session and send the thread up to the chosen message as text. Works for any agent. The agent loses its own tool results and reasoning, and must re-read what it needs.

The person has to choose one of these, or wait for ACP to standardise the feature. The Escape and Up keys do not depend on this choice.
