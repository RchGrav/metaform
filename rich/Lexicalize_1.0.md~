# ============================================================
# AXIOM SCRIPT :: prompt-lexicalization  (v1.0)
# Compiled by Metaform Axiom-OS v1.0
# ============================================================

@STATE_INIT:
  {Prompt_Text}       := [the imported prompt or workflow, verbatim]
  {Map}               := [this project's namespace, read via {MAP_READ}]
  {Subjects}          := []      # each: span in {Prompt_Text}, canonical name, namespace address
  {Unresolved}        := []      # spans that name something with no entry in {Map}
  {Output}            := NULL

  # ---------- OWNER PLACEHOLDERS (fill before use) ----------
  {MAP_READ}          := [MCP tool that reads map entries]
  {PROMPT_STORE}      := [MCP tool that saves a lexicalized prompt]
  {UNRESOLVED_POLICY} := [keep wording | mark missing | stop and ask]
  {ADDRESS_PLACEMENT} := [inline after each name | one block of name -> address]

@CONSTRAINT:
  !> NEVER paraphrase, reorder, summarize, or add to any instruction. The only change is replacing a name.
  !> NEVER use the short name (name_length lookback). Use the entry's canonical `name` field.
  !> NEVER invent a name or address that is not in {Map}.
  +> Every subject the prompt names that has an entry in {Map} carries its canonical name and its namespace address.
  +> Match by what the wording refers to, not by exact spelling.
  +> Handle every span with no entry in {Map} per {UNRESOLVED_POLICY}.

@CONDITION (PLACEHOLDER_CHECK):
  ?IF ( any OWNER PLACEHOLDER is unfilled ) -> SAY which; HALT
  :ELSE -> CONTINUE

@CONDITION (MATCH):               # per span that names something
  ?IF ( the span refers to an entry in {Map} ) -> RESOLVED
  :ELSE -> UNRESOLVED

@ROUTER:
  APPLY PLACEHOLDER_CHECK.
  EXECUTE_PIPELINE( Identify_Subjects )
  FOR each span:
    @MATCH ( MATCH ):
      | [RESOLVED]   -> EXECUTE_PIPELINE( Replace_Name )
      | [UNRESOLVED] -> EXECUTE_PIPELINE( Apply_Unresolved_Policy )
  EXECUTE_PIPELINE( Assemble )

@EXECUTE_PIPELINE (Identify_Subjects):
  [STEP 1]: ∇({Prompt_Text}) => isolate every span that names something in the system. YIELD spans.

@EXECUTE_PIPELINE (Replace_Name):
  [STEP 1]: ∇(span, {Map}) => isolate the entry's canonical name and namespace address.
  [STEP 2]: Δ => replace the span with the canonical name; APPEND (span, name, address) to {Subjects}. YIELD.

@EXECUTE_PIPELINE (Apply_Unresolved_Policy):
  [STEP 1]: APPEND span to {Unresolved}; act per {UNRESOLVED_POLICY}. YIELD.

@EXECUTE_PIPELINE (Assemble):
  [STEP 1]: Δ({Prompt_Text} with replacements, {Subjects}) => attach addresses per {ADDRESS_PLACEMENT}.
  [STEP 2]: {Output} := result; SAVE via {PROMPT_STORE}. YIELD.

@VERIFY:
  [V1] Is every difference between {Prompt_Text} and {Output} a name replacement or an attached address?
       NO  -> RECURSE Assemble from the original text.
  [V2] Does every name in {Subjects} match its entry's canonical `name` field exactly?   NO -> RECURSE Replace_Name.
  [V3] Is every span in {Unresolved} handled per {UNRESOLVED_POLICY}?                   NO -> RECURSE Apply_Unresolved_Policy.
  [V4] All pass?                                                                         YES -> YIELD {Output}.
