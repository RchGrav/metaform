# ModularShift: completing W-1.4's agent writing procedure

This contribution is incorporated as B-3.7 and two authoring operations in blueprint-spec.md.

The premise chain is operational: W-5.5 requires building a solution from user intent; W-5.3 requires its module to carry the port manifest; W-3.5 stores modules under their content hashes. The existing add_node operation accepts an existing content key, and submit requires hashes to resolve. Without an operation that stores newly compiled code and returns its key, an agent cannot complete a feature requiring behavior absent from the content store.

The correction supplies content.publish_component (store compiled bytes and associated manifest, validate format/types/imports, return hashes) and blueprint.bind_component (bind a published component to an owned draft slot, check planned interface agreement, invalidate stale evidence). New slots can use the published key directly with add_node. Draft port edits cannot modify a shared module and block submission until backed by a published component.

The blueprint holds component and manifest hashes; executable bytes stay in the content store. The agent record associates sourceHash with componentHash through buildInfo. Release pins the tested componentHash, because source text and compiled WASM are different artifacts.

Acceptance: with no existing lever controller, publishing creates a content key but no entity; add_node plus submit produces the test instance. A boolean planned port paired with a string published port is rejected before instantiation. A changed compiled component cannot use the previous build's test evidence.
