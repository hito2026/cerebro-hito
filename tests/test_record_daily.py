import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_daily.py"
SPEC = importlib.util.spec_from_file_location("record_daily", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordDailyPendingStateTests(unittest.TestCase):
    def test_negative_approval_wording_is_not_counted_as_approved(self):
        self.assertFalse(MODULE.approval_status_is_approved("No aprobado"))
        self.assertFalse(MODULE.approval_status_is_approved("Pendiente de aprobación"))
        self.assertFalse(MODULE.approval_status_is_approved("Requiere reparación"))
        self.assertTrue(MODULE.approval_status_is_approved("Aprobado"))

    def test_non_approved_daily_is_registered_with_pending_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily_file = root / "daily_planning.json"
            evolution_file = root / "planning_evolution.json"
            tracking_file = root / "user_daily_tracking.json"
            input_file = root / "pending.json"
            daily_file.write_text(json.dumps({"report": {}, "schema_version": "1.0", "rows": []}))
            evolution_file.write_text(json.dumps({"report": {}, "metrics": {}, "days": [], "people": []}))
            tracking_file.write_text(json.dumps({"report": {}, "metrics": {}, "people": []}))
            input_file.write_text(json.dumps({
                "daily_record": {
                    "date": "2026-08-28",
                    "approved": False,
                    "persona": "Private Person",
                    "persona_label": "Pri***",
                    "area_label": "Dato protegido",
                    "objetivo_del_dia": "Registrar estado pendiente sanitizado.",
                    "tickets_tareas": ["Actividad pendiente de aprobación"],
                    "bloqueos": [],
                    "interconsultas": [],
                    "estado_aprobacion": "Pendiente de aprobación / requiere reparación",
                    "public_sanitized": True,
                    "identity": {"source": "whatsapp", "verification_status": "pendiente_de_verificación"},
                    "registro_continuidad": {
                        "tareas_sin_hacer": ["Aprobación final de la ficha"],
                        "bloqueo_actual": "Sin bloqueo declarado"
                    },
                    "item_evidence": [{
                        "item": "Actividad pendiente de aprobación",
                        "tipo": "other",
                        "estado_evidencia": "requiere_verificación",
                        "documentation_link_status": "requested_once",
                        "link_request_sequence": ["link_requested"]
                    }]
                }
            }))

            with mock.patch.object(MODULE, "DAILY_FILE", daily_file), \
                 mock.patch.object(MODULE, "EVOLUTION_FILE", evolution_file), \
                 mock.patch.object(MODULE, "USER_TRACKING_FILE", tracking_file):
                action, row_id = MODULE.register_daily(input_file)

            self.assertEqual(action, "appended")
            self.assertTrue(row_id.startswith("daily-2026-08-28-pri"))
            daily = json.loads(daily_file.read_text())
            evolution = json.loads(evolution_file.read_text())
            tracking = json.loads(tracking_file.read_text())
            self.assertEqual(daily["rows"][0]["estado_aprobacion"], "Pendiente de aprobación / requiere reparación")
            self.assertEqual(evolution["metrics"]["approved_plans"], 0)
            self.assertEqual(evolution["metrics"]["pending_plans"], 1)
            self.assertEqual(tracking["people"][0]["approval_status"], "Pendiente de aprobación / requiere reparación")


if __name__ == "__main__":
    unittest.main()
