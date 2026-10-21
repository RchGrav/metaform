# Roundtable 5: final synthesis and plan

Table `5ebe493b`, 2026-10-21 11:43Z. Seats: Sol (codex/gpt-6.1-sol), Astra (codex/gpt-6-astra), Fable (claude/fable), Opus (claude/opus). Source: `mechanical-report.md` and `export.json` in this folder; idea numbers are the synthesizer's.

**Question:** What is the perfect signature environment for ai and user collaboration in metaform to create 3D interactive experiences?

## Answer

A shared, playable 3D canvas where the person and agents edit the same world through one operation format, and every meaningful object and rule keeps its purpose, constraints and decisions through Metaform (I1). Its core is an authoritative scene service (I5) over a portable, renderer-independent world format with one runtime for editor, web export and headless checks (I4). Agents act through a small typed vocabulary (I7) with spatial perception (I8), propose edits as reviewable patches against a revision (I9), and prove intent with bounded simulation checks (I14). Build it JavaScript-first: TypeScript, Three.js, Rapier WASM, Web Workers (I2, I16).

All four seats ranked I1, I3, I4, I5 and I7 in their top seven. Disagreements the table left open: whether object ids equal Metaform addresses or stay separate UUIDs with optional map links (I6); whether intent operations or snapshots plus history are authoritative (I12, the later proposals favored snapshots plus history).

## Plan, in order

1. **Minimal playable editor (I3).** Blank canvas, orbit camera, grid, selection, primitives, transforms, materials, spawn placement, undo, Play/Edit. Done when: a pressure plate opens a door in Play.
2. **World format and shared runtime (I4).** Entities, transforms, assets, declarative behaviors in versioned JSON; same runtime in editor, web export, headless Node. Done when: the plate-door scene runs headless with the same result.
3. **Authoritative scene service (I5).** Validates commands, checks expected revision, persists, broadcasts; toolbar and agent use one operation format. Done when: a human edit and an agent edit on one scene both land through it.
4. **Agent controls and perception (I7, I8).** observe, probe, sketch, propose, preview, commit, check, claim, step, reset; named-camera images plus raycasts and volume queries. Done when: an agent places the plate and door from a request.
5. **Reviewable edits and isolated play (I9, I11).** Patches against a revision, preview, commit or discard, soft region claims; Play starts from a snapshot. Done when: an agent's patch is previewed and discarded without touching the canvas.
6. **Behavior rules and physics (I10, I16, I17).** Fixed event-condition-action library; Rapier rigid bodies, sensors, fixed timestep, snapshot reset. Done when: the plate-door check repeats identically in browser and Node.
7. **Persistence and intent checks (I12, I14, I15).** Snapshots plus edit history; purposes as bounded assertions with stated assumptions and accepted exceptions.
8. **Later, when measured need appears (I27):** SDF terrain in sparse bricks (I20, I21, I22), procedural generation (I24), destruction (I19), environmental simulation (I26), multiplayer authority (I11). Integration benchmark: hillside settlement with tunnel, redirected stream and bridge.
