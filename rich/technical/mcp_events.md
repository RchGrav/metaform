MCP Events is an extension to the Model Context Protocol (MCP) that lets AI agents listen for and react to state changes on MCP servers without constantly polling for updates. 

https://github.com/modelcontextprotocol/experimental-ext-triggers-events

How MCP Events Work

• Proactive Triggering: Instead of waiting for a user prompt, an MCP server can wake up an agent when a specific external event happens (such as a failed build, a new support ticket, or an incoming email). [1] (https://www.linkedin.com/posts/koushikmarka_openai-quietly-shipped-one-of-the-more-interesting-activity-7511432649106743297-sAHy), [2] (https://hookdeck.com/webhooks/guides/what-are-mcp-events)
• Standardized Methods: Servers implement three core event methods alongside their normal tools:
	• events/list: Describes available event types, filters, schemas, and delivery modes.
	• events/subscribe: Creates or refreshes an active event subscription.
	• events/unsubscribe: Stops an active subscription. [1] (https://developers.openai.com/plugins/build/mcp-events)
• Delivery Modes:
	• Webhook: The server POSTs signed event payloads directly to a client-owned URL.
	• Push: The server streams events over a long-lived connection.
	• Pull: The client polls for events on a timer using a pagination cursor. [1] (https://www.youtube.com/watch?v=nPMbXzJqKmQ&t=13), [2] (https://bird.com/docs/ai/mcp-events)

Use Cases

• DevOps & CI/CD: Automatically wake an agent to investigate when a GitHub Actions build fails.
• Customer Support: Trigger an agent to pull account context and draft a response when a new enterprise ticket arrives.
• Inbox & Alerts: Process incoming messages or alerts in real time.

Instead of forcing an LLM agent to continuously poll a read_sensor_grid tool, the hardware-connected MCP server monitors the 8x8 matrix locally and pushes an event only when structural spatial thresholds are breached.

8x8 ToF Event Payload Schema

When the 8x8 Time-of-Flight (ToF) array detects a spatial change, the MCP server can emit a standardized payload under a custom event type like spatial/motion_detected or spatial/proximity_alert.
json
{
  "event": "spatial/proximity_alert",
  "timestamp": "2026-10-27T17:53:45Z",
  "data": {
    "zone": "front_quadrant",
    "trigger_type": "breakaway_entry",
    "min_distance_mm": 120,
    "matrix_snapshot": [
      [4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000],
      [4000, 4000, 3800, 3500, 3500, 3800, 4000, 4000],
      [4000, 3500, 1200,  800,  800, 1200, 3500, 4000],
      [4000, 3200,  600,  120,  120,  600, 3200, 4000],
      [4000, 3200,  550,  130,  140,  580, 3200, 4000],
      [4000, 3500, 1100,  750,  810, 1150, 3500, 4000],
      [4000, 4000, 3700, 3400, 3450, 3750, 4000, 4000],
      [4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000]
    ],
    "vector": {
      "dx": 0.05,
      "dy": -0.12,
      "velocity_m_s": 0.45
    }
  }
}
Use code with caution.

Spatial Event Types & Edge Processing

To keep the JSON payload lightweight and prevent agent alert fatigue, the microcontrollers or SBC handling the sensor does the heavy lifting, acting as an event filter:
• spatial/proximity_alert: Triggered when any pixel in the 8x8 matrix drops below a critical distance threshold (e.g., < 200mm), indicating an imminent obstacle or collision.
• spatial/gesture_recognized: Triggered when localized frame-to-frame delta patterns match specific movement shapes (e.g., a hand swipe across the 8 zones, causing sequential pixel drops from left to right).
• spatial/occupancy_change: Triggered when the average ambient depth profile changes permanently, signaling that an object has been placed or removed from the environment.
• spatial/loitering_detected: Triggered when an object enters a specific spatial zone and remains static for a configurable duration.

Agent Loop Execution Flow

1. Subscription: The agent starts up and calls events/subscribe with a filter for spatial/*.
2. Sleep State: The agent remains idle, consuming zero LLM tokens or inference processing while the robot sits stationary.
3. Edge Detection: An object suddenly moves within 120mm of the ToF sensor. The local firmware flags the anomaly.
4. Asynchronous Broadcast: The hardware MCP bridge wraps the 8x8 snapshot and vector data into an event payload and sends it via the active push channel.
5. Agent Activation: The host client receives the event, populates the agent's context window with the spatial snapshot, and triggers the next loop iteration (e.g., calling an embedded navigate_around_obstacle tool).

The ECR / Metaform Functional Identity
(We map structural elements to functional elements in our contextual interface.)

mermaid
graph TD
    subgraph ECR Runtime Interface
        Entity[Entity ID] <--> Components[Component Data Structs]
        Systems[System Execution Loops] <-- Queries Signature --> Components
    end

    subgraph Metaform Functional Topology
        Node[Structural Element] <--> Specs[Objective Purpose / Encounter Function]
        Agent[Agent / Harness Traversal] <-- Evaluates Bounds --> Specs
    end

    Entity === Node
    Components === Specs
    Systems === Agent

    style Entity fill:#f9f,stroke:#333,stroke-width:2px
    style Node fill:#f9f,stroke:#333,stroke-width:2px
    style Components fill:#bbf,stroke:#333,stroke-width:2px
    style Specs fill:#bbf,stroke:#333,stroke-width:2px
Use code with caution.

1. Elements are Entities

A node in your namespace (e.g., code.engine.game.fps) isn't a text file or a folder string. It is a unique Entity ID in a database. On its own, it has no behavior; it is simply a placeholder for semantic identity in the functional space.

2. Purposes & Functions are Components

You attach data structures (Components) directly to these Entity IDs to give them meaning:
• The Receiving Element Component (ObjectivePurpose): Stores the localized specifications, requirements, and target metrics that this specific subsystem must achieve.
• The Providing Element Component (EncounterFunction): Stores the capacity for response, structural constraints, and strict interface laws that this element imposes on anything that couples with it.

3. Agent Footprints are System Queries

The AI agent is a pure ECR System. When a ticket is assigned, the agent doesn't scan the workspace blindly. The system executes a query filtering for a specific signature:
rust
// The agent loop is a system that only executes where an objective intersects a provider
fn functional_proximity_triage_system(
    tickets: Query<(&ActiveTicket, &TargetElement)>,
    elements: Query<(&ObjectivePurpose, &LocalizedSpecs)>,
    dependencies: Query<(&EncounterFunction, &AuthorizedSkills)>,
) {
    // The harness instantly collapses to this exact intersection matrix
}

How the Harness Materializes "In Proximity"

Because the agent's context window and active tool schema are derived dynamically by traversing this structural graph, the presentation layer changes seamlessly based on the agent's coordinate position in the functional topology:
1. Contextual Ticket Isolation: When a ticket is placed in a Kanban lane, it is tagged with a target Entity ID. The lane itself is just a filter displaying tickets whose Functional Proximity matches a certain node depth.
2. Localized Specification Injection: The agent is booted with an environment payload containing only the ObjectivePurpose component of the target node and the EncounterFunction components of its immediate structural dependencies.
3. Dynamic Skill Pruning: The MCP server doesn't provide a static list of tools. It evaluates the Encounter Function of the providing elements and presents functionally localized tools, WASM modules, or skills that are structurally cleared to interact with that interface.

Focus is sharply on emerging standards for MCP and others systems such as drone control, ROS, and Metaforms ECR Intelligence Analogsas well as supporting mdx files for componential mc

https://github.com/modelcontextprotocol/ext-tasks
https://github.com/modelcontextprotocol/ext-server-card
https://github.com/modelcontextprotocol/ext-skills



Skills and other context is driven by Progressive disclosure.

Progressive disclosure
Agents load skills progressively, pulling in more detail only as a task calls for it. Skills should be structured to take advantage of this:
Metadata (~100 tokens): The name and description fields are loaded at startup for all skills
Instructions (< 5000 tokens recommended): The full SKILL.md body is loaded when the skill is activated
Resources (as needed): Files (e.g. those in scripts/, references/, or assets/) are loaded only when required|

skills are evaluated using https://github.com/agentskills/agentskills/tree/main/skills-ref

Skills are used according to the SEP-2640 Skills Extension with the difference that skill visibility is perceptiually contextual by either functional or spatial proximity.  Agents receive an event notifying them when new skills are learned based on perceptual distance.  Once skills are learned in a context they are not removed until the agent performs a handoff.  Agents may handoff based on % of context used, or based on satisfying a goal.  Agent identities are seeded based on their genesis context when they are born, past interactions an agent has had are retained and referenceable, this carries agent to agent and user to agent comms, as well as feature commit details and other related refs which can be attached.  See AgentIdentity