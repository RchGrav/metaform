---
name: investigate-work
description: Trace a failure, research a question or reconcile evidence without discarding current project understanding.
metadata:
  ing.metaform.address: prompt.skill.investigate-work
  ing.metaform.discover: "true"
  ing.metaform.version: "1.0.0"
  ing.metaform.tier: "1"
  ing.metaform.requires: ""
---

Read the selected procedure with `orchestration_apply name=prompt.skill.investigate-work`.
When orchestration is not available, `metaform_skills op=load name=investigate-work` serves the same selected source.
Native deployments retain `references/procedure.axiom` as the complete selected artifact.
