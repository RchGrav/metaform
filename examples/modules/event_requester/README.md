# Event requester: derive a cooperating module from the template

Usage guidance is embedded in this module's Python `Plugin.help` contribution,
alongside its settings and commands. Contextual CLI help displays that guidance;
derived modules provide their own text with `replace(TEMPLATE, help=...)`.

This is the first of two cooperating event modules. It stores a prompt, publishes
`harness.request` with the record's revision reference, and receives the eventual
`harness.response`. The second module, [harness_runner](../../../modules/harness_runner/README.md),
queues the agent job and returns immediately. Both use the chassis's event bus.

The [standalone showcase](../showcase/README.md) is their reusable hello-world
template. The derivation is explicit:

```python
from dataclasses import replace
from .template import PLUGIN as TEMPLATE
from metaform import cli, data, event

PLUGIN = replace(
    TEMPLATE,
    id='event_requester',
    operations={'request': request},
    commands=(request_command,),
    subscriptions=(Subscription('harness.response', response),),
    command_visibility={},
    operation_visibility={},
    # Keep only the lifecycle settings used by this module.
)
```

Each event package owns a small `template.py` copied from the showcase lifecycle
scaffold: sync start, async stop, lifecycle settings, and an optional event
observer. Its `plugin.py` specializes that local template with feature
contributions. Both packages use the chassis event service. Each can be copied,
installed, or removed independently; the showcase package is optional.

## Package responsibilities

| File | Owns |
| --- | --- |
| `__init__.py` | Exposes `PLUGIN`. |
| `plugin.py` | Composes the local template and contributions. |
| `operations.py` | Stores and publishes a request. |
| `commands.py` | Adapts `request-work` to the registered operation. |
| `events.py` | Receives the eventual response. |
| `dao.py` | Resolves exact response joins and stores the local receipt through `metaform.data`. |
| `settings.py`, `help.py` | Declarations consumed by the chassis menus. |
| `template.py` | Owns the copied lifecycle scaffold. |

This follows the [module structure guide](../../../specifications/module-structure-refined.md).
The event payload carries a `JoinRef`, so the receiver consumes the exact
revision published by the sender. The receipt retains that object reference in
`response_ref`. Storage placement, transactions and producing-operation links
belong to the chassis.

## Run the two-module exchange

Activate the chassis environment and set `METAFORM_DEMO_REPO` to the repository
path. Load just these two modules; no extra plugin import path is needed:

```bash
mf() { metaform --project demo "$@"; }
mf modules load "$METAFORM_DEMO_REPO/examples/modules/event_requester"
mf modules load "$METAFORM_DEMO_REPO/modules/harness_runner"
mf enter event_requester
mf request-work --prompt 'Explain the request exactly as delivered.'
mf events
mf records data.event_requester.response --provenance
mf exit
mf jobs
mf jobs show JOB_ID
```

The request command's delivery result contains the queued harness job id. Inspect
it from the base menu because jobs are scoped to the selected module/assignment.
The response record appears when the harness finishes, fails, or is cancelled.
It carries `status`, `request_ref`, `response_ref`, and any operational error;
the referenced harness record retains stdout, stderr, and process exit status.
Its producer retains the
project, nonce and causal parent; its content references the exact harness record
revision and event id. The fixture default makes this runnable without credentials.

Select an installed provider in the responder's menu:

```bash
mf enter harness_runner
mf harness-config --provider codex
mf exit
mf enter event_requester
mf request-work --prompt 'Describe the project.'
mf exit
```

Use `--provider claude` for Claude, or `--provider fixture` to restore the local
protocol demonstration. The requester is independent of the provider choice.

Unload either event module independently with `modules unload MODULE_ID`. Stored
requests, responses, jobs and provenance remain inspectable. The standalone
showcase remains usable throughout. When the responder is absent, a request still
produces an event with no responder delivery; it does not fabricate a response.

## Package installation

Build this package and `harness_runner` independently, then install their wheels
into the chassis environment. Each wheel includes its local lifecycle scaffold
and depends only on the chassis and Click. Source packages can also be copied
directly into the data root's `modules` folder.

```bash
python -m build --wheel --no-isolation examples/modules/event_requester
```

`modules load` accepts the package directory, either source or installed. Installing
a package makes it importable; loading it registers its live chassis contributions.
