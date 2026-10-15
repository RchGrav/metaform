$PY -m metaform web start 2>&1 | tail -2; hold list | grep -c "metaform-web-27466"; $PY -m metaform web stop; echo "after stop: $(hold list | grep -c 'metaform-web-27466') call(s) in the ledger"
state: started ... 1 ... state: stopped
after stop: 0 call(s) in the ledger
memory: conftest.py sets it empty so tests never write Rich's hold ledger (before that line, test runs left failed metaform-web-<port> calls there).