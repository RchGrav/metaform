# Hello World

A demonstration of every Metaform module feature, each working once.

## Purpose

hello greets names, keeps each greeting as an item of a layer in the project's store, and publishes an event for every greeting. It exists to show how a module behaves on the CLI and over MCP.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = True`, so it is off until `metaform enable hello`. `MODULE` declares eight verbs, one subscription and a status hook.

## Common base used

`metaform.module` for the declaration and `Context`, `metaform.settings` for its three settings, `metaform.data` for its layer, `metaform.nonce` for `noncedemo`.

## Verbs

- `greet <name> [--loud]`: returns the greeting and publishes `hello.greeted`. Tool `hello_greet`.
- `wait <seconds>`: waits, then returns `waited <n> s`. Tool `hello_wait`.
- `history`: returns the names greeted so far. Tool `hello_history`.
- `forget [--confirm]`: deletes the greeting layer. A caution verb. Tool `hello_forget`, with `confirm`.
- `beep`: rings the terminal bell, on Windows only.
- `todo <task>`: writes a `tbd` work record on the module's own element, `code.module.hello`, with the task; returns the record id. Tool `hello_todo`.
- `done <id> <resolution>`: marks that record done, its resolution kept beside it. Tool `hello_done`.
- `noncedemo`: walks an agent through a nonce, BASE-050. Run directly it requests a nonce whose function is `noncedemo` itself and prints `Please run metaform <nonce>`. Run through that nonce, `nonce.reached()` holds it, and `noncedemo` does the step the nonce's value in the chassis holds, or the step written after the nonce, `next` or `complete`. `next` updates the value, so the nonce run alone gives the same message again. `complete` closes the nonce and requests a new one, the nonce an agent would pass to the main agent. That one, run, closes itself and ends the demo; run again, it prints `Error: Invalid or Unknown Nonce`. Tool `hello_noncedemo`.

## Settings

`--greeting`, default `hello`. `--loud`, default off, also greet's switch. `--favorite`, a select whose choices are the names greeted in this folder's project.

## Events

Publishes `hello.greeted` with `{"name": ...}`. Subscribes to it to record the name, and finishes its layer on the first greeting so it is seen in context. It has no code to announce the write: the chassis fires `map.changed` when the greet command ends, so an open web GUI shows the greeting at once, VIEW-018 and QUAL-016.

## Sync and async

`wait` is a coroutine. Every other verb and the subscriber are plain functions.

## Work records

A module keeps the condition of an object as a work record, apart from the map, MAP-046 and STORE-042: `store.add_work(Node('element', address), 'tbd', task=...)`, `store.edit_work(id, {...})` and `store.finish_work(id, resolution)`. `todo` and `done` show it; the status line counts the open ones, `Hello: 1 greeted, 1 to do`; the web GUI draws the element ghostly while a tbd record is open and solid once it is done. Every element and join read, a subtype join's included, carries `open_work`, the conditions of its open records.

## Layers

`hello.greetings`, a knowledge layer, mutable and hideable, with provenance module `hello`, workflow `greet`, role `module`. Its items attach to the element `code.module.hello` the layer creates for them.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks. Unloading leaves the layer in the store.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows. `beep` runs on Windows only.

## Resources owned

None beyond its layer.

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
