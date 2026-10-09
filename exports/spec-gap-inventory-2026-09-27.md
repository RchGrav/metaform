# Spec gap inventory, 2026-09-27

What this is: design points that live in notes or in conversation and have no specification record, plus places where the specification and the MetaformFoundation disagree. Made by keyword checks against `specifications/spec/01` to `09`, not by reading all 273 records. A keyword match shows a record mentions the subject. It does not show the record states the design correctly.

## Files to hand to the next AI

| File | Holds |
|---|---|
| `exports/notes-export-2026-09-27.md` | All 63 Claude memory notes and their index, unedited, 147 KB |
| `exports/metaform-intake-20260927T212631Z-full.md` | The last intake, every field of 63 elements, 41 joins, 29 subtype joins, 273 refs, 19 work records |
| `exports/metaform-intake-20260927T212631Z-full.json` | The same intake as the exchange document, with ids |
| `exports/e8db85b1f53d4ad69db860d5b17b55d5-report.md` | The intake agent's report on the project |
| `exports/e8db85b1f53d4ad69db860d5b17b55d5-feedback.md` | The intake agent's feedback on the intake process |
| `specifications/spec/CAPTURE.md` | 221 design points from 09-11 to 09-27, each with the record said to carry it |
| `specifications/spec/OPEN-QUESTIONS.md` | The open D questions |
| `CLAUDE.md` in the repo | The MetaformFoundation, the owner's own text |

## 1. Said in the session of 2026-09-27 evening, written nowhere else

Each point has the reason as I understand it.

1. **Join text is a short statement, enough to orient an agent.** It is not documentation. Reason: an agent reads a node to learn what a part is for, who receives it and what surrounds it, a 360 degree view from where it works. File details are in the file, which the path ref names. Detail copied into the map goes stale and is paid for on every read. The last intake wrote documentation into the observation and function fields.
2. **The Canonical Intake states no size or aim for join fields.** The words short, concise and orient do not appear for them. This is the gap that let point 1 happen.
3. **The instructions an agent receives at connection must instruct.** Today they are each module's `purpose` text, which describes the module. Reason: an agent connecting needs its next action, not a catalog.
4. **When the repository is not onboarded, the instructions say to onboard it.** MCP-009 has a no-intake notice. Whether that notice is the onboarding instruction the owner means is not confirmed.
5. **An intake must not read past notes or memories.** The footer says so since step 40. It cannot hold while the notes sit in the folder being mapped, `specifications/spec` is 1.49 MB, and while a subagent inherits CLAUDE.md and the memory index from the harness. Measured effect: about 130K tokens before, 300K to 600K and 25 minutes on the last runs.
6. **A Markdown exporter.** A concise export of a system's understanding from the map. Agreed fields: element name, address, role and paths, and per join the receiver, provider, purpose, relation and non_goal. Not built. No spec record.
7. **Metaform's MCP server is not registered in Claude Code on this machine.** `metaform install claude` has not been run since the rebuild. One old entry exists for another project and uses the bare launcher path, which MCP-016 rules out.
8. **The module field named `purpose` collides with Operative Purpose.** It is a module's short description. One vocabulary says a second meaning for a term is a defect.

## 2. The specification disagrees with the MetaformFoundation

The Foundation is the owner's text. I have not judged which side is current.

| Subject | Foundation | Specification |
|---|---|---|
| Bases | code, document, media, data, exterior | MAP-014: code, document, media, data, stakeholder. "Exterior is gone." |
| Join roles | hard dependency, property, supportive | CAPTURE 09-25: hard dependency is no longer a join role, MAP open question 17 |
| Parametric | An array of tunables on a Type, names reserved as illegal entries | No record mentions parametric |
| Signal | The way an Operative Purpose is satisfied | No record uses signal in this sense |
| SE | supportive is a role in the join | MAP-017: SE is Substantial Element. The intake agent found both meanings in use |
| C(T) | Each Receiving Entity bound to its Operative Purpose and the Type's single Encounter Function | MAP-001: C(T) is theory, no Type record holds a single encounter function |

## 3. In notes, with no specification record found

| Note | Point |
|---|---|
| `mgm-is-employer-code` | MGM is employer code and never appears in demos, tests or anything public |
| `intake-is-ip` | The intake ships with the release. Attribution is what is protected |
| `start-intake-before-agent` | The intake is started before the agent launches, so the page shows it from the first moment |
| `metaform-de-is-the-chassis` | The DE is nearly the artifact itself. CAPTURE marks it not placed |
| CAPTURE, Not placed | Jev: optional, never a requirement, low confidence bounces back to the entering agent |
| CAPTURE 09-11 | Coarse intake and deep intake, superseded, not placed |
| CAPTURE 09-12 | The XML workflow format, waits on the workflow module, D44 |
| CAPTURE 09-25 | Backup and restore are separate from import and export and not specified |

## 4. Recorded as design, mechanism open or not built

CAPTURE says step 63 placed these. Each record is design with the mechanism open.

- Work states on nodes, lifecycle looks, questions at nodes. VIEW-020, MAP-048.
- Tasks on nodes and the work queue in the MCP server.
- For-each prompts that build knowledge layers.
- Item flags: task, read_first, always shown. Rules listed, not shown every time.
- Past work references.
- Critics write the task. Blind-spot entries in a blind-spot layer. No critic prompt exists.
- No correction layers, changes are versioned updates. The intake agent reports this is not placed and the stack still stands.
- The element is only its address and name_length, the project's name goes on the join.
- TRAO-DAG state on nodes and the computed blind-spot delta, D101.
- Submitting work in the web GUI, D92. First-run provisioning, D96.

## 5. The quality problem across the specification

- 214 of 273 records have status confirmed and 46 recommended. A recommended record is an agent's choice, not the owner's decision.
- 53 lines in the nine sections name the owner. The memory notes quote him more heavily. A record that holds his words and a date holds no reason that survives the session.
- CAPTURE lists each point with a record id. It does not show that the record's Why states the reason. That check needs a read of each record against the design, and I have not done it.
