# packet

Writes work as a packet, a plain ZIP with a tamper seal, and checks or opens one.

## Purpose

A packet carries work from one home to another. Its work is visible to anyone who opens the ZIP. Its provenance and data are sealed inside it, so any change made after it was written shows. The seal keeps no one out: every copy of Metaform opens every packet, PROJ-027. It ships disabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ('cryptography>=42',)`, `SHIPS_DISABLED = True`. `MODULE` declares three verbs, each for the command line only, so the module adds no tool.

## Common base used

`metaform.module` for the declaration, `Context`, `Noun`, `Verb` and `Stop`; `metaform.settings` for the `packet_evidence` setting.

## Verbs

`seal work=<folder> data=<folder> file=<zip> [origin=<path>] [parent=<zip>]` writes a packet. The work is the folder's files, leaving out git's files and what is built from the source. `origin` names the work file the packet is grounded in, `origin.zip` when the work has one. `parent` is the packet this one was made from: the new packet takes the next place in its lineage and carries the hash of its parent's manifest.

`check <zip>` says whether a packet is as it was sealed. It names the first thing that does not match.

`open <zip> into=<folder>` checks a packet, then writes its work to `<folder>/work` and its data to `<folder>/data`.

A packet that was changed stops each verb with `This packet was tampered with`. A packet sealed with evidence this tool does not hold stops it with `sealed with other evidence`, which is not tampering. A `.metaform/` folder holding anything but its two files is refused.

## Settings

`--packet-evidence <file>`: a file of 32 bytes or more to seal and open with, for someone who needs secrecy. Empty means the evidence every copy of Metaform holds.

## Events

None.

## Sync and async

Each verb is a plain function.

## Layers

None.

## Lifecycle and cleanup

None. It holds nothing between calls.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

None. It reads the folders and packets it is given and writes the file or folder it is told to.

## Installed and direct wheel

`cryptography` is compiled, so it is installed and not carried in the wheel. A directly run wheel needs it installed.

## Demonstration

```
metaform enable packet
metaform packet seal work=out data=state file=app.zip
metaform packet check app.zip
```
