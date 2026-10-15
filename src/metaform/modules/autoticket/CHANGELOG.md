# Changelog

Each change to the module, newest first.

## Unreleased

- The module, from the design in `artifacts/specs-draft/autoticket.md`, ticket 0fc3c02b: watched logs, local or over ssh, read as they grow and never kept; entries joined from their lines; errors grouped by onhold's FNV-1a and Dice method at 0.45; one example per group with secrets masked; a lease per log so two processes never count one line twice; the ranked list as a signal every `autoticket_interval_minutes`, the first setting the baseline, and a group first seen after it reported at once; `promote` to make a group a ticket. Tables at version 1: `groups`, `logs`, `rules`, `state`. The intake step and the connect notice are read from prompts.xml once their wording is approved.
