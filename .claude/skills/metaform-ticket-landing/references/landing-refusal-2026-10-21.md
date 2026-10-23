# Landing refusal, 2026-10-21

Ticket code.system.management.knowledge#a0 (roundtable 6 proposal) finished its commit and push on metaform/2752890838f1, then the landing into main was refused.

Worker-visible error:

    Missing: error: Untracked working tree file 'docs/roundtables/6-in-the-last-roundtable-we-talked-about-this-as-a-possibility/export.json' would be overwritten by merge.

Cause: the roundtables module had written export.json and mechanical-report.md untracked into the main checkout. The delta added the same paths as tracked files.

Resolution: both untracked files were byte-identical to the committed versions (cmp), were removed, and `metaform dispatch merge id=2752890838f14bb981689d5ad0e40e4c --json` returned merged and pushed with no conflict. main and origin moved to 3189be9b. The ticket closed at 14:36:01Z.
