import datetime as dt
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_recurrences.py"
SPEC = importlib.util.spec_from_file_location("generate_recurrences", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenerateRecurrencesTests(unittest.TestCase):
    def test_sanitizes_sensitive_chatter_values(self):
        clean = MODULE.sanitize_chatter(
            "<p>Escribir a ana@example.com o +54 11 5555-1234.</p> "
            "Token: secreto123 https://interno.example/path"
        )
        self.assertNotIn("ana@example.com", clean)
        self.assertNotIn("5555-1234", clean)
        self.assertNotIn("secreto123", clean)
        self.assertNotIn("interno.example", clean)

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

    def test_chatter_can_supply_the_recurrence_signal(self):
        cluster = {
            "cluster_id": "CLUSTER-2",
            "title": "Descuadre al conciliar cheque bancario",
            "symptoms": ["saldo incorrecto"],
            "search_terms": [],
        }
        ticket = {"name": "Consulta", "description": "Sin detalle", "_chatter_text": "Saldo incorrecto al conciliar cheque bancario"}
        matches = MODULE.match_recent_tickets([cluster], [ticket])
        self.assertEqual(matches["CLUSTER-2"], [ticket])

    def test_large_chatter_does_not_dilute_title_match(self):
        cluster = {
            "cluster_id": "CLUSTER-3",
            "title": "Saldo incorrecto en conciliación bancaria",
            "symptoms": [],
            "search_terms": [],
        }
        ticket = {
            "name": "Saldo incorrecto en conciliación bancaria",
            "description": "",
            "_chatter_text": " ".join(f"palabra{index}" for index in range(500)),
        }
        matches = MODULE.match_recent_tickets([cluster], [ticket])
        self.assertEqual(matches["CLUSTER-3"], [ticket])

    def test_attach_chatter_keeps_only_sanitized_transient_text(self):
        tickets = [{"id": 42, "name": "Caso"}]
        messages = [{"res_id": 42, "body": "<b>Falla de saldo</b> ana@example.com"}]
        enriched = MODULE.attach_chatter(tickets, messages)
        self.assertEqual(enriched[0]["_chatter_count"], 1)
        self.assertIn("Falla de saldo", enriched[0]["_chatter_text"])
        self.assertNotIn("ana@example.com", enriched[0]["_chatter_text"])

    def test_public_topic_redacts_company_legal_variants(self):
        topic = MODULE.public_topic({
            "title": "RE: Incidente Ecoflow SRL - Usuario Silvio Pedrozo Error en diario FCI",
            "clients": ["ECOFLOW S.R.L."],
        })
        self.assertEqual(topic, "Error en diario FCI")

    def test_public_topic_redacts_uncatalogued_client_phrase(self):
        topic = MODULE.public_topic({
            "title": "Error validación pago cliente Alkanos S.A. (conversión USD/ARS)",
            "clients": [],
        })
        self.assertNotIn("Alkanos", topic)
        self.assertIn("conversión USD/ARS", topic)

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
            "_chatter_count": 2,
            "_chatter_text": "Token: supersecreto",
        }]
        report = MODULE.build_report(kb, tickets, dt.datetime(2026, 8, 24, 9, 0).astimezone(), chatter_total=2)
        self.assertEqual(len(report["clusters"]), 1)
        rendered = str(report)
        self.assertNotIn("Cliente Secreto", rendered)
        self.assertNotIn("Silvio Pedrozo", rendered)
        self.assertNotIn("supersecreto", rendered)
        self.assertIn("Error de pagos duplicados", rendered)
        self.assertEqual(report["clusters"][0]["client"], "Varios clientes")
        self.assertEqual(report["metrics"][3]["value"], "activa")
        self.assertIn("2 mensajes sanitizados", report["clusters"][0]["evidence"])
        self.assertGreaterEqual(report["clusters"][0]["score"], 70)


if __name__ == "__main__":
    unittest.main()
