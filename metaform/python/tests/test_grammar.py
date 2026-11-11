"""The grammar of a want's `why` and `how` (R-3.17, R-6.17; documentation set, module 6.4).

The first test checks the rule on texts. The others perform commands as an agent's harness does,
`python3 -m metaform call`, on a new home in a temporary folder.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from metaform.rules import grammar_fault

PACKAGE = Path(__file__).resolve().parents[1]
GAME = "code.engine.game"
ROUTER = "code.engine.router"
RULE = "why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values. Detail belongs in a knowledge layer."
WHY_PLACEHOLDER = "<base verb phrase, as: drain raw frames from the network interface card>"
HOW_PLACEHOLDER = "<verb phrase ending in -s, as: holds descriptor pointers across contiguous memory segments>"

PASSES = {
    "why": [
        "Receive player input and collision telemetry for frame simulation.",
        "drain raw frames from the network interface card",
        "String the tokens into one line",
        "ping the peer",
        "Verify the S256 challenge of OAuth2 over HTTP/2 as utf-8 on x86-64",
    ],
    "how": [
        "Dispatches subscribed runtime event streams.",
        "holds descriptor pointers across contiguous memory segments",
        "  Stores: frames on disk  ",
        "Verifies S256 challenges for OAuth2 clients.",
        "passes checking results on",
    ],
}
BREAKS = {
    "why": [
        "to drain raw frames",
        "To: drain raw frames",
        "draining raw frames",
        "Parsing, then storing",
        "The router needs parameters",
        "it needs parameters",
        "keep frames. Store them on disk",
        "keep frames; store them on disk",
        "keep frames!\nstore them",
        "score answers from 0 to 5",
        "wait 3.9 seconds",
        "retry 5",
        "list items 1-5",
    ],
    "how": [
        "holding descriptor pointers",
        "hold descriptor pointers",
        "The router stores parameters.",
        "this stores parameters",
        "its parameters are stored",
        "Stores parameters. Decodes them first.",
        "Returns yes/no confidences and 0 to 5 scores from the JEV model.",
        "...",
    ],
}

# A text, and the first fault the message names for it.
FAULTS = [
    ("why", "to keep 5 frames", "starts with 'to'"),
    ("why", "keeping the frames. Store them", "starts with an '-ing' verb"),
    ("why", "The router needs 5 parameters", "starts with a subject"),
    ("why", "keep frames; store 5 of them", "holds more than one fragment"),
    ("why", "retry 5", "holds a value"),
    ("how", "The router stores 5 items.", "starts with a subject"),
    ("how", "its parameters are stored", "starts with a subject"),
    ("how", "hold 5 pointers. Free them", "does not start with a verb ending in -s"),
    ("how", "holding descriptor pointers", "does not start with a verb ending in -s"),
    ("how", "Stores parameters. Decodes 5 first.", "holds more than one fragment"),
    ("how", "Returns 0 to 5 scores", "holds a value"),
]


class Grammar(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory(prefix="metaform-python-test-")
        self.home = Path(self.folder.name) / "home"
        self.project = Path(self.folder.name) / "project"
        self.home.mkdir()
        self.project.mkdir()

    def tearDown(self) -> None:
        self.folder.cleanup()

    def call(self, command: Any) -> Any:
        done = subprocess.run(
            [sys.executable, "-m", "metaform", "call", json.dumps(command), "--home", str(self.home), "--project", str(self.project)],
            capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(PACKAGE)),
        )
        return json.loads(done.stdout)

    def write(self, command: Any) -> None:
        self.assertEqual(self.call(command), {"status": "ok"}, command)

    def seed(self) -> None:
        self.write({"add": {GAME: {"technical_name": "game engine", "name": "Quake core", "role": "Definitive"}}})
        # The procedure's own example.
        self.write({"update": {GAME: {"wants": {ROUTER: {
            "why": "Receive player input and collision telemetry for frame simulation.",
            "how": "Dispatches subscribed runtime event streams.",
            "direction": "inbound",
        }}}}})

    def test_the_rule_on_texts(self) -> None:
        for field, texts in PASSES.items():
            for text in texts:
                self.assertIsNone(grammar_fault(field, text), (field, text))
        for field, texts in BREAKS.items():
            for text in texts:
                self.assertIsNotNone(grammar_fault(field, text), (field, text))

    def test_the_first_fault_of_a_text_in_the_fixed_order_of_checks(self) -> None:
        for field, text, fault in FAULTS:
            self.assertEqual(grammar_fault(field, text), fault, (field, text))
        self.assertIsNone(grammar_fault("why", "drain raw frames."))
        self.assertIsNone(grammar_fault("how", "Stores frames."))

    def test_a_refusal_names_the_parts_that_broke_the_rule_and_stores_nothing(self) -> None:
        self.seed()
        command = {"update": {GAME: {"wants": {ROUTER: {"how": "The router stores parameters."}}}}}
        answer = self.call(command)
        self.assertEqual(list(answer), ["update", "status", "code", "message", "tested_sentence", "remediation"])
        self.assertEqual(answer, {
            **command,
            "status": "error",
            "code": "GRAMMAR_CONSTRAINT_VIOLATION",
            "message": f"how starts with a subject. {RULE}",
            "tested_sentence": "code.engine.game (Quake core) requires code.engine.router in order to Receive player input and collision telemetry for frame simulation, which The router stores parameters.",
            "remediation": {"update": {GAME: {"wants": {ROUTER: {"how": HOW_PLACEHOLDER}}}}},
        })
        # Both parts break the rule. The first want that breaks it is reported, and the valid
        # want before it in the same command is not stored. The want is new, so the remediation
        # has the whole want: a want needs all of its fields.
        answer = self.call({"update": {GAME: {"wants": {
            "code.engine.store": {"why": "keep frames", "how": "holds frames on disk", "direction": "inbound"},
            "code.engine.zeta": {"how": "holding frames", "why": "to keep frames", "direction": "inbound"},
            "code.engine.alpha": {"why": "keep 5 frames", "how": "holds frames", "direction": "inbound"},
        }}}})
        self.assertEqual(answer["remediation"], {"update": {GAME: {"wants": {"code.engine.zeta": {"why": WHY_PLACEHOLDER, "how": HOW_PLACEHOLDER, "direction": "inbound"}}}}})
        self.assertEqual(list(answer["remediation"]["update"][GAME]["wants"]["code.engine.zeta"]), ["why", "how", "direction"])
        self.assertEqual(answer["tested_sentence"], "code.engine.game (Quake core) requires code.engine.zeta in order to to keep frames, which holding frames.")
        # The message names each part and its first fault, `why` first, then states the rule.
        self.assertEqual(answer["message"], f"why starts with 'to'; how does not start with a verb ending in -s. {RULE}")
        # For a `how`, the subject check comes before the `-s` check and the value check.
        both = self.call({"update": {GAME: {"wants": {ROUTER: {"why": "to drain frames", "how": "The router stores 5 items."}}}}})
        self.assertEqual(
            both["message"],
            "why starts with 'to'; how starts with a subject. why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values. Detail belongs in a knowledge layer.",
        )
        self.assertEqual(self.call({GAME: {"wants": {}}})[GAME]["wants"][ROUTER]["how"], "Dispatches subscribed runtime event streams.")
        self.assertEqual(self.call({"code.engine.store": {}})["code"], "NOT_FOUND")

    def test_a_part_the_command_does_not_write_is_not_checked(self) -> None:
        self.seed()
        self.write({"update": {GAME: {"wants": {ROUTER: {"how": "Stores decoded parameters."}}}}})
        self.write({"update": {GAME: {"wants": {ROUTER: {"direction": "outbound"}}}}})
        self.write({"update": {GAME: {"status": "built"}}})


if __name__ == "__main__":
    unittest.main()
