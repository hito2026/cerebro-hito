import datetime as dt
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_recurrences.py"
SPEC = importlib.util.spec_from_file_location("generate_recurrences", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenerateRecurrencesTests(unittest.TestCase):
    def test_filters_tests_and_non_development_issues(self):
        self.assertFalse(MODULE.eligible({"title": "Prueba Ale", "size": 4, "issue_type": "BUG"}))
        self.assertFalse(MODULE.eligible({"title": "Consulta", "size": 4, "issue_type": "USER"}))
        self.assertTrue(MODULE.eligible({"title": "Conciliación bancaria", "size": 3, "issue_type": "BUG"}))

    def test_matches_related_recent_ticket(self):
        cluster = {
            "cluster_id": "CLUSTER-1",
            "title": "Error de conciliación bancaria con cheque",
            "symptoms": ["saldo incorrecto al conciliar"],
            "search_terms": [],
        }
        tickets = [{"name": "Saldo incorrecto en conciliación bancaria", "description": "Falla al conciliar cheque"}]
        matches = MODULE.match_recent_tickets([cluster], tickets)
        self.assertEqual(matches["CLUSTER-1"], tickets)

    def test_public_topic_redacts_company_legal_variants(self):
        topic = MODULE.public_topic({
            "title": "RE: Incidente Ecoflow SRL - Usuario Silvio Pedrozo Error en diario FCI",
            "clients": ["ECOFLOW S.R.L."],
        })
        self.assertEqual(topic, "Error en diario FCI")

    def test_report_is_sanitized_and_ranked(self):
        kb = [{
            "cluster_id": "CLUSTER-1",
            "title": "Incidente Cliente Secreto - Usuario Silvio Pedrozo Error de pagos duplicados",
            "module": "account",
            "issue_type": "BUG",
            "size": 5,
            "reusability_rate": 0.5,
            "multi_client": True,
            "cause": "causa interna",
            "clients": ["Cliente Secreto", "Otro Cliente"],
            "patterns": [{"date": "2026-07-01"}],
            "symptoms": ["pago descalzado"],
            "search_terms": [],
        }]
        tickets = [{
            "name": "Pago descalzado",
            "description": "error de pagos",
            "partner_id": [4, "Cliente Secreto"],
            "write_date": "2026-08-23 10:00:00",
        }]
        report = MODULE.build_report(kb, tickets, dt.datetime(2026, 8, 24, 9, 0).astimezone())
        self.assertEqual(len(report["clusters"]), 1)
        rendered = str(report)
        self.assertNotIn("Cliente Secreto", rendered)
        self.assertNotIn("Silvio Pedrozo", rendered)
        self.assertIn("Error de pagos duplicados", rendered)
        self.assertEqual(report["clusters"][0]["client"], "Varios clientes")
        self.assertGreaterEqual(report["clusters"][0]["score"], 70)


if __name__ == "__main__":
    unittest.main()
