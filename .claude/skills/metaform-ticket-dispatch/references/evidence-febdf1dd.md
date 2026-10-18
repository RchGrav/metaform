src/metaform/modules/dispatch/merge.py:109:    git(folder, 'add', '-A')

assistant: Found the bug: `checkpoint()` and the related `finished()`/`removed()` only check for a `.git` presence, so when resumed sessions pass the main project folder instead of a worktree, it commits (or deletes) the whole shared tree under the ticket's name.

assistant: 4. **Completions no longer commit or delete your checkout.** A resumed session was handing your main folder to the "finish worktree" step, which `git add -A`'d everyone's work into one commit, and for a cancelled ticket it would have tried to remove the folder.