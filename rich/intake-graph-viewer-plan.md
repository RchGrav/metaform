# Intake graph viewer implementation

## Agreed behavior

Offer an optional Graph view beside the workflow editor in the web GUI.
Display collected namespace objects and receiver-owned joins. Use Mermaid to lay out the named nodes and labeled edges. Smoothly move
between connected nodes with arrow keys, pan, zoom, and fit the whole drawing.
Reveal collected join detail when close; fade the base presentation when viewing
attached knowledge layers. Object positions remain stable during those view changes.
Selecting a graph object selects its editor reference; dragging it inserts that
reference into authored text. The displayed noun uses its stored name_length.
The rendered prompt preview continues to show the supplied context. A searchable
Insert object menu inserts at the remembered cursor position. The editor displays
authored text with noneditable inline object content; clicking that content opens
its properties and layer choices. The content comes from the same renderer used
to issue the prompt. The underlying definition retains typed bindings and authored
text, so an edit beside an object does not turn its contribution into copied prose.

This is presentation of collected data. Opening a layer for inspection changes
the view; selecting its contributions for an inserted reference controls the
prompt context. Canonical intake XML owns the input semantics, including the
provider's encounter function recorded in the receiving element's join.

## Implementation

- [x] XML import and graph projection in the external web feature. Preserve
  source fields, receiver ownership, names, refs, and explicit layer attachments.
  Cover canonical nested results and the repository's collected sample shapes.
- [x] Locally bundled Mermaid rendering with stable IDs and a camera controlled
  by the web feature. Add connected-node keyboard navigation, pointer pan/zoom,
  pinch support, interruptible eased transitions, overview/detail, and layer views.
- [x] Integrate the graph on the left of the existing editor. Add XML import,
  selection and drag/drop bindings; preserve the current workflow journey.
- [x] Verify XML fidelity, real SVG navigation and layer viewing, actual editor
  insertion, rendered prompt, and the existing workflow tests. Retain an isolated
  demonstration and screenshots.

## Workflow import and execution

Workflow documents roundtrip through Markdown, XML, and JSON with their local
section names, alias table, authored content, and object references preserved.
Nested XML response schemas remain structured nodes. This allows the editor and
execution surfaces to use the same document without losing the relationships
that give a step its inputs and outputs.

Workflow intake is itself a workflow: an agent interprets the imported document
and infers its steps, handoffs, and input/output relationships. It supplies the
local aliases that explain how source sections are used. Intake is a core workflow
definition maintained separately inside Metaform. Whether users can edit the
supplied definition remains open.

The conversion code preserves the source and supplied interpretation. Execution
must use that interpretation to deliver assigned steps through nonces, retain
their exact issued prompts and inputs, and record headed answers for subsequent
handoffs. The current workflow joins and chassis assignment tables still have
separate lifecycles; their shared nonce/MCP path remains implementation work.

## Shared interfaces

`graph_data.import_xml(namespace_store, xml_text)` imports collected XML and returns
counts and its source ID. `graph_data.project_graph(namespace_store)` returns:

```text
{nodes: [{id, namespace_address, name, name_length, details, contributions}],
 edges: [{id, source, target, label, ref, details, layer}],
 layers: [{id, name}]}
```

Contributions use `{ref, value, layer}`; refs retain project, namespace_address,
join_id, and revision. An edge's source is its receiving namespace and its target
is the provider named by that join. Layer IDs come from collected data.

`NamespaceGraph(container, {onSelect, onJoin, onInsert})` provides
`setData(graph)`, `focusNode(address)`, `setLayer(id)`, `fit()`, and `destroy()`.
The browser imports `/workflow-assets/namespace_graph.js`, which uses the locally
served `/workflow-assets/vendor/mermaid.min.js`. The graph sends namespace addresses
on drag using `application/x-metaform-object`, matching the current editor.

Web endpoints: GET `/api/workflows/graph?project=ID`; POST
`/api/workflows/import-xml` with `{project, xml}`. Both use the current project
namespace service. The authored XML is retained; conversion does not infer content.

## Live database and workflow updates

Rich requested a dynamically updating web view on 2026-09-18: objects and joins
should become browseable as agents record them, with workflow progress and
outputs visible as a run proceeds. This extends the current snapshot-based view;
the live connection is not implemented yet.

The proposed implementation sends change notifications to the authenticated
browser and refreshes the affected graph objects and workflow history from the
stored records. The storage remains the source of the displayed information.
The view preserves its camera position, selection, and unfinished authored text
when new records arrive. Existing inserted bindings retain their selected
revisions; newly available contributions can be inspected and selected explicitly.
Transport and integration with the shared workflow execution path remain to be
implemented alongside that path.
