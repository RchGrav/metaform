# Probe a Claude Code sandbox write list

Run this before a runner relies on a new allowWrite or denyWrite list. It is a live check: a unit test of the settings file does not show what the sandbox enforces.

1. Make a scratch project folder with one file that has a ref on the map, one file that has none, a folder with no linked file in it, and a `.venv` folder.
2. Build the settings the runner would send: allowWrite holds only the home folder, the temp folder, `/tmp` and `/var/tmp`. denyWrite holds the unlinked file, the folder with no linked file, and any ignore-listed path. Do not put `/` in allowWrite.
3. Start `claude -p` with bypassPermissions and those settings, in the scratch folder. Ask it to append one line to each path with a shell command, and to Edit the unlinked file.
4. Expected: writes to the unlinked file, the unlinked folder and the ignore-listed path fail, with `Read-only file system` or `Device or resource busy`. Writes to the linked file and to `.venv` succeed. A command that fails on every path with `bwrap: Can't mkdir` means the allow list is wrong, not the deny list.
5. Run the same probe on the Claude Code build the adapter bundles, not only the global `claude` on PATH. Results differ between builds.
6. Record each path, its command and its verbatim result in the ticket.

Known limits, each to be stated and not worked around: a denied existing file cannot be removed or moved, and a new file under an unknown name in an allowed folder stays writable.
