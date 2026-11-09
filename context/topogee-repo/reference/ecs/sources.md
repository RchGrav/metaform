# Source inventory and verification scope

Prepared October 27, 2026. The source files listed below were read but not modified. The author’s clarifications in this conversation govern terminology, scope, equal participation, and context-delivery intent. Raw research notes are not treated as verified standards documentation.

## Supplied source files

| Source | SHA-256 of supplied bytes |
|---|---|
| `inference-metaform.md` | `2a67b72d204e082be6adaa31901e64c92ca8545b37008d2a812c1bdec39c92e3` |
| `three_paradigms.md` | `2db9fd9ece8ad137894ee3ea95014c04d9e9a2d43ca85f20370f19d77bb5e835` |
| `intake.xml` | `956481decb6a011a5e07e7304266781e6f0ffddbc9d57af7e6b9bddd2d8b52d8` |
| `spec intake and recomposition.md` | `afcfa1f069802be844b45db7bff4b090675a3411f5b0665e1e2c941697bf2063` |
| `agent_identity.md` | `50fe9f6e494a52cac7383f52fb07eff71a9ac6a8134e77701adbfb92ce49ddf5` |
| `example-layers.md` | `e1cd4c8db1b05ddeac793ee6a7073fc4d38228790b2c6436144d38dd2c9a323c` |
| `mcp_events.md` | `563ad913362295cc765a36fcf508d410bfc1b658e5c30ed9753b490245e9e314` |
| `hermes-agent-intake.xml` | `5fc8835c61d9a161d102a675c0ee38ecd2540e2a01aba2c57ac2d34e34cc5453` |
| `hermes-agent-ice-corrections.xml` | `e8150d0c173e3c7b2563d963df82712c613ab98bd81198e3b9510093f114f6b1` |

## Primary public references

**MCP Tools, 2026-07-28: Capabilities; Tool; ToolAnnotations; List Changed Notification**  
`https://modelcontextprotocol.io/specification/2026-07-28/server/tools`

**MCP Resources, 2026-07-28: Capabilities; Reading Resources; Resource Contents**  
`https://modelcontextprotocol.io/specification/2026-07-28/server/resources`

**MCP Base Protocol: request _meta**  
`https://modelcontextprotocol.io/specification/2026-07-28/basic/index`

**MCP Schema Reference: RequestMetaObject; ReadResourceResult; TextResourceContents**  
`https://modelcontextprotocol.io/specification/2026-07-28/schema`

**MCP Subscriptions: Opening a Stream; Acknowledgment; Receiving Notifications**  
`https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions`

**Official skills extension: capability negotiation; Skill; list/get/read; host loading responsibilities**  
`https://raw.githubusercontent.com/modelcontextprotocol/ext-skills/main/specification/stable/skills.mdx`

**Experimental Triggers & Events: incubation status, not normative wake-up transport**  
`https://github.com/modelcontextprotocol/experimental-ext-triggers-events`

**ACP v1 Prompt Turn**  
`https://agentclientprotocol.com/protocol/v1/prompt-turn`

**ACP v1 Session Setup**  
`https://agentclientprotocol.com/protocol/v1/session-setup`

**LadybugDB Create Table: primary keys and typed relationship endpoints**  
`https://docs.ladybugdb.com/cypher/data-definition/create-table/`

**LadybugDB Match: recursive relationships and default bounds**  
`https://docs.ladybugdb.com/cypher/query-clauses/match/`

**LadybugDB Transactions: concurrency and transaction statements**  
`https://docs.ladybugdb.com/cypher/transaction/`

**Bevy Getting Started: ECS — authoritative definition of Entity-Component-System**  
`https://bevy.org/learn/quick-start/getting-started/ecs/`

**Bevy Getting Started: Resources — shared state within Bevy ECS**  
`https://bevy.org/learn/quick-start/getting-started/resources/`

**Bevy browser examples**  
`https://bevy.org/examples/`

**STMicroelectronics VL53L5CX product**  
`https://www.st.com/en/imaging-and-photonics-solutions/vl53l5cx`

**STMicroelectronics UM2887, Section 3; 8x8/4x4 timing table inspected visually**  
`https://www.st.com/resource/en/user_manual/um2887-a-software-integration-guide-to-implement-the-ultra-light-driver-of-the-vl53l5cx-timeofflight-8-x-8-multizone-ranging-sensor-with-wide-field-of-view-stmicroelectronics.pdf`

**ST employee explanation of perpendicular distance, February 17 2022**  
`https://community.st.com/mems-sensors-48/for-vl53l5cx-what-does-resultsdata-distance-mm-zonenum-exactly-mean-7106`

**ROS REP 103**  
`https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0103.rst`

**ROS REP 118**  
`https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-0118.rst`

**ROS Image message**  
`https://raw.githubusercontent.com/ros2/common_interfaces/rolling/sensor_msgs/msg/Image.msg`

**ROS PointCloud2 message**  
`https://raw.githubusercontent.com/ros2/common_interfaces/rolling/sensor_msgs/msg/PointCloud2.msg`

**ROS TwistStamped message**  
`https://raw.githubusercontent.com/ros2/common_interfaces/rolling/geometry_msgs/msg/TwistStamped.msg`

**MAVLink common messages: OBSTACLE_DISTANCE**  
`https://mavlink.io/en/messages/common.html`

**Git diff**  
`https://git-scm.com/docs/git-diff`

**Meta Prompting for AI Systems, cited version**  
`https://arxiv.org/abs/2311.11482v10`

**From Local to Global: A Graph RAG Approach to Query-Focused Summarization, cited version**  
`https://arxiv.org/abs/2404.16130v2`

**Reflexion, cited version**  
`https://arxiv.org/abs/2303.11366v4`

**PROV-DM, dated recommendation**  
`https://www.w3.org/TR/2013/REC-prov-dm-20130430/`

**Metaform core glossary, pinned repository source**  
`https://github.com/RchGrav/metaform/blob/6ebe54b899c294629c5190655783e4d5ef5b759a/rich/metaform_core.axiom`

**Metaform repository: capability references, not a prescribed complete product**  
`https://github.com/RchGrav/metaform`

## Evidence boundary

The manuscript’s September 26 project-map counts are historical reported figures. The supplied Hermes correction was parsed locally: five Blocks, fifteen unique members. Current protocol/data-format claims were checked against the primary references above. Public documentation does not establish that a target harness implements every optional capability.

The application schemas and small reference-semantics fixtures were exercised locally; results are in `verification/results.json`. LadybugDB query execution, hardware behavior, MCP/ACP interoperability, Bevy integration, and performance were not exercised. Source-reviewed Cypher is not described as engine-tested.
