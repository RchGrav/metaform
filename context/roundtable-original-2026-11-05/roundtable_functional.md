# Roundtable — Functional System Specification

**Language-agnostic functional design**

## 1. Theory of Operation

Roundtable is a collaborative multi-agent system in which independent AI agents work together to accomplish a user-defined objective.

The objective is supplied by the user and may involve developing a design, completing or refining a specification, solving technical problems, producing software, or another substantial undertaking.

Roundtable is not a conversation summarization system. Conversation is the mechanism through which participants exchange ideas, challenge assumptions, coordinate their work, and develop the requested deliverable.

Participants share a working directory where they can independently or collaboratively produce substantive artifacts.

### 1.1 Collective Intelligence Through Diversity

Roundtable is designed around the observation that different AI models possess different intellectual tendencies, strengths, weaknesses, and approaches to problems.

A model may recognize a good idea when presented with it without necessarily volunteering that idea independently.

More capable models are not necessarily more inclined to challenge assumptions, explore alternatives, or introduce unrequested insights.

Different model families, providers, and harnesses may therefore contribute perspectives that would not emerge from multiple instances of the same model.

Roundtable brings these intelligences together so they can introduce, criticize, refine, and develop one another's ideas.

Agreement is not the objective. Productive collaboration toward the user's goal is.

### 1.2 The Economics of Multi-Agent Communication

In multi-agent collaboration, every message distributed to the group consumes inference tokens when the other participants process it.

A repetitive or unproductive message therefore incurs more than its original generation cost. Its contents are also consumed by the other participants, potentially repeatedly as their context grows.

Roundtable uses an inexpensive AI judgment engine, JEV, to evaluate contributions before distributing them.

Messages that contribute nothing useful are vetoed before they consume the attention and inference budgets of the other participants.

This makes JEV an inference-efficiency mechanism as well as a contribution evaluator.

### 1.3 Strategic Participation

Agents are not obligated to contribute on every turn.

They may speak immediately, pass and listen to others, or spend time independently developing more substantial ideas in the shared workspace.

Passing and being skipped while working accumulate additional speaking capacity.

This gives participants a strategic choice between immediate discussion, observation, and deeper independent work.

The system is intended to support productive thought and work, not require constant conversational output.

### 1.4 Collective Direction

Roundtable can pursue multiple discussion topics within the same overall objective.

When a topic is exhausted, participants independently propose what the group should address next.

JEV judges whether the proposals express the same underlying intent, rather than merely whether they use similar language or discuss related concepts.

The proposals receiving the greatest aggregate confidence of sameness determine the next topic.

This allows collective direction to emerge from the independently expressed intentions of the participants.

### 1.5 Persistent Work and Reasoning

Topic changes do not restart the collaboration.

The user's original objective, preceding discussion, reasoning, and shared artifacts remain part of the continuing work.

A topic is a focus of collective attention within the larger undertaking, not a new independent conversation.

---

## 2. Participants and Shared Workspace

A Roundtable contains multiple independently operating AI agents.

Participants may use different models, different providers, and different agent harnesses.

All participants receive the user's objective and a common explanation of the Roundtable process.

They work within a shared directory.

The shared workspace supports collaborative production and refinement of:

- Markdown documents
- Designs and specifications
- Proposals and detailed explanations
- Mermaid diagrams
- Code samples and implementations
- Other artifacts relevant to the objective

Agents may develop substantial work in the shared folder outside the discussion channel.

Other participants can inspect, challenge, extend, and refine that work.

The workspace is where the substantive deliverables are produced. The discussion provides coordination and deliberation.

The wider platform uses a Rust chassis, Bevy, and an event-driven architecture. Agents may also produce WASM artifacts intended for the gameworld. Roundtable is a collaborative component of this larger system.

---

## 3. Participant System Prompt

The following plain-English prompt is given to every participating agent, alongside the user's objective and the current Roundtable context.

> You are an independent participant in a Roundtable of AI agents collaborating to accomplish the objective provided by the user.
>
> Contribute your intelligence, expertise, ideas, and critical judgment. Challenge, refine, and build upon one another's work. Your purpose is to produce the requested result, not merely discuss or summarize it.
>
> You share a workspace where you can create and collaboratively develop Markdown documents, specifications, proposals, Mermaid diagrams, code, and other artifacts. You may spend time developing substantial work independently of the discussion.
>
> Discussion is turn-based. You are informed of your current character allowance. You can contribute, pass and listen while banking another 512 characters, or work independently while your turns are skipped and your allowance grows by 512 characters per skipped turn.
>
> Contributions are evaluated before reaching the group. Vetoes and truncation are explained when your next turn arrives.
>
> Choose strategically when to speak, listen, or develop your ideas in the workspace. Topics may change, but the overall objective and preceding work continue throughout the collaboration.

The system supplies each participant with the current speaking allowance, applicable feedback, discussion context, and current topic.

---

## 4. Roundtable Discussion Loop

Roundtable uses a turn-based discussion process.

Each participant has an opportunity to contribute, pass, or perform independent work.

The process continues around the participating agents while the system evaluates and distributes accepted contributions.

### 4.1 Speaking Allowance

Every participant begins with a **512-character** discussion allowance.

The participant is informed of the number of characters available before contributing.

This allowance can increase through passing or being skipped while performing independent work.

The character allowance applies to discussion messages, not to the contents of shared workspace artifacts.

### 4.2 Contributing

An agent can submit a contribution addressing the current topic.

The contribution may introduce an idea, make an argument, express a position, challenge another participant, or draw attention to work developed in the shared directory.

The submitted message is evaluated by JEV before being distributed to the other participants.

An accepted contribution becomes part of the discussion shared with the group.

### 4.3 Passing

A participant may decline to contribute on its turn.

Passing allows the agent to listen to the other participants and decide when it has something worthwhile to contribute.

**Every pass credits the participant with an additional 512 characters of speaking capacity.**

The accumulated allowance is available for a future contribution.

Passing is a legitimate strategic choice, not a failure to participate.

### 4.4 Independent Work

An agent may spend time developing its ideas in the shared workspace.

This may include writing detailed proposals, specifications, explanations, diagrams, or code.

While the agent is occupied with independent work, the discussion continues without waiting for it.

The agent is skipped during its occupied turns.

**Each skipped turn credits the agent with an additional 512 characters of speaking capacity.**

When the agent returns to discussion, its accumulated speaking allowance reflects those skipped turns.

Independent work is an intended part of Roundtable participation and must not be interpreted as an instruction to abandon or terminate the agent's work.

### 4.5 Oversized Contributions

Messages exceeding the participant's current character allowance are not rejected for their length.

Instead:

1. The message is truncated to the permitted character allowance.
2. The truncated message is submitted to JEV for evaluation.
3. The discussion continues normally.
4. When the participant's next turn arrives, it is informed that its previous message was truncated and how many characters were removed.

The truncated contribution may still be accepted if it passes JEV evaluation.

### 4.6 Vetoes and Deferred Feedback

If JEV vetoes a contribution, that contribution is not distributed to the other participants.

**A veto does not credit the participant with additional speaking capacity.**

The participant is not immediately given another opportunity to revise the message.

Instead, the discussion advances to the next participant.

When the vetoed participant's next turn arrives, the system informs it of the disposition of its previous contribution and explains why it was rejected.

The participant can use that feedback alongside the discussion's subsequent developments when deciding what to contribute next.

If the previous contribution was simply accepted, no disposition message is necessary.

Truncation feedback is likewise delivered at the participant's next turn.

### 4.7 The Continuing Loop

The basic participation cycle is:

1. Identify the next participant.
2. Provide any pending feedback from its previous contribution.
3. Inform the participant of its available character allowance and current discussion context.
4. Allow it to contribute, pass, or pursue independent workspace activity.
5. Credit passing or skipped turns as specified.
6. Truncate any oversized discussion contribution before evaluation.
7. Submit contributions to JEV.
8. Distribute accepted contributions; withhold vetoed contributions.
9. Continue to the next participant.

Agents performing independent work do not prevent the rest of the Roundtable from progressing.

The discussion continues until its topic progression conditions are met.

---

## 5. JEV — Judgment Engine

JEV is an AI-based conditional judgment engine accessed through OpenRouter.

Its role is not limited to conventional semantic classification.

JEV uses a capable model to evaluate questions and conditions, returning constrained selections or judgments with associated confidence values.

Conceptually, it operates like an intelligent `if` or `case` statement.

Its output can be treated as a binary decision using a confidence threshold, or its confidence values can be used directly as numerical judgments.

JEV can evaluate multiple questions in a single inference request.

The operating characteristics discussed for JEV are:

- A 64K-token input context
- Millisecond-scale responses
- Multiple classifications per request
- No output-token charge
- An input cost of approximately $0.42 per million tokens

These characteristics make it economical to evaluate contributions before distributing them to potentially expensive participant models.

### 5.1 Contribution Evaluation

Every submitted discussion contribution is evaluated against three conditions:

**1. New contribution or position**

Does the contribution add something previously unstated, or express a position on a recently raised matter?

**2. Value**

Does the contribution move the discussion forward and help answer the question?

**3. Relevance**

Does the contribution address the subject being discussed?

Each condition must receive **70% confidence or higher**.

A contribution passes only when all three conditions meet that threshold.

JEV provides the judgment and the reasons for a veto.

The Roundtable uses those results to determine whether a contribution reaches the other participants.

These are the three specified contribution gates.

### 5.2 Why the Evaluation Occurs Before Distribution

The purpose is to prevent redundant, irrelevant, or nonproductive discussion from multiplying inference costs across the group.

A message that contributes no new information or position does not need to be processed by every other model.

The judgment occurs once before the message is broadcast.

The mechanism also encourages participants to contribute meaningful ideas rather than repeat one another or fill conversational space.

Disagreement is not inherently unproductive. A position on a recently raised matter can satisfy the first condition even when the underlying subject has already been introduced.

---

## 6. Topic Completion

The Roundtable remains focused on a topic while discussion is productive.

A topic can proceed to the next topic when either of these conditions occurs:

1. **Two nonproductive rounds.**
2. **All participants pass for two rounds.**

These conditions are independent alternatives.

Reaching either condition initiates the next-topic selection process.

The overall Roundtable objective remains unchanged.

---

## 7. Next-Topic Selection

All participating agents are polled for the topic they believe the Roundtable should address next.

Each agent independently proposes a topic.

JEV then evaluates the proposals through pairwise judgments of sameness.

### 7.1 What JEV Is Asked to Judge

JEV is asked whether two proposed topics express the same underlying intent.

For example, one participant may propose improving coordination of shared documents, while another proposes preventing conflicting edits between collaborating agents.

JEV determines whether those proposals are expressions of the same intended subject.

The judgment is not simply whether the topics contain similar words or are broadly related.

### 7.2 Pairwise Evaluation

Each unique pair of proposed topics is evaluated once.

With four agents, the comparisons are:

- 1–2
- 1–3
- 1–4
- 2–3
- 2–4
- 3–4

After agent 1 has been compared with agents 2, 3, and 4, it has no remaining pairings. The subsequent comparisons involve the remaining agents.

Each comparison produces a confidence percentage representing JEV's judgment that the two proposals express the same intent.

**The confidence value from a pairing is credited to both proposals in that pairing.**

With four participants, every proposed topic receives three scores.

### 7.3 Score Accumulation

The scores associated with each proposal are added together.

For example:

| Pair | Confidence |
|---|---:|
| 1–2 | 95% |
| 1–3 | 20% |
| 1–4 | 15% |
| 2–3 | 30% |
| 2–4 | 25% |
| 3–4 | 85% |

The resulting totals are:

| Agent | Confidence total |
|---|---:|
| 1 | 130 |
| 2 | **150** |
| 3 | 135 |
| 4 | 125 |

Agent 2's proposed topic wins.

For \(N\) participants, each proposal receives \(N-1\) judgments, with:

\[
\frac{N(N-1)}{2}
\]

unique pairwise evaluations overall.

The score for proposal \(i\) is:

\[
S_i=\sum_{j\ne i}C_{ij}
\]

Where \(C_{ij}\) is JEV's confidence that proposals \(i\) and \(j\) express the same intent.

The proposal with the highest total becomes the next topic.

Dividing every total by \(N-1\) would produce an average confidence percentage but would not change the winner or ties. Summation is the specified method.

There is no separate 70% acceptance threshold for topic selection.

### 7.4 Tied Topics

If two proposals tie for the highest score, their topic statements are joined using **"and"**.

The combined statement becomes the next discussion topic.

This preserves both expressions of the participants' intended direction rather than arbitrarily discarding one.

### 7.5 Purpose of the Selection Mechanism

This is a mechanism for recognizing collective intent.

Each participant independently expresses what it believes should be addressed next.

JEV evaluates the degree to which those independently expressed intentions are the same.

Accumulating these judgments selects the proposal that receives the greatest total confidence of representing the group's shared intended direction.

JEV is not independently deciding what the group ought to discuss. It is evaluating the relationships between the intentions expressed by the participants.

### 7.6 Alternative Considered

An alternative discussed was to provide JEV with the last **30K tokens of the preceding discussion** and the candidate topics, then use a `case` selection to choose the next topic.

That approach would use the discussion's substantive context to select among the proposed topics.

It differs from pairwise summed-confidence selection, which derives its result from independently expressed topic intentions.

This was identified as a possible alternative, not a replacement for the specified pairwise algorithm.

---

## 8. Continuity Across Topics

A Roundtable is a continuing collaborative undertaking.

Changing the current discussion topic does not reset the agents' context or discard preceding reasoning.

Participants continue with the understanding of:

- The original user objective
- Previous discussions and decisions
- The work already developed
- The shared workspace artifacts
- The newly selected discussion topic

Topic progression changes what the participants are currently discussing, not what the overall collaboration is trying to accomplish.

The Roundtable must remain oriented toward producing the user's requested deliverable.

---

## 9. Universal Agent Harness and Model Selection

Roundtable must support the selection of participants from different agent harnesses, models, and providers.

It must not depend on manually implementing an individual communication protocol for every supported harness.

### 9.1 Agent Client Protocol

**Resource:** [Agent Client Protocol](https://agentclientprotocol.com/)

ACP provides the common communication interface between Roundtable and compatible agent harnesses.

The purpose is to allow the Roundtable to communicate with different agents through the same protocol rather than through individual vendor-specific integrations.

Relevant ACP functionality includes:

| ACP operation | Function in Roundtable |
|---|---|
| `initialize` | Establish communication and discover the harness's supported capabilities |
| `authenticate` | Complete agent-managed authentication when required |
| `session/new` | Establish a participant's agent session and working directory |
| `session/prompt` | Deliver participant turns, context, and instructions |
| `session/update` | Receive generated messages, progress, and tool activity |
| `session/load` | Restore a previously established session where supported by ACP v1 |
| `session/resume` | Reconnect and synchronize an existing session where ACP v2 is supported |
| `session/set_config_option` | Select advertised agent configuration options, including models where exposed |

ACP also provides filesystem and terminal interfaces that compatible harnesses can use to access resources and perform work.

The shared workspace may be accessed through the harness's own tools or supported ACP filesystem facilities.

The method used to supply the Roundtable's common system prompt depends on what the selected harness supports. ACP does not currently guarantee a universal system-prompt replacement mechanism across all agents.

**References:**

- [ACP v1 protocol overview](https://agentclientprotocol.com/protocol/v1/overview)
- [ACP session setup](https://agentclientprotocol.com/protocol/v1/session-setup)
- [ACP prompt lifecycle](https://agentclientprotocol.com/protocol/v1/prompt-turn)
- [ACP v2 session lifecycle](https://agentclientprotocol.com/protocol/v2/prompt-lifecycle)
- [ACP filesystem facilities](https://agentclientprotocol.com/protocol/v1/file-system)
- [Official ACP Rust SDK](https://github.com/agentclientprotocol/rust-sdk)

### 9.2 Universal Harness Discovery

**Resources:**

- [Official ACP Registry](https://github.com/agentclientprotocol/registry)
- [ACP Registry catalog](https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json)
- [acpr launcher](https://github.com/agentclientprotocol/acpr)
- [acpx](https://github.com/openclaw/acpx)

The ACP Registry provides discoverable information about published ACP-compatible agents.

`acpr` uses that registry to resolve and launch compatible agents.

`acpx` provides another existing reference for common harness names, adapter commands, and ACP session interaction.

Together, these resources provide the basis for discovering and launching supported harnesses without maintaining bespoke protocol implementations for each one.

Locally installed or otherwise unregistered ACP-compatible harnesses must also be usable.

A harness that does not natively support ACP requires an ACP-compatible adapter. The registry is not a universal detector of every arbitrary executable installed on a machine.

### 9.3 Common Agent Harnesses

Roundtable should support compatible harnesses including:

| Harness | Relevant resource |
|---|---|
| Claude Code / Claude Agent SDK | [Claude ACP adapter](https://github.com/agentclientprotocol/claude-agent-acp) |
| OpenAI Codex | [Codex ACP adapter](https://github.com/agentclientprotocol/codex-acp) |
| Pi | [Pi](https://github.com/badlogic/pi-mono) and [pi-acp](https://github.com/svkozak/pi-acp) |
| OpenCode | [OpenCode](https://github.com/anomalyco/opencode) |
| Other ACP agents | [ACP Registry](https://github.com/agentclientprotocol/registry) |

The specific harness is independent of the participant's role in the Roundtable.

### 9.4 OpenRouter Support

**Resources:**

- [OpenRouter](https://openrouter.ai/)
- [OpenRouter Models API](https://openrouter.ai/docs/api/api-reference/models/get-models)
- [OpenRouter Agent SDK](https://openrouter.ai/docs/agent-sdk/overview)

Roundtable must allow an OpenRouter API key to be supplied.

The user must be able to select participating agents by OpenRouter model identifier, including models from different providers.

Available models are obtained from OpenRouter's published model catalog, rather than from a fixed list.

The OpenRouter Agent SDK provides an agent execution framework that can be used to run models through OpenRouter. As it is not itself a turnkey ACP agent server, an ACP-facing adapter is needed when using it through the common ACP interface.

Pi provides another route for running OpenRouter models as ACP participants through its ACP adapter.

OpenRouter is also the provider used to access JEV.

This allows Roundtable participants to combine models accessed through OpenRouter with models running through Claude, Codex, Pi, and other harnesses.

---

## 10. Asynchronous Agent Operation and Activity Monitoring

Roundtable must support independently operating agents without requiring the discussion to wait for one participant to finish its work.

This is especially important because agents may spend extended periods developing artifacts, invoking tools, performing inference, or waiting on an upstream model provider.

The system must distinguish between the state of the Roundtable's participation process and the observable activity of the underlying agent.

### 10.1 ACP Activity Information

ACP provides agent-generated messages, tool activity, and session lifecycle information.

ACP v1 reports progress through `session/update` and communicates completion through the `session/prompt` response.

The draft ACP v2 protocol additionally supports explicit session activity notifications, including:

- `running`
- `idle`
- `requires_action`

These are reports from the harness.

They do not independently prove that an agent is progressing, nor do they reveal every possible upstream-provider problem.

An agent waiting for inference may legitimately produce no ACP updates for some time.

### 10.2 Independent Activity Monitoring with AgentSight

**Resource:** [AgentSight](https://github.com/eunomia-bpf/agentsight)

**Relevant library:** [agentsight-capture](https://github.com/eunomia-bpf/agentsight/tree/master/agentsight-capture)

AgentSight provides monitoring of agent activity independently of ACP messages.

Its purpose in Roundtable is to make underlying agent execution observable without depending entirely on each harness reporting what it is doing.

AgentSight supports observation of:

- Agent process activity and process trees
- Resource utilization
- Tool and subprocess execution
- Filesystem activity
- Network communication
- Model-provider requests and responses where observable
- Activity patterns associated with stalls, retries, and delays

AgentSight uses system-level tracing, including eBPF and TLS observation on supported Linux systems, and can also obtain information from agent-native session records.

Its reusable capture components can be incorporated into an application without adopting its complete dashboard.

Full eBPF observation is Linux-specific; other platforms and unprivileged operation provide more limited visibility.

### 10.3 Role of Monitoring in the Roundtable

The monitoring capability provides observations that help distinguish circumstances such as:

- An agent generating a response
- An agent executing tools
- An agent actively modifying shared artifacts
- An agent waiting on network or provider activity
- An agent process that has exited
- An agent that is alive but producing no observable activity

An agent working independently may be deliberately absent from the discussion while continuing to perform useful work.

Likewise, an agent waiting on an upstream provider may appear inactive without being hung.

The purpose of independent monitoring is to provide visibility into these conditions, not to reinterpret every period of silence as a failure.

**Being busy with independent work is not a reason to abort an agent.**

The Roundtable's specified behavior is to skip occupied participants and credit their skipped discussion turns while the group continues.

No automatic timeout-based termination of busy agents is part of the specified Roundtable behavior.

### 10.4 Upstream Provider Overload

ACP does not universally expose provider overload, internal retry activity, or rate-limit conditions.

A harness may continue waiting or retrying internally without sending detailed progress notifications.

Independent monitoring can expose some evidence of network requests, retry activity, process execution, and resource usage.

It cannot always determine whether remote inference is merely slow, overloaded, or stalled.

Roundtable uses the available observations without treating the absence of an ACP reply as proof that an agent should be terminated.

### 10.5 Relationship to the Existing Event Bus

Roundtable is part of a larger event-driven platform.

ACP provides communication with the agent harnesses.

AgentSight provides independent observations of their activity.

Roundtable itself manages participant turns, message dispositions, accumulated speaking allowances, topic progression, and collaboration.

These functions operate within the existing event-driven system without requiring agents to block one another while performing their work.

---

## 11. Intended Productive Behavior

The Roundtable's purpose is to accomplish the objective supplied by the user.

The collaboration is expected to produce substantive outcomes appropriate to that objective.

For example, a Roundtable tasked with completing an engineering specification should produce the specification, addressing technical gaps through the participants' expertise and collaborative analysis.

A Roundtable tasked with producing code should work toward producing the requested code.

The agents are expected to exercise independent judgment rather than simply restate the user's request, repeat each other, or produce conversational summaries.

Where a technical question has an established, defensible best answer, the agents should contribute that answer.

Where legitimate alternatives have materially different consequences, the agents can use the Roundtable to examine those differences, challenge one another, and develop a justified recommendation.

The shared workspace, strategic passing mechanism, independent artifact development, JEV contribution evaluation, and collective topic-selection process all exist to support this productive collaboration.

## 12. Functional Boundaries

The implementation language and internal engineering mechanisms are separate from this functional specification.

The specified behavior establishes:

- The user's objective governs the collaboration.
- Participants contribute independently and collaboratively.
- Discussion and shared artifact production are complementary activities.
- Speaking allowance begins at 512 characters.
- Passing and skipped turns each add 512 characters.
- Vetoes do not add speaking allowance.
- Oversized contributions are truncated before evaluation, not rejected for length.
- Veto and truncation feedback are delivered at the next turn.
- JEV evaluates contributions using the three specified conditions and their 70% confidence thresholds.
- Two nonproductive rounds or two rounds in which all agents pass permit topic progression.
- Every agent proposes a next topic.
- JEV compares the underlying intent of every unique topic pairing.
- Pairwise confidence values are credited to both topics and summed.
- The highest-scoring proposal wins; two tied winners are joined with "and".
- Context and work continue across topic transitions.
- Different models and ACP-compatible harnesses can participate together.
- OpenRouter model selection and its agent framework are supported.
- ACP handles harness communication.
- AgentSight provides independent execution observability.
- Occupied agents are skipped rather than terminated for being busy.
- The expected output is the requested work product, not a discussion summary.

The developer is responsible for choosing the technical implementation necessary to realize these functions without altering their intended behavior.

The existing Python implementation may be examined as historical reference, but its accumulated behavior is not authoritative where it differs from this specification.
