"""Tests for configuration label normalization."""

import unittest

from label_tools import normalize_label


class NormalizeLabelTests(unittest.TestCase):
    def test_trims_and_collapses_spaces(self):
        self.assertEqual(normalize_label("  Core Switch  "), "core_switch")

    def test_collapses_actual_tabs(self):
        self.assertEqual(normalize_label("WAN\t\tUplink"), "wan_uplink")

    def test_preserves_hyphen(self):
        self.assertEqual(normalize_label("Core-Switch"), "core-switch")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_label("")

    def test_rejects_spaces_only(self):
        with self.assertRaises(ValueError):
            normalize_label("   ")

    def test_mixed_whitespace(self):
        self.assertEqual(
            normalize_label("\t Core \r\n\t Switch\v\f Uplink \n"),
            "core_switch_uplink",
        )

    def test_unicode_whitespace(self):
        self.assertEqual(normalize_label("\u2003Core\u00a0\u2003Switch\u2003"), "core_switch")

    def test_rejects_other_whitespace_only(self):
        for text in ("\t\r\n\v\f", "\u00a0\u2003"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                normalize_label(text)

    def test_preserves_punctuation_and_existing_underscores(self):
        self.assertEqual(normalize_label(" A_B.C:/D-1!  (E) "), "a_b.c:/d-1!_(e)")

    def test_punctuation_only_is_valid(self):
        self.assertEqual(normalize_label("  -_.!  "), "-_.!")

    def test_single_character_and_normalized_label(self):
        self.assertEqual(normalize_label(" X "), "x")
        self.assertEqual(normalize_label("core_switch"), "core_switch")


if __name__ == "__main__":
    unittest.main()
