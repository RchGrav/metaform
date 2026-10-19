git push -q origin main 2>&1 | grep -v "gc\|prune\|^$\|Automatic\|and remove"; git log --oneline -1
Output: warning: The last gc run reported the following. Please correct the root cause
and remove .git/gc.log
Automatic cleanup will not be performed until the file is removed.
warning: There are too many unreachable loose objects; run 'git prune' to remove them.