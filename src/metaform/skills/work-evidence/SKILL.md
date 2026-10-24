---
name: work-evidence
description: "Optional references for faithful assignments, reuse, debugging, verification, review and current documentation. Load the reference that helps the assigned outcome."
metadata:
  ing.metaform.address: "prompt.skill.work-evidence"
  ing.metaform.discover: "true"
  ing.metaform.version: "1.0.0"
  ing.metaform.tier: "1"
  ing.metaform.requires: ""
---

# Work evidence references

Use these informational references when they contribute to the assigned work. They add no approval states, role restrictions or completion prerequisites.

| Reference | Useful when |
|---|---|
| [Assignment](references/assignment.md) | Preparing a delegation or investigating intent drift |
| [Reuse](references/reuse.md) | Considering a new implementation mechanism |
| [Debugging](references/debugging.md) | Establishing cause from evidence |
| [Verification](references/verification.md) | Matching an outcome to observations |
| [Review](references/review.md) | Reporting or reconciling a concrete finding |
| [Documentation](references/documentation.md) | Maintaining an authoritative current description |

Through MCP, discover the manifest with `skills/get` at `skill://metaform/work-evidence/SKILL.md`. Use `resources/read` for that URI or a selected reference such as `skill://metaform/work-evidence/references/assignment.md`. Native deployments use the relative links above.

These references adapt the selective ideas recorded in `COOKBOOK_ASSESSMENT.md` and `PROMPT_REVISIONS.md` in the supplied Metaform_Context_and_Agent_Flow_Audit package. The underlying cookbook and omitted prompt-writing materials were not supplied with that package. These are Metaform adaptations of that assessment, not imported cookbook policy or a measured efficiency claim.
