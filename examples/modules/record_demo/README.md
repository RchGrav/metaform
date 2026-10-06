# Record demo: compatibility record example

This small package demonstrates the compatibility record API through Metaform's
public plugin contract. The canonical template is [showcase](../showcase/README.md),
which teaches namespace objects, owned joins and exact references. Record demo
remains a separately loadable example for existing record API consumers, outside
the three current teaching roles.

Run these commands from the checkout with its environment active:

```sh
metaform --root /tmp/metaform-demo projects add sample "$PWD"
metaform --root /tmp/metaform-demo modules load examples/modules/record_demo
metaform --root /tmp/metaform-demo --project sample record-demo data.report --text 'A real record'
metaform --root /tmp/metaform-demo --project sample fingerprint data.source README.md
metaform --root /tmp/metaform-demo --project sample records data.report --provenance
metaform --root /tmp/metaform-demo settings set record_demo label '"My report"'
metaform --root /tmp/metaform-demo modules unload record_demo
```

`record` runs in a worker thread and `fingerprint` runs asynchronously. Both
write a project-owned record with its producer, then publish an event. The
subscriber writes an observation with its own producer linked to the publisher.
The stored records and saved setting survive unloading and reloading the module.

The chassis owns the database, context, scheduler, and contributed commands.
Module code supplies operations, complete Click commands, settings, and event
subscriptions. `start()` and `stop()` hooks can acquire and release module
resources. Importing the package defines its capabilities; work happens when
operations or hooks execute. In-process Python modules share the host's privileges.

This example's `joins` dictionary remains inside the receiving record. It is
empty because recording text and a file digest does not infer an OP/EF relation.
Layer inference and workflow definitions are later consumers of these services.

See [the public contract](../../../docs/plugin-api.md) for lifecycle, submission,
settings, and event semantics.
