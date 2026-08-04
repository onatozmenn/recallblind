"""Hazard taxonomy and annotation campaign tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reclume import campaign, hazards
from reclume.schema import Recall


def make_recall(source_id: str, hazard: str, title: str = "Acme recalls a thing") -> Recall:
    return Recall(
        source="cpsc",
        source_id=source_id,
        recall_date="2025-01-15",
        title=title,
        description="",
        hazards=[hazard],
        manufacturers=["Acme"],
    )


class Taxonomy(unittest.TestCase):
    def test_categories_have_unique_names(self):
        names = [category.name for category in hazards.CATEGORIES]
        self.assertEqual(len(names), len(set(names)))

    def test_every_category_documents_its_boundary(self):
        for category in hazards.CATEGORIES:
            with self.subTest(category=category.name):
                self.assertTrue(category.definition.strip())
                self.assertTrue(category.includes)

    def test_mechanisms_are_recognised(self):
        self.assertIn("fire_burn", hazards.classify("posing a fire hazard"))
        self.assertIn("fall_tipover", hazards.classify("the dresser can tip over"))
        self.assertIn("ingestion_choking", hazards.classify("small parts pose a choking hazard"))
        self.assertIn("electrical", hazards.classify("risk of shock and electrocution"))

    def test_outcome_language_is_not_a_mechanism(self):
        # "serious injury or death" appears in a third of notices and names no cause.
        self.assertEqual(hazards.classify("posing a risk of serious injury or death"), set())

    def test_severity_is_recorded_separately(self):
        self.assertEqual(hazards.severity("risk of death"), "death")
        self.assertEqual(hazards.severity("serious injury"), "serious_injury")
        self.assertEqual(hazards.severity("an injury hazard"), "injury")

    def test_multi_label(self):
        found = hazards.classify("the heater can tip over and start a fire")
        self.assertEqual(found, {"fall_tipover", "fire_burn"})

    def test_coverage_report(self):
        records = [make_recall("1", "posing a fire hazard"), make_recall("2", "an injury hazard")]
        report = hazards.coverage(records)
        self.assertEqual(report["records"], 2)
        self.assertEqual(report["labelled"], 1)
        self.assertEqual(report["coverage"], 0.5)
        self.assertEqual(len(report["unlabelled_examples"]), 1)


class Campaigns(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_registry_is_consistent(self):
        for name, spec in campaign.CAMPAIGNS.items():
            with self.subTest(campaign=name):
                self.assertEqual(name, spec.name)
                self.assertTrue(spec.choices)
                self.assertTrue(spec.guidance.strip())

    def test_hazard_choices_track_the_taxonomy(self):
        self.assertEqual(
            campaign.CAMPAIGNS["hazards"].choices,
            tuple(category.name for category in hazards.CATEGORIES),
        )

    def test_negative_sample_is_stratified_by_family(self):
        rows = [
            {
                "negative_id": f"{family}-{i}",
                "family": family,
                "brand": "Acme",
                "category": "crib",
                "identifier": f"X{i}",
                "rationale": "because",
            }
            for family in ("adjacent_code", "corrected_successor", "brand_other_category")
            for i in range(20)
        ]
        sample = campaign.sample_negatives(rows, size=30, seed=1)
        families = {row["family"] for row in sample}
        self.assertEqual(len(families), 3)
        counts = [sum(1 for row in sample if row["family"] == f) for f in families]
        self.assertEqual(len(set(counts)), 1)

    def _annotate(self, name: str, answers: list[str]) -> list[dict]:
        spec = campaign.CAMPAIGNS[name]
        sample = self.tmp / "sample.jsonl"
        campaign.write_sample(
            [{"id": f"x{i}", "text": "t", "context": "c", "suggested": []} for i in range(len(answers))],
            sample,
        )
        out = self.tmp / f"{name}.jsonl"
        replies = iter(answers)
        campaign.annotate(spec, sample, out, "tester", reader=lambda _: next(replies))
        return campaign.load(out)

    def test_labels_are_saved_and_resumable(self):
        rows = self._annotate("negatives", ["1", "2"])
        self.assertEqual([row["labels"] for row in rows], [["valid"], ["implausible"]])

    def test_single_choice_campaign_takes_only_the_first(self):
        rows = self._annotate("negatives", ["3 1"])
        self.assertEqual(rows[0]["labels"], ["wrong"])

    def test_multi_choice_campaign_keeps_all(self):
        rows = self._annotate("hazards", ["1 2"])
        self.assertEqual(rows[0]["labels"], ["fire_burn", "fall_tipover"])

    def test_blank_answer_skips_without_recording(self):
        rows = self._annotate("negatives", ["", "1"])
        self.assertEqual(len(rows), 1)

    def _write_labels(self, name: str, labels: list[list[str]]) -> Path:
        path = self.tmp / f"{name}.jsonl"
        path.write_text(
            "\n".join(
                json.dumps({"id": f"x{i}", "annotator": name, "labels": value})
                for i, value in enumerate(labels)
            ),
            encoding="utf-8",
        )
        return path

    def test_single_label_kappa_is_one_on_perfect_agreement(self):
        spec = campaign.CAMPAIGNS["negatives"]
        a = self._write_labels("a", [["valid"], ["wrong"], ["valid"], ["implausible"]])
        b = self._write_labels("b", [["valid"], ["wrong"], ["valid"], ["implausible"]])
        self.assertEqual(campaign.agreement(spec, a, b)["cohens_kappa"], 1.0)

    def test_single_label_kappa_flags_disagreement(self):
        spec = campaign.CAMPAIGNS["negatives"]
        a = self._write_labels("a", [["valid"], ["valid"], ["wrong"], ["wrong"]])
        b = self._write_labels("b", [["wrong"], ["wrong"], ["valid"], ["valid"]])
        result = campaign.agreement(spec, a, b)
        self.assertLess(result["cohens_kappa"], 0.0)
        self.assertEqual(result["verdict"], "rewrite the definitions")

    def test_multi_label_kappa_is_reported_per_category(self):
        spec = campaign.CAMPAIGNS["hazards"]
        a = self._write_labels("a", [["fire_burn"], ["fall_tipover"], ["fire_burn"]])
        b = self._write_labels("b", [["fire_burn"], ["electrical"], ["fire_burn"]])
        result = campaign.agreement(spec, a, b)
        self.assertEqual(result["kappa_by_category"]["fire_burn"], 1.0)
        self.assertIn("fall_tipover", result["below_threshold"])

    def test_agreement_needs_overlap(self):
        spec = campaign.CAMPAIGNS["negatives"]
        a = self._write_labels("a", [["valid"]])
        b = self.tmp / "empty.jsonl"
        b.write_text("", encoding="utf-8")
        self.assertIn("error", campaign.agreement(spec, a, b))

    def test_report_breaks_rates_down_by_family(self):
        spec = campaign.CAMPAIGNS["negatives"]
        sample = self.tmp / "sample.jsonl"
        campaign.write_sample(
            [
                {"id": "x0", "text": "t", "family": "adjacent_code"},
                {"id": "x1", "text": "t", "family": "adjacent_code"},
                {"id": "x2", "text": "t", "family": "brand_other_category"},
            ],
            sample,
        )
        labels = self._write_labels("a", [["implausible"], ["implausible"], ["valid"]])
        report = campaign.summarise(spec, [labels], sample)
        self.assertEqual(report["by_family"]["adjacent_code"]["rates"]["implausible"], 1.0)
        self.assertEqual(report["families_over_20pc_implausible"], ["adjacent_code"])

    def test_report_works_without_a_sample(self):
        spec = campaign.CAMPAIGNS["negatives"]
        labels = self._write_labels("a", [["valid"], ["wrong"]])
        report = campaign.summarise(spec, [labels])
        self.assertEqual(report["annotations"], 2)
        self.assertEqual(report["rate_by_label"]["valid"], 0.5)
        self.assertNotIn("by_family", report)


if __name__ == "__main__":
    unittest.main()
