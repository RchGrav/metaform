## What changed in this pass

**Bugs fixed:**
- The closure loop can now finish. `Record_Join` removes each OP it satisfies from `{Open_OPs}`.
- Every new entry now goes through `Create_Entry`, which validates the address and then creates or reuses the entry. Step 5's entries and new upstream and downstream entries no longer skip validation.
- `{AUE_Set}` is set in step 1.
- `EXISTENCE_CHECK` runs per member for folders.
- Step 3 groups by DE type and writes `{AT_Groups}`. Step 4 reads it.
- `FINDING_CLASS` now has an `:ELSE`.
- A missing intake MCP now produces a one-line message and a halt.

**Gaps closed that would have broken runs:**
- **Structural prefixes.** `downstream.cqu.seller` reversed reads "seller cqu downstream," so every CQU address would have failed the reversibility test and looped through V2. The naming tests now apply only to the segments after `upstream` or `downstream.cqu`. This is my addition.
- **Step 4 provider.** Step 4 now says explicitly that the CQU's join points at the AT address.

**Removed:**
- `~> Prefer aggregation…`: `ENCAPSULATION_GATE` already makes that decision.
- `~> Saying less on many things…`: already in `{LB_STEP_1}`.

## MCP field changes

| Field | Change from 1.2 |
|---|---|
| `relation` | Removed. Active voice lives in `ef`. |
| `perspective` | Removed. |
| `scope` | Removed. |
| entry `findings` | Removed. Replaced by `condition` + `note` on the entry or join. |
| `observations` | Renamed `observation`. |
| `verb` | Kept: the verb that opens `ef`. |
| `ifd` | Enum is `sends` \| `receives` \| `both`. |
| `condition` | Enum is `missing` \| `broken` \| `exclude`. Check these names against the tool's values. |
| `non_goal` | Unchanged, but confirm the tool has a column for it. |
| roots | `stakeholder` removed; `upstream` and `downstream` added. Any server-side root whitelist needs updating. |

## Implementation checks before a real run

1. **Placeholder fill.** If the server fills `{prompt}` with Python's `str.format` or similar, every other `{…}` in the script will raise an error. A plain string replace is safe. One test run with a stated target will show which it is.
2. **Reuse lookup.** `Create_Entry` needs to check whether an address exists before creating it. The MCP needs a get-by-address, an exists check, or an upsert.
3. **Context length.** `{Open_OPs}` lives only in the agent's context. A very large intake that runs past one context window loses it. That's acceptable for now, but worth knowing.
4. **Serving.** Point `intake_file` at `Intake_2.0.md` for the test.

## Decisions only you can make

1. **`{LB_COMPLETION}`** says "the code node containing all other elements." That can't hold for a photo or novel project. "Singular root" also fails when one project spans two roots, such as `code` plus `document` for its documentation. V12 applies the text to the project's tree, which is my interpretation of load-bearing text you own.
2. **`{LB_EF}`** says "CQU-owned join." Everywhere else, joins now live in the RE, and the CQU is only the top-level RE.
3. **The structural-prefix rule** above was my addition, to keep CQU addresses from failing their own naming rules. Confirm or replace it.
