"""Generation-side invariants.

The one that matters: a negative that is actually recalled would invert the
benchmark and every reported BOR would be meaningless.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reclume import negatives, tasks
from reclume.gold import cohens_kappa, score_extractor
from reclume.index import RecallIndex, brand_of, build_index, category_of, normalize_code
from reclume.schema import Recall, write_jsonl


def make_recall(source_id: str, title: str, **overrides) -> Recall:
    record = Recall(
        source="cpsc",
        source_id=source_id,
        recall_date="2025-01-15",
        title=title,
        description="",
        product_names=[title],
        hazards=["The unit can overheat, posing a fire hazard."],
        remedies=["Consumers should stop using the product and contact Acme for a full refund."],
        manufacturers=["Acme"],
        url="https://example.invalid/recall",
    )
    for name, value in overrides.items():
        setattr(record, name, value)
    return record


def build_test_index(records: list[Recall], identifiers: dict[str, list[str]]) -> tuple[RecallIndex, Path]:
    tmp = Path(tempfile.mkdtemp())
    path = tmp / "identifiers.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for key, values in identifiers.items():
            handle.write(
                json.dumps(
                    {"key": key, "identifiers": [{"kind": "model", "value": v} for v in values]}
                )
                + "\n"
            )
    return build_index(records, path), tmp


class Indexing(unittest.TestCase):
    def test_longest_category_match_wins(self):
        record = make_recall("1", "Acme recalls space heater due to fire hazard")
        self.assertEqual(category_of(record), "space heater")

    def test_brand_falls_back_to_the_title(self):
        record = make_recall("1", "Zephyr recalls cribs", manufacturers=[])
        self.assertEqual(brand_of(record), "Zephyr")

    def test_code_normalisation_ignores_punctuation_and_case(self):
        self.assertEqual(normalize_code("bx-4400"), "BX4400")
        self.assertEqual(normalize_code("BX 4400"), "BX4400")

    def test_code_owner_resolves_back_to_the_recall(self):
        records = [make_recall("1", "Acme recalls space heater")]
        index, _ = build_test_index(records, {"cpsc:1": ["BX-4400"]})
        found = index.recall_for_code("bx 4400")
        self.assertIsNotNone(found)
        self.assertEqual(found.key, "cpsc:1")


class NegativeSafety(unittest.TestCase):
    def setUp(self):
        records = [
            make_recall("1", "Acme recalls space heater due to fire hazard"),
            make_recall("2", "Acme recalls crib due to entrapment hazard"),
        ]
        self.index, self.tmp = build_test_index(
            records, {"cpsc:1": ["BX-4400"], "cpsc:2": ["CR-1200"]}
        )

    def test_no_generated_negative_is_actually_recalled(self):
        out = self.tmp / "negatives.jsonl"
        negatives.build(self.index, out, per_brand=3)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line]
        self.assertTrue(rows)
        for row in rows:
            if row["identifier"]:
                self.assertFalse(
                    self.index.is_recalled_code(row["identifier"]),
                    f"{row['negative_id']} emitted a recalled code",
                )

    def test_all_three_families_are_produced(self):
        out = self.tmp / "negatives.jsonl"
        report = negatives.build(self.index, out, per_brand=3)
        self.assertEqual(
            set(report["by_family"]),
            {"adjacent_code", "corrected_successor", "brand_other_category"},
        )

    def test_brand_negatives_avoid_categories_the_brand_was_recalled_in(self):
        out = self.tmp / "negatives.jsonl"
        negatives.build(self.index, out, per_brand=20)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line]
        for row in rows:
            if row["family"] == "brand_other_category":
                self.assertFalse(self.index.brand_has_category(row["brand"], row["category"]))

    def test_successor_differs_from_the_recalled_code(self):
        successors = negatives.corrected_successor(self.index)
        self.assertTrue(successors)
        for negative in successors:
            self.assertFalse(self.index.is_recalled_code(negative.identifier))


class TaskConstruction(unittest.TestCase):
    def setUp(self):
        records = [
            make_recall("1", "Acme recalls space heater due to fire hazard"),
            make_recall("2", "Acme recalls crib", recall_date="2026-07-01"),
            make_recall("3", "Zephyr recalls stroller", manufacturers=["Zephyr"], recall_date="2024-01-01"),
        ]
        self.index, self.tmp = build_test_index(
            records, {"cpsc:1": ["BX-4400"], "cpsc:2": ["CR-1200"], "cpsc:3": ["ST-9000"]}
        )
        self.negatives_path = self.tmp / "negatives.jsonl"
        negatives.build(self.index, self.negatives_path, per_brand=2)

    def _build(self, **kwargs):
        out = self.tmp / "tasks.jsonl"
        report = tasks.build(self.index, self.negatives_path, out, **kwargs)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line]
        return report, rows

    def test_all_four_tasks_are_present(self):
        report, _ = self._build()
        self.assertEqual(set(report["by_task"]), {"T1", "T2", "T3", "T4"})

    def test_status_labels_stay_balanced(self):
        report, _ = self._build()
        self.assertEqual(report["recalled"], report["not_recalled"])

    def test_temporal_splits(self):
        _, rows = self._build(cutoff="2025-06-01")
        splits = {row["source_key"]: row["split"] for row in rows if row["task"] == "T1"}
        self.assertEqual(splits["cpsc:1"], "pre_cutoff")
        self.assertEqual(splits["cpsc:2"], "post_cutoff")

    def test_fresh_split_overrides_post_cutoff(self):
        _, rows = self._build(cutoff="2025-06-01", fresh_after="2026-06-01")
        splits = {row["source_key"]: row["split"] for row in rows if row["task"] == "T1"}
        self.assertEqual(splits["cpsc:2"], "fresh")

    def test_action_and_notice_items_carry_their_gold(self):
        _, rows = self._build()
        for row in rows:
            if row["task"] in ("T3", "T4"):
                self.assertTrue(row["gold_remedies"], row["item_id"])
                self.assertTrue(row["gold_hazards"], row["item_id"])

    def test_notice_prompt_shows_the_hazard_it_is_scored_on(self):
        _, rows = self._build()
        for row in rows:
            if row["task"] == "T4":
                self.assertIn("Hazard identified by the authority:", row["prompt"])

    def test_output_is_deterministic(self):
        first = self._build()[1]
        second = self._build()[1]
        self.assertEqual([row["item_id"] for row in first], [row["item_id"] for row in second])


class GoldMath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _write(self, name: str, decisions: list[bool]) -> Path:
        path = self.tmp / f"{name}.jsonl"
        path.write_text(
            "\n".join(
                json.dumps(
                    {
                        "key": f"cpsc:{i}",
                        "annotator": name,
                        "decisions": [{"kind": "model", "value": f"V{i}", "correct": value}],
                        "added": [],
                    }
                )
                for i, value in enumerate(decisions)
            ),
            encoding="utf-8",
        )
        return path

    def test_perfect_agreement(self):
        a = self._write("a", [True, True, False, False])
        b = self._write("b", [True, True, False, False])
        self.assertEqual(cohens_kappa(a, b)["cohens_kappa"], 1.0)

    def test_chance_agreement_scores_zero(self):
        # Both annotators say True 50% of the time but never on the same item.
        a = self._write("a", [True, True, False, False])
        b = self._write("b", [False, False, True, True])
        self.assertEqual(cohens_kappa(a, b)["cohens_kappa"], -1.0)

    def test_f1_counts_rejections_as_false_positives(self):
        path = self._write("a", [True, True, False, False])
        result = score_extractor([path])
        self.assertEqual(result["true_positives"], 2)
        self.assertEqual(result["false_positives"], 2)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1.0)

    def test_missed_codes_become_false_negatives(self):
        path = self.tmp / "c.jsonl"
        path.write_text(
            json.dumps(
                {
                    "key": "cpsc:1",
                    "annotator": "c",
                    "decisions": [{"kind": "model", "value": "A1", "correct": True}],
                    "added": ["B2"],
                }
            ),
            encoding="utf-8",
        )
        result = score_extractor([path])
        self.assertEqual(result["false_negatives"], 1)
        self.assertEqual(result["recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
