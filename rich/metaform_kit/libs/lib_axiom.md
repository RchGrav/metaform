# lib_axiom · the Axiom grammar
# Load once per agent. Marker: [lib_axiom loaded]. Source: axiom-language v1, modules through errors
# (corpus 444-504), unchanged. No examples here; each skill carries the examples for its task.

## Which dialect
- A workflow subroutine (a logic requirement on a workflow element) is axiom-language v1, below:
  YIELD returns control to @ROUTER; RECURSE <Pipeline> re-runs it; a script with one pipeline routes directly.
- A standalone script or a skill is Axiom-OS 2.0: `#! AXIOM/2.0` header, YIELD ends, RECURSE(max=N),
  every @MATCH has `| [*]`, runtime text bound as <<DATA: ...>>, optional modules @BUDGET @FALLBACK @PRIORITY
  @TRACE @ASSERT @LOOP(max=N) @SPAWN/@AWAIT @GROUND, operators ⊕ merge ⊘ nullify ⟳(max=N) HALT.
  The full 2.0 rule list and the lint rules are in lib_quality; only the linting skill needs them.

--- Modules [v1.1] ---
Every script has these six modules, in this order.

  1. @STATE_INIT               Variables.            {Name} := value
  2. @CONSTRAINT               Rules.                !> forbidden   +> required   ~> heuristic
  3. @CONDITION (Name)         Decisions.            ?IF ( condition ) -> outcome  :ELSE -> outcome
  4. @ROUTER                   Which pipeline runs.  @MATCH ( {Var} ):
                                                       | [VALUE] -> EXECUTE_PIPELINE( Name )
                               [new] A script with one pipeline may route directly:
                               EXECUTE_PIPELINE( Name )
  5. @EXECUTE_PIPELINE (Name)  Numbered steps.       [STEP n]: ...
  6. @VERIFY                   Yes/no checks run before the result is used.
                               Each failed check names what to redo.

  A heuristic (~>) is a strong preference. Break it only with a stated reason.

--- Operators [∇ and Δ: v1.1; the rest: new] ---
  :=          assign
  ∇( x )      isolate: break x down and analyze it
  Δ( x )      synthesize: build the result.   Δ => {Var}  writes the result to {Var}
  =>          produces
  APPLY Name  decide using the @CONDITION of that name
  YIELD       end this pipeline; control returns to @ROUTER
  RECURSE X   run pipeline X again
  NULL        empty

--- Subroutines [v1.1, except this] ---
A subroutine is one Axiom script, stored as one logic requirement (workflow-logic).
It is called by its element's address and its name.

  Parameters   declared in @STATE_INIT:
                 {target}   := PARAM                  required
                 {standard} := PARAM = "default"      optional, with a default
  Return       RETURN {value}            a single value
               RETURN ( {a}, {b} )       a tuple
  Call         ( {a}, {b} ) := <address>.<name>( param=value, ... )
                 <address> is the element that holds the subroutine. Arguments are by keyword.
                 The returned values land in the caller's variables.
  this         [new] The element the logic is on. In a logic join on a project element, this is
               that element. Inside a subroutine on a workflow element, this is the workflow
               element. Values are read in Python's syntax; metaform-system lists every name.
               this is read, never assigned. There is no call through this: every call names
               an element's address.

--- Control flow (Amazon States Language terms) [new] ---
  Choice     Branch on a condition.
  Parallel   Run independent work at once. Continues when every branch has returned.
  Map        Work through several things. Always MaxConcurrency: 1: one item UNTIL its
             acceptance holds, then the next.
  UNTIL      Repeat until the acceptance holds. Every loop states MaxAttempts.
  Retry: [{ ErrorEquals, MaxAttempts, BackoffRate }]      retry work that can fail
  Catch: [{ ErrorEquals, Next: <address>.<name>(...) }]  route an error to a handler subroutine

  Two different counts. A loop's MaxAttempts counts tries at reaching acceptance.
  A Retry's MaxAttempts counts retries after an error. State each where it applies.

--- Errors [new] ---
  An error has a name in UpperCamelCase that says what went wrong: FixFailed, SourceUnreadable.
  A subroutine lists the errors it can raise in its @CONSTRAINT:  +> Raises: FixFailed, SourceUnreadable
  Retry and Catch match errors by those names. ErrorEquals: [any] matches every error.
  Reading a missing key on an element raises KeyError, as in Python.
