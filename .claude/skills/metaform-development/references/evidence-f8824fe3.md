+            # the project's room alone, for the person's own agent, which may take one place beyond the machine's
+            'own_room': max(0, 1 + max(0, limit - len(workers)) - len(called)),
+    if kind != 'worker' and (held['own_room'] if beyond else held['room']) <= 0:

E           metaform.modules.dispatch.Refused: Every agent slot is in use: dispatch_agents allows 5 agents besides the one you can always summon. Ask again when one is free.