#31 is closed out with no code change: the error no longer happens on current code. The fix was already on main in commit `837f226c`, and a before/after test run confirms it. The ticket is now in "fix landed, watching" and closes once the fix is proven.

**Cause.** Commit `bca6cd17` let a person's Start launch a runner even when routing hadn't chosen a specialist.