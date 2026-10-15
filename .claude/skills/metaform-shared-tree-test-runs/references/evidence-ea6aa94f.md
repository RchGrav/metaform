  1917971 /home/rich/metaform/.venv/bin/python3 -m metaform.modules.web.server --bind 127.0.0.1 --port 21704 --nonce 7815a8058ac7651f
..............................................                           [100%]
46 passed in 100.22s (0:01:40)

Running pytest in the shared tree ends other sessions' test web servers: conftest treats them as leftovers of an earlier run and kills them.