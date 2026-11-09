# Reconnaissance, isolation and implementation ordering

## Guiding approach

Build and review the new functional specification first, grounded where possible in documented semantics and the observed repository. Legacy inspection is a final completeness and mechanism-recovery sweep, **not a substitute** for specifying the intended system.

## Suggested stages

1. **Candidate spec first.** Consolidate the decisions and current design into detailed behavior and contracts. Respect source precedence and preserve original semantic formulas.
2. **Read-only reconnaissance.** Agents examine the old repository for functional knowledge, inter-module dependencies, integration constraints, useful mechanisms, prompt bodies, and behavior not covered in the spec. Produce a referenced extraction package, distinguishing fact, interpretation and suggestion.
3. **Owner review of extraction.** Present the collected functional knowledge and every candidate legacy prompt for inspection, including conflicts, weak prompting and gaps. Do not transfer implementation code. The owner can correct omissions and decide prompt disposition.
4. **Independent specification critique.** Refine the candidate with critical agent review and optionally BMAD techniques. Only accepted findings become normative requirements. Address major open choices outside a long Pro run.
5. **Isolated clean rebuild.** Create a new implementation workspace/container whose agents do not automatically index or import the legacy source tree. Permit specific read-only references for an explicitly identified question; no bulk code migration. Carry forward agreed functionality, not unreviewed implementations.
6. **Dependency-ordered development.** Lay the storage/namespace and semantic contracts down before depending modules; introduce intake and retrieval operations, knowledge delivery, orchestration, messaging/lifecycle, and presentation/integrations in an order determined by actual dependencies. Split worktrees by dependency boundaries, not merely by directory or file; do not separate tightly coupled interfaces across concurrent workers without a shared contract.
7. **Continuous verification.** Evaluate each slice against spec-derived acceptance tests, including duplicate context delivery, no unsolicited informational model turns, read/write semantics, team selection and agent retirement behavior.

## Repository evidence already inspected in conversation

Existing architecture and remediation documents describe frozen GUI controls, duplicate paid turns and oversized contextual reads. They are historical diagnostic evidence, not authorization to implement their proposed solutions. The existing peer messaging implementation describes informational notes; this directly requires conflict review against the new no-informational-messaging instruction. The Python project metadata specifies Python >=3.11; the optional local voice GPU dependencies target NVIDIA/CUDA on Linux/Windows. These facts do not require running the new development process on a particular host.

## Environment recommendation

Prefer the Mac Studio's Linux container setup for convenience if its container filesystem, mounted workspace and provider credentials behave correctly. WSL2 is equally legitimate. Keep the bootstrap/agent instructions portable and the legacy repository mounted read-only when examining it; leave it unmounted for normal clean implementation work. No environment was created or modified in this handoff.
