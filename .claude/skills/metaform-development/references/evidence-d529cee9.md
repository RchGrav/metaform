E       AssertionError: assert '3' == 'all'
E         - all
E         + 3
src/metaform/modules/web/tests/test_web.py:8878: AssertionError

Then: >       assert not problems
E       AssertionError: assert not ['node not found: 7c60064f9071412cbe5d41aa2fcb4512', 'node not found: 7c60064f9071412cbe5d41aa2fcb4512', 'node not fou...

Memory observation written by the agent: "Gotcha: 3d-force-graph logs 'node not found: <id>' to the console for a link whose end is not in nodes; the namespace 'tree' link in addElements is now only drawn when its parent is shown."