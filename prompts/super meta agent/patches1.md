Below is a two-phase review and upgrade plan for the large “Agentic Workflow Orchestrator” prompt you supplied.
The focus is on maximising real-world performance inside **Claude Code CLI** while keeping the spirit of the original design intact.

---

## 1 · Deep Prompt Understanding (Current State)

| Aspect                                 | What it does well                                             | Observed gaps / risks                                                             |
| -------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **Task-decomposition & role clarity**  | Enumerates concrete roles, insists on independent evaluators. | No explicit cap on recursion/loop length → risk of runaway iterations.            |
| **Verification discipline**            | Mandates separate evaluator agents.                           | Evaluator scoring rubric is unspecified; success threshold ambiguous.             |
| **Iterative refinement**               | Describes a loop until “APPROVE”.                             | No stop-loss after N failed cycles; unclear how to surface dead-ends to the user. |
| **Tool utilisation (MCP)**             | Mentions MCP generically.                                     | Does not tell agents how to *invoke* MCP (syntax/examples).                       |
| **File-I/O spec**                      | Detailed directory tree.                                      | Paths hard-coded; no variable expansion; could collide across runs.               |
| **User interaction**                   | Asks to minimise clarifying questions.                        | But many mandatory confirmations (parallelism, assumptions) may prolong chat.     |
| **Guardrails / hallucination control** | Advises “no guessing”.                                        | Lacks an explicit *LLM-judge* or automatic fact-checker step.                     |

---

## 2 · Practical Enhancements (Phase-2 Integration)

### 2.1 – Modern Prompt-Engineering Techniques

| Technique                                                                                  | Integration point                                                                | Benefit                                                                         | Key reference                            |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ---------------------------------------- |
| **Self-Refine / Reflexion loop** – model generates, critiques, revises its own output      | Insert *“Self-Reflector”* agent between creator & evaluator.                     | Reduces evaluator retries; encourages model to fix errors before formal review. | ([arxiv.org][1], [promptingguide.ai][2]) |
| **PromptBreeder-style evolution** – mutate & score candidate prompts automatically         | Nightly “Prompt-Breeder” cron inside CLI; keeps best-scoring variant as default. | Enables *self-evolving* prompt without human in loop.                           | ([arxiv.org][3])                         |
| **LLM-Judge guardrail** – separate lightweight model scores factuality & policy compliance | Add *“Rapid-Judge”* agent before final APPROVE.                                  | Early detection of hallucinations, policy violations.                           | ([ml6.eu][4])                            |
| **Explicit XML/section tagging** (Anthropic best practice)                                 | Wrap agent instructions & required outputs in `<section>` tags.                  | Improves Claude’s reliability parsing long, nested instructions.                | ([docs.anthropic.com][5])                |
| **Worked examples / few-shot canon**                                                       | Attach a miniature “toy task” that walks through one full loop.                  | Faster convergence during first live run; clarifies spec.                       | ([journal.daniellopes.dev][6])           |
| **Dynamic stop-loss**                                                                      | Count evaluator “ITERATE” verdicts; abort or fallback after e.g. 3 cycles.       | Prevents infinite loops; surfaces issue to user quickly.                        | (Engineering best practice)              |
| **Versioned output root**                                                                  | Use `outputs/{task}_{ISO-timestamp}/` with ISO string from orchestrator.         | Avoids path collisions in CLI multi-run context.                                | (Engineering best practice)              |

### 2.2 – Concrete Prompt Edits

1. **Introduce a global YAML header** at top of orchestrator prompt

   ```yaml
   max_iterations: 3
   default_parallel_agents: 4
   output_root_template: "./outputs/{task}_{timestamp}/"
   ```

   Agents read this via environment variables; orchestrator enforces limits.

2. **Add Self-Reflector agent template**

   ```markdown
   # Self-Reflector
   **Role:** Review the just-generated output *before* evaluator sees it.  
   **Instructions:**  
   - Identify factual, logical, or format flaws.  
   - Rewrite the output if you give yourself ≤ 90 / 100.  
   - Write both *score* and *final (possibly revised) output* to the same file, clearly separated by `---`.  
   ```

3. **Embed Reflexion meta-feedback**
   After each evaluator report, append it to a rolling `memory/reflexion.log`.
   The design agent receives last 2 entries and must show how it addressed them.

4. **Guardrail agent**
   Lightweight judge with policy/factual heuristic. If score < 0.8, block release.

5. **MCP call examples**
   Provide concrete syntax, e.g.

   ```bash
   ### Agent (python executor) ###
   !mcp.exec python3 ./phase2/code.py
   ```

   This demystifies how agents invoke external tools. ([theverge.com][7])

---

## 3 · Blueprint for a Self-Evolving Prompt

> **Goal:** At the end of each successful main task run, allow the system to spawn a “Prompt-Breeder” cycle that tries to improve its own root prompt off-line, stores versions, and promotes better prompts.

### 3.1 Lifecycle

1. **Seed**: Current orchestrator prompt `prompt_vX.Y.md`.
2. **Mutation**: “Breeder” agent creates *k* prompt variants (synonym swaps, reordered instructions, added clarifications).
3. **Fitness test**:

   * Re-run a small canonical regression task with each variant.
   * Score via the Rapid-Judge (accuracy) + runtime metrics (iterations used).
4. **Selection**: Keep variant with highest composite score if it outperforms baseline by Δ≥ 5 %.
5. **Version bump & commit**:

   * Save as `prompt_v(X+1).0.md`;
   * `git commit` through GitHub MCP with changelog.

### 3.2 CLI Implementation Snippet (pseudo-bash)

```bash
ORCH=prompt_v1.4.md
for P in $(breeder $ORCH --k 5); do
  run_task --prompt $P --regression_case quick.json >score.txt
done
best=$(select_best ./scores)
if [ "$best" better_than "$ORCH" ]; then
  mv $best prompt_v1.5.md
  mcp.git.commit prompt_v1.5.md -m "auto-evolved prompt"
fi
```

This keeps evolution bounded and observable.

---

## 4 · Minimal Patch-set Summary

| Category            | Change                                                                     |
| ------------------- | -------------------------------------------------------------------------- |
| **Reliability**     | Cap iterations; add self-reflection; explicit scoring rubric.              |
| **Maintainability** | YAML header variables; timestamped output roots; Git-tracked versions.     |
| **Capability**      | PromptBreeder loop; concrete MCP invocation examples; LLM-Judge guardrail. |
| **Compliance**      | XML tagging; fact-check step before release.                               |

Implementing the above requires only **three new agent prompt files and minor edits** to the orchestrator markdown; it remains fully runnable inside Claude Code CLI with no external dependencies beyond the optional GitHub MCP connector.
