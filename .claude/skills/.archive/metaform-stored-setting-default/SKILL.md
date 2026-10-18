---
name: metaform-stored-setting-default
description: Use when a page default is stored in localStorage.
category: development
---

# A changed default must rename the stored key

A value the browser already stored outranks a changed code default, so editing the default alone changes nothing for anyone who pressed the key before. When the default changes, give the storage key a new name so old stored values are never read, and say in the ticket that a reload is enough.

- Find every reader and writer of the key in `src/metaform/modules/web/page/` before editing. Grep for the key name, not the setting's label.
- Read the old default with `git show HEAD:FILE`, not the working tree, before saying what it was. The working tree may already hold the change.
- Check the start state for each case by evaluating the shipped expression: no stored key, each stored value, and storage blocked. Confirm in a fresh browser profile that the first note reads the new default.
- Leave the old key unread, so no stored choice from before the change can override the new default.
