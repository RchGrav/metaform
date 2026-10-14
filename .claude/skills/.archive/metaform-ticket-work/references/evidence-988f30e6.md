Before writing any held task I'll check the two claimed gaps myself.

{"command":"sed -n 20,30p src/metaform/relay.py; echo ---; sed -n 110,120p src/metaform/relay.py; echo ---; sed -n 90,104p src/metaform/modules/workflow/__init__.py; echo ---; grep -n \"listen\\|Listener\" src/metaform/loader.py | head; echo ---; sed -n 1605,1626p src/metaform/modules/web/server.py","description":"Verify event bus gap evidence"}

Confirmed both gaps: the loader never tracks listeners (only async tasks), and only `map.changed` actually crosses processes via relay.py, with `signal.raised` only reaching other processes indirectly through dispatch.