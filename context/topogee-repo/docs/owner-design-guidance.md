<!-- The founder's own design guidance, copied word for word from ~/ccl-min/docs/design-guidence.md (2025-10-10) on his other machine, sent by the c3lab Claude session on 2026-11-06. The founder confirmed it is his personal design. Its meshvm commands are examples; its principles apply to Topogee. -->

# meshvm: Design Guidance with Real Examples

## A. Defaults are home, not a void

**Philosophy.** Resetting shouldn’t erase value; it should take you back to a fully working lab—the place you want to live most of the time.

**In code.**

* `mvm unset all` resets sensible defaults instead of nulls (nodes/memory/ports/etc.). The help explicitly documents `unset all`.&#x20;
* The main help shows the “just run it” flow; after `mvm build` and `mvm set --image …`, `mvm lab` runs the lab immediately.&#x20;

**Why this removes friction.** You can try things freely and never fear “losing tweaks”: reset brings you to a **stocked**, usable bench, not back to nothing.

---

## B. TUI and CLI are the same tool

**Philosophy.** The TUI is a lens on the same state the CLI manipulates; there’s no drift. Script everything; discover via TUI.

**In code.**

* `mvm config` surfaces the same defaults you’d change via `mvm set`—documented side-by-side. &#x20;
* Status/Help put CLI and TUI flows next to each other (e.g., `config --show`, `config --wizard`).&#x20;

**Why this removes friction.** New users orient in the TUI; power users script the exact same knobs.

---

## C. Switches are purposeful workflow levers, not sticky gremlins

**Philosophy.** A command is an action; a **switch of the same name** is a temporary **mode**. Flip it on for an activity, off when you’re done. And the breaker is always `unset all`.

**In code (today).**

* Stage as a switch: `mvm build --stage` folds `overlay/staging` into the FILES composition for the build; the lab path can apply staging live after start if enabled. &#x20;
* The lab checks a persisted `stage_enabled` flag (if present) to apply staging every run; a one-shot `--stage` triggers it now.&#x20;

**Why this removes friction.** You don’t “configure forever”; you **flip** intent for the current session. `unset all` is the breaker that takes you home.

---

## D. Staging is a scratchpad—with airbags

**Philosophy.** Staging is where you experiment; it’s ephemeral by **purpose** and **protected by design** so mistakes can’t silently poison builds.

**In code.**

* Safety rails: staging is audited; ELFs/kmods make **hardware** builds refuse; x86 dev builds **warn** only.&#x20;
* Save/load/clear guardrails: you can snapshot (`stage save`), list, and refuse destructive ops unless `--force`. Saved bases show timestamped snapshots. &#x20;
* Promotion: `stage export name@<target>` emits a **tagged** overlay with minimal metadata (target, arch, created\_at, sha). &#x20;

**Why this removes friction.** You can tinker fearlessly. Safety checks prevent bad artifacts; promotion is a single, explicit step.

---

## E. Overlays are auditable, deterministic artifacts

**Philosophy.** Once exported, overlays are durable—portable, composable, conflict-aware.

**In code.**

* Combine overlay+stage with **transparent precedence** and deterministic names:

  * `base.stage` → no conflicts; just combined.
  * `base-stage` → stage overwrote base files.
  * `base_stage` → base “won” (stage files omitted).

  The code chooses the separator (`.`, `-`, `_`) based on conflict/precedence and tags the artifact with `@<target>`.  &#x20;
* Each combined overlay writes a tiny **plain-text** `overlay.meta` (target, arch, created\_at, base sha, omitted lists) for traceability without entangling filenames.&#x20;

**Why this removes friction.** You don’t memorize merge orders; the artifact name itself telegraphs precedence, while the meta is there if automation needs it. No databases, no lock-in.

---

## F. The lab is turnkey—and friendly at the edges

**Philosophy.** On first run, the lab should “just work,” and the console should feel like a normal app.

**In code.**

* tmux viewer with sane keybindings and mouse: Alt-Left/Right (windows), Alt-Up/Down (panes), Alt-Enter zoom; pane titles show node + key ports.&#x20;
* Each node writes a `.ports` file with HTTP/HTTPS/SSH and a serial socket; `status --urls` prints friendly URLs/SSH commands. &#x20;
* Ready checks and guardrails (e.g., rolling back failed starts, waiting for services).&#x20;

**Why this removes friction.** No hunting for ports, no mystical flags—just attach, click, type.

---

## G. Platforms are guided, not guessed

**Philosophy.** Picking targets should be obvious and scriptable.

**In code.**

* `mvm platforms list` prints a grouped human list; `mvm platforms set` accepts **indices** or **IDs** and persists to `state/config.json`. &#x20;

**Why this removes friction.** Humans can pick by number; scripts can pick by ID—both stable.

---

## H. Best-effort integrations never block

**Philosophy.** If a private or optional bit isn’t available, degrade silently and keep going.

**In code.**

* `comm3_sync.sh`: “not available; nothing to sync”—exits cleanly; comments document “safe to run without auth.” &#x20;
* Prereqs script tries to install what’s missing, writes a marker, and offers an editor pick—then proceeds. &#x20;

**Why this removes friction.** No brick walls. Worst case is a usable, reduced experience.

---

## I. Everything leaves a trace (auditable builds)

**Philosophy.** Reproducibility is built-in: when something goes wrong, you can inspect what happened.

**In code.**

* Build emits a JSON manifest next to the image: input overlays (with sha/size), composition order, conflict samples, and a **files tree hash**—plus image sha/size. &#x20;

**Why this removes friction.** Debugging is a read, not a séance.

---

## J. “Patterns, not laws”

**Philosophy.** These aesthetics are optional **approaches**, not gatekeeping rules. If a subsystem is fine as-is, leave it. Use patterns whenever they reduce friction; don’t enforce them where they don’t help.

**In code.**

* Overlay/underlay naming & metadata add clarity **without** adding tech debt: filenames encode precedence; metadata is lightweight and ignorable (automation can read it, humans don’t have to). Renames don’t require editing JSON, and the artifact still carries internal provenance. &#x20;

**Why this removes friction.** Clarity when you want it; zero penalty when you don’t.

---

# Further Alignment Opportunities (nice to have, not criticisms)

These are places where **Z could be as nice as X/Y**:

1. **Verify as a proper switch.**
   Today `verify` is a one-shot command with `--suite`. Making `mvm set --verify [suite]` flip the lab into “verify mode” until `unset` would mirror the stage pattern (like `--stage`). Help already lists `verify --suite …`; it just needs the toggle path.&#x20;

2. **Help entries for Stage/Overlay.**
   The verbs are implemented and powerful, but not exposed under `mvm help stage` / `mvm help overlay` in the top help index. Adding short help pages completes discoverability.

3. **Centralize all persistent toggles in config.json.**
   `overlay_active` (layers/overlays/.active marker) and `stage_enabled` currently live outside the core toggle set. Pull them into config so `status/config/unset` always see the same truth. (The lab already reads `stage_enabled` if present.)&#x20;

4. **Expose toggles in `status`.**
   You already summarize some switches in help and defaults; surfacing active toggles in `mvm status` would make invisible state obvious.&#x20;

5. **Unify command/switch naming for runtime modes.**
   `--legacy/--virtio` behave like mode levers; consider a persisted `io-mode` (or similar) to match the “switch equals mode” pattern, while keeping the one-shot flags for per-run overrides.&#x20;

6. **Verb surface pruning.**
   `dev` utilities could be tucked under `lab` (e.g., `mvm lab exec`, `mvm lab sync`) to keep the command grammar tight, while preserving the same behavior.

All of the above preserve the three absolutes: **never a blocker**, **no tech debt**, **always resettable**—and keep the meta-rule: **patterns aren’t laws**.

---

# Bonus: a tiny “Zen of meshvm”

* **Defaults are home.** Not a lobby; a living room.
* **Switches are impulses.** Flip them for a task, not for life.
* **Staging is curiosity in quarantine.** Play freely; promotion is a choice.
* **Overlays are stories you can reread.** Title them well; keep the receipts.
* **Help is a map, not a maze.** If you need a compass, we failed.
* **When in doubt, reset.** Baseline is not “empty”—it’s *ready*.
* **Patterns are guides, not guards.** Use them when they lighten the load.
