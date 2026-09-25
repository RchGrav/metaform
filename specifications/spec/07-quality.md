# 07 Quality

This section sets the quality bar for all Metaform code, and says how that bar is checked on every change.
It covers the engineering standard, cross-platform proof, typing, linting, what tests are for, reviews, the cold build check of this spec, and traceability.

### QUAL-001 The code quality standard is the bar

- Requirement: All chassis, common base, template and module code meets the standard in specifications/code_quality_standards.md.
- What this means: The standard treats Metaform as mission-critical engineering with aerospace-grade expectations for quality, reliability, maintainability and technical discipline. Code is:
  - organized by responsibility and ownership;
  - easy to understand, inspect, test and change;
  - strongly typed wherever interfaces and state cross a boundary;
  - explicit about lifecycle, who owns each resource, where each thing runs, and what happens when it fails;
  - reliable across synchronous, asynchronous, event-driven, persistence, unload, reload and shutdown paths;
  - documented at its public and architectural boundaries;
  - resistant to hidden coupling, leaked resources, corrupted state, concurrency faults and unclear ownership;
  - built from small, cohesive parts with stable interfaces;
  - shaped to keep future maintenance cost and technical debt low.

  Simple, explicit, durable engineering wins over cleverness and needless abstraction. No architecture is added for a hypothetical future need, and no shortcut is accepted that leaves lifecycle, concurrency, persistence or maintenance fragile. The standard's immediate aim is the right module shape: one repeatable structure that substantial modules follow while staying clean participants in the chassis contract.
- Why: The code will face outside scrutiny and must pass it. Community authors copy the template and build on the common base, so every flaw in them is copied into every fork.
- How it shows: Each part of the code has one clear owner. Resources are acquired and released in visible places. Failure behavior is stated where it happens. A reviewer can follow any boundary without reading unrelated code.
- Build: The standard file stays in specifications/ with its wording unchanged. The spec index lists it as the bar. The critic review in QUAL-008 checks code against it item by item.
- Acceptance: Every merge has a critic review that names each standard item the change touches and states whether the change meets it. A change with an unmet item does not merge.
- Relates to: QUAL-008, QUAL-006, BASE-018, BASE-019.
- Status: confirmed.

### QUAL-002 Everything works on Linux, macOS and Windows

- Requirement: By default, every part of Metaform works on Linux, macOS and Windows.
- What this means: The chassis, the common base, the template and every repo module run on all three systems. Paths, file locations, process handling, terminal behavior and each AI tool's config locations are handled per system. When something genuinely cannot run on a system, compatibility is stated rather than left to fail. A module states the systems it supports in SUPPORTED_OS. A verb may narrow its own compatibility. A small system-specific piece can also be its own module, so the main module stays usable everywhere.
- Why: Metaform runs wherever its users and their agents work. A piece that fails silently on one system breaks trust in the whole tool.
- How it shows: A fresh install on each of the three systems runs the same commands with the same results. On a system a verb does not support, `metaform help <verb>` says where it runs and gives one next step.
- Build: The CLAUDE.md rule states this for every agent working on the code. The per-verb mechanism reuses the command filter described in the CLI section. CI proof is QUAL-003.
- Acceptance: The QUAL-003 runs pass on all three systems for every change.
- Relates to: QUAL-003, BASE-015, BASE-016, MCP-023.
- Status: confirmed for the rule and module-level compatibility; per-verb narrowing confirmed as acceptable; its mechanism recommended.

### QUAL-003 CI proves cross-platform on every change

- Requirement: CI runs the full check set on Linux, macOS and Windows for every change, and the template's CI does the same.
- What this means: Every push and pull request to the repo runs type checking, linting and the tests on all three systems. The template module ships with the same CI configuration, so every community fork built from it tests on all three systems too. The offer to maintain a user's fork and CI carries this matrix.
- Why: Cross-platform needs proof, not a promise. Without runs on every system, one system breaks quietly and nobody sees it until a user does.
- How it shows: Every change shows three results, one per system. A change that fails on any system does not merge.
- Build: GitHub Actions with a job matrix of ubuntu-latest, macos-latest and windows-latest. Each job installs with uv from pyproject.toml, then runs the type check (QUAL-004), the lint (QUAL-005) and the tests. The Python version is the project's declared minimum. The template carries its own copy of this workflow file.
- Acceptance: The workflow file lists all three systems. A deliberately system-specific failure, such as a hard-coded POSIX path separator in a check fixture, fails the Windows job.
- Relates to: QUAL-002, QUAL-004, QUAL-005, QUAL-006, BASE-019, BASE-027.
- Status: confirmed.

### QUAL-004 Strict type checking of the common base and the chassis

- Requirement: The common base and the chassis pass strict type checking on every change.
- What this means: Everything a module imports from the common base is fully typed, and so is the chassis. The checker runs in strict mode over those packages. Modules are checked too, and the template is written so it passes strict mode, so authors start from typed code.
- Why: The common base is the contract modules build on. Typing makes a broken contract fail the build instead of failing in a user's session. It catches whole classes of defects mechanically. It is a floor, not a measure of quality.
- How it shows: A change that alters a base signature without updating its callers fails CI.
- Build: Pyright in strict mode over src/metaform and the shipped modules, configured in pyproject.toml. It runs in every QUAL-003 job.
- Acceptance: The pyproject configuration sets strict mode for the base and chassis paths. CI fails on any type error in them.
- Relates to: QUAL-001, QUAL-003, BASE-004.
- Status: confirmed.

### QUAL-005 One lint configuration

- Requirement: All code is linted by one configuration, with no local exceptions unless each carries a written reason.
- What this means: The whole repo, including the template, uses one lint setup. An exception to a rule sits next to the code it excuses and states why.
- Why: One configuration keeps the codebase consistent for every reader and every fork. Unexplained exceptions hide defects.
- How it shows: A suppression without a reason fails the lint.
- Build: Ruff, configured once in pyproject.toml, run in every QUAL-003 job. The rule set and the required format of a reasoned suppression are open.
- Acceptance: CI fails on any lint error, and on any suppression without a reason.
- Relates to: QUAL-003.
- Status: confirmed for one config; the rule set is open.

### QUAL-006 Tests exist only to protect the design

- Requirement: Every test protects one requirement of this spec, and would fail on a build that gets that requirement wrong.
- What this means: A test is written from a requirement, before the code that meets it, and fails until that code exists. A test that mirrors the implementation is not written. Neither is a test for a reversible, low-impact change. A test that would pass on a wrong build is treated as failing, even when it passes. Passing tests are not evidence of quality. They prove only that their own conditions held. Quality is judged on the code itself, through QUAL-001 and QUAL-008.
- Why: Tests that mirror the code pass on wrong builds, cost tokens, and make corrections harder. A suite full of them protects whatever the code happens to do, including a misreading of the design, so correcting the design means fighting the tests. A test is only as good as the condition it checks.
- How it shows: The suite stays small, at roughly the number of requirements that need protecting. Changing a requirement means changing one record and its tests, not rewriting a suite.
- Build: Tests live in tests/. Each test states the requirement ID it protects (QUAL-009). Tests are written before the code and are seen to fail first. The test-gaming review in QUAL-007 runs over every new or changed test.
- Acceptance: Every test names a requirement ID that exists in the spec. The QUAL-007 review finds no test that mirrors the implementation or would pass on a wrong build.
- Relates to: QUAL-007, QUAL-009, QUAL-011.
- Status: confirmed.

### QUAL-007 A test-gaming review agent checks the tests

- Requirement: A review agent examines every new or changed test for signs that it games its purpose.
- What this means: The agent reads each test next to the requirement it names, and asks whether it would fail on a build that gets the requirement wrong. It flags tests that:
  - check form instead of behavior;
  - restate the implementation;
  - assert only what the code happens to return;
  - weaken or skip the requirement;
  - exist for show.

  A flagged test is fixed or removed before merge.
- Why: A test can pass while protecting nothing. An author, human or agent, tends to write tests that confirm what was built. An outside reader with the requirement in hand catches that.
- How it shows: Each merge carries the review's findings for the tests it adds or changes.
- Build: The reviewing agent gets only the spec records and the test code, with no access to the implementation it is checking against. Whether it runs as a CI step or as a pre-merge agent run is open.
- Acceptance: Every merge that touches tests/ has a completed review with no unresolved findings.
- Relates to: QUAL-006, QUAL-008, QUAL-009.
- Status: confirmed for the review; its trigger is open.

### QUAL-008 A critic review against the standard before merge

- Requirement: Before any code merges, a critic review judges it against the code quality standard.
- What this means: A critic agent reads the change and writes a review against QUAL-001, item by item:
  - ownership;
  - lifecycle;
  - failure behavior;
  - typing at boundaries;
  - coupling;
  - resource handling;
  - part size;
  - interface stability;
  - speculative architecture.

  Rich judges behavior. The critic judges the code.
- Why: Passing tests are not quality. The standard's qualities can only be judged by reading the code. A reviewer who did not write the change sees what the author missed.
- How it shows: Every merged change has a written review attached that names each standard item it touches and the verdict for each.
- Build: A critic agent receives the diff, the standard and the spec records the change claims to meet. Findings that fail the standard block the merge until they are fixed. Where the review is stored is open.
- Acceptance: Every merge has a review with a verdict on each standard item the change touches, and no blocking finding left open.
- Relates to: QUAL-001, QUAL-006, QUAL-007.
- Status: confirmed.

### QUAL-009 Traceability between requirements and tests

- Requirement: Every requirement names the tests that protect it, and every test names the requirement it protects.
- What this means: Each spec record's Acceptance line points to its tests where tests apply. Each test carries the ID of its requirement. A requirement with no test either needs none, which its record states, or is a gap. A test with no requirement protects nothing and is removed.
- Why: Links in both directions show at a glance what is protected and what is not. They keep tests tied to the design instead of to the code, and they make a requirement change find its tests.
- How it shows: A listing shows every requirement ID with its tests, and every test with its requirement. Orphans on either side are shown.
- Build: A test states its requirement ID in its name or a marker. A check lists orphans on both sides and fails CI when it finds a test with no existing requirement ID. The exact marker form is open.
- Acceptance: The orphan check passes: no test without a requirement, and no requirement that needs a test but has none.
- Relates to: QUAL-006, QUAL-011, every section of the spec.
- Status: confirmed.

### QUAL-010 Lifecycle checks where the standard names a real risk

- Requirement: Lifecycle checks exist for module unload, reload, shutdown and async cancel, and for no other lifecycle path.
- What this means: The standard names these paths because state corruption or leaked resources there otherwise go unseen. For each one, a check proves that no state is corrupted and no resource is left held:
  - a module is unloaded;
  - a module is reloaded;
  - the chassis shuts down with work in flight;
  - an async verb is cancelled.

  Each check names the requirement it protects. No lifecycle check is written for a path that carries no such risk.
- Why: These failures are silent. A leaked database handle or half-written record shows up much later and far from its cause. Checking only the named risks keeps the suite small and meaningful.
- How it shows: Cancelling an async verb leaves storage consistent and releases its resources. Unloading and reloading a module leaves no stale registration of its verbs, settings or subscriptions.
- Build: The checks run the real CLI and the real module loader against an isolated Metaform home. Their exact cases are written with the common base and chassis sections, which define the lifecycle.
- Acceptance: Each of the four paths has checks tied to a requirement ID, and each check fails on a build that leaks or corrupts on that path.
- Relates to: QUAL-001, QUAL-006, BASE-009, BASE-018, STORE-006.
- Status: confirmed.

### QUAL-011 The cold build check of this spec

- Requirement: The spec is buildable when a fresh agent, given only the spec, can list no point where it would have to guess, choose, or ask.
- What this means: An agent with no memory, no repository and no conversation history reads the spec and lists every place where it would have to guess, choose between readings, or ask. Each item is either a gap fixed from the confirmed design, or a question for Rich. Nothing on the list is filled in by guesswork. The check repeats until the list comes back empty.
- Why: Earlier builds were rebuilt many times because builders reinterpreted a spec that left room to guess. An empty list is the evidence that the build follows from the spec without reinterpretation.
- How it shows: Each run produces a list. The list shrinks across runs, and open questions go to Rich in batches.
- Build: A clean agent run, with no instruction files and no access to earlier branches, gets the specifications/ folder and one instruction: list every point where you would guess, choose, or ask to build this, citing the record. The run follows the clean-run pattern of the intake, on a copy outside the repository.
- Acceptance: The latest cold build run returns an empty list, and every item from earlier runs is traced to a fix or to Rich's answer.
- Relates to: QUAL-009, every section of the spec.
- Status: confirmed.

### QUAL-012 The existing chassis tests are reviewed against the spec

- Requirement: Each existing chassis test is kept only if it protects a requirement of this spec.
- What this means: The chassis branch holds 54 tests written before this spec existed. Once the spec is written, each test is read against it. A test that protects a requirement is kept and given that requirement's ID. A test that mirrors the code, or protects nothing in the spec, is removed. A requirement left uncovered gets a new test, written first.
- Why: Tests written before the spec may protect behavior the spec changes, such as the XML map import and value-style booleans, and would resist the realignment.
- How it shows: After the review, every remaining test names a requirement, and the removed tests are listed with the reason for each.
- Build: The QUAL-007 review agent performs this pass against the finished spec, before the chassis is realigned.
- Acceptance: The QUAL-009 orphan check passes over the whole chassis test suite.
- Relates to: QUAL-006, QUAL-007, QUAL-009.
- Status: confirmed.

### QUAL-013 Documentation shows who owns what, and there is one current contract

- Requirement: Developer documentation makes it clear whether a behavior belongs to the chassis or to a module, and presents exactly one current module contract.
- What this means: Chassis documentation describes the chassis and the common base. Each module's README describes that module. The template and its changelog are the one current module contract. Documents describing earlier contracts are removed from the current docs; they stay in git history and the archive branches.
- Why: Two contracts in the docs means agents follow whichever they read first. That is how earlier rebuilds carried old designs forward.
- How it shows: A developer looking for how modules work finds one answer, in the template and its README.
- Build: The docs index lists the chassis docs, the template README and changelog, and each module README. The critic review under QUAL-008 checks that no document describes a second module contract.
- Acceptance: checked in the critic review, QUAL-008.
- Relates to: BASE-019, BASE-034, QUAL-008.
- Status: confirmed.

### QUAL-014 Fixtures, simulations and real runs are named for what they are

- Requirement: Every report of a result says whether it came from a deterministic fixture, a local offline simulation, or a real run, and a real run names the provider and path it exercised.
- What this means: A fixture shows that the mechanics work. A simulation shows that its own environment works. A real run in Claude Code or Codex shows only that host on that path. None of them is reported as another. The first working test counts as done only with a real run in a real host.
- Why: Reports that pass fixtures off as real runs make features look finished when they have never met a real agent, and the gap is found by users.
- How it shows: Test names and status reports carry fixture, simulation or real, and real results name the host.
- Build: Tests that use fixtures are marked as fixture tests. The installer's proof step, MCP-017, and the first working test, MCP-024, record the real host and version they ran against.
- Acceptance:
  1. The report for MCP-024 names the host, its version and the operating system it ran on.
- Relates to: QUAL-006, QUAL-009, MCP-017, MCP-024.
- Status: confirmed.

## Open questions

1. QUAL-005: Which Ruff rule set applies, and what form must a reasoned suppression take?
2. QUAL-007: Does the test-gaming review run as a CI step, or as an agent run before merge?
3. QUAL-008: Where is each critic review stored: in the pull request, in the repository, or both?
4. QUAL-009: What marker ties a test to its requirement ID: the test name, a pytest marker, or a docstring line?
5. QUAL-003: What is the declared minimum Python version the CI matrix runs? The pros and cons of 3.10 against 3.11 are set aside for now.
