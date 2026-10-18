# Checking process start times against a fix

```bash
ps -eo pid,lstart,args | grep -E 'metaform (mcp serve|dispatch run)|metaform.modules.web.server' | grep -v grep
stat -c '%y' src/metaform/data/refs.py
```

A process whose `lstart` is earlier than the file's mtime still holds the code from before the change. Restart it, or report it as old.
