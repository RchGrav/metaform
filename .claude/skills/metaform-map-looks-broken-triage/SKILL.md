---
name: metaform-map-looks-broken-triage
description: Use when the map or page looks broken, blank or wrong.
category: development
---

# A "the map is broken" report is a reproduction task, not an explanation

Do not say what broke, or that nothing is broken, until you have reproduced the person's view and compared it with HEAD.

1. **Settle the open tab first.** A page loaded before a fix or a removal keeps what it drew. Ask the person to reload, and say so in your reply.
2. **List what changed.** Read the sibling agents' ticket logs (`map_work`), `git diff` on `src/metaform/modules/web/page`, and any page file newer than the running server (see restart-processes-after-code-fix).
3. **Reproduce on a scratch copy** of the live base at the person's settings: the same depth, layers and lens. Run it once on the working tree and once on HEAD, headless, on the real GPU. [scripts/depth-probe.py](scripts/depth-probe.py) steps the keys and prints node and edge counts plus page errors. Run it as `depth-probe.py OUT_DIR URL TAG KEY...`.
4. **Read the result.** A difference between tree and HEAD is the regression. Identical counts on both mean the code is not the cause; say that with the numbers.
5. **Report counts, not impressions.** Give node and edge counts per setting, the page errors, and what you did not check. Remove any probe element you added and read back that it is gone.

Page-error floods (`scale(Infinity)`) are code defects: fix them at the source, never by hiding the symptom.
