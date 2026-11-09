---
name: metaform
description: Read the functional namespace, use the knowledge needed for the current work, and record findings at the receiving element.
---

# Work with Metaform

The stored JSON tree is the functional namespace. Read addresses backward. `name` is the project's own name. `name_length` counts the trailing segments used for the industry short name. RE and PE are perspectives on the same element.

Work on one receiving element at a time. The single tool is named `project-map`; it handles reads as well as changes. Its input selects an operation and an address; it does not define storage layout. Use `add` or `update` with the receiving address as the key and the supplied fields as its value. Do not add a `data`, `properties`, or `layers` wrapper.

Reason with the authored RE, PE, OP, EF, IFD, CQU, and other concepts. Record the PE's namespace address in the RE's `wants[]`, OP as `goal`, the encounter-specific EF as `function`, and IFD as `direction`. Field names do not replace the definitions or change the method.

`wants[]` is the receiver's functional knowledge layer. Each member maps a provider address to a want record. `goal` states what the receiver seeks to accomplish. `function` states how the provider serves that goal in this encounter. `direction` states the direction of the substantial flow of information which satisfies the (OP) goal, relative to the receiver, not including the request: `outbound`, `inbound`, or `two-way`. Optional `ice` records indivisible coupling. CQU and the other authored concepts retain their meanings.

Every provider also exists at its own nested namespace location. Its properties, knowledge, and own wants live there. Do not copy them beneath a reference. Keep one want per provider address within a receiver. Set one source `uri` on the actual element, pointing to the entry point for its functionality. Keep extra evidence references with the findings that need them.

Read one element with `{"code.masher.widget":{}}`. Delete a want with `{"delete":{"code.protocol.network.tracker.cs":{"wants":["code.masher.widget"]}}}`. Delete an element with `{"delete":{"code.masher.widget":{}}}`. A referenced element cannot be deleted. Inspect returned remediation before submitting it; the error does not authorize automatic deletion of other records.

Use `{"orphaned":{}}` to find unreferenced elements. Do not treat that result as an instruction to delete them. Remove a property with `update` and `null`, for example `{"update":{"code.masher.widget":{"role":null}}}`. Omitted fields remain unchanged. Input validation and validation of the resulting map are separate checks. Do not repeat a write with an unknown outcome until it has been reconciled.

Read-only projections are `local_functional`, `global_functional`, and `local_knowledge`. They do not require a separate viewing tool. Use the single tool for addressed reads; a URI may identify a generated projection. Local functional views include direct wants and incoming receivers. Local knowledge adds knowledge on the focus, without neighbors' knowledge bodies. Global views retain wants but exclude ancillary knowledge bodies. A global read is not required at startup. A URI can also identify a generated view, such as a sparse tree of element names.

Native plural arrays such as `skills[]`, `memories[]`, `tasks[]`, and `inbox[]` retain their contents. Do not invent record IDs or rewrite native skill frontmatter. Record intended functionality not yet built with `status: "un_built"`. Intake records functional intent and separate investigation findings. It does not label unfamiliar intent broken.

Use clear, simple technical English for the recorded goal and function fields. Use the same term for the same thing. Keep the authored intake concepts, exclusions, examples, trace, annealing, and readback across arbitrary artifacts and mixed collections. The current procedure is in `Intake.xml`.

Read needed skills and knowledge while working in their functional scope. A prior visit or read receipt is not a prerequisite for using an available tool. Discovery, delivery, and retained context are different facts.

Purposeful assignments, peer questions, and events are allowed. Routine logs must not stream into agent context. Mailbox availability is a short notice such as "1 message waiting"; use the known mailbox-read capability to retrieve messages. Do not poll. Context and tool-surface monitoring belongs in the operator view.
