@STATE_INIT:
  {Layer}:=[{{ layer }}]; {Challenges}:=[{{ challenges }}]; {Challenge}:=NULL; {Answer}:=UNRESOLVED

@CONSTRAINT:
  +> Act as the project agent answering blind-spot challenges in {Layer}.
  +> Review every challenge using project knowledge.
  +> Classify each challenge exactly:
     A := not useful; considered and not an oversight, with reason.
     B := useful; should be taken up.
     C := already handled by an existing element; a want is handled by the element that holds it.
  +> Answer using:
     metaform map answer <challenge> A
     metaform map answer <challenge> B
     metaform map answer <challenge> C link=element:<address>

@CONDITION:
  ?IF ( not useful AND considered ) -> {Answer}:=A
  :ELSE ?IF ( useful AND should be taken up ) -> {Answer}:=B
  :ELSE ?IF ( already handled ) -> {Answer}:=C

@ROUTER:
  @MATCH({Answer}):
    | [A] -> EXECUTE_PIPELINE(Answer_A)
    | [B] -> EXECUTE_PIPELINE(Answer_B)
    | [C] -> EXECUTE_PIPELINE(Answer_C)

@EXECUTE_PIPELINE(Answer_A):
  Δ({Challenge}) => answer A with reason.

@EXECUTE_PIPELINE(Answer_B):
  Δ({Challenge}) => answer B.

@EXECUTE_PIPELINE(Answer_C):
  ∇(project map) => resolve the existing element; for a want, the element that holds it.
  Δ({Challenge}, resolved link) => answer C with link=element:<address>.

@VERIFY:
  {Valid}:=(every challenge reviewed AND every answer is A|B|C AND every C links the existing element)
  ?IF ({Valid}) -> YIELD answers
  :ELSE -> CORRECT unresolved challenge
