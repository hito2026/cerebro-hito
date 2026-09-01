import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DAILY_FILES = [
    ROOT / "data" / "daily_planning.json",
    ROOT / "data" / "planning_evolution.json",
    ROOT / "data" / "user_daily_tracking.json",
    ROOT / "data" / "employee_followups.json",
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
FORBIDDEN_PRIVATE_IDENTIFIERS = [
    "Matías Marziali",
    "Matias Marziali",
    "Nelson.T",
    "Nelson Tontarelli",
    "Lafee✌️",
    "Mesopotamia",
    "mesopotamia_payment_by_lines",
    "Valentín",
    "Valentin",
    "Samuel Marcano",
    "Inketoy",
    "Intektoy",
    "realdecatorce",
    "skepsis-consulting",
    "Ariadna Hitofusion",
    "Encometal",
    "Codimat",
    "CUIT",
    "constructora",
]


class PublicDailyDataTests(unittest.TestCase):
    def test_public_daily_datasets_publish_only_sanitized_real_records(self):
        daily = json.loads((ROOT / "data" / "daily_planning.json").read_text())
        evolution = json.loads((ROOT / "data" / "planning_evolution.json").read_text())
        tracking = json.loads((ROOT / "data" / "user_daily_tracking.json").read_text())

        self.assertEqual(tracking["metrics"]["total_dailies"], len(daily["rows"]))
        self.assertEqual(tracking["metrics"]["people_count"], len(tracking["people"]))
        self.assertLessEqual(len(evolution["people"]), len(daily["rows"]))
        approved_items = sum(
            int(day.get("approved") or 0)
            for person in evolution["people"]
            for day in person.get("days", [])
        )
        self.assertEqual(evolution["metrics"]["approved_plans"], approved_items)
        if daily["rows"]:
            self.assertNotIn("Sin evolución real publicada todavía", evolution["report"]["summary"])
        for row in daily["rows"]:
            self.assertTrue(row["public_sanitized"] if "public_sanitized" in row else True)
            self.assertNotRegex(json.dumps(row, ensure_ascii=False), r"https?://")
            self.assertNotRegex(json.dumps(row, ensure_ascii=False), r"@s\.whatsapp\.net|@lid")

    def test_public_daily_datasets_do_not_publish_placeholder_rows(self):
        public_text = "\n".join(path.read_text() for path in PUBLIC_DAILY_FILES)

        for forbidden in FORBIDDEN_PLACEHOLDERS + FORBIDDEN_PRIVATE_IDENTIFIERS:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, public_text)

    def test_app_empty_states_describe_valid_empty_data_not_load_failure(self):
        app = (ROOT / "assets" / "app.js").read_text()

        self.assertIn("Sin planificación publicada", app)
        self.assertIn("Todavía no hay dailies reales procesadas", app)
        self.assertIn("Sin evolución publicada", app)
        self.assertIn("Sin seguimiento de dailies publicado todavía", app)
        self.assertNotIn("No se pudo cargar data/planning_evolution.json", app)
        self.assertNotIn("filas demo", app)
        self.assertNotIn("demo.mode", app)

    def test_employee_followups_publish_contact_state(self):
        followups = json.loads((ROOT / "data" / "employee_followups.json").read_text())
        people = followups["people"]
        by_name = {person["persona"]: person for person in people}

        self.assertEqual(followups["metrics"]["people_count"], len(people))
        self.assertIn("Samuel M.", by_name)
        self.assertEqual(by_name["Samuel M."]["conversation_state"], "friccion_tecnica_en_curso")
        self.assertIn("Falta referencia de Odoo/ticket/tarea", by_name["Samuel M."]["blockers"])
        public_text = json.dumps(followups, ensure_ascii=False)
        self.assertNotRegex(public_text, r"https?://")
        self.assertNotRegex(public_text, r"@s\.whatsapp\.net|@lid")


if __name__ == "__main__":
    unittest.main()
