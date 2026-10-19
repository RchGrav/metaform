# Verify a setup script in a throwaway clone, inside the base image

Use this file when testing a devcontainer or setup script against a lockfile. Run the setup script from a fresh clone, in a directory you will delete, and check its result in the same base image the devcontainer uses. Never run it in the user's working tree, so their `.venv` and `.git/hooks` stay untouched. Parity script: `scripts/check-lock-parity.sh`.

## Before the container run
- Check the project memory and CLAUDE.md for a stated cost or verification preference. If the user has not asked for a container run in this session, ask first; do not start one on your own initiative.
- Clone to a new temp directory, copy in the uncommitted script, then run it there.
- Run `chmod -R a+rwX "$D"` on the temp directory before the container run. The container writes `.venv` and `.git/hooks` as its own user, so a plain `rm` would fail later.

## The run
- Run inside the base image with `docker run --rm -v "$D/flask":/workspace -w /workspace -u USER IMAGE bash -lc '...'`, using the user the devcontainer runs as. Inside the container set `git config --global --add safe.directory /workspace`.
- Do not add PATH entries: run the script with the image's own environment, because a hand-set PATH can hide a bootstrap failure the user would hit in VS Code. Check `command -v <tool>` for each bootstrapped tool before trusting the install. For the python image, `PIPX_BIN_DIR=/usr/local/py-utils/bin` already puts pipx-installed tools on PATH.
- Run the script a second time in the same container and require exit 0 again. A setup script that works only on a fresh container is not a passing setup.

## What to check
- Exit code, the tools the script should install, editable installs, hook files such as `.git/hooks/pre-commit`, and one targeted test.
- When the project has a lockfile (uv.lock, poetry.lock, requirements pins), check version parity. Run `uv sync --locked --check`, then mount this skill folder read-only and run `bash /skill/scripts/check-lock-parity.sh /workspace PKG...`. It exits 1 on any drift. An exit-0 install that resolves the latest versions is not a passing setup. Read the log tail for `[INFO]` and `ERROR` lines.

## Clean up
- Delete the clone and the log with plain `rm -rf` after the chmod. Do not use sudo. If removal still fails, remove it with a throwaway container that mounts the parent directory. Confirm with `ls -d "$D"`.

## Report
- State the exit code and what was checked. Say the change is uncommitted if it is.
- If the user declines the container run, do not re-issue it or split it into a new command. Report the run as not performed and list which checks are unverified.
