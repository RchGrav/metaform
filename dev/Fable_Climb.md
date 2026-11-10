Work directly in the current repository to review and fix verified code gaps, improve repository organization where there is a clear benefit, and refine the README and other relevant documentation. Then begin a disciplined hill-climbing process that follows the repository’s design and improvement intent, especially any applicable skills instructions.

## 1. Inspect repository state and instructions
- Check the working tree, current branch, and recent project context before making changes. Preserve all existing user changes; do not overwrite, discard, or reformat unrelated work.
- Read contributor guidance and agent instructions, including applicable `AGENTS.md` files, skills instructions, design documents, improvement plans, and project-specific test, evaluation, or documentation requirements. Follow the most specific applicable guidance.
- Map the relevant architecture, repository structure, code paths, tests, benchmarks, evaluation harnesses, README, and documentation.
- Identify documented conventions for folder structure, naming, documentation style, and generated files. Do not reorganize files merely for aesthetics or move files in ways that break imports, links, tooling, or established conventions.
- If instructions conflict, follow the more specific repository guidance where possible and explain any unresolved conflict before proceeding.

## 2. Establish a baseline
- Identify standardized tests, benchmarks, evaluations, rubrics, production-trace fixtures, and documentation checks relevant to the target code or agent behavior.
- Run the most relevant baseline checks before changing code or documentation. Record exact commands, results, scores, failures, and environmental limitations. Do not claim checks passed unless they were run.
- Treat the current implementation, repository organization, documentation, and measured results as the baseline. Do not invent scores or outcomes.
- If no suitable evaluation exists, choose the smallest defensible, repeatable test set from existing project tests and documented requirements. Do not create a broad benchmark or change evaluation criteria without explaining why.

## 3. Review and fix verified code gaps
- Look for concrete defects, missing behavior, incorrect assumptions, edge cases, security or reliability issues, and mismatches with repository design requirements.
- Prioritize findings supported by code, tests, documentation, or reproducible behavior. Avoid speculative rewrites and unrelated cleanup.
- Make focused fixes that preserve established interfaces and design intent. Add or update targeted regression tests for verified defects when appropriate.
- Keep bug fixes distinct from repository organization, documentation work, and later hill-climbing experiments so their effects can be evaluated separately.
- After verified fixes, rerun relevant checks and record the post-fix results.

## 4. Improve repository organization and documentation
- Identify specific, evidence-based problems in the repository structure or documentation, such as duplicated or misplaced material, unclear entry points, stale instructions, broken links, undocumented setup or workflows, or a README that does not accurately describe the project.
- Make only focused, low-risk organizational changes that improve discoverability or maintainability and comply with repository conventions. Preserve public interfaces, build and test behavior, import paths, links, and user work. Avoid broad restructures without strong evidence and a migration plan.
- Refine the README and relevant documentation to be accurate, concise, navigable, and consistent with the actual code. Verify commands, paths, options, examples, and claims against the repository; do not invent features or capabilities.
- Update references affected by any approved file moves. Run available documentation, link, formatting, build, or test checks relevant to these changes.
- Keep documentation and organization improvements separate from code fixes and hill-climbing experiments. Record the files changed and the evidence for each change.

## 5. Begin the hill-climbing loop
Follow the repository’s skills instructions and use this controlled cycle:
1. Select one specific, evidence-based improvement hypothesis.
2. Change only one meaningful variable at a time, such as a prompt, context layer, tool definition, implementation behavior, model setting, or harness configuration. Do not bundle independent experimental changes.
3. Run the same evaluation set and commands used for the comparison baseline, using consistent conditions where practical.
4. Compare results against the baseline and inspect for regressions, including correctness, reliability, safety, latency, and cost where available.
5. Keep the change only when evidence supports an improvement and no unacceptable regression appears. Otherwise revert only that experimental change, preserving unrelated work.
6. Record the hypothesis, exact change, evaluation results, decision, and rationale before attempting another experiment.

Start with one hill-climbing experiment if the repository has an adequate evaluation loop. Keep this experiment distinct from code repairs and documentation or organization changes. If no reliable evaluation loop exists, finish the verified repairs and documentation work, explain the limitation, and propose the smallest practical next step needed to make hill climbing measurable. Do not claim an improvement without evidence.

## Constraints
- Follow all applicable repository and skills instructions; they define the intended design, organization, documentation conventions, and improvement direction.
- Preserve existing user changes and avoid destructive commands.
- Do not make multiple independent experimental changes before evaluation.
- Do not weaken tests, alter scoring criteria to manufacture gains, or report unverified outcomes.
- Keep changes scoped, maintainable, and consistent with project conventions. Avoid cosmetic reorganization that adds churn without a concrete benefit.
- If an action is blocked by missing dependencies, credentials, unavailable services, or ambiguous instructions, state the blocker and continue with safe work that can be verified.

## Final report
Summarize:
- Repository guidance and improvement intent followed.
- Verified code gaps found and fixes made.
- Baseline and post-fix commands and results.
- Repository organization and README/documentation issues addressed, files changed, and relevant validation results.
- The hill-climbing hypothesis, single change tested, comparison results, and keep/revert decision—or why a valid experiment could not be run.
- Remaining risks or blockers and the most useful next experiment.

Be explicit about what you actually inspected, changed, and tested. Do not claim completion of steps that were not performed.
