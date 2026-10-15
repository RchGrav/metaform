I noticed the fourth touch—a second write a second later—was marking the watch dirty even though nothing actually changed, since the start event matched the same identity and offset. I'll update the logic so it only marks dirty when the position actually moves.

Replacement in src/metaform/modules/autoticket/watch.py:
-            self.dirty = True
-            kind = event[0]
+            kind = event[0]
+            # something to write: a line read, a drop or a reconnect, or a file started at another place than written
+            self.dirty = self.dirty or kind != 'file' or (event[1], event[2]) != (held.identity, held.offset)