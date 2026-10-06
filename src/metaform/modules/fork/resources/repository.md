# My Metaform modules

Each module lives in a folder at this repository's root. The repository extends a released Metaform chassis. Its pyproject.toml pins that release. It holds no chassis source.

Install uv, then run `uv sync --group dev`. Enable the harness with `uv run metaform enable fork`, `uv run metaform enable map`, `uv run metaform enable dispatch`, and `uv run metaform enable mcp`. Register it with `uv run metaform add project my-modules .`.

Implement your feature in the module copied from the template. Write behavior tests in its tests folder. The inherited template's repository tests concern Metaform's shipped hello/template pair, so those tests are not copied. An empty module has no behavior tests and is left out of a wheel.

Publish this repository to your own GitHub repository. The generated workflow runs type checking, lint and tests on Linux, macOS and Windows with Python 3.11 and 3.14. Each module's results are independent, so a broken module cannot hide the others. Pull requests run these checks without agent secrets. A push or manual run then dispatches an agent review for each module and builds the wheel with modules that pass.

Set the repository Actions secret `@SECRET@` to the API key for `@AGENT@`. The agent adapter reads it from its environment. Configure its ACP command through `--dispatch-@AGENT@` when using a different adapter. The generated CI grants this isolated run's dispatched agent tool permissions through `dispatch_prompts=approve-all` so the unattended review can complete. Credentials never belong in a ticket. CI fails naming the secret when it is absent.

Download the metaform-wheel artifact. Run it with `python path/to/metaform.whl` or update your installed copy with `python path/to/metaform.whl install`. The wheel includes the released chassis and reviewed modules.

After updating the pinned release and running `uv sync --group dev`, run `uv run metaform fork upkeep --fork-agent @AGENT@`. Authenticate `gh` for this repository first. The dispatched agent applies newer released template changelog entries, updates the module's Template version, validates it and opens a pull request. Repeating upkeep reuses an open ticket for the same update. Unreleased changelog entries are not versioned updates. An automatic installation-stage trigger is pending in Metaform.
