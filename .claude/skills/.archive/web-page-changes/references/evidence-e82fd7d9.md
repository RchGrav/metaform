edit('app/settings/screen.js', '''import {AUTO, readAutostart, renderAgents} from '/page/app/agents/dispatch.js';''',
'''import {AUTO, PROMPT_WORDS, readAutostart, renderAgents} from '/page/app/agents/dispatch.js';''')

E           playwright._impl._errors.TimeoutError: Page.select_option: Timeout 10000ms exceeded.
Call log:
E             - waiting for locator("#settings .setrow[data-key=\"dispatch_prompts\"] select")

cd /home/rich/metaform/src/metaform/modules/web/page/app/settings && cp screen.js /tmp/screen.mine.js && python3 - <<'EOF'
... cd /home/rich/metaform && timeout 300 uv run pytest -m browser -n 0 src/metaform/modules/web/tests/test_web.py -k "test_the_admin_sets_how_agent_prompts" -q 2>&1 | tail -2; cp /tmp/screen.mine.js src/metaform/modules/web/page/app/settings/screen.js; grep -c "PROMPT_WORDS, readAutostart" src/metaform/modules/web/page/app/settings/screen.js