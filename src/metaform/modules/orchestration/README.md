# Historical orchestration records

The previous role organization is retired. This module exposes only `history`, a read of existing assignment records.
It registers no roles, executor, commissions, authority policy, subscriptions or automatic agent launches.
GC and triage cannot be restored through its records.

The original table layout remains in `records.py` so existing lineage and results remain readable.
Historical prompt texts remain source material for the user-directed, one-at-a-time definition of tasks and skills.
They are not registered as executable duties. Assigned execution now belongs to the `tasks` module.
