# DeifiedArrow — evidence for two qualifications

These notes support `resolution.md`; they do not modify source behavior.

1. **Duplicate names fail differently depending on who rates.** With indices 0 and 1 both named X, index 0's prompt filters out X (`turn.rs:438`), but a manually supplied X card matches only index 1 because the parser excludes index 0 (`463`). A third rater matches both and is rejected. Thus GF4 identifies a real name-key defect but overstates impossibility between exactly two same-named peers. Stable seat IDs fix both prompt omission and third-party ambiguity.

2. **Profile reading at finalization can double count.** Let the historical profile have 100 points. An early current-table card adds 50 in memory and publishes an event (`turn.rs:471–484`). If the web consumer saves it (`app.rs:500–508`) before the last rater completes, finalization reads 150 as its alleged prior score and adds the same 50 again (`turn.rs:521–532`), displaying 200 rather than 150. This is an ordering-dependent possibility from the visible read/write paths, not a measured execution trace. Capture history before current-table cards, or exclude the table's entries, to define a stable cumulative total.

Engine lifecycle and original-owner attribution assertions remain limited by missing files in the supplied snapshot.
