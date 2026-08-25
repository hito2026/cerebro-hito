import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_dashboard.py"
SPEC = importlib.util.spec_from_file_location("update_dashboard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UpdateDashboardBacklogTests(unittest.TestCase):
    def test_open_stage_rules_include_client_verification(self):
        self.assertTrue(MODULE.stage_is_open([3, "Verificación del cliente"]))
        self.assertTrue(MODULE.stage_is_open([984, "En proceso"]))
        self.assertFalse(MODULE.stage_is_open([4, "Solved"]))
        self.assertFalse(MODULE.stage_is_open([31, "Implementado en produccion"]))
        self.assertFalse(MODULE.stage_is_open([526, "Tareas padre"]))
        self.assertFalse(MODULE.stage_is_open([99, "Terminado"]))

    def test_counts_open_assignments_per_internal_user(self):
        users = {7: "Ana", 8: "Bruno"}
        tickets = [
            {"user_id": [7, "Ana"], "stage_id": [3, "Verificación del cliente"], "close_date": False},
            {"user_id": [7, "Ana"], "stage_id": [4, "Solved"], "close_date": "2026-08-24"},
        ]
        tasks = [
            {"user_ids": [7, 8], "stage_id": [984, "En proceso"]},
            {"user_ids": [8], "stage_id": [31, "Implementado en produccion"]},
        ]
        backlog = MODULE.backlog_by_person(tickets, tasks, users)
        self.assertEqual(backlog["Ana"], {"tickets": 1, "tasks": 1, "total": 2})
        self.assertEqual(backlog["Bruno"], {"tickets": 0, "tasks": 1, "total": 1})


class UpdateDashboardDeduplicationTests(unittest.TestCase):
    def test_removes_rows_that_are_identical_in_the_public_tracking(self):
        visible = {
            "date": "2026-08-24",
            "time": "00:52",
            "area": "desarrollo",
            "source": "GitHub",
            "person": "Sin usuario interno vinculado",
            "users": ["Sin usuario interno vinculado"],
            "client": "Interno",
            "project": "cerebro-hito",
            "title": "PushEvent en cerebro-hito",
            "description": "Actividad técnica registrada en GitHub; contenido omitido en la vista pública.",
        }
        rows = [dict(visible, id="github-1"), dict(visible, id="github-2")]

        unique = MODULE.deduplicate_activities(rows)

        self.assertEqual([row["id"] for row in unique], ["github-1"])

    def test_keeps_events_that_differ_in_a_visible_field(self):
        rows = [
            {"id": "github-1", "date": "2026-08-24", "time": "00:52", "source": "GitHub", "person": "Ana", "users": ["Ana"], "project": "repo-a", "title": "PushEvent", "description": "Actividad"},
            {"id": "github-2", "date": "2026-08-24", "time": "00:52", "source": "GitHub", "person": "Ana", "users": ["Ana"], "project": "repo-b", "title": "PushEvent", "description": "Actividad"},
        ]

        self.assertEqual(MODULE.deduplicate_activities(rows), rows)


if __name__ == "__main__":
    unittest.main()
