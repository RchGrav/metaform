# Hello World

A demonstration of every Metaform module feature, each working once.

## Purpose

hello greets names, keeps each greeting as an item of a layer in the project's store, and publishes an event for every greeting. It exists to show how a module behaves on the CLI and over MCP.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = True`, so it is off until `metaform enable hello`. `MODULE` declares its verbs, one subscription, `start` and `stop` hooks, a status hook, and `default='history'`, so `metaform hello` with no verb runs `history`; `metaform hello --help` still prints the syntax.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop`, and the report functions `save_report`, `feedback`, `list_reports` and `read_report`. `metaform.settings` for its five settings, one of each kind. `metaform.data` for its layer and work records. `metaform.nonce` for `noncedemo`.

## Verbs

- `greet <name> [--loud]`: returns the greeting and publishes `hello.greeted`. Tool `hello_greet`.
- `wait <seconds>`: waits, then returns `waited <n> s`. Tool `hello_wait`.
- `history`: returns the names greeted so far. The default verb. Tool `hello_history`.
- `forget [--confirm]`: deletes the greeting layer. A caution verb. Tool `hello_forget`, with `confirm`.
- `beep`: rings the terminal bell, on Windows only.
- `todo <task>`: writes a `missing` work record on the module's own element, `code.module.hello`, with the task; returns the record id. Tool `hello_todo`.
- `done <id> <resolution>`: marks that record done, its resolution kept beside it. Tool `hello_done`.
- `noncedemo`: walks an agent through a nonce, BASE-050. Run directly it requests a nonce whose function is `noncedemo` itself and prints `Please run metaform <nonce>`. Run through that nonce, `nonce.reached()` holds it, and `noncedemo` does the step the nonce's value in the chassis holds, or the step written after the nonce, `next` or `complete`. `next` updates the value, so the nonce run alone gives the same message again. `complete` closes the nonce and requests a new one, the nonce an agent would pass to the main agent. That one, run, closes itself and ends the demo; run again, it prints `Error: Invalid or Unknown Nonce`. Tool `hello_noncedemo`.
- `count`: says `hello has greeted <n> names.` with `ctx.say` and returns `{"greeted": n}`. With `--json` the sentence goes to standard error and only the data to standard output; over MCP it is a line of the result. Tool `hello_count`.
- `welcome <name>`: an async verb that publishes `hello.greeted` with `await ctx.publish_async(...)`; `ctx.publish` inside a running loop is refused, BASE-009. Returns `welcome, <name>`. Tool `hello_welcome`.
- `later <name> <seconds>`: starts a task with `ctx.spawn` that greets the name after the seconds, and returns at once. The task belongs to hello: it runs on after the verb returns for as long as the process runs, as the MCP server does, and the chassis cancels it when the process ends or hello unloads, BASE-018. From the command line the process ends at once, so the name is not greeted. Tool `hello_later`.
- `greet-favorite`: greets the `--favorite` name. With none set it raises `Stop('No favorite is set.', 'metaform set --favorite <name>')`, which the CLI prints as `Error:` and `Next:` lines with exit 2, CLI-009. Tool `hello_greet-favorite`.
- `uptime`: returns how long ago `start` ran in this process. Tool `hello_uptime`.
- `repeat <name> [--times <n>]`: returns the greeting `--times` times. Tool `hello_repeat`.
- `greet-friends [--friends <names>]`: greets each name in `--friends` and publishes `hello.greeted` for each. Tool `hello_greet-friends`.
- `report <text>`: saves a report with `save_report`, run id and layer the id of `hello.greetings`, and returns the file name; the layer's provenance then carries it as a `report` ref, BASE-045. Tool `hello_report`.
- `feedback <text>`: saves feedback on the Metaform process with `feedback` and returns the project, the run id and the file names. Tool `hello_feedback`.
- `reports`: returns the file names `list_reports` gives for this project, one a line. Tool `hello_reports`.
- `read-report <name>`: returns one listed file's text exactly with `read_report`; a name that is not listed stops with `Next: metaform list reports`. Tool `hello_read-report`.

## Settings

`--greeting`, default `hello`. `--loud`, default off, also greet's switch. `--favorite`, a select whose choices are the names greeted in this folder's project. `--times`, a number from 1 to 10, default 1, repeat's switch. `--friends`, a list, default empty, written `--friends ada,bob`, greet-friends' switch.

## Events

Publishes `hello.greeted` with `{"name": ...}`, from `greet` with `ctx.publish` and from `welcome` and `later` with `ctx.publish_async`. Subscribes to it to record the name, and finishes its layer on the first greeting so it is seen in context. It has no code to announce the write: the chassis fires `map.changed` when the greet command ends, so an open web GUI shows the greeting at once, VIEW-018 and QUAL-016.

## Sync and async

`wait`, `welcome` and `later` are coroutines, and so is the task `later` spawns. Every other verb, the subscriber and the hooks are plain functions.

## Work records

A module keeps the condition of an object as a work record, apart from the map, MAP-046 and STORE-042: `store.add_work(Node('element', address), 'missing', task=...)`, `store.edit_work(id, {...})` and `store.finish_work(id, resolution)`. `todo` and `done` show it; the status line counts the open ones, `Hello: 1 greeted, 1 to do`; the web GUI draws the element ghostly while a missing record is open and solid once it is done. Every element and join read, a subtype join's included, carries `open_work`, the conditions of its open records.

## Layers

`hello.greetings`, a knowledge layer, mutable and hideable, with provenance module `hello`, workflow `greet`, role `module`. Its items attach to the element `code.module.hello` the layer creates for them.

## Lifecycle and cleanup

`start` runs once when hello loads, before its first verb, subscriber or tool call, and records when it ran; `uptime` reads that. `stop` runs once when hello unloads or the process ends, after the chassis has cancelled the tasks `later` spawned, and clears it. Unloading leaves the layer and the report files in place.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows. `beep` runs on Windows only.

## Resources owned

Its layer, and the report and feedback files `report` and `feedback` write under the home's `projects/<id>/reports/`, never in the project folder.

## Installed and direct wheel

The same in both: its data lives in the project store of the Metaform home the run uses.

## Demonstration

```
metaform enable hello
metaform add project demo .
metaform hello greet world --loud
metaform hello history
metaform hello todo "greet in every language"
metaform hello done <id> "greets in Latin now"
metaform hello forget --confirm
metaform hello noncedemo
```

The nonce demo, with the nonces the service issued in one run:

```
$ metaform hello noncedemo
Please run metaform 6984268
$ metaform 6984268
Hello World! Now type the command again, but this time with metaform 6984268 next
$ metaform 6984268 next
This is a next message for the agent. Try running metaform 6984268. You will notice you get this same message, because metaform 6984268 is updating the db in the chassis for this nonce and using it to control the module. After you did the step, run metaform 6984268 complete
$ metaform 6984268
This is a next message for the agent. Try running metaform 6984268. You will notice you get this same message, because metaform 6984268 is updating the db in the chassis for this nonce and using it to control the module. After you did the step, run metaform 6984268 complete
$ metaform 6984268 complete
Congratulations, now you know how nonces work. The dev can recall the nonce, update the existing nonce, and generate new ones. So imagine it was time to pass to the main agent. The plugin could say: tell the main agent to run metaform 9772227. But don't really, just do it to see what will happen.
$ metaform 9772227
Congrats, the nonce demo is over. We already cleaned up the nonce you just used. Try it again to see.
$ metaform 9772227
Error: Invalid or Unknown Nonce
```

Each public import a module can use, and the command that shows it:

| Import | Command |
|---|---|
| `ctx.say` | `metaform hello count`, and `metaform hello count --json` to see the sentence leave standard output |
| `ctx.publish_async` | `metaform hello welcome ada` |
| `ctx.spawn` | `metaform hello later ada 5`; over MCP, `later` with name `ada` and seconds `5`, then `history` after five seconds |
| `Stop` from a verb | `metaform hello greet-favorite` with no favorite set |
| `start` and `stop` | `metaform hello uptime` |
| `Module.default` | `metaform hello` |
| `settings.number` | `metaform hello repeat ada --times 3` |
| `settings.items` | `metaform set --friends ada,bob`, then `metaform hello greet-friends` |
| `save_report` | `metaform hello report "Greets in English only."` |
| `feedback` | `metaform hello feedback "The greet help was clear."` |
| `list_reports` | `metaform hello reports` |
| `read_report` | `metaform hello read-report <name>`, a name `reports` lists |
