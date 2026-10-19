# API cost and waste evidence

The [report](../../docs/reviews/2026-10-19-token-waste-analysis.md) explains the attribution and pricing assumptions.
`2026-10-19-summary.json` contains aggregate packet usage and the measured waste subtotal. Cost concentration
figures include useful work and are not added to the confirmed waste subtotal. No private message bodies are included.

Reproduce the payload subtotal against a **copy** of the imported home, with its dispatch and agents modules
available. The script uses the public Store API, reads records without starting agents, and makes no model calls.
Normal Store initialization may upgrade the copied home's schema; preserve the original packet separately.

```bash
METAFORM_HOME=/path/to/copied-home .venv/bin/python evidence/token-waste/reproduce.py \
  --project metaform --output /tmp/metaform-waste.json
```

The action-manifest count comes from retained `orchestration:actions` receipts. The peer-wrapper count subtracts
the exact `note` binding from each retained `dispatch:peer_note` ACP prompt. These are different components.
The tool-result candidate scan compares identical completed text, tool and arguments within one Claude session,
excluding entire sessions with recorded compaction notices. Candidates are reported separately. Missing historical
receipts, internal provider requests and incomplete compaction telemetry are not reconstructed or assumed free.

Pricing scenarios use declared rates and character/token sensitivities, not a provider tokenizer or invoice export.
They do not establish the complete historical dollar amount of waste. The report specifies the invocation ledger
and controlled comparisons needed for that measurement.
