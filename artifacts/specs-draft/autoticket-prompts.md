# autoticket: the intake step and the connect notice (drafts for Rich's approval, 2026-10-15)

Status: drafts, not in `src/metaform/modules/autoticket/resources/prompts.xml`. The module's status hook already reads both prompts by name and sends nothing while they are absent, so approving a text means pasting its element into that file, and nothing else changes. Ticket 0fc3c02b.

## When each is sent

Both are sent only while the module is on and the project has no watched log and has not recorded that it has none (`autoticket no-logs`). Adding a log, or recording that there is none, stops both.

- `intake_step`: to an intake agent, one started by dispatch with the role `intake`, at connect.
- `connect_notice`: to the person's own agent, one with no role, at connect. Agents dispatched to tickets do not receive it, since setting up the project's logs is not their ticket's work.

Each is one instruction in the connect message, so it counts against the 2,048 characters Claude Code keeps of it; each draft is under 450.

## intake_step

```xml
<!-- Sent at connect to an intake agent while autoticket is on and no log is configured. It asks the intake to find
     out which logs to watch. Remove the element, or leave it empty, to send nothing. -->
<intake_step>autoticket is on and watches no log yet. As part of this intake, ask the person which of the project's logs to watch: a local file, or a file on a host reached by ssh. Add each with autoticket add <path> or autoticket add ssh://<host>/<absolute path>. If the project is not built yet and only its intent exists, there are no logs to watch: record that with autoticket no-logs.</intake_step>
```

## connect_notice

```xml
<!-- Sent at connect to the person's own agent while autoticket is on and no log is configured. It asks the agent to
     point autoticket at the project's logs. Remove the element, or leave it empty, to send nothing. -->
<connect_notice>autoticket is on but watches no log. Configure it against this project's logs: autoticket add <path> for a local file, or autoticket add ssh://<host>/<absolute path> for a file on a host, then autoticket watch. If the project has no logs to capture yet, ignore this message, or record it with autoticket no-logs so it is not sent again.</connect_notice>
```

## Questions for Rich

1. Should the connect notice reach every agent, as the draft design says, or only the person's own agent, as built? A dispatched worker that follows it would leave its ticket to configure logs.
2. Should `no-logs` silence the connect notice, or should the notice keep coming until a log is added?
