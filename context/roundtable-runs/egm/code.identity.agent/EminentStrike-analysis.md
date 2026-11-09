# EminentStrike — verified evidence for `code.identity.agent`

All paths are relative to `source/`. This file records checks I ran independently of the
reviewers' line citations; it supports the addendum in `resolution.md`.

## 1. The supplied source is a subset

```
crates/roundtable/src/names.rs
crates/roundtable/src/config.rs
crates/roundtable/resources/names/adjectives.txt
crates/roundtable/resources/names/nouns.txt
```

`engine.rs`, `turn.rs`, `app.rs`, `index.html`, `acp-host/src/harness.rs` are **not** present.
The reviewers cite them (GF1, GF2, GF3, GF7). Their runtime claims are therefore not
verifiable here. I treat a finding as *decidable* when it is about what `element.md` says
(GF4–GF10 wholly; GF1–GF3 in part) and mark the rest as *conditional on the omitted files*.

## 2. The derivation, reproduced numerically

`names.rs:11-19` implements 32-bit FNV-1a over the session id's UTF-8 bytes:

```
h = 2166136261
for b: h = (h ^ b) * 16777619  (wrapping u32)
folded = (h ^ (h >> 16)) & 0xFFFF
adjective = ADJECTIVES[folded >> 8]      # high byte, zero-based
noun      = NOUNS[folded & 0xFF]         # low byte, zero-based
name      = capitalize(adjective) + capitalize(noun)
```

Independent Python reproduction of the test vector in `names.rs:37-40`:

```
session id  01a1ae33-9d9f-76e1-bfbf-37eb6d762b7e
folded      14758  (0x39A6)
high byte   57  -> adjectives[57] = "deadeye"
low byte   166 -> nouns[166]      = "quokka"
result      "DeadeyeQuokka"   (matches names.rs:40)
```

`names.rs:1-6` (the module doc comment) already states every fact in GF4 and GF8:
genesis context = first session a harness opens; FNV-1a; XOR fold; high/low byte;
capitalisation; "two agents can share a name and nothing rehashes".
**The information exists in the code and is missing only from `element.md`.**

## 3. Word lists

- Both lists have exactly 256 non-blank lines (verified; `names.rs:35-36` asserts it).
- All 256 entries in each list are **distinct** (verified; no within-list duplicates).
- 10 words appear in both lists: `cloud, elite, ghost, hunter, laser, marine, plasma,
  shadow, solid, steel`. This does **not** create duplicate names: a name is the ordered
  pair (adjective index, noun index), and with distinct entries per list all
  256 x 256 = 65536 ordered pairs are distinct.
- Therefore two sessions share a name **only** when two different session ids fold to the
  same 16-bit value. With a 16-bit space the birthday bound is small: ~300 identities
  gives roughly a 50% chance of at least one collision. `names.rs:5-6` says nothing
  rehashes, so collisions are permanent and expected at scale, not exotic.

`names.rs:17` `unwrap_or("agent")` is per-index and only fires if a list is short or
blank lines are removed; with 256 clean entries it is defensive. It capitalises to `Agent`.
It is not a collision resolver.

## 4. config.rs facts that bear on several findings

| Fact | Where | Bearing |
|---|---|---|
| `resume_session: Option<String>`, `#[serde(default)]` | `config.rs:23-28` | Default `None` = fresh session every table. Resume is opt-in (GF1, GF2). |
| "Resume this earlier session instead of opening a new one, so the agent keeps its identity ... The harness must be the one that holds that session." | `config.rs:23-28` | The resume mechanism is documented in code (GF2, GF5). |
| `Identities::profile(&self, session: &str)`; "Profiles are keyed by session, not by name ... two sessions can derive the same name" | `config.rs:45-49` | The real identity key is the genesis session id (GF3, GF6). |
| `validate()` rejects duplicate seat names case-insensitively: "two seats are named ..." | `config.rs:119-129` | **Tension with GF3's scenario** (two same-named agents at one table) and with `elephant.gaps` "Two agents can share a name". See below. |
| "The chair sets it; agents cannot change it"; `ROUNDTABLE_TOKEN` "never reaches an agent" | `config.rs:154-156`, `config.rs:52-55` | Chair = privileged operator, not an agent, not the JEV evaluator (GF7). |
| "A setting that fails is a loud error and the seat still joins" | `config.rs:15-16` | Supports failing loudly on a broken resume rather than a silent fallback (GF2). |

### The GF3 tension

`element.md:36` (`elephant.gaps`) says "Two agents can share a name". `config.rs:127-129`
makes duplicate *seat* names a hard table-start error. These are consistent only if the
genesis name and `SeatConfig.name` are different fields, or if collisions are understood
as cross-table. `element.md:16` says `code.manager.chat.group` "Derives the agent's name
from its first session id", which suggests the derived name becomes the seat name — in
which case a within-table collision would be rejected by `validate()` and the table
would not start at all, rather than producing two co-seated same-named agents that
cannot rate each other. `element.md` never says which name `SeatConfig.name` is, which
name agents see, or which name rating/feedback matches on. **The description must
reconcile this before GF3's claimed consequence can be stated as fact.**

## 5. Historical sources actually named in the code

- `archaeology/rich/technical/agent_identity.md` — `names.rs:1`, `config.rs:25`.
  Quoted in `names.rs:2-3`: "An agent is born with its genesis context, the first session
  a harness opens for it. The id of that session is the seed of the agent's identity."
- `dispatch/names.py` (`session_name`) — `names.rs:39`, the reference implementation the
  test vector is checked against.

Both are outside the supplied source. `element.md:10` says paths are relative to the
Roundtable folder; `element.md:32` currently gives neither path, only "owner's agent
identity document (earlier system)" (GF10).

## 6. What "a resumed session keeps its name" actually means

`genesis_name` is a pure function; no name is stored anywhere in the supplied code
(`config.rs` stores `Profile` = score/ratings/sessions, keyed by session, not a name).
A resumed session "keeps its name" only because the caller supplies the **same genesis
session id** again, so the pure function recomputes the same string. The durable seed is
the genesis id; the name is a derived display label. This is the mechanism GF2 and GF5
ask for, and it is why a silent fresh-session fallback on a failed resume would be wrong:
it would swap the identity while the operator believes the session was resumed.

## 6b. Call-graph boundary (verified after R1)

`grep -rn` over the supplied source:

```
genesis_name  -> 1 definition (names.rs:11) + 3 test uses (names.rs:37,38,42)
              -> 0 production callers in this copy
resume_session -> 1 field declaration (config.rs:28), 0 readers in this copy
```

So `names.rs` is a pure, unwired library in the supplied excerpt: all wiring (who passes
the session id, who reads `resume_session`, who resolves names in feedback) lives in files
not provided. This confirms CloudyPeace's argument that a pure function cannot preserve
identity across inputs, and UnknownArrow's zero-caller observation. It also means every
"code change" proposal (GF3's resolver repair) cannot be verified or implemented against
this copy — it must be filed against the owning element with a cross-reference here.

## 7. Net verdict

No finding justifies a change to `names.rs`. Every verified fix is a description change.
GF3 identifies a plausible code repair in the omitted targeting/feedback layer,
conditional on verifying the cited `turn.rs` / `engine.rs` behavior and on reconciling
`config.rs:127-129`.
