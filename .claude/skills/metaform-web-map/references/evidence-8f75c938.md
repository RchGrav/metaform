cd /home/rich/metaform/src/metaform/modules/web/page/app && for f in figures/ask.js figures/eyes.js; do node --input-type=module --check < $f && echo "$f ok"; done
figures/ask.js ok
figures/eyes.js ok

The last-click browser test's queued mascot step marks the system agent's session 'starting' by rewriting /api/dispatch-sessions, asks through the mascot about the join, clicks the alarm node, and then expects the join in the prompt once the session reads as running.