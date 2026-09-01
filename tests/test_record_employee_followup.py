import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_employee_followup.py"
SPEC = importlib.util.spec_from_file_location("record_employee_followup", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordEmployeeFollowupTests(unittest.TestCase):
    def test_registers_sanitized_followup_without_private_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "employee_followups.json"
            input_file = Path(tmp) / "followup.json"
            input_file.write_text(json.dumps({
                "contact_followup": {
                    "persona_label": "Samuel M.",
                    "area_label": "Dato protegido",
                    "identity_status": "pendiente_de_verificación",
                    "onboarding_status": "incompleto",
                    "conversation_state": "friccion_tecnica_en_curso",
                    "cadence": "indefinida",
                    "last_interaction": "2026-09-01",
                    "last_report_type": "pedido_tecnico_reencuadrado",
                    "contact_hint": {"name_hint": "Samuel M.", "phone_hint": "258879824916619@lid"},
                    "topics_with_alejandro": ["Problema técnico en https://privado.example/base"],
                    "current_focus": ["Pedir link de Odoo"],
                    "blockers": ["Falta referencia 258879824916619@lid"],
                    "missing_evidence": ["Link de Odoo"],
                    "next_action": "Pedir referencia sin exponer https://privado.example/tarea",
                    "public_sanitized": True,
                }
            }))

            with mock.patch.object(MODULE, "FOLLOWUPS_FILE", output):
                action, row_id = MODULE.register_followup(input_file)

            self.assertEqual(action, "appended")
            self.assertEqual(row_id, "followup-samuel-m-dato-protegido")
            payload = json.loads(output.read_text())
            row = payload["people"][0]
            self.assertEqual(row["persona"], "Samuel M.")
            self.assertEqual(row["conversation_state"], "friccion_tecnica_en_curso")
            self.assertEqual(row["contact_hint"]["phone_hint"], "Dato protegido")
            self.assertEqual(payload["metrics"]["people_count"], 1)
            self.assertEqual(payload["metrics"]["technical_frictions"], 1)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("https://privado.example", text)
            self.assertNotIn("258879824916619@lid", text)
            self.assertNotIn("@lid", text)
            self.assertNotIn("@s.whatsapp.net", text)

    def test_requires_public_sanitized_gate(self):
        with self.assertRaises(ValueError):
            MODULE.render_followup({"contact_followup": {"persona_label": "Persona", "public_sanitized": False}})


if __name__ == "__main__":
    unittest.main()
