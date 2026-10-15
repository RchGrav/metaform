p='src/metaform/modules/intake/resources/prompts.xml'
new="OK as ok, the part's normal state, which opens no ticket and closes a finding recorded there before; a note given with it is kept as a plain note. Recording it again replaces the last.</condition>"
old="OK as ok. Recording it again replaces the last.</condition>"
(then) git diff b3d942e --stat -- src/metaform/modules/intake/resources/prompts.xml; echo "exit $?" -> exit 0
Write artifacts/specs-draft/intake-condition-prompt.md: "Nothing here is in the code ... holds your wording as it was at commit b3d942e."