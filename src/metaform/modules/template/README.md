# template

The empty start of every Metaform module. Copy this folder to begin a module; every heading below is one a module's README answers.

## Purpose

What the module is for, in two to four sentences.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS`, `DEPENDENCIES`, `SHIPS_DISABLED` and `MODULE`, with what each is set to and why.

## Common base used

Which of `metaform.module`, `metaform.settings`, `metaform.data` and `metaform.events` the module uses, and for what.

## Verbs

Each verb, what it returns, and its CLI form `metaform <id> <verb>` and tool form `<id>_<verb>`.

## Settings

Each setting the module declares, its default, and which verbs read it as a switch.

## Events

The topics the module publishes and those it subscribes to.

## Sync and async

Which verbs and subscribers are coroutines.

## Layers

The layers the module writes, their mutable and hideable declaration, and their provenance.

## Lifecycle and cleanup

What `start` and `stop` do, the tasks the module spawns, and what unload leaves behind.

## Modules relied on

Other modules this one needs, reached through their verbs and events, never by import.

## Systems supported

The systems in `SUPPORTED_OS`, and any verb that narrows them.

## Resources owned

Files, processes or connections the module owns, and when it releases them.

## Installed and direct wheel

How the module behaves in an installed Metaform and in a directly run wheel.

## Demonstration

A short command sequence that shows the module working.
