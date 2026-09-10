import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HyperrelationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data" / "hyperrelations.json").read_text())

    def test_roster_and_events_are_complete(self):
        self.assertEqual(len(self.data["people"]), 23)
        self.assertEqual(len(self.data["events"]), 92)
        self.assertEqual(
            {event["day"] for event in self.data["events"]},
            {"2026-09-09", "2026-09-10"},
        )

    def test_events_have_required_public_fields(self):
        required = {
            "day", "time", "actor", "counterpart", "type",
            "source", "reference", "title", "evidence",
        }
        roster = set(self.data["people"])
        for event in self.data["events"]:
            self.assertTrue(required.issubset(event))
            self.assertIn(event["actor"], roster)
            self.assertIn(event["counterpart"], roster)
            self.assertNotEqual(event["actor"], event["counterpart"])

    def test_source_edges_are_deduplicated(self):
        keys = [
            (
                event["day"], event["time"], event["actor"],
                event["counterpart"], event["type"], event["reference"],
                event.get("message_id"),
            )
            for event in self.data["events"]
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_daily_edge_is_present_once(self):
        daily = [event for event in self.data["events"] if event["source"] == "Daily Meeting"]
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["actor"], "Matias Marziali")
        self.assertEqual(daily[0]["counterpart"], "Samuel Marcano")


if __name__ == "__main__":
    unittest.main()
