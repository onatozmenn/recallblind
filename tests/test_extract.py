"""Identifier extraction tests.

The two truncation and year cases here were found by reading real proposals in
the gold sample, not by imagining failure modes.
"""

from __future__ import annotations

import unittest

from recallblind.extract_identifiers import extract


def values(text: str) -> set[str]:
    return {identifier.value for identifier in extract(text)}


class Extraction(unittest.TestCase):
    def test_plain_model_number(self):
        self.assertIn("MK04", values("air purifiers, model MK04. The recalled units"))

    def test_plural_anchors_are_matched(self):
        # "models X and Y" was missed entirely: the word boundary after "model"
        # cannot fall inside "models".
        found = values("pressure washers, models RY142300 and RY142711VNM. The recalled")
        self.assertIn("RY142300", found)
        self.assertIn("RY142711VNM", found)
        self.assertIn("246898", values("cribs have the following SKUs 246898 and 534758"))
        self.assertIn("A09050", values("recalled lots A09050 and A10055 are printed"))

    def test_lot_and_sku(self):
        found = values("lot numbers, A09050 and A10055, are printed")
        self.assertEqual(found, {"A09050", "A10055"})
        self.assertIn("2407018985445734", values("sold in blue (SKU 2407018985445734), pink"))

    def test_codes_are_not_cut_at_the_window_edge(self):
        # A fixed 160-character window used to slice the last code in half and the
        # fragment still passed validation.
        filler = "colour variants listed in the notice " * 4
        text = f"Model Color {filler} 427CRESINSBG Beige 427CRESINSBK Black"
        found = values(text)
        self.assertIn("427CRESINSBG", found)
        self.assertNotIn("427CR", found)

    def test_model_year_range_is_not_an_identifier(self):
        self.assertNotIn("2023-2024", values("all VINs of Polaris Model Year 2023-2024 Ranger"))

    def test_single_year_is_not_an_identifier(self):
        self.assertNotIn("2024", values("model year 2024 electric bicycles"))

    def test_units_are_not_identifiers(self):
        for spec in ("40V", "20-in", "3.5oz"):
            with self.subTest(spec=spec):
                self.assertNotIn(spec, values(f"model with a {spec} rating"))

    def test_short_bare_numbers_are_rejected(self):
        self.assertNotIn("30", values("model 30 balls"))

    def test_non_identifier_shapes_are_rejected(self):
        cases = {
            "4/13/17": "model BEA01-001 4/13/17 through 4/27/19",
            "4th": "the serial break level is the 4th digit",
            "8.5": "Model AW42 29 inches x 8.5 inches",
            "4x2": "utility vehicle models Gator TX 4x2 and",
            "10-Piece": "SKU Product Name 137214 10-Piece Safari Baby Crib",
            "w/1973": "model TRX113 Deluxe Pit Kit (w/1973 Datsun Body)",
        }
        for token, text in cases.items():
            with self.subTest(token=token):
                self.assertNotIn(token, values(text))

    def test_real_codes_beside_the_rejected_shapes_survive(self):
        self.assertIn("BEA01-001", values("model BEA01-001 4/13/17 through 4/27/19"))
        self.assertIn("AW42", values("Model AW42 29 inches x 8.5 inches"))
        self.assertIn("137214", values("SKU Product Name 137214 10-Piece Safari Baby Crib"))

    def test_slash_joined_codes_are_split(self):
        found = values('Model No.: BXP99/BXP93/BXP94 and Batch')
        self.assertIn("BXP99", found)
        self.assertIn("BXP93", found)
        self.assertNotIn("BXP99/BXP93/BXP94", found)

    def test_date_codes_are_not_split(self):
        # "06/15/23CH1" is one date code; its parts are not codes on their own.
        self.assertIn("06/15/23CH1", values("model TRX113 Body 06/15/23CH1 TRX114"))

    def test_upc_digits_are_split_into_whole_codes(self):
        found = values("UPC 049398065631 049398065648")
        self.assertIn("049398065631", found)
        self.assertIn("049398065648", found)

    def test_empty_text(self):
        self.assertEqual(extract(""), [])

    def test_evidence_is_recorded(self):
        identifiers = extract("model number SG021. They were sold in white")
        self.assertTrue(identifiers)
        self.assertIn("model", identifiers[0].evidence.lower())


if __name__ == "__main__":
    unittest.main()
