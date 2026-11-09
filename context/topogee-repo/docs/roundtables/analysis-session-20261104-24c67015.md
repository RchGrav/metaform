# Analysis of roundtable session 20261104-24c67015

**Reader:** Claude (Opus 5.5), for the owner, 2026-11-04, 20:55.
**Material:** the session folder through R5 Part 1, including P7, the R3 and R5 crosswalks, and the owner brief in `review-evidence.md`. P10 is not written yet.
**Basis:** the panel fills gaps in the specification with recommended choices. I read each choice as a decision, and I test how it could fail.

## 1. Link the map to the world; do not host it in Bevy (L-1)

**Why:** the owner already keeps the functional map server a standalone Node process (`DECISIONS.md:124`). The brief requires "one serious tool for any project", so a code project must not carry a game engine. A Bevy `Entity` id is reused after restart, but an address is permanent.

**What it means:** two processes with two kinds of entity. The map holds functional addresses. The world holds objects. A narrow link joins them.

**How it could be wrong:** the owner's Bevy decision is for the chassis, not only the world. `DECISIONS.md:124` records that Bevy's ECS matches `TOPOGEE.md` §2, where addresses are entities and layers are components. That sentence is the recorder's, not a quote from the owner. If the owner means the chassis to hold the functional map as ECS data, the link answers the wrong boundary.

**Damage scenario:** the chassis arrives. The Context Resolver, Composer and Facilitator are Systems that query entities and components (`TOPOGEE.md` §2). Every query crosses a process boundary to a Node JSON store. To make that fast, the chassis mirrors the map into Bevy, which R-2.11 permits. The project now has two copies of the map and a sync problem, which is the cost the link was chosen to avoid. None of the L-4 review triggers fires on this, because trigger 3 waits for a "same-tick" read.

## 2. The functional map server alone persists map data, and the chassis only supplies it (L-30, C-8)

**Why:** R-4.4 makes the functional map server the only writer under the home. The panel reads R-2.11 narrowly so that the decided writer rule survives a chassis.

**What it means:** functional data stays in Node JSON files permanently, with or without a chassis.

**How it could be wrong:** R-2.11 says that, with a chassis present, a module uses the chassis "as its data source" for deep integration. The narrow reading turns "data source" into "data supplier". The owner did not say that.

**Damage scenario:** the same as decision 1. Together, decisions 1 and 2 fix the functional map outside the ECS before the chassis is specified. This is the panel choice with the most foundational weight.

## 3. The link record holds `world` and `instance_id`; `status` is derived at runtime (L-7, L-33)

**Why:** a minted `instance_id` survives restarts, and a Bevy `Entity` does not. Status is a fact about the live world, so storing it would make every restart a map write.

**What it means:** the map keeps a durable pointer only. The world owns object identity. Both stores hold the pair, and the world writes first.

**How it could be wrong:** the panel never states which world objects get an address link. L-8 allows any number of instances per address.

**Damage scenario:** a contraption spawns thousands of instances, or each claimed block gets a link. Every new pair is a map write through the project queue, and the layer file at that address grows with the world's population. The fair lane protects agent writes from starvation, but the map turns into a world object registry. That breaks L-3 in spirit, because runtime population becomes map content. A second scenario: a friend restores a world backup, or forks a world. Every pair mismatches, every link goes `unbound`, and "no identity is replaced automatically" means manual reconciliation at scale.

## 4. Storage split: JSON map, SQLite effect log, one Ladybug database per world (L-20, L-29)

**Why:** JSON is owner-decided. Ladybug suits world objects and stores blobs from Rust. It fails for raw binary from Node (`world-ideas.md:129`), so the Rust world server owns it.

**What it means:** each store has one owner and its own fair queue. The map and world never share a transaction.

**How it could be wrong:** "one database per world" is the panel's judgment. Default Ladybug settings failed at about seven databases in one process (`world-ideas.md:124`). Tuned settings held 200 small databases (`:125`).

**Damage scenario:** a shared install serves many friends' worlds from one world-server process. Each world's database needs tuned memory limits, and large worlds are untested. This is an operational risk and can be measured. It is not foundational, because L-20 keeps the world store behind the world server.

## 5. Device bindings and limits stay at the bound address; context reaches agents through the resolver (L-10, L-10a, L-17)

**Why:** a parent prefix must never supply or override a motor limit. Planning context may inherit, but enforcement may not. The device enforces its own copy.

**What it means:** safety does not depend on the map, the queue or an agent. This is the strongest choice in the session.

**How it could be wrong:** delivery rides the resolver, and the resolver has no contract. After R5 accepted my F2, P10 plans to mark the resolver "blocked" for the owner.

**Damage scenario:** device work proceeds with no specified path for context to reach an agent. Each module then invents its own delivery, and the single-delivery tracking in `TOPOGEE.md` §5 and R-5.30 breaks into several systems.

## 6. Every world start forces fresh binding with a boot token (L-9)

**Why:** a recycled `Entity` id could send a command to the wrong object. With a robot, that is a physical hazard.

**What it means:** every restart refuses commands until rebind. Failure is safe and visible.

**How it could be wrong:** a world restart produces a rebind storm, and a robot pauses mid-task. This is a cost the owner might accept, and it does no foundational damage.

## 7. Schedule: R5 answered the review instead of holding the device panel

**Why:** one session remained, and the owner had sent a review.

**What it means:** P5 device contracts, P6 leases, P8 safeguards and P9 roadmap go forward unreviewed.

**How it could be wrong:** the brief requires reasoning about the "control scheme, ToF-sensor-style device contracts, and a common interface spanning physical and virtual space". Those are the items now deferred. R5 also renamed P7's boundary "world link" (my G2). The brief's common interface is the physical-to-virtual one, so the rename is correct. It also shows that the brief's common interface has had no panel yet.

## Where my review steered the panel wrong

- **F2 and F4:** the seats accepted both. P10 now plans to send the resolver contract and the chassis data scope to the owner as blocked items, instead of recommending answers. Those are gaps the panel exists to fill.
- **Review item 6:** it treated the world server as unrecorded. The brief records it: Rust, LadybugDB and Bevy. Astra corrected this in R5.
- **R5 time:** the response to my review took the session that would have covered devices and the common interface.

## Final thoughts

The panel's work is careful and mostly sound. Its safety choices (decisions 5 and 6) and its separation of stores (decision 4) are the best of it. They protect the system in the places where an error would be physical or would destroy data.

The foundational risk is the relation between the functional map and the chassis ECS. Decisions 1 and 2 settle it by default. The panel never recommended directly how addresses become entities when a chassis is present. The brief asked the panel to "reimagine" the map and the MCP server. The panel answered for the world, which is the easier case. The owner's own words connect Bevy to the chassis and to `TOPOGEE.md` §2.

Second, the link record has no admission rule. Without a rule for which world objects deserve an address, the map can fill with world population.

P10 is not written. If the owner wants these gaps filled, P10 can still recommend a resolver contract, a chassis data scope and a link admission rule instead of marking them blocked.
