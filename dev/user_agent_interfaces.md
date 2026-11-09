Design and, if code generation is available, implement a polished, desktop-first Metaform graph workspace prototype. The graph—not a dashboard—is the primary work surface. Position the Rust version as the premium experience through precise typography, purposeful graph styling, efficient use of space, restrained color, and confident interaction design. Avoid decorative gradients or glow.

PRODUCT AND IMPLEMENTATION CONTEXT
- Build the interface in React and TypeScript when implementing code. If a Rust-native web GUI or serving framework is available, treat it as the host for the React/TypeScript interface; do not imply that the prototype is connected to a real Metaform service.
- Use realistic local mock data and simulated live events. Label simulated events and service behavior honestly. Keep the graph model and event sources replaceable so a real backend can be connected later.
- Support one main web GUI serving multiple registered projects, within the capabilities of the provided environment. Include a credible first-run/onboarding state: explain how to register a project with `metaform register <project_name>`, show a clear simulated first-intake action, and indicate the user-facing command for opening the interface again. Do not claim that these commands or service startup work unless implemented in the supplied environment.
- If code generation is unavailable, provide a directly implementable screen specification and interaction map instead.

CORE EXPERIENCE
1. Start in a spacious, dark-first graph view with visible project identity, graph title, breadcrumbs, zoom status, and a compact control affordance. Use a large interactive SVG or canvas graph with an automatic Mermaid-style layout. Use the existing project stack where practical; otherwise choose a suitable graph-rendering and layout approach and state the choice briefly.
2. Provide Graph, Focused Node/Details, and Presentation modes. Switching modes must preserve the current project, graph path, focal node, and useful viewport context where appropriate.
3. Implement smooth, predictable pan and zoom, visible zoom percentage, zoom-in/out, and fit-to-view. Provide a clear way to restore the compact menu after it hides.
4. Single-click selects a node and reveals contextual details. Double-click traverses into a node’s nested graph; show an obvious breadcrumb or back action to return. Ctrl-click traverses to the broader graph context and is discoverable through a concise hint or tooltip.
5. Support node collapse and expansion. Clearly distinguish nodes with hidden descendants from leaf nodes and show collapsed versus expanded state.
6. Support multiple projects, project switching, and cross-project links. Make project boundaries explicit, allow navigation to a linked project, and provide a clear route back to the originating project and graph context.
7. Add layer controls to show or hide individual layers, toggle all layers, and isolate one layer. Visually distinguish visible, hidden, and isolated states.
8. Show quiet, informative agent presence with names or initials, activity status, and the node or region being worked on. Include a restrained activity stream or intake indicator for simulated incoming updates. New activity must be identifiable without unexpectedly moving the viewport or stealing focus.
9. Support graph pivoting: let users set a new focal or starting node, explain the resulting context change, and make it reversible.
10. Use a compact autohiding menu: keep essential actions discoverable, reveal secondary controls on hover, keyboard focus, or deliberate interaction, and provide an obvious re-open affordance. On narrow screens, keep the same essential tasks usable with adapted panels and controls.

SAMPLE SCENARIO
Populate the prototype with at least three projects, one nested graph, cross-project links, three distinguishable layers, multiple node types, two or more active agents, and incoming simulated updates. Include enough graph content to demonstrate layout, navigation, collapse, and layer filtering without overwhelming the initial view. Use consistent sample names and make the active project immediately apparent.

DELIVERY AND VERIFICATION
- Present a cohesive working experience, not a checklist or static mockup, whenever the environment permits implementation.
- Make the primary interactions actually work: menu hide/reveal, view switching, pan, zoom, fit-to-view, node selection and traversal, Ctrl-click return to broader context, collapse/expand, layer filtering and isolation, project navigation, simulated live intake, and graph pivoting.
- Include concise in-product hints for non-obvious gestures, readable labels, visible keyboard focus, accessible contrast, and distinct visual treatment for node types, layers, selection, agent presence, and new activity.
- Keep animation brief and non-blocking. Preserve orientation cues during navigation and avoid disrupting the user’s current viewport when updates arrive.
- Before finishing, verify each interaction above in the prototype or explicitly mark it as unavailable. Summarize the implementation approach, how to run it, which behaviors are simulated, and any remaining limitations. Do not describe unimplemented behavior as functional.
