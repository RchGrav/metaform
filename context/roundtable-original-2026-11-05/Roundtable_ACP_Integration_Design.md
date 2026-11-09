# Roundtable — ACP Integration and Agent Activity Design

**Companion to the language-agnostic Roundtable functional specification**  
**Reference date:** 5 November 2026  
**Scope:** Existing ACP facilities, universal harness selection, OpenRouter-based participants, AgentSight observability, and how these facilities support the specified Roundtable. This is a functional integration design, not an instruction to redesign Roundtable or introduce additional decision gates.

## 1. Theory of operation

Roundtable brings independently reasoning agents—potentially from different model families, providers and harnesses—together to accomplish the **user's stated objective**. The objective may be completing a specification, resolving design questions, producing software, or creating another substantive deliverable. Discussion is a coordination mechanism; the shared workspace contains developing work products. A coherent transcript or summary is not a substitute for the requested result.

The design relies on several deliberate mechanisms:

- **Heterogeneous intelligence.** Different models can introduce, recognize, criticize and refine ideas that other models would not independently offer. Participants exercise independent technical judgment rather than simply comply with the most recent statement. For an engineering objective, an established best technical answer is theirs to contribute; where legitimate choices materially diverge, they explain the ramifications and recommend a reasoned choice instead of returning routine engineering decisions to the user.
- **Inference economics.** Broadcasting redundant conversation multiplies its input-token cost across the receiving agents and their subsequent turns. The inexpensive JEV model evaluates a proposed message **before** it is distributed.
- **Strategic participation.** Agents can speak, pass to listen, or work on shared artifacts. Passing and being skipped for independent work bank additional speaking capacity. They are not required to speak just to fill their turn.
- **Group-directed topics.** At topic transitions, each participant independently proposes a new topic. JEV evaluates whether pairs express the **same intended subject**, not just lexical or topical similarity; summed judgments determine the next topic.
- **Continuity.** Topic changes redirect collective attention within the same undertaking. They do not erase earlier discussion, the user's goal, or work in the shared folder.

JEV is an intelligent, trained conditional-judgment model, conceptually an AI-powered **if/case** decision mechanism rather than a keyword or semantics-only filter. Its reported confidence can be thresholded for contribution acceptance or used directly as a numeric value for topic sameness. It can evaluate multiple questions in one request. The operating characteristics provided for this system are **64K input context, millisecond-scale responses, free output, and approximately $0.42 per million input tokens** through OpenRouter. The three contribution judgments can be requested together, and topic pairings may be batched without changing their scoring rules. These are the specified operating characteristics, not separately verified current provider guarantees.

ACP connects each participant to its harness. The official ACP Registry and `acpr` help discover and launch harnesses. OpenRouter supplies selectable models and JEV. AgentSight provides **independent observation** of process, tool, file and network activity when ACP is silent. The existing chassis/event bus carries these observations and the Roundtable's own events; neither ACP nor AgentSight replaces Roundtable's collaboration logic.

## 2. Functional Roundtable loop being supported

These are Roundtable rules, **not ACP protocol methods**:

1. Each participant receives the user's objective, common participant instructions, the current topic, relevant continuing discussion, any deferred feedback, and its current character allowance.
2. Initial discussion allowance: **512 characters** per participant.
3. On its discussion opportunity, a participant may **contribute**, **pass**, or continue **independent workspace work**.
4. **Pass:** listen rather than speak; bank **+512 characters**.
5. **Occupied with independent work:** the group continues past the agent; each skipped discussion turn banks **+512 characters**. Busy work is not an instruction to abort the agent.
6. **Contribution:** if longer than the current allowance, **truncate first**, then evaluate the transmitted portion. Length alone does not reject the contribution.
7. JEV judges the transmitted contribution against **three conditions**, each requiring **at least 70% confidence**: (a) something new *or* a position on a recently raised matter; (b) value toward answering the question; (c) relevance to the subject.
8. **Accepted:** distribute to the other agents; no disposition notice needed. **Vetoed:** withhold from the group; **do not bank +512** merely because of the veto.
9. Deliver veto reasons and any truncation notice, including number of characters removed, **when that participant's next turn arrives**, not as an immediate retry prompt. Then continue around the group. When that agent returns, it sees the discussion developments that occurred during its absence.
10. A topic can advance after **two nonproductive rounds** or **two rounds in which all agents pass**.
11. Poll **all** participants for proposed next topics. Compare each unique pair once with JEV asking whether they express the **same intent**. Credit each confidence value to **both** proposals in that pair. Sum each proposal's `N − 1` values; the highest total wins. **Two tied winners** are connected with **“and”** to form the next topic. There is no 70% threshold in topic selection.
12. Continue the same collaboration toward the user's deliverable with preceding context and shared artifacts intact.

The alternative idea of giving JEV the last **30K tokens** of discussion and having it select a topic through a `case` judgment was discussed as **an alternative**, not as a replacement for the pairwise summed-confidence process.

**Shared workspace:** agents may independently or jointly create and refine Markdown, detailed proposals, specifications, Mermaid diagrams, code samples, implementations, and other relevant artifacts. Discussion-character limits apply to the short discussion contribution, **not** to artifact contents.

### Common participant prompt

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

**ACP compatibility note:** There is no universally supported ACP RPC that sets a participant's *system* prompt across all harnesses. The client can deliver the common instructions in the initial `session/prompt` as ordinary prompt content. Harness-specific facilities for a true system-prompt override may also be used when available; for example, acpx documents Claude's `_meta.systemPrompt` extension on `session/new`. That extension is **not** universal ACP. This distinction must remain visible to the developer rather than being hidden under a nonexistent standard call.

## 3. Roles and existing resources

| Responsibility | Existing mechanism | Function in Roundtable |
|---|---|---|
| Agent/client communication | [ACP specification](https://agentclientprotocol.com/protocol/v1/overview) and [official Rust SDK](https://github.com/agentclientprotocol/rust-sdk) | Persistent, asynchronous sessions with each selected harness; prompts, updates, tool observations, lifecycle |
| Published harness discovery | [ACP Registry](https://github.com/agentclientprotocol/registry) | A dynamically updated catalog of published ACP agents and their launch distributions |
| Registry-driven launch | [acpr](https://github.com/agentclientprotocol/acpr) | Resolves and launches registered agents via appropriate binaries, `npx`, or `uvx` |
| Common harness aliases / adapter commands | [acpx](https://github.com/openclaw/acpx) and its [agent catalog](https://github.com/openclaw/acpx/blob/main/docs/agents.md) | Existing reference for Claude, Codex, Pi, OpenCode and other adapter commands; acpx itself is an ACP *client*, not a replacement for Roundtable's scheduler |
| OpenRouter model discovery | [OpenRouter models endpoint](https://openrouter.ai/docs/api/api-reference/models/get-models) | Dynamic model IDs for user selection, separate from harness selection |
| OpenRouter agent execution | [OpenRouter Agent SDK](https://openrouter.ai/docs/agent-sdk/overview) | Agent loop and tool execution for OpenRouter-selected models, **behind an ACP-facing adapter** |
| Pi harness route | [Pi](https://github.com/badlogic/pi-mono) and [pi-acp](https://github.com/svkozak/pi-acp) | Reuse an existing ACP bridge for Pi with an OpenRouter model/provider configuration |
| Contribution and topic judgment | JEV through OpenRouter | Three contribution judgments; pairwise next-topic sameness confidence |
| Independent activity observations | [AgentSight](https://github.com/eunomia-bpf/agentsight), especially `agentsight-capture` | Process, tool, filesystem and network activity independently of ACP notifications |
| Scheduling, credits, JEV disposition, topic progression, artifacts | Existing Rust chassis and event bus | Roundtable-specific behavior and continuity; these are **not** built-in ACP or AgentSight functions |

### Discovery is not a universal local executable scanner

`acpr --list` lists agents in the **published ACP Registry**. `acpr <agent-name>` launches one of those entries. `acpx` offers an independently maintained catalog of familiar harness aliases and adapter commands, and supports a custom command route. Locally installed but unregistered compatible harnesses can also be selected through their actual ACP launch command. Neither project guarantees automatic detection of every arbitrary program installed on a host.

Supported model selection and supported harness selection are **different dimensions**. Selecting an OpenRouter model name does not make the model itself an ACP harness; an agent runtime (such as Pi or an ACP adapter around the OpenRouter Agent SDK) is what speaks ACP.

## 4. Concrete ACP RPC map

ACP uses JSON-RPC 2.0. The standard local transport is newline-delimited JSON over the agent subprocess's stdin/stdout; stderr may carry diagnostics. The **client initiates** `initialize`, creates sessions, and sends prompts. The **agent sends** `session/update` notifications and may call supported client-side tools.

The current stable specification is **ACP v1**. **ACP v2 is a draft** and changes completion and several APIs. The SDK and integration must follow the version negotiated by `initialize`; it is incorrect to apply v2 state semantics to a v1 harness.

| Direction | Actual method / update | v1 | v2 draft | Use in this system |
|---|---|---|---|---|
| Client → agent | `initialize` | Yes | Yes; different field layout | Negotiate protocol version, capabilities, agent details, authentication |
| Client → agent | `authenticate` | Where advertised | Renamed `auth/login` | Agent-managed authentication when applicable |
| Client → agent | `session/new` | Yes | Yes | Create participant session with the **shared working directory** and optional MCP tools |
| Client → agent | `session/set_config_option` | Where advertised | Where options advertised; `type` required | Select an advertised model or other harness session configuration |
| Client → agent | `session/prompt` | Yes | Yes | Deliver participant instructions, user's objective, current discussion turn, deferred feedback, current topic, allowance |
| Agent → client | `session/update` | Yes | Yes | Stream agent responses, tool activity, plans and other updates |
| Agent → client | `session/update` with `agent_message_chunk` | Yes | Yes | Collect the participant's actual contribution / reply |
| Agent → client | `session/update` with `tool_call` / `tool_call_update` | `tool_call` and `tool_call_update` | `tool_call_update` (upsert); no separate `tool_call` | Observe agent tool activity while it develops artifacts |
| Agent → client | `session/update` with `state_update` | No | Yes | Foreground `running`, `requires_action`, `idle`; may report background work |
| Agent → client | `session/prompt` **response** | Ends the turn with `stopReason` | Acknowledges **message insertion**, returns `messageId`; does **not** end work | Distinguish v1 turn completion from v2 acceptance |
| Client → agent | `session/load` | Where `loadSession` advertised | Removed | Restore and replay a v1 session when supported |
| Client → agent | `session/resume` | Where resume advertised | Baseline session method; optional `replayFrom` | Rejoin a session with its context rather than replacing it at topic changes |
| Client → agent | `session/cancel` | Yes | Yes | Explicit cooperative cancellation **when requested**, not automatic handling of an occupied participant |
| Client → agent | `session/close` | Where advertised | Baseline | Explicit end of session; this is not a topic-transition step |
| Agent → client | `session/request_permission` | Yes | Yes; changed payload | Existing ACP interaction when the harness asks for permission; distinct from JEV's contribution judgments |
| Agent → client | `fs/read_text_file`, `fs/write_text_file` | Only if client advertises them | Removed | Optional v1 client-provided filesystem operations |
| Agent → client | `terminal/create`, `terminal/output`, `terminal/wait_for_exit`, `terminal/release`, `terminal/kill` | Only if client advertises terminal | Removed | Optional v1 client terminal facilities; **not** a Roundtable watchdog |

**ACP v2 workspace/tool distinction:** v2 removes the v1 *client* filesystem and terminal calls. Agents can still use their own tools, and clients can expose tools through MCP servers passed during `session/new`/`session/resume`. v2 `terminal_update` is agent-owned **display reporting**, not a replacement for client `terminal/create`.

Relevant sources: [v1 overview](https://agentclientprotocol.com/protocol/v1/overview), [v1 initialization](https://agentclientprotocol.com/protocol/v1/initialization), [v1 prompt lifecycle](https://agentclientprotocol.com/protocol/v1/prompt-turn), [v1 session setup](https://agentclientprotocol.com/protocol/v1/session-setup), [v1 config options](https://agentclientprotocol.com/protocol/v1/session-config-options), [v2 migration](https://agentclientprotocol.com/protocol/v2/migration), [v2 session setup](https://agentclientprotocol.com/protocol/v2/session-setup), [v2 prompt lifecycle](https://agentclientprotocol.com/protocol/v2/prompt-lifecycle).

## 5. Actual wire examples

The following are **illustrative valid request shapes**, not a proposed replacement for the official SDK. Placeholder paths, agent IDs and prompt text are contextual examples.

### 5.1 ACP v1: initialize, create, select model, prompt, observe, finish

**Client → agent:** `initialize` (only advertise client facilities actually provided):

```json
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{},"clientInfo":{"name":"roundtable","version":"1.0.0"}}}
```

**Client → agent:** `session/new` (same collaborative workspace for the participating sessions):

```json
{"jsonrpc":"2.0","id":1,"method":"session/new","params":{"cwd":"/workspace/roundtable","mcpServers":[]}}
```

**Agent → client:** example response:

```json
{"jsonrpc":"2.0","id":1,"result":{"sessionId":"participant-session-1"}}
```

The session response may also include `configOptions`. If a **model** option is actually advertised, its `id` and accepted values determine the proper `session/set_config_option` request. For v1, the schema uses `configId` and `value`:

```json
{"jsonrpc":"2.0","id":2,"method":"session/set_config_option","params":{"sessionId":"participant-session-1","configId":"model","value":"<advertised-model-value>"}}
```

**Client → agent:** `session/prompt` carries the participant's instructions and this turn's content. The actual user objective and current topic are supplied as content, not inferred from a prior turn or replaced by a summary:

```json
{"jsonrpc":"2.0","id":3,"method":"session/prompt","params":{"sessionId":"participant-session-1","prompt":[{"type":"text","text":"<participant prompt, user objective, current topic, current allowance, relevant continuing context and pending previous-turn feedback>"}]}}
```

**Agent → client:** streamed message content:

```json
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"participant-session-1","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"<agent contribution>"}}}}
```

**Agent → client:** in v1, the prompt response indicates turn completion:

```json
{"jsonrpc":"2.0","id":3,"result":{"stopReason":"end_turn"}}
```

**Roundtable then applies its own behavior:** interpret the participant's action (contribute/pass/independent work); apply the documented character accounting; truncate a contribution if needed; call JEV; distribute it only if accepted; retain deferred feedback. These are application functions, **not ACP RPCs**.

### 5.2 ACP v2 draft: different initialization and completion

**Client → agent:**

```json
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":2,"info":{"name":"roundtable","version":"1.0.0"},"capabilities":{}}}
```

**Client → agent:**

```json
{"jsonrpc":"2.0","id":1,"method":"session/new","params":{"cwd":"/workspace/roundtable","mcpServers":[]}}
```

`session/prompt` retains the same shape as v1, but its **response only acknowledges acceptance/insertion** (by message ID). Foreground work continues to be observed using `session/update`.

**Agent → client:** running:

```json
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"participant-session-1","update":{"sessionUpdate":"state_update","state":"running"}}}
```

**Agent → client:** eventual foreground completion:

```json
{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"participant-session-1","update":{"sessionUpdate":"state_update","state":"idle","stopReason":"end_turn"}}}
```

If the agent advertises background work, `state_update` can also report a `background` snapshot. **`idle` does not necessarily mean background work has ceased.** Omitted background information means **not reported**, not proven absent.

To select an **advertised** v2 model option, `session/set_config_option` uses the v2 discriminator `type: "id"`:

```json
{"jsonrpc":"2.0","id":2,"method":"session/set_config_option","params":{"sessionId":"participant-session-1","configId":"model","type":"id","value":"<advertised-model-value>"}}
```

v2 updates are upserts for the indicated message/tool IDs, not simply a blind concatenation of all updates. The ACP SDK should handle the wire format and types.

## 6. End-to-end execution design

This sequence identifies **actual protocol interactions**, then places Roundtable's distinct actions around them:

```mermaid
sequenceDiagram
    participant U as User / Roundtable
    participant R as Chassis + Roundtable
    participant H as ACP harness
    participant O as AgentSight
    participant J as JEV via OpenRouter

    U->>R: Objective and selected participants
    R->>R: Resolve harness via Registry/acpr or acpx adapter catalog
    R->>H: Launch ACP program (stdio)
    R->>H: initialize
    H-->>R: Version, capabilities, auth methods
    R->>H: session/new (shared cwd, optional MCP servers)
    H-->>R: sessionId; advertised config options
    opt Advertised model selector
      R->>H: session/set_config_option
    end
    R->>O: Associate harness process with observations
    loop Discussion opportunities
      R->>H: session/prompt (goal, context, allowance, prior feedback)
      H-->>R: session/update (messages / tools / state as supported)
      O-->>R: Independent process, file, network observations
      alt Agent is still doing independent work
        R->>R: Continue with others; +512 each skipped turn
      else Agent passes
        R->>R: +512 to passing agent
      else Agent contributes
        R->>R: Truncate only if over allowance
        R->>J: Evaluate novelty-or-position, value, relevance
        J-->>R: Three confidences and veto reasons if applicable
        alt Accepted by all three 70% judgments
          R->>R: Distribute to other participants' continuing context
        else Vetoed
          R->>R: Withhold; retain reason for next turn; no +512 veto credit
        end
      end
    end
    R->>R: Topic eligible after either specified two-round condition
    R->>H: session/prompt (ask participant for next topic)
    H-->>R: Proposed next topic
    R->>J: Evaluate every unique proposal pair for same intent
    J-->>R: Pairwise confidence percentages
    R->>R: Credit both endpoints, sum N-1 per topic, select maximum
    R->>R: Combine two tied winners with "and"
    R->>R: Continue same objective, workspace and agent contexts
```

**Reading the diagram:** the Roundtable never equates an ACP request being in flight with a failed agent. While one harness is performing useful work, other participants continue. Activity observations supplement ACP; they are not JEV contribution gates. The exact application representation of **pass**, **work**, and **contribution** is a Roundtable concern; ACP does not define corresponding standard `session/pass` or `session/work` RPCs.

### Event-bus responsibility map (conceptual, not a new schema)

| Source | What it contributes | What Roundtable uses it for |
|---|---|---|
| ACP `session/update` | Message chunks; reported tool calls; v2 lifecycle and background reports | Participant replies and reported progress |
| ACP prompt result | v1 turn completion or v2 message-acceptance acknowledgment | Correct per-version lifecycle accounting |
| AgentSight capture | Independent process, network, file, subprocess and resource observations | Visibility during long or silent work; identifying evidence of continued activity |
| Roundtable loop | Passes, skips, allowance credits, contributions, truncation, deferred feedback | Participation rules and discussion sequencing |
| JEV | Three confidence judgments or pairwise sameness confidences | Contribution distribution and topic selection |
| Shared workspace | Markdown, designs, diagrams, code and other artifacts | Collaborative deliverable and continuing context |

This preserves the existing event bus as the integration point. The design does not require a new message broker or a second orchestration engine.

## 7. Universal harness selection and OpenRouter paths

### 7.1 Published ACP agents: official Registry and acpr

Existing commands and service:

```text
acpr --list
acpr <registered-agent-name>
https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json
```

`acpr` resolves registry distribution types and launches the agent: npm packages through `npx`, Python packages through `uvx`, or cached platform-specific binaries. Its job is launch resolution; Roundtable remains the ACP client and owns its participant sessions and discussion loop.

### 7.2 Common installed harnesses: acpx agent catalog

The [acpx agent catalog](https://github.com/openclaw/acpx/blob/main/docs/agents.md) documents the executable/adapter mappings for common harnesses. Examples from the current catalog:

| Participant harness | Existing ACP command / adapter |
|---|---|
| Claude Code | `npx -y @agentclientprotocol/claude-agent-acp` |
| OpenAI Codex | `npx -y @agentclientprotocol/codex-acp` |
| Pi | `npx pi-acp` |
| OpenCode | `npx -y opencode-ai acp` |
| Other agents | Additional acpx aliases or a supplied ACP executable command |

These are **references to available mechanisms**, not a fixed hardcoded list for Roundtable. `acpx` provides a complete separate ACP-client command surface (`prompt`, `sessions`, `status`, `cancel` etc.); it is useful as an integration example, but invoking its one-shot `exec` command in place of persistent per-agent sessions would not reproduce Roundtable's specified continuity and scheduling.

### 7.3 OpenRouter models are selected by their published identifiers

OpenRouter supplies model discovery through:

```http
GET https://openrouter.ai/api/v1/models
Authorization: Bearer <OpenRouter API key>
```

Use the model identifiers returned by this API to present and select OpenRouter participants. A model ID is **not** an ACP harness name; the selected runtime must execute it.

Two useful agent execution paths:

1. **Pi + OpenRouter:** configure Pi's OpenRouter provider/key and selected model, and communicate with Pi through the existing `pi-acp` bridge. The OpenRouter API key is available through `OPENROUTER_API_KEY` in the runtime's provider environment as documented by the relevant tooling.
2. **OpenRouter Agent SDK + ACP adapter:** use OpenRouter's existing `@openrouter/agent` agent loop, tooling and conversational state, but expose it through an ACP-compatible agent adapter. That adapter implements ACP's agent side (`initialize`, `session/new`, `session/prompt`, `session/update`, and relevant lifecycle/configuration operations) while invoking the OpenRouter Agent SDK internally. One adapter can work with multiple OpenRouter model identifiers; one custom adapter *per model* is unnecessary.

The [OpenRouter Agent SDK](https://openrouter.ai/docs/agent-sdk/overview) is a genuine agent framework, with TypeScript, Python, and Go packages documented. **It does not advertise a ready-made ACP endpoint.** An ACP-facing integration is the required boundary if all Roundtable participants are to use the same ACP lifecycle. The chassis remains Rust; external harnesses/adapters need not use the chassis language.

The OpenRouter key used for participant models and the key used to access JEV may use the same OpenRouter provider, but these are separate functional uses: **agent execution** versus **judgment**.

## 8. AgentSight: activity monitoring independently of ACP

**Resource:** [AgentSight](https://github.com/eunomia-bpf/agentsight) — specifically its reusable Rust `agentsight-capture` components, whose documented facilities include eBPF runners, agent-native sources, analyzers, an event model, materialized views and sinks.

AgentSight is an **observer**, not the Roundtable scheduler. It supplies evidence when a harness sends no ACP messages: process existence/activity, spawned tools, filesystem access, network operations, and observed model/provider traffic. AgentSight can reveal ongoing work or retries even when ACP has not emitted updates; it cannot prove whether a remote inference provider is reasoning slowly, overloaded, or deadlocked merely from silence.

### Existing AgentSight entry points

| Tool / API | Documented capability | Roundtable relevance |
|---|---|---|
| `agentsight top` | Live agent/session activity from process observations and native session sources | Interactive inspection during development and operations |
| `agentsight record -- <command>` | Launch and monitor a specific command with process/TLS/file observation | Diagnostic tracing of an ACP harness in an isolated test |
| `agentsight record -p <pid>` / `-c <comm>` | Attach monitoring to an existing process or matching command | Observe already-running harnesses without replacing their ACP transport |
| `agentsight report audit --json` | Query recorded process, file and API-call effects | Inspect recorded behavior |
| `agentsight report export -o snapshot.json` | Export recorded session data | Structured inspection or reporting |
| `agentsight debug trace --otel --otel-endpoint ...` | Emit captured LLM calls as OpenTelemetry GenAI spans | Optional integration with existing observability infrastructure |
| `agentsight-capture` | Rust library with capture, native sources, event model and sinks | Direct integration into the Rust chassis's event bus |

AgentSight's standard `record` produces local SQLite session files. For live embedded integration, its **capture/event facilities** or existing process-attach mode are more relevant than treating saved reports as a prerequisite for every Roundtable turn. The developer can choose the supported capture interface that fits the chassis.

### Correlation with ACP sessions

The chassis knows the ACP harness process it launched and the `sessionId` returned by `session/new`. AgentSight observations can be related to that process and its subprocesses; the Roundtable then has **two complementary views**:

- **Reported:** ACP's tool/message/state updates and completion semantics.
- **Observed:** actual local process, tool, file and network activity captured independently.

A harness process may serve more than one ACP session, so process-level observation is not always sufficient to attribute every syscall to one session. Session-specific attribution remains an evidence question; the design does not pretend AgentSight can infer an unreported ACP session ID from a kernel event.

The function of this integration is to help tell *active work*, *waiting*, *process exit*, and *unknown activity* apart where observations permit it. It is **not** a mechanism for automatically aborting an agent because it has been occupied or silent for a fixed period. Occupied agents continue their independent work while the Roundtable skips their discussion opportunities and credits those skips.

### Platform limits from AgentSight's own documentation

- Full eBPF/TLS activity tracing is Linux-dependent and requires the relevant kernel support and privileges.
- On Windows and macOS, AgentSight can still use native session data and lighter process information, with less general visibility.
- TLS tracing depends on the executable and its SSL implementation; AgentSight documents separate handling for statically linked runtimes.
- Recorded traces may contain prompts, responses, paths and other sensitive content.

Sources: [AgentSight README](https://github.com/eunomia-bpf/agentsight/blob/master/README.md), [AgentSight supported-agent tracing](https://github.com/eunomia-bpf/agentsight/blob/master/docs/agents.md), [AgentSight repository capture components](https://github.com/eunomia-bpf/agentsight/tree/master/agentsight-capture).

## 9. Integration traceability: which facility does which job?

| Required function | Existing call/resource actually used | Responsibility boundary |
|---|---|---|
| Select heterogeneous agents | ACP Registry/acpr + acpx catalog + user-supplied ACP launch command | Resolver finds/launches; Roundtable chooses participants |
| Select provider models | OpenRouter `GET /api/v1/models`; harness model configuration | OpenRouter model identifiers are not ACP harness identifiers |
| Connect to each participant | ACP `initialize` | One negotiated protocol contract per harness connection |
| Keep participant context | ACP `session/new`, continuing `session/prompt`, supported `session/resume`/`session/load` | Topic progression occurs **inside** continuing sessions |
| Choose advertised harness model | ACP `session/set_config_option` | Only when a harness actually offers a model config option |
| Deliver the Roundtable prompt | ACP `session/prompt`; harness-native system-prompt mechanism where supported | No universal ACP system-prompt setter exists |
| Produce shared artifacts | Session `cwd`, agent native tools, optional MCP tools; v1 client fs/terminal capabilities where offered | Use the harness's actual tooling rather than inventing an ACP file-writing method for v2 |
| Observe reply and tool work | ACP `session/update` | v1 and v2 have different completion rules |
| Observe otherwise silent activity | AgentSight capture / process-attach | Independent observation complements reported ACP state |
| Continue other agents while one works | Existing async chassis/event bus | Application scheduling; no ACP `pass` method |
| Credit passes and skips | Roundtable allowance accounting | Exactly +512 per pass or skipped occupied turn |
| Evaluate short contributions | JEV through OpenRouter | Exactly the three specified 70% contribution judgments |
| Handle length / veto feedback | Roundtable contribution disposition | Truncate before JEV; defer notice until next turn; veto has no +512 credit |
| Move between topics | Roundtable two-round conditions, agent topic proposals, JEV pairwise scores | Highest sum; join two tied winners with “and” |
| Preserve original purpose | User objective + continuing agent contexts + artifacts | Output is the actual deliverable, not a summary |

## 10. Integration proof points for the developer

These are **evidence of using the specified mechanisms**, not additional runtime gates or participation rules:

1. For a registered agent, the working trace shows a resolved ACP executable, `initialize`, `session/new`, `session/prompt`, and the corresponding real ACP updates/completion.
2. For an agent using an advertised model option, the trace shows `session/set_config_option` with the correct version-specific request shape. For OpenRouter, model IDs originate from its model API, while the ACP runtime is separately identified (Pi or an OpenRouter SDK adapter).
3. An occupied participant remains active while another participant takes a discussion turn; the skipped participant's +512 credit and later return are visible without cancelling its ACP work.
4. A long contribution is truncated *before* JEV; veto reasons and truncation amounts are surfaced on that agent's **next** turn; a veto never earns a pass/skip credit.
5. A two-round topic transition produces topic proposals from the participants, pairwise JEV sameness judgments, credits each pair's score to both participants, sums scores, and selects the maximum. Two tied winners are joined with “and”.
6. A subsequent topic uses the **same continuing collaboration** and shared workspace rather than resetting each agent's conversation.
7. AgentSight shows independent process/file/network or subprocess observations for a launched harness, and those observations can be correlated to the chassis's ACP process/session records without equating inactivity with failure.

## 11. Primary references

- ACP v1 overview: https://agentclientprotocol.com/protocol/v1/overview
- ACP v1 initialize: https://agentclientprotocol.com/protocol/v1/initialization
- ACP v1 session setup/resume: https://agentclientprotocol.com/protocol/v1/session-setup
- ACP v1 prompt lifecycle: https://agentclientprotocol.com/protocol/v1/prompt-turn
- ACP v1 session config: https://agentclientprotocol.com/protocol/v1/session-config-options
- ACP v1 transports: https://agentclientprotocol.com/protocol/v1/transports
- ACP v2 migration (including removed APIs): https://agentclientprotocol.com/protocol/v2/migration
- ACP v2 session setup: https://agentclientprotocol.com/protocol/v2/session-setup
- ACP v2 prompt lifecycle: https://agentclientprotocol.com/protocol/v2/prompt-lifecycle
- ACP v2 session config: https://agentclientprotocol.com/protocol/v2/session-config-options
- Official ACP Rust SDK: https://github.com/agentclientprotocol/rust-sdk
- ACP Registry: https://github.com/agentclientprotocol/registry
- ACP launcher `acpr`: https://github.com/agentclientprotocol/acpr
- acpx client/agent aliases: https://github.com/openclaw/acpx/blob/main/docs/agents.md
- Pi ACP adapter: https://github.com/svkozak/pi-acp
- OpenRouter Agent SDK: https://openrouter.ai/docs/agent-sdk/overview
- OpenRouter models: https://openrouter.ai/docs/api/api-reference/models/get-models
- AgentSight: https://github.com/eunomia-bpf/agentsight
- AgentSight tracing: https://github.com/eunomia-bpf/agentsight/blob/master/docs/agents.md

---

**Intent boundary:** This document identifies how to use the existing ecosystem to implement the user's described Roundtable. It does not introduce new contribution gates, new participation constraints, automatic busy-agent aborts, topic-transition context resets, or an independent orchestration platform. Engineering details not decided by the functional specification remain implementation decisions for the developer.
