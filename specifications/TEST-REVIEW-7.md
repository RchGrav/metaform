# Test review 7

Scope: the two browser tests step 25 rewrote in `src/metaform/modules/web/tests/test_web.py`, by a test-review agent on Sonnet, 2026-09-26, judged only against VIEW-003, VIEW-005, VIEW-008, VIEW-010, VIEW-012 and MAP-002; no page file was read. `test_the_page_draws_each_join_as_its_path_and_both_views_select_together` and `test_every_element_and_join_of_every_page_is_drawn`.

## Findings and what was done

1. Subtype links were checked only by their targets, so a subtype hung from the receiver instead of its join's purpose vertex passed. Each join's links are now compared whole, the subtype links included with their source.
2. Namespace edges were checked only by count, so edges drawn to the wrong parent passed. They are now compared as pairs against each element's nearest parent element from `/api/graph`.
3. No fixture held two elements that each receive from the other, the case VIEW-005's How it shows names. The multi-page store now adds one, and the same path check runs over all 601 of its joins.

The multi-page test was found sound. The checks now live in one helper, `drawn_as_paths`, used by both tests. Each of three breaks in the page fails both tests: a subtype hung from the receiver, every namespace edge drawn from one element, and one purpose vertex shared by the two joins of a pair.
