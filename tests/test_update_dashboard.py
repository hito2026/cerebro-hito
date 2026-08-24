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


if __name__ == "__main__":
    unittest.main()
