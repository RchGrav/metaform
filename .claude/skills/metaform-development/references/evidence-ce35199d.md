An earlier test run stopped before its teardown left these metaform processes running; they are now ended:
  1665511 /home/rich/metaform/.venv/bin/python3 -m metaform dispatch run 1bfb2357a40541e0a25ffdf00cad31bf claude system=true
  1767928 /home/rich/metaform/.venv/bin/python3 -m metaform.modules.web.server --bind 127.0.0.1 --port 25337 --nonce f9da54ee2f412f04
  1664721 /home/rich/metaform/.venv/bin/python3 -m metaform dispatch run 4be529a79dfa4be78241f87a9b1cc75c claude system=true
  1712890 /home/rich/metaform/.venv/bin/python3 -m metaform dispatch run a87e1b27090343b4a2d59c75e65f1ccc claude system=true
...
  1771768 /home/rich/metaform/.venv/bin/python3 -m metaform.modules.web.server --bind 127.0.0.1 --port 22258 --nonce 381ffc9e8b39714b
  1712890 /home/rich/metaform/.venv/bin/python3 -m metaform dispatch run a87e1b27090343b4a2d59c75e65f1ccc claude system=true