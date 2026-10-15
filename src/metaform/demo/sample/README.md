# Pocket Ledger

A small command line ledger for a household: record what you spend, and see each month's total by category.

```sh
python -m ledger add 2026-10-03 groceries 19.99
python -m ledger add 2026-10-05 transport 8.20
python -m ledger month 2026-10
```

Entries are kept in `ledger.json` beside where you run it. Amounts are stored as whole cents, so totals never drift.

This is the sample project of `metaform demo`; its map ships with Metaform, finished.
