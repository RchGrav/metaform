**Shared knowledge service and portable projects — initial feature brief**

**Concept.** Metaform uses one operating model with either a shared service or a self-contained project copy. The service stores global inference and local project data, tracks each project, and supplies the knowledge associated with it.

**Purpose and beneficiaries.** People and agents working across projects can use centrally maintained knowledge while retaining the ability to export an individual project and continue working independently of the service and its database.

**Proposed behavior.** A connected project operates through the shared service. Export gathers the project's local inference and the related global inference by following globally inferred joins and joins inferred locally for that project. Workflow attachments and latent inference can connect objects outside the project's own contents; those relationships participate in gathering the knowledge the project needs.

For example, a project's workflow may attach to an external object whose globally inferred joins lead to further relevant knowledge. Those connections travel with the project. Another project's local joins attached to that shared object do not extend this project's traversal.

The portable copy operates with JSON knowledge storage and local SQLite execution state. Its prompts, workflows, and graph operations retain the same operating model.

**Shared-service process management.** When the CLI or MCP loads for service-backed operation, it checks whether the global service is actually running. It reuses a verified running instance and starts the service when needed. The check must distinguish the live Metaform service from stale records left by a previous instance; the mere presence of a PID file, lock file, or startup marker does not establish that the service is running.

**Metaform participation.** The feature connects project tracking, global and local inference storage, join traversal, workflow relationships, and portable export. The exported knowledge retains its source provenance and the independent Contextual and Latent representations.

**Positioning and value.** Shared knowledge supports work across projects; a project-focused export carries the developed understanding associated with one project into an independently usable copy. The extent of exported global knowledge follows the project's related inference rather than the size of the shared store.

**Initial scope.**

- A shared service storing global inference and each project's local data.
- CLI and MCP startup that checks actual service liveness, reuses a running instance, and starts one when needed.
- Project tracking and association with related knowledge.
- Export traversal through globally inferred joins and the selected project's locally inferred joins, including connections from workflows and latent inference.
- Uniform project operation through the service or a portable copy.
- JSON knowledge storage and local SQLite execution state for portable operation.

**Open choices.** The service interface, process-management mechanism and liveness test, project-selection experience, physical storage layout, and concrete traversal implementation remain to be designed. Returning portable changes to the shared service has not been developed in this discussion.

**Source context.** This brief records Rich's agreed concept from the current discussion. Source inspection used repository revision `f2f78b79c56142e39a5d507cbe4c78b6d0841dad`: `src/metaform/portable.py` already exports an executable project but copies the entire global graph; `src/metaform/backends.py` supplies JSON graph operations; `src/metaform/app.py` opens project-scoped storage and uses SQLite for execution state. `docs/serena-reference.md` supplies the multi-project service reference, and `docs/SPEC.md` supplies the source-separation contract. This proposal has not been implemented; existing export tests were inspected but not rerun.
