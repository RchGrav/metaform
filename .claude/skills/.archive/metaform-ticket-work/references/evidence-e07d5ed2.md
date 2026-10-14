$ for a in code.interface.command_line ...; do grep -E '^memory:' /tmp/where_$a.txt | python3 -c '...'; done
== code.interface.command_line
 - named required nouns are read as positional (2026-10-11) | 1 obs: grammar.py:100-109 reads name=value only when name is an optional noun; a word naming a required noun falls to positional.
 - named required nouns (2026-10-11) | 1 obs: A name=value word naming a required noun now fills it: map citing key=path value=<file> finds what map citing path <file> finds.
== code.loader.module
== code.manager.prompt
kind: element: provides: receives: work: layers: properties: messages: past_work: join_layers: memory: