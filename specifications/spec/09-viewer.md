# Web GUI and viewer

This section specifies Metaform's one web GUI, user global, and its first view, the viewer: a floating 3D graph of the metaform and its layers, and a 2D drill-in view of one object and its joins.
The GUI is built after the intake and debug system is stable and the fix pass is complete.

### VIEW-001 Metaform has one web GUI, and the viewer is its first view
- Requirement: One module, `web`, holds Metaform's single web GUI for the user: one server and one app that serve every project registered in the home. The viewer, the floating 3D graph of a project's active metaform and the 2D graph of one object in the left window, is the GUI's first view. Every view a person uses in a browser is part of this one GUI; no module runs a web server of its own.
- What this means: The GUI is user global, not per project: it lists every registered project and switches between them and their metaforms. It owns no data. Three things stay outside it. Web variants of a user's artifact are the artifact running, not Metaform's GUI, so each is served on its own port, PROJ-019; the GUI can list and launch them. MCP stays on stdio, one server per AI tool, MCP-002, since agents, not people, use it. The terminal settings screen stays for people in a terminal, CLI-026; the GUI reads and writes the same settings through the same settings module. The deferral of the workflow editor, the rulebook and the browser terminal under D44 still stands; when they come, they are views of this GUI. How a module adds a view to it is open, question 3.
- Why: One GUI gives one address for everything Metaform shows a person, one process to start and stop, and one place to move between projects and between the map, its layers, its provenance and its prompts. Separate servers per module or per project would each need their own port, token and start, and could not show two projects side by side.
- How it shows: `metaform list modules` lists `web`. `metaform help web` gives its man page. The page opens on the 3D view of a project's active metaform, with a project switcher that lists every registered project.
- Build: The module lives at `src/metaform/modules/web/` with `__init__.py`, `server.py`, `page/` for the HTML, CSS and scripts of the app and its views, `vendor/` for the bundled libraries, and `README.md`. It declares `SUPPORTED_OS = ('linux', 'macos', 'windows')`. It ships enabled. Its verbs are in VIEW-002. Until question 3 is answered, the map views, the provenance view and the prompt editor are the web module's own.
- Acceptance: With the web module disabled, every chassis verb and every other module works. `metaform web` then stops with `Next: metaform enable web`.
- Relates to: BASE-017, BASE-019, BASE-035, CLI-026, MCP-002, PROJ-019, VIEW-002, D44.
- Status: confirmed for one unified web GUI, user global, serving every project, with the viewer as its first view, Rich 2026-09-25. The module name `web` and shipping enabled are recommended.

### VIEW-002 The web GUI is one server for the user, on one fixed port, started with `metaform web`
- Requirement: One server per Metaform home serves the web GUI for every registered project on one fixed port, at a bind address that is loopback by default. `metaform web` starts it when it is not running and prints its address; when it is already running, it prints the address it runs at. `metaform web stop` stops it.
- What this means: The home is the user's Metaform data folder, so in practice this is one server per user; a second home, such as a test's, has its own server and needs another port. Starting from any folder, or for any project, finds the running server and starts no second one. The page lists every registered project and switches between them; the folder `metaform web` ran in chooses only which project the page shows first. The port is fixed, so the address stays the same across restarts and a bookmark keeps working. After an intake, agents start it and tell the user the address, VIEW-015. Which folder's settings, such as `--layers`, the GUI shows and changes is open, question 5.
- Why: A local server keeps all data on the machine and needs no account. Bound to loopback, as it is by default, nothing on the network can read the metaform; a person who sets another bind address opens it to that network, and the token still guards every request. A fixed address lets a person keep the GUI open while agents work.
- How it shows: `metaform web` prints `Web: started at http://127.0.0.1:<port>/?t=<token>`. Run again, from any folder, it prints `Web: running at http://127.0.0.1:<port>/?t=<token>`. `metaform web stop` prints `Web: stopped`.
- Build:
  - The module's verbs are `start`, its default, BASE-035, so `metaform web` runs it and over MCP it is the tool `web_start`, and `stop`, the tool `web_stop`. `start` returns the address and whether it started the server or found it running.
  - `start` launches the server as a process detached from the terminal, so it runs until `metaform web stop`, logout or restart: on POSIX in a new session, on Windows as a detached process, with no console. It returns once the server answers on its port.
  - The server uses the standard library, `http.server` with a threading server, so the GUI adds no compiled dependency.
  - The home has one token, made on the server's first start and stored in the home. The page URL carries it, and every request without it is refused with 403. This stops other local pages from reading the metaform through the browser, and the address stays the same across restarts.
  - The server records its address and process id under `~/.metaform/run/web.json`. `start` reads that file first and reuses a live server. `stop` ends that process and removes the file.
  - `--web-port` is a chassis-schema setting declared by the module, an integer, with a fixed default, question 6. When the port is held by another program, `start` stops with the port named and `Next: metaform set --web-port <port>`.
  - `--web-bind` is a chassis-schema setting declared by the module, text, default `127.0.0.1`: the address the server binds to. When the server cannot bind there, `start` stops with the address named and `Next: metaform set --web-bind <address>`.
- Acceptance:
  - `metaform web` starts the server and prints its address; run again, it reports the same address as running and no second process exists; `metaform web stop` ends it and removes the run file.
  - `web` run from the folders of two projects leaves one server running, serving both projects.
  - A request without the home's token is refused.
  - With `--web-bind` at its default, the server accepts no connection on a non-loopback address; set to another address, it listens there and still refuses a request without the token.
- Relates to: BASE-035, CLI-011, PROJ-003, PROJ-019, VIEW-001, VIEW-004, VIEW-015.
- Status: confirmed for one server for the user serving every project on one fixed port, for `metaform web` to start it and `metaform web stop` to stop it, and for a locally served GUI, Rich 2026-09-25. A bind address setting, loopback by default, is confirmed, Rich 2026-09-25. The default verb, the output lines, the token kept in the home and the setting names are recommended.

### VIEW-003 The viewer works offline with every script bundled
- Requirement: The viewer loads nothing from the network: every script, style and font it uses is bundled in the module with its license.
- What this means: The page references only files served by the viewer's own server. The bundled libraries are three.js, a force-graph library for three.js such as `3d-force-graph` with its layout engine, Mermaid, the version already vetted on the earlier branch, 12.0.0, and CodeMirror 6 for the prompt editor, VIEW-013. Each is an unchanged release file with its license file next to it and a `vendor/README.md` naming the version, source and SHA-256.
- Why: Metaform runs offline and in restricted environments. A page that needs a CDN breaks there and sends the user's browsing to a third party.
- How it shows: With the network disconnected, the viewer opens and draws the graph.
- Build: `vendor/` holds `three.module.min.js`, the force-graph bundle, `mermaid.min.js`, the CodeMirror bundle with its XML and Markdown modes, and their `LICENSE` files. The page has a Content Security Policy of `default-src 'self'`, so any accidental remote reference fails visibly. The wheel build carries the vendor files as package data.
- Acceptance: The served page and every file it loads come from the viewer server; a check of every `src` and `href` in the page and its scripts finds no remote URL. The wheel contains the vendor files and their licenses.
- Relates to: BASE-041, QUAL-002, VIEW-001, VIEW-013.
- Status: confirmed for offline with nothing from a CDN. The library choice is recommended.

### VIEW-004 The viewer reads only through the data access object and follows every visibility rule
- Requirement: Everything the viewer shows comes from data access object reads, under the same rules that govern what agents see.
- What this means: The server calls the store reads of STORE-025 and nothing else. It never opens a database file and never parses an intake document. What is shown is the metaform with the correction stack applied, LAYER-011, plus the knowledge layers the folder's `--layers` setting turns on, CLI-033, with select and mask applied at each address, LAYER-007. Hidden layers do not appear, LAYER-006. Orphaned items do not appear unless the viewer's raw toggle is on, and then they are marked orphaned, STORE-017. Every edge and every item shows the name of the layer it comes from. Every object shows its intake flag, missing, broken or cruft, MAP-046, and every challenge shows its state, LAYER-015.
- Why: A viewer that shows something agents cannot see, or hides something they can, misleads the person checking the map. One source of truth for visibility keeps the picture honest.
- How it shows: Turning a layer off with `metaform set --layers` and refreshing the viewer removes that layer's joins and items from both views. A masked layer at `code.engine` is absent under `code.engine` in the viewer as it is in `map context`.
- Build: The server exposes read-only JSON endpoints that map one to one onto store reads: `/api/roots`, `/api/graph`, `/api/children`, `/api/node`, `/api/joins`, `/api/layers`, `/api/findings`, `/api/search`, each with the paging of STORE-005 and a `raw` flag. Each endpoint passes the folder's resolved selection to the read. The page never computes visibility itself.
- Acceptance:
  - For a store with a hidden layer, a masked layer at one address, an orphaned knowledge item and a flagged element, each endpoint returns exactly what the matching store read returns, raw and in context.
  - The page's data for a node equals `metaform map node` for that node.
- Relates to: LAYER-006, LAYER-007, LAYER-011, LAYER-015, MAP-046, STORE-005, STORE-017, STORE-025, CLI-033.
- Status: confirmed.

### VIEW-005 The 3D view floats the metaform in space in its tripartite form and untangles it
- Requirement: The main view is a 3D graph floating in space that shows every join in its tripartite form and settles itself into the metaform's actual mesh shape through a force layout.
- What this means: Joins are not collapsed in the 3D view. Each join is drawn as the tripartite unit it is: the receiver, the purpose and the encounter, three vertices of one triangle face, with the encounter vertex tied to the provider element that serves it. Faces that share a receiver or a provider share that vertex, so the joins form the non-manifold triangle mesh the metaform is. Because every join is its own face, two elements that each receive from the other appear as two separate joins with their own purposes, never as a loop. The namespace tree, along which properties travel, is drawn as its own kind of edge from each element to its nearest parent element, and no namespace branch is collapsed. Subtypes sit inside their join as small vertices attached to the join's encounter. The layout starts from the roots and lets the forces pull connected parts together and push unconnected ones apart, so the tangle opens up into the mesh's shape and settles. The camera orbits, zooms and pans. Hovering a vertex names it. The layout can be paused and resumed while it settles.
- Looks: the 3D mesh reads like a synaptic map in 3D. Elements are glowing nodes against a dark space, joins are fiber-like connections in their tripartite form, and layers are colors, so the whole shape reads like a neural map of the project.
- Why: The receiver, purpose and encounter structure is a shape. Collapsing a join into one edge hides the purpose and the encounter and turns two-way pairs into apparent loops. Drawing each join in full shows the real mesh: where the load-bearing parts are, which branches are thin, and what sits apart from the rest.
- How it shows: Opening the viewer on the MGM metaform shows the VE and DE near the center with triangles of joins arranged around them, settling within seconds. Two elements that each serve the other show two triangles between them.
- Build:
  - Vertices: one per element, and for each join one purpose vertex and one encounter vertex. Face: receiver element, purpose vertex, encounter vertex. Tie: encounter vertex to provider element. Namespace edge: element to nearest parent element.
  - The force simulation gives the face edges and the encounter ties higher strength than namespace edges, so function structure dominates the shape.
  - Positions of drawn vertices are kept when more of the graph arrives, so the picture does not jump. A reset control re-runs the layout.
  - Motion respects the browser's reduced-motion setting.
  - Synaptic look: element vertices are drawn as emissive spheres with a soft glow sprite, sized by how many joins meet there; purpose and encounter vertices are smaller and dimmer. Face edges and encounter ties are drawn as thin curved fibers with additive blending, so dense regions glow brighter. The background is dark space. Hover and selection brighten a node and the fibers of its joins.
- Acceptance: Manual: on each operating system, the MGM metaform opens, settles into its mesh, reads as a glowing neural-like map, orbits and zooms. Automated: the page's graph data holds one vertex per visible element, one face per visible join made of its receiver, purpose and encounter vertices, one tie from each encounter to its provider, and one namespace edge per element with a parent element; no join is represented as a single element-to-element edge.
- Relates to: MAP-001, MAP-005, MAP-022, MAP-030, VIEW-006, VIEW-010.
- Status: confirmed for the floating 3D graph that untangles into the shape, joins shown uncollapsed in their tripartite form, two-way pairs as separate joins, no collapsed namespace branches, and the look of a synaptic map in 3D. The face and tie geometry and the drawing technique for the synaptic look are recommended.

### VIEW-006 Edges and nodes are colored by layer and by kind
- Requirement: Edge color and style show which layer an edge comes from and what kind of encounter it is, and node style shows each object's flag and state.
- What this means:
  - Kind is shown by style. A join's triangle face and its encounter tie are solid, with an arrow on the tie toward the provider. A namespace edge, the path properties travel, is a thin dashed line. An object or join that a correction layer added or relocated is outlined in that correction layer's color.
  - Layer is shown by color. The intake map has one base color. Each knowledge layer that is on gets its own color from a fixed palette, assigned in layer order so a layer keeps its color between sessions. Memory has its own color.
  - Flags are shown on nodes: missing, broken and cruft each have a distinct marker. Plans and blind spots from challenges are marked by state.
  - A legend shows every color and style currently in view with the layer name.
- Why: Color by layer shows at a glance what each layer adds to the metaform. Style by kind keeps functions and properties apart, since only properties travel along the namespace.
- How it shows: Turning on a best-practice layer adds its join triangles in its own color. A broken element carries the broken marker in both views.
- Build: The palette is defined once in the page's styles and checked for contrast in light and dark backgrounds. Colors come from the layer's position in `/api/layers`, not from its name, so renaming a layer does not change its color.
- Acceptance: For a store with the intake, one correction layer, two knowledge layers, memory and one element of each flag, the legend lists each with its color, and every edge and node carries the style its kind, layer and flag call for.
- Relates to: LAYER-011, LAYER-012, LAYER-015, LAYER-016, MAP-046, VIEW-005.
- Status: confirmed for colored edges by layer and kind. The specific styles and palette are recommended.

### VIEW-007 Viewing never changes settings; a separate control applies the layer choice
- Requirement: The viewer lists the metaform's layers with their tags and lets the person choose which knowledge layers are shown; active viewing never changes any setting, and a separate control applies the viewer's layer choice to the folder's `--layers`.
- What this means: The layer panel shows each layer's name, kind, tags, whether it is ready, and whether it is on for the folder, the same fields as `list layers`, LAYER-019. Toggling a layer in the panel, orbiting, selecting, searching and every other act of viewing change only the viewer's own view. A separate apply control writes the viewer's current choice to the folder, as the same operation as `metaform set --layers`. Correction layers are listed as a stack in order and cannot be toggled, LAYER-011.
- Why: The viewer is for viewing. Looking at the effect of a layer must not change what agents working in the folder see. Applying it to the folder is a deliberate act.
- How it shows: Toggling a layer in the panel changes the graph at once. The folder's `--layers` setting is unchanged until the apply control is used.
- Build: The view's layer choice is held in the page. Reads pass it as the selection for the view. The apply control calls one endpoint that performs `set --layers` through the chassis settings operation, VIEW-011.
- Acceptance: Toggling layers in the panel and browsing the whole graph leaves `metaform set` output unchanged. Using apply makes `metaform` status show the new `--layers` value.
- Relates to: CLI-033, LAYER-011, LAYER-019, VIEW-011.
- Status: confirmed. The panel and endpoint mechanics are recommended.

### VIEW-008 Clicking an object opens it as a 2D graph in the left window
- Requirement: Clicking an object in the 3D view opens that object in the left window as a Mermaid-like 2D graph of the object and its joins.
- What this means: In the 2D view, joins are collapsed into labeled edges between elements, which keeps one object's purposes and functions readable on a flat page. The left window shows the selected element in the middle, the elements it receives from on one side and the elements it provides to on the other, each join labeled with its relation. Subtypes appear inside their join. Clicking an element in the 2D graph moves the selection to it in both views. The window keeps a back history. The 2D view is the one built on the earlier branch, kept where it matches this spec: Mermaid lays out the named nodes and labeled edges with stable ids; the viewer owns the camera, with pan, zoom, pinch, fit, eased transitions that can be interrupted, keyboard movement between connected nodes, and a closer view that reveals join detail.
- Why: The 3D view shows the shape. Reading one object's purposes and functions needs a flat, labeled view that stays still.
- How it shows: Clicking the DE in the 3D view opens the DE in the left window with its joins labeled, and the 3D camera centers on it.
- Build:
  - Salvaged from `modules/web/namespace_graph.js`, `namespace_graph.css` and `vendor/mermaid.min.js` on branch `main-wip-2026-09-24`: the Mermaid rendering with stable ids, the camera and its transitions, pointer and keyboard navigation, fit, and reduced-motion handling.
  - Not carried over: XML import and `graph_data.py`'s XML projection, the workflow editor, dragging objects into authored text, and the hard dependency, property and supportive edge styles. Joins are functions and properties are separate records, MAP-022, so edges use the styles of VIEW-006.
  - The 2D graph's data is `/api/node` and `/api/joins` for the selected element, VIEW-004.
- Acceptance: Manual: clicking objects in the 3D view opens them in the left window, keyboard navigation moves between connected nodes, and back returns. Automated: for a selected element, the 2D graph's nodes are exactly the element and its current join partners, and each edge label is the join's relation.
- Relates to: MAP-022, MAP-030, VIEW-004, VIEW-005, VIEW-009.
- Status: confirmed for the click into a Mermaid-like 2D view in the left window, with joins collapsed into labeled edges there. The salvage list is recommended.

### VIEW-009 The inspector shows everything about the selected object
- Requirement: Beside the 2D view, an inspector shows the selected object's full record as agents read it.
- What this means: For an element: its address, name, role, flag and note; its properties, applying and visible, with the layer each comes from; its joins as receiver and as provider, each with purpose, function, relation, observation, refs and layer; its subtypes; its memory observations; and any challenges at it with their state. For a join: the same fields for the join itself. For every layer shown, and for the layer each object comes from, the inspector shows its provenance: what prompt produced it, the exact prompt version, and the model, role, blinded, module and workflow, VIEW-013, plus its report, feedback and shape refs.
- Why: A person checking an intake needs the words, not just the lines. The inspector shows exactly what an agent would receive for that object.
- How it shows: Selecting an element with a memory shows the memory under it, marked with the memory layer's color.
- Build: The inspector renders `/api/node` for the selected object. It shows raw fields as text, never as HTML, so stored text cannot inject markup.
- Acceptance: For an element with properties, joins in both directions, a subtype, a memory, a flag and a challenge, the inspector shows every one of them with its layer name.
- Relates to: LAYER-005, LAYER-010, LAYER-013, LAYER-015, MAP-046, STORE-025, STORE-044, VIEW-004, VIEW-013.
- Status: confirmed that the selected object's details are shown. The inspector layout is recommended.

### VIEW-010 The viewer meets the storage scale through rendering technique, not by hiding structure
- Requirement: The viewer opens and stays responsive on a metaform at the scale STORE-005 measures, 100,000 elements and a million layer items, while showing the full structure.
- What this means: Scale is met by how the graph is computed and drawn. No namespace branch is collapsed and no join is merged to save work. The layout is computed off the main thread and cached, the geometry is drawn with instanced WebGL rendering, and labels appear by level of detail as the camera comes close. The graph data arrives through paged reads streamed in the background, and the page draws what has arrived while the rest loads.
- Why: A viewer that freezes on a large project is useless exactly where the picture is most needed, and one that hides structure to keep up shows a shape that is not the metaform's.
- How it shows: On the 100,000-element test store, the first vertices appear within two seconds, the whole mesh fills in while the view stays interactive, and reopening the same metaform shows the settled layout at once from the cache.
- Build:
  - Loading: the server streams `/api/graph` in pages of the paged reads of STORE-005, roots first.
  - Layout: the force simulation runs in a Web Worker. Settled positions are cached by the viewer under `~/.metaform/cache/viewer/<project>/<metaform>/`, keyed by the metaform, the correction stack's top and the visible layer set, and reused when unchanged. The cache is viewer data, never part of the store.
  - Drawing: vertices and edges are drawn as instanced meshes and line segments, one draw call per style, so the frame cost does not grow with the number of objects drawn separately.
  - Labels: a label is drawn only when its vertex is within a set screen size, nearest first, up to a fixed label budget per frame.
- Acceptance: On the storage test store from STORE-005: the first vertices render in under 2 seconds on the test machine; the full graph finishes loading with the page staying above 30 frames per second while orbiting; every visible element and join is present in the drawn data; and a second open with an unchanged store uses the cached layout.
- Relates to: STORE-005, STORE-025, VIEW-005.
- Status: confirmed that scale is met by rendering technique, not by hiding structure. The worker layout, the cache, instanced rendering and label level of detail are recommended.

### VIEW-011 The viewer writes exactly three things
- Requirement: The viewer writes exactly three things: it applies its layer choice to the folder's `--layers`, it saves an edited prompt as a new prompt version, and it removes the top correction layer after a warning; it writes nothing else.
- What this means: Agents and people change the metaform through the tools and commands; the viewer shows it. The three writes each go through the same operation the CLI and tools use: the settings operation for `--layers`, VIEW-007; the prompt-version operation, VIEW-013 and STORE-044; and peel followed by discard of the top correction layer, VIEW-014. Writing memories, answering challenges, adding knowledge or correcting the map from the page is not part of this module.
- Why: The viewer is for viewing. One path for each write keeps every change under the rules that record provenance and never block. A page that wrote on its own would need its own copy of those rules.
- How it shows: Every API endpoint is a GET that changes nothing, except three POSTs: apply layers, save prompt version, and remove the top correction layer.
- Build: The server routes GET for reads and exactly three POST endpoints. Each POST calls the chassis or store operation named above and returns its result and notices.
- Acceptance: A store's contents and the folder's settings are byte-for-byte unchanged after a session of reads through every GET endpoint. The server exposes no other POST, PUT, PATCH or DELETE route.
- Relates to: BASE-044, STORE-017, STORE-044, VIEW-007, VIEW-013, VIEW-014.
- Status: confirmed.

### VIEW-012 The viewer is accepted by hand and by automated checks
- Requirement: The viewer counts as done only after a manual test on each operating system as well as its automated checks.
- What this means: The automated checks in VIEW-002 to VIEW-011 prove the data and the rules. A person, or an agent driving a real browser, then opens the viewer on the MGM metaform on Linux, macOS and Windows and confirms: it opens and settles; orbit, zoom and pan work; colors and the legend match the layers; clicking opens the 2D view and the inspector; layer toggles change the view; flags show; it works offline. The results are recorded in `MANUAL-TEST.md` with what was done and what was seen.
- Why: A graph can pass every data check and still be unreadable or broken in a browser. Only looking at it proves it works.
- How it shows: `MANUAL-TEST.md` has a viewer section with one line per check and its result on each system.
- Build: Browser checks are scripted where possible with a headless browser against the local server; the visual checks are done by hand.
- Acceptance: The viewer section of `MANUAL-TEST.md` passes on all three systems.
- Relates to: QUAL-002, QUAL-014, VIEW-001.
- Status: confirmed.

### VIEW-013 The viewer shows provenance, and prompts can be edited as new versions
- Requirement: For any layer or object, the viewer shows what prompt produced it, with the model, role, blinded, module and workflow; prompts can be edited in the viewer, and an edit creates a new prompt version without changing any provenance record.
- What this means: Seeing which prompt made a layer, and changing that prompt, is part of what the viewer is for. So that provenance stays a true record of how a layer was made, prompts are stored as their own records with versions, STORE-044. A layer's provenance references the exact prompt version it was created with. Opening a prompt in the viewer shows that version's text. Saving an edit creates the next version of the prompt for future runs. The version an existing provenance record references never changes, so every layer still shows the exact text it was produced from. The provenance panel shows all versions of a prompt and which layers each produced.
- Why: The metaform improves by improving the prompts that build it. Seeing the prompt beside what it produced shows what to change. Keeping every version and never rewriting the one a layer references keeps layers trustworthy, comparable and reproducible.
- How it shows: Selecting a knowledge layer shows its prompt, version 3, and its model and role. Editing the prompt and saving shows version 4 as current; the layer still shows version 3.
- Editing is in an actual text editor, never field-by-field forms. The editor pane has syntax highlighting for the prompt's format, XML or Markdown, search and replace, undo, line numbers, and a diff against the version it came from, shown before saving as a new version.
- Build:
  - The provenance panel reads `/api/provenance?layer=` and `/api/prompts?prompt=`, which map onto the provenance and prompt reads of STORE-044. Saving calls the one POST that creates a prompt version, STORE-044's `add_prompt_version`, with the version it was edited from.
  - The editor is a locally bundled code editor, CodeMirror 6, with its license kept in `vendor/`, VIEW-003. Its format modes are XML and Markdown. The diff view compares the edited text with the version it came from, line by line, before save.
  - Salvaged where it fits the current spec, the same way as the 2D graph, VIEW-008: the editor from `modules/web/workflow_editor.html`, `workflow_editor.js` and `workflow_editor.css` on branch `main-wip-2026-09-24`, including inline namespace object references shown within the text. Not carried over: the workflow document model, workflow execution, and anything that reads XML intake results.
  - Text in the inspector and panels is shown as plain text, never as HTML.
- Acceptance:
  - For a layer created with prompt version 3, the panel shows version 3's exact text and the provenance fields.
  - Saving an edit creates version 4; the layer's provenance still references version 3 and shows its text unchanged; a new layer created afterwards with that prompt references version 4.
  - Manual: the editor highlights XML and Markdown, search and replace and undo work, line numbers show, and the diff against the source version appears before saving.
- Relates to: LAYER-010, STORE-016, STORE-044, VIEW-009, VIEW-011.
- Status: confirmed for viewing provenance, modifiable prompts edited in an actual text editor, prompts as their own versioned records, editing creating a new version for future runs, and provenance referencing the exact version that produced the layer. CodeMirror, its feature set and the salvage list are recommended.

### VIEW-014 Correction layers are removed one at a time from the top, with a warning
- Requirement: The viewer can remove correction layers only one at a time, in reverse order from the top of the stack, and only after a warning that names what the removal will change.
- What this means: Correction layers depend on their order. If one went bad, removing it from the middle would change what every layer above it applied to. So the viewer offers removal only for the top correction layer. The warning lists what the metaform will change: elements, joins and properties added by that layer disappear, what it removed or relocated returns to its earlier state, knowledge items it orphaned show again, and items attached to things it added become orphaned. Confirming peels the layer off the stack and discards it, STORE-017 and STORE-032. The next layer down then becomes the top and can be removed the same way.
- Why: A bad correction must be undoable without breaking the stack. Removing in reverse, one at a time, keeps every remaining correction applied to exactly the metaform it was made against, and the warning makes the change visible before it happens.
- How it shows: The stack panel shows a remove control only on the top correction layer. Choosing it shows the list of changes and asks to confirm. After confirming, that layer is gone and the next one shows the control.
- Build: The warning comes from a read that computes what peeling the top layer would change, from the layer's rows through the `_by_layer` indexes, without writing. The POST performs `peel` then `discard` of that layer in the store, only if it is still the top layer when the request arrives; if it is not, nothing changes and a notice says the stack moved. The removal's provenance record is removed with the layer.
- Acceptance:
  - With a stack of three correction layers, only the third has a remove control; removing it restores the metaform to the first two applied; then only the second has the control.
  - The warning for a layer that relocated an element and added a join names both changes.
  - A remove request for a layer that is no longer on top changes nothing.
- Relates to: LAYER-011, STORE-017, STORE-032, STORE-036, VIEW-011.
- Status: confirmed for removal one at a time in reverse with a warning. Peel then discard as the mechanism, and the warning read, are recommended.

### VIEW-015 After an intake, agents start the web GUI and tell the user its address
- Requirement: A setting, on by default, puts an instruction in what agents read: after an intake, start the web GUI if it is not already running, and if it was not running, tell the user its address once it starts.
- What this means: With the setting on, the person who asked for an intake is handed the GUI's address when the map is ready, without having to start anything. When the GUI was already running, the agent starts nothing and says nothing about it. With the setting off, the instruction is not given and the GUI starts only when someone runs `metaform web`.
- Why: The map is most worth seeing right after an intake, and the agent that ran it is the one talking to the person.
- How it shows: With the default, an agent finishes an intake, calls `web_start`, and tells the user `The map is in the web GUI at http://127.0.0.1:<port>/?t=<token>` when it started the server. With `metaform set --no-web-autostart`, the composed instructions hold no such line.
- Build:
  - The setting is `web_autostart`, switch `--web-autostart`, a boolean, default true, folder scope, declared by the web module, CLI-011.
  - The instruction reaches agents through the web module's status hook, BASE-035: when the setting is true for the folder, the hook returns it as its notice, so it is in the composed instructions, MCP-007, and in `metaform help agents`; when false, the hook returns no notice. The notice reads: `After an intake, start the web GUI with metaform web, or the web_start tool, if it is not already running. If it was not running, tell the user its address once it starts.`
  - `web_start` returns whether it started the server or found it running, with the address, so the agent knows whether to tell the user, VIEW-002.
- Acceptance:
  - With the setting at its default, the composed instructions hold the notice; after `set --no-web-autostart` they do not.
  - `web_start` with no server running returns `started` and the address; called again, it returns `running` and the same address.
- Relates to: BASE-035, CLI-011, MCP-007, VIEW-002.
- Status: confirmed for a setting, true by default, that instructs agents to start the GUI after an intake when it is not running and to tell the user its address when they started it, Rich 2026-09-25. The setting name, the delivery through the status notice and the notice's wording are recommended.

## Open questions

1. Answered: active viewing never changes settings; a separate control applies the viewer's layer choice to the folder, VIEW-007.
2. Answered: the viewer writes exactly three things, applying layers, new prompt versions, and removing the top correction layer with a warning, VIEW-011.
3. NEW How does a module add a view to the web GUI? Recommended: a module declares its views as a page folder and the read endpoints they need, and the web module serves them under the module's id; decided when a second module has a view. (VIEW-001)
4. Answered: `metaform web` starts it and `metaform web stop` stops it; a setting, true by default, instructs agents to start it after an intake when it is not running and to tell the user its address, VIEW-002 and VIEW-015.
5. NEW Which folder's settings does the GUI show and change, such as `--layers`, CLI-033, since a browser has no folder? Recommended: the folder it was opened from, shown with its path at the top of the page. (VIEW-002, VIEW-004, VIEW-007)
6. NEW What is the default of `--web-port`? (VIEW-002)
