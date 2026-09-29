# Jev and Metaform: analysis

Status: analysis, 2026-09-23, written by metaform-68 for mgm-main-f8 at Rich's request. No code was written and no API was called.

## Recommendation

Use Jev as one optional backend behind a provider-neutral **typed decision** capability. Do not make it a dependency of the chassis or of intake.

1. Run a measured pilot on three decisions before building anything around Jev: change impact, core-or-layer routing of facts, and finding kind. Each is a closed choice over options that Metaform already records. Each is made today by an LLM or by nobody. Each is cheap to check against labels on the MGM map.
2. Record every decision as a receiver-owned join with its schema, options, probabilities, confidence and pinned model version, as described below. A decision is an observation. It never rejects, gates or rewrites an intake answer.
3. Keep Jev away from everything that writes purpose, function, relation or observation prose, and from naming new namespace addresses. Those are the intake's work, and Jev cannot write text.

The hypothesis to test was that Jev is the "fast recognition step" of amortized inference made explicit. It holds only halfway:
- **Where it fails.** The recognition that builds the amortized record is the intake. The intake names types from an open vocabulary and writes each join's particulars, and Jev can do neither.
- **Where it holds.** Once the map exists, many later steps are recognitions over a finite set the map supplies: which recorded element a change touches, which address a task is about, which layer a fact belongs to. Jev fits there. It is a cheap reader of the amortized record, not the thing that amortizes.

## What Jev is, verified and claimed

"Verified" below means stated in TypeSafe's own pages or in the Pydantic AI documentation, read on 2026-09-23. Nothing here was tested by running Jev.

| Statement | Source | Standing |
|---|---|---|
| A "System One" model from TypeSafe AI, in early access since 2026-09-15 | typesafe.ai blog; Wikipedia | Verified as stated |
| Generates no text: "Jev is not a language model. You give it a text and typed questions, and it answers each one with a confidence. It does not write text." | Pydantic AI docs | Verified as stated |
| Three question types: Choice picks one option from a list, Score rates against ordered levels, and Noul asks "is this statement true?" | docs.typesafe.ai | Verified as stated |
| Up to 255 options per question: "Jev supports a cardinality up to 255" | blog; Pydantic AI docs | Verified as stated |
| Supported output types in Pydantic AI: `bool`, `Literal` or `Enum`, bounded `float`, `IntEnum` rubrics, lists of `Literal` for several yes/no answers, dicts from `Literal` to `bool`, and nested models. Not `str`, unbounded numbers, dates or media. | Pydantic AI docs | Verified as stated |
| Returns a typed value, a probability distribution for Choice and Score, and a confidence | docs.typesafe.ai; Pydantic AI docs | Verified as stated |
| Confidence is described two ways. Pydantic AI calls it the "margin from decision threshold". The blog says it is "calibrated: higher confidence means higher accuracy". | Pydantic AI docs; blog | The definition is verified as stated. Calibration is a vendor claim, not tested. |
| "Type errors: 0%": output cannot fall outside the schema | blog | Follows from the design. The vendor also says it "can't hallucinate", which is a claim, because a wrong option is still possible. |
| Latency 70 to 500 ms end to end | blog | Vendor claim |
| Price $0.042 per million input tokens, output free | blog; docs.typesafe.ai models page | Verified as stated. The brief quoted $0.42 per million, and the primary sources say $0.042. |
| About $0.0004 per average decision | third-party pages citing TypeSafe benchmarks | Vendor claim, secondhand |
| "40 to 200 times faster", "40 to 400 times cheaper" than frontier LLMs | blog; Wikipedia | Vendor claim. Wikipedia reports TypeSafe's own caveat that the tested workflows were built by its team, and that gains are "likely to sit at the high end of real-world results". |
| Limits: 64k tokens per request, of which 32k for the state plus the longest question. Text input only. 250,000 tokens per second and 1,200 requests per minute, "adjusting dynamically". | docs.typesafe.ai models page | Verified as stated |
| Model ids: `jev-1.13.0`, with moving aliases `jev-latest` and `jev-preview` | docs; Pydantic AI docs | Verified as stated |
| "Jev is not trained on customer requests or responses". Zero data retention for enterprise customers under a DPA. | docs.typesafe.ai models page | Verified as stated |
| Hosted service only. No self-hosted or on-premises option is described. | blog; docs | No option found in the pages read |
| Pydantic AI integration: `typesafe:jev-latest`, `TYPESAFE_API_KEY`, thresholds such as `typesafe_boolean_threshold`. It cannot revise answers through retries. It is unreliable for arithmetic, counting and dates. | Pydantic AI docs | Verified as stated |
| Trained only on synthetic data with "Reinforcement Learning for Calibrated Decisions" | Wikipedia | Secondhand |

Sources:
- https://typesafe.ai/blog/introducing-system-one-models-and-jev
- https://docs.typesafe.ai/ and https://docs.typesafe.ai/models
- https://pydantic.dev/docs/ai/models/typesafe/
- https://en.wikipedia.org/wiki/Jev_(AI_model)

## Two rules that shape every use

- **No gating on inference.** Contracts describe and never reject, and intake is never gated or judged. A Jev decision about an intake answer is therefore recorded for observation. It never refuses, repairs or hands back the answer. Routing a low-confidence decision to an LLM or a person is allowed only where the workflow author or the orchestrator wrote that route. The server adds none.
- **Context is selected by masks, never by similarity.** The spec says `orient` is lexical and deterministic. A Jev pick among addresses is a model judgment. So Jev may suggest candidates as a recorded decision, but it must not become the way context is selected unless Rich changes that rule.

## Candidate uses

Each entry gives the decision's schema, what feeds it, and what consumes the output. "Value" is my ranking. It weighs how often the decision is needed, how much it costs today, and how well it fits a closed choice.

### 1. Change impact. Value: highest.
- **Schema:** Noul per element, "does this change alter what the element does for its receivers?". Or a list of `Literal` over the map's roots and subtypes, which holds 72 on MGM.
- **Fed by:** a commit diff or a changed file list, plus each candidate element's core fields from `element`. `where` gives the first candidates by path, and Jev decides which of them changed in function.
- **Consumed by:**
  - the reinfer path: `workflows.reinfer` regenerates only the recipes whose inputs changed;
  - the staleness mark on a layer;
  - a job's address list.
- **Why it fits:** keeping the record current is the running cost of amortized inference. Today an agent rereads the code to find this out, and that rereading is exactly what the record is meant to spare.

### 2. Core or layer routing of a fact. Value: high.
- **Schema:** Choice over `core`, `layer:medium`, `layer:encoding`, `layer:language`, `layer:genre`, `layer:style`, `layer:purpose`, `layer:other`. The last seven follow the intake's list of non-functionalities.
- **Fed by:** one sentence or one ref, taken from an import's notes, an agent's memory, or a layer file, plus the receiving element's core fields.
- **Consumed by:** layer import and memory creation, which place the fact accordingly. A `core` answer on text headed for a layer becomes a finding, never a silent move.
- **Why it fits:** mixing notes into the functional core was one of the orientation failures recorded on 2026-09-23. It is a closed choice.
- **Both branches:**
  - Under the current attachment model, the answer picks a layer address.
  - Under the layer-join model, it picks a layer join type. If selectors key on `type#id`, a second Choice picks the instance.

### 3. Finding kind. Value: high.
- **Schema:** Choice over `drift`, meaning the map and the code have diverged; `violation`, meaning the code breaks a designer rule; and `missing`, meaning the map lacks an element the code has. Add `stale_note` if Rich wants the MGM layer's "Notes: ... stale" findings kept apart.
- **Fed by:** the finding's text and the element it names.
- **Consumed by:** the layer's item `kind` field, the latent critic's output, and the orchestrator deciding what to fix first.
- **Why it fits:** the MGM layer's 22 findings already fall into these kinds by hand. It is cheap, frequent, and easy to label.

### 4. Authored branch conditions and per-step choices in workflows. Value: high, under the authored-flow rule.
- **Schema:** Noul, or a Choice among the branches the author wrote.
- **Fed by:** the step's state: the previous step's answer and the bound inputs.
- **Consumed by:** the workflow engine's branch step, in place of an LLM call or a person's answer.
- **Why it fits:** it evaluates a condition the author wrote. It does not invent one. The probabilities are recorded with the run, so a replay shows why the branch went the way it did. This supports Rich's deterministic prompt chain.
- **Limit:** Jev may choose "hand off or not" and "blind to the repo or not" only where the author wrote that choice as a branch. It never adds a handoff.

### 5. Candidate addresses for a task, a suggestion beside `orient`. Value: medium to high.
- **Schema:** a list of `Literal` over the map's addresses, which is 72 on MGM. For a map over 255, split it into stages: roots first, then the subtypes inside the chosen roots.
- **Fed by:** the task or bug text, and the addresses' readings.
- **Consumed by:** the orchestrator when it sets up a job's addresses and scope.
- **Condition:** only as a recorded suggestion beside the lexical `orient`, under the similarity rule above.

### 6. Layers a job gets. Value: medium. It depends on the layer model.
- **Schema:** a list of `Literal` over the project's layer keys.
- **Fed by:** the job's instructions and addresses.
- **Consumed by:** the job's `layers` field. This is a suggestion the orchestrator confirms, because the job model says the orchestrator chooses exactly which layers a worker gets.
- **Both branches:** under the attachment model the options are layer addresses. Under the layer-join model they are layer join types, or `type#id` pairs if selectors key on instances.

### 7. The latent critic's triage. Value: medium, with a risk.
- **Schema:** Choice per join over `agree`, `questionable` and `missing_something`.
- **Fed by:** the Native account, one join at a time.
- **Consumed by:** the latent pass, which can spend deeper reasoning on the flagged joins.
- **Risk:** the latent pass exists to reason from an uninvolved position and "follow what its latent space says feels right". A cheap first filter can narrow what it looks at, and that is a blind spot of its own. Use it to order the work, never to skip joins.

### 8. Role assignment: VE, AUE, DE, SE, NE. Value: medium as an audit, low as an author.
- **Schema:**
  - Choice over the five roles, per element.
  - For the Defining Element, a better schema is a Choice over the candidate elements: "which element's loss would leave the artifact unable to remain the same type?" The role is relational, and a per-element label cannot see the whole graph.
- **Fed by:** the element's core fields and joins.
- **Consumed by:** a finding when it disagrees with the recorded role. It never rewrites the role.

### 9. Namespace typology test. Value: medium as an audit.
- **Schema:** Choice over `same_type_as_parent`, `function_within_parent` and `non_functionality`. A second Choice, asked only when the answer is `non_functionality`, names the kind: genre, medium, encoding, language, style or purpose.
- **Fed by:** the address, its reading, the parent's reading, the join's function text, and the intake's namespace validity examples as part of the state.
- **Consumed by:** a finding on the element. It never refuses the entry. It is also a check on layer names only if Rich wants one, because layer addresses are exempt from the validity rules.
- **Why only an audit:** this is the intake's core judgment, made with the whole trace in view. A per-entry recognizer is a useful second opinion, not a replacement.

### 10. Memory relation verbs. Value: depends on Rich's answer.
- **Fixed set:** a Choice over the verbs, fed by the two roots and the observation that prompted the link.
- **Free active-voice text:** Jev cannot produce it. At most it can say whether a verb an agent wrote matches an existing one, as a Choice among the verbs in use.

### 11. Other uses found
- **Imperative strength of a rule.** A Choice over `must`, `must_not`, `should` and `prefer` when prose rules are imported into a layer. The MGM layer uses exactly these.
- **Practice applicability.** Noul per practice: "does this change fall under this rule?". It feeds a handoff with only the practices that apply.
- **Duplicate memory.** Noul: "do these two observations state the same fact?". It suggests a merge, and never deletes.
- **Answer shape.** A Score over "how fully does this answer follow the output instruction?". Recorded only, and never used to reject an answer.

## Where Jev does not fit

- **Anything that writes text.** That covers purpose, function, relation, observation, non_goal, notes, statements, `why` and `check`, which is all of the intake's join content.
- **Naming a new namespace address,** because the vocabulary is open.
- **Choices over more than 255 options** unless they are split into stages. A large map needs root, then subtype. A layer with more than 255 items needs grouping first.
- **Whole-graph judgments** from one call, such as "exactly which element is the DE" over a large map, unless the question is posed as one Choice over the candidates.
- **Large states.** The state plus the longest question must fit in 32k tokens. The MGM map XML is about 100 KB, likely near or over that limit, so decisions should be fed one element's record, not the whole map.
- **Arithmetic, counting and dates,** which the Pydantic AI docs call unreliable.
- **Images and other media.** Jev takes text only, so media artifacts need another path.

## How it enters the system

Two ways in. Both keep the nonce chain and the chassis-and-module split.

**A. As a workflow step kind, run by a `harness_runner` provider.**
- A workflow step of kind `decision` carries its authored schema.
- The harness delivery already has `schema` and `output` keys (`modules/workflows/operations.py`, `drive`).
- A `jev` provider beside `claude` and `codex` reads the assignment's prompt as the state and the schema from the delivery. It calls Jev and submits the typed answer, the probabilities and the confidence under the assignment's header.
- The nonce chain and the exact issued prompt stay as they are.

**B. As a module's agent command.**
- A `decisions` module declares `purpose` and an agent command `decide(question, schema, inputs)`, where `inputs` are references to joins in the record. It is served as the MCP tool `decisions_decide` and as `metaform <nonce> decide`.
- Recording a decision is a write, so under the Authority rule it needs an orchestrator nonce, unless Rich counts decisions with memories.

**Recommendation: build B first, provider-neutral.**
- The module's backend setting picks Jev, or any LLM with structured output, for example Claude Sonnet 5 with a JSON schema, or a person.
- The same decision record comes out whichever backend answered, so switching backends needs no change elsewhere, and an A/B comparison needs no second format.
- A uses B's recording once workflows need decision steps.
- Pydantic AI, MIT licensed and standard in the AI space, is the client for Jev and needs no code of TypeSafe's own. That fits the dependency rule.

## How a decision is recorded

Every record is a join owned by its receiver, and the metaform is its own provenance.

- **Receiver:** the element or join the decision is about.
  - A change impact decision about `code.failsafe.gateway.mesh` is owned by that element.
  - A decision about a join is owned by the join's owning element, with `subject` naming the join.
  - A decision about an internal subtype is a knowledge-only record at its address, per M2 option A.
- **Join fields:** `type: decision`, `question`, `schema` with its kind (choice, score or noul) and its exact option list, `answer`, `probabilities` for every option, `confidence`, `provider`, `model` pinned as for example `jev-1.13.0`, never an alias, `threshold` if one was applied, `routed_to` as accepted, llm or person with the reference of the follow-up decision, `inputs` as exact join references, and `dependencies` set to those inputs.
- **The exact state sent:** either retained whole, as workflows retain issued prompts, or as a sha256 plus the input references that rebuild it. Retaining it whole is safer for audit, and the byte cost is small.
- **Provenance:** comes from the existing production joins. The producing operation `decisions.decide` records module, operation, nonce, inputs and outputs, and the output's owner gets its `provenance` join.
- **Both branches of the layer model:**
  - Under the attachment model, the decision join sits on the receiver, attached in a `decisions` layer.
  - Under the layer-join model, the decision is itself a layer join of a decision type with its own id.
  - Either way it stays out of the functional core.

## Calibration and trust

- **Vendor claim, not tested:** confidence is calibrated.
- **What would be measured:**
  1. **Labels.** Rich, or a reviewer he names, labels the MGM map's decisions:
     - roles for the 16 roots;
     - typology for the 56 internal subtypes, plus invalid entries taken from the intake's own examples, such as `code.cpp`, `media.photo.jpg` and `code.game.engine.platformer`, and from the old map's mixed-in notes;
     - finding kinds for the MGM layer's 22 findings;
     - core-or-layer routing for sentences from the old map's notes.
  2. **A/B.** The same decisions through Jev and through Claude Sonnet 5 at high effort with a schema-constrained output, both recorded by the `decisions` module in the same format.
  3. **Measures:** accuracy against the labels; a reliability table of confidence buckets against the accuracy within each bucket; cost; latency.
  4. **Thresholds from the data.** Pick each decision's handoff threshold from the reliability table, not from the vendor's default of 0.6 for tool calls. Below the threshold, the route the author or orchestrator wrote sends the decision to an LLM or a person. Both answers are recorded.
- **Sample size.** It is small: 16 roles and 22 findings give wide error bars. Extending the labels with the other intake samples in `specs/`, `intake_sample_a` to `d`, raises the count. Until then, results are indicative.
- **Drift over time.** Pin the model id, and rerun the labeled set on every model change.

## Cost and latency

- **Figures used:**
  - Jev input is $0.042 per million tokens, and output is free. That is verified as stated.
  - Claude Sonnet 5 is $2 input and $10 output per million tokens, and Claude Opus 5.5 is $4 and $20. Those come from the Claude API reference bundled with this session, cached 2026-06-24.
- **Example, one role decision with a 4,000-token state:**

| Worker | Estimate | Latency |
|---|---|---|
| Jev | about $0.00017 | 70 to 500 ms, vendor claim |
| Sonnet 5, about 300 output tokens | about $0.011, about 65 times Jev | seconds |
| Sonnet 5 at high effort, about 2,000 thinking and output tokens | about $0.028, about 165 times Jev | seconds to tens of seconds |

- **Honest scale.** Metaform's current LLM spend is the intake and latent passes, which write prose. Jev replaces none of it. Its saving applies to decision steps, and most of those do not exist yet. The gain is mainly that checks become cheap enough to run on every change, not a smaller bill for today's work.

## Risks

- **Proprietary and hosted.**
  - No self-hosted option is described.
  - Every decision sends its state, which may include project code or client data, to TypeSafe. Zero data retention is offered to enterprise customers under a DPA, or through a gateway.
  - For MGM, the state would include code excerpts and designer rules.
- **Early access since 2026-09-15.**
  - Rate limits are "adjusting dynamically".
  - The aliases move.
  - Availability and pricing can change.
- **Lock-in.** It is reduced by the provider-neutral `decisions` module and by recording each decision in one format whatever the backend.
- **Vendor-built benchmarks.** TypeSafe's own gains come from workflows its team built. The A/B above is the only evidence that counts for Metaform.
- **Confidence misread.** Confidence is a margin, and calibration is claimed. A high-confidence wrong answer is possible, so every decision is recorded and reviewable, never final by itself.
- **Scope creep toward gates.** Cheap, typed checks invite rejecting answers. Rich's no-gating rule forbids that: a Jev decision is recorded for observation and never refuses work.
- **A sign-up is needed for any pilot.** No account exists, and none was created.

## Open items that change this analysis

- **The layer model:** where a layer's metadata lives, how a join type is known to be a layer, and whether selectors key on type or `type#id`. This affects uses 2 and 6 and the recording branch.
- **Memory:** whether relation verbs are a fixed set, which affects use 10, and whether decisions count with memories for the nonce rule.
- **Whether Rich accepts Jev suggestions beside the lexical `orient`,** which is use 5.
