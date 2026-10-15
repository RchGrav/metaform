"""Run the ledger's command line: python -m ledger."""
import sys

from .cli import main

sys.exit(main(sys.argv[1:]))
