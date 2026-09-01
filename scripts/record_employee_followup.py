#!/usr/bin/env python3
"""Registra seguimiento de contactos WhatsApp en un dataset público sanitizado."""
import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLLOWUPS_FILE = ROOT / "data" / "employee_followups.json"
PUBLIC_FALLBACK = "Dato protegido"
SENSITIVE_PATTERNS = [
    (re.compile(r"\b\d+@(?:s\.whatsapp\.net|lid)\b", re.I), "[contacto protegido]"),
    (re.compile(r"https?://\S+", re.I), "[enlace protegido]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b"), "[email protegido]"),
    (re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"), "[teléfono protegido]"),
]
ALLOWED_IDENTITY = {"verificado", "pendiente_de_verificación", "no_encontrado_en_odoo", "empleado_provisional"}
ALLOWED_ONBOARDING = {"no_iniciado", "presentacion_solicitada", "presentacion_recibida", "incompleto", "completo", "requiere_verificación"}
ALLOWED_STATES = {"onboarding_inicial", "daily_en_curso", "daily_aprobada", "daily_pendiente_aprobacion", "weekly_followup", "friccion_tecnica_en_curso", "requiere_reparación", "sin_respuesta", "cerrado"}
ALLOWED_CADENCE = {"daily", "weekly", "eventual", "indefinida"}
ALLOWED_EVIDENCE = {"completa", "link_odoo_pendiente", "requiere_verificación", "sin_evidencia", "no_aplica"}


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(value):
    return " ".join(unicodedata.normalize("NFD", str(value).lower()).encode("ascii", "ignore").decode().split())


def slug(value):
    candidate = re.sub(r"[^a-z0-9]+", "-", normalized(value)).strip("-")
    return candidate or "dato-protegido"


def sanitize_text(value, fallback=PUBLIC_FALLBACK, limit=500):
    if value is None:
        return fallback
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    if not text:
        return fallback
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:limit]


def sanitize_enum(value, allowed, fallback):
    candidate = sanitize_text(value, fallback)
    return candidate if candidate in allowed else fallback


def sanitize_list(record, key, limit=8):
    values = record.get(key, [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{key} debe ser una lista")
    return [sanitize_text(item) for item in values if sanitize_text(item, "")][:limit]


def mask_phone_hint(value):
    text = str(value or "")
    if text in (PUBLIC_FALLBACK, "no_disponible"):
        return text
    if "@lid" in text or "@s.whatsapp.net" in text:
        return PUBLIC_FALLBACK
    digits = re.sub(r"\D+", "", text)
    if len(digits) < 4:
        return PUBLIC_FALLBACK
    return f"***-{digits[-4:]}"


def sanitize_contact_hint(record):
    hint = record.get("contact_hint") or record.get("public_contact_hint") or {}
    if hint and not isinstance(hint, dict):
        raise ValueError("contact_hint debe ser un objeto")
    name = hint.get("name_hint") or record.get("persona_label")
    phone = hint.get("phone_hint") or record.get("phone") or record.get("telefono") or record.get("whatsapp_phone")
    return {
        "name_hint": sanitize_text(name, PUBLIC_FALLBACK, limit=80),
        "phone_hint": mask_phone_hint(phone),
    }


def render_followup(raw):
    record = raw.get("contact_followup", raw) if isinstance(raw, dict) else raw
    if not isinstance(record, dict):
        raise ValueError("el archivo debe contener un objeto JSON")
    if record.get("public_sanitized") is not True:
        raise ValueError("public_sanitized=true es obligatorio")
    persona = sanitize_text(record.get("persona_label"), PUBLIC_FALLBACK, limit=80)
    area = sanitize_text(record.get("area_label"), PUBLIC_FALLBACK, limit=80)
    if persona == PUBLIC_FALLBACK:
        raise ValueError("persona_label es obligatorio")
    last_interaction = " ".join(str(record.get("last_interaction") or "").split()).strip()[:10]
    if last_interaction:
        try:
            dt.date.fromisoformat(last_interaction)
        except ValueError as exc:
            raise ValueError("last_interaction debe tener formato YYYY-MM-DD") from exc
    else:
        last_interaction = dt.date.today().isoformat()
    row_id = sanitize_text(record.get("id"), "", limit=120) or f"followup-{slug(persona)}-{slug(area)}"
    return {
        "id": slug(row_id),
        "persona": persona,
        "area": area,
        "identity_status": sanitize_enum(record.get("identity_status"), ALLOWED_IDENTITY, "pendiente_de_verificación"),
        "onboarding_status": sanitize_enum(record.get("onboarding_status"), ALLOWED_ONBOARDING, "incompleto"),
        "conversation_state": sanitize_enum(record.get("conversation_state"), ALLOWED_STATES, "onboarding_inicial"),
        "cadence": sanitize_enum(record.get("cadence"), ALLOWED_CADENCE, "indefinida"),
        "last_interaction": last_interaction,
        "last_report_type": sanitize_text(record.get("last_report_type"), "seguimiento_whatsapp", limit=120),
        "contact_hint": sanitize_contact_hint(record),
        "topics_with_alejandro": sanitize_list(record, "topics_with_alejandro"),
        "current_focus": sanitize_list(record, "current_focus"),
        "blockers": sanitize_list(record, "blockers"),
        "missing_evidence": sanitize_list(record, "missing_evidence"),
        "next_action": sanitize_text(record.get("next_action"), "Retomar en el próximo contacto", limit=500),
        "publication_status": "publicado_sanitizado",
    }


def upsert(rows, row):
    for index, existing in enumerate(rows):
        if existing.get("id") == row["id"] or (existing.get("persona") == row["persona"] and existing.get("area") == row["area"]):
            rows[index] = row
            return "updated"
    rows.append(row)
    return "appended"


def recompute(payload):
    rows = sorted(payload.get("people", []), key=lambda item: (item.get("last_interaction", ""), item.get("persona", "")), reverse=True)
    payload["people"] = rows
    payload["metrics"] = {
        "people_count": len(rows),
        "onboarding_incomplete": sum(1 for row in rows if row.get("onboarding_status") != "completo"),
        "daily_or_weekly_active": sum(1 for row in rows if row.get("conversation_state") in {"daily_en_curso", "daily_aprobada", "daily_pendiente_aprobacion", "weekly_followup"}),
        "technical_frictions": sum(1 for row in rows if row.get("conversation_state") == "friccion_tecnica_en_curso"),
        "missing_evidence": sum(len(row.get("missing_evidence", [])) for row in rows),
        "requires_action": sum(1 for row in rows if row.get("missing_evidence") or row.get("blockers") or row.get("conversation_state") in {"requiere_reparación", "friccion_tecnica_en_curso", "daily_pendiente_aprobacion"}),
    }
    payload["report"] = {
        "updated_at": dt.datetime.now().astimezone().strftime("%d/%m/%Y %H:%M %z"),
        "mode": "operator-sanitized",
        "summary": "Seguimiento público sanitizado de contactos WhatsApp; no incluye JID, teléfonos completos, links crudos ni nombres privados.",
    }


def register_followup(input_path):
    raw = read_json(input_path)
    row = render_followup(raw)
    payload = read_json(FOLLOWUPS_FILE) if FOLLOWUPS_FILE.exists() else {"report": {}, "metrics": {}, "people": []}
    payload.setdefault("people", [])
    action = upsert(payload["people"], row)
    recompute(payload)
    write_json(FOLLOWUPS_FILE, payload)
    return action, row["id"]


def main():
    parser = argparse.ArgumentParser(description="Registra seguimiento público sanitizado de contactos WhatsApp")
    parser.add_argument("input", type=Path, help="JSON con un CEREBRO_CONTACT_FOLLOWUP_RECORD sanitizado")
    args = parser.parse_args()
    action, row_id = register_followup(args.input)
    print(f"{action}: {row_id}")


if __name__ == "__main__":
    main()
