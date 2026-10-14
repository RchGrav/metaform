{"type":"assistant","text":"Writing the dispatch side now: 14 per-option settings, a reader that replaces `parse_options`, and a one-time migration gated by a marker file in the Metaform home."}
Switching the migration to the public `home.save`/`home.clear` calls so caches and change notices stay right, and wiring it to dispatch's start hook.
Completion missed module settings because the hook never ran discovery. Fixing that:
Restart needed: Metaform processes started before the change (MCP server on 7434, live runners) still read the removed dispatch_agent_options.