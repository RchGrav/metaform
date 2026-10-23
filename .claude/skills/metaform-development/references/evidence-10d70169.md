Delivery is staged and waiting on the runner. Commit `8642ab28` is on the ticket branch (`metaform/10140adfbe34`) but not on main yet. When this turn ends, the dispatch runner merges it into main, pushes and restarts the changed code. If a step fails it gives me the missing step back, and the ticket stays open until main has the commit. — modular-engine

**Result on #8b:**
- **Engine ships with Metaform.** The Roundtable 2 engine is copied into the module as `roundtables/roundtable/`