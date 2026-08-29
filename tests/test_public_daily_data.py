import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DAILY_FILES = [
    ROOT / "data" / "daily_planning.json",
    ROOT / "data" / "planning_evolution.json",
    ROOT / "data" / "user_daily_tracking.json",
]
FORBIDDEN_PLACEHOLDERS = [
    "Persona protegida",
    "Persona A",
    "Persona B",
    "Persona C",
    "Persona D",
    "Persona E",
    "Tarea demo",
    "Ticket demo",
    "plan-demo",
    "ejemplos/demo",
]


class PublicDailyDataTests(unittest.TestCase):
    def test_public_daily_datasets_start_empty_until_real_records_are_processed(self):
        daily = json.loads((ROOT / "data" / "daily_planning.json").read_text())
        evolution = json.loads((ROOT / "data" / "planning_evolution.json").read_text())
        tracking = json.loads((ROOT / "data" / "user_daily_tracking.json").read_text())

        self.assertEqual(daily["rows"], [])
        self.assertEqual(evolution["people"], [])
        self.assertEqual(evolution["days"], [])
        self.assertEqual(tracking["people"], [])
        self.assertEqual(tracking["metrics"]["people_count"], 0)
        self.assertEqual(tracking["metrics"]["total_dailies"], 0)

    def test_public_daily_datasets_do_not_publish_placeholder_rows(self):
        public_text = "\n".join(path.read_text() for path in PUBLIC_DAILY_FILES)

        for forbidden in FORBIDDEN_PLACEHOLDERS:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, public_text)

    def test_app_empty_states_describe_valid_empty_data_not_load_failure(self):
        app = (ROOT / "assets" / "app.js").read_text()

        self.assertIn("Sin planificación publicada", app)
        self.assertIn("Todavía no hay dailies reales aprobadas", app)
        self.assertIn("Sin evolución publicada", app)
        self.assertIn("Sin seguimiento de dailies publicado todavía", app)
        self.assertNotIn("No se pudo cargar data/planning_evolution.json", app)
        self.assertNotIn("filas demo", app)
        self.assertNotIn("demo.mode", app)


if __name__ == "__main__":
    unittest.main()
