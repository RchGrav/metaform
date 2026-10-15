Error: The tables of dispatch this store holds conflict with what this dispatch needs: sessions.session_id is held as REAL and dispatch declares it TEXT. Nothing of dispatch was changed, and the rest of Metaform works as before.
sqlite3.IntegrityError: datatype mismatch
git -C /home/rich/metaform show HEAD:src/metaform/data/tables.py > /tmp/claude-03f8/old/src/metaform/data/tables.py