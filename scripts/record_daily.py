#!/usr/bin/env python3
"""Registra una daily aprobada de Ale en los datasets públicos sanitizados."""
import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_FILE = ROOT / "data" / "daily_planning.json"
EVOLUTION_FILE = ROOT / "data" / "planning_evolution.json"
USER_TRACKING_FILE = ROOT / "data" / "user_daily_tracking.json"
PUBLIC_FALLBACK = "Dato protegido"
APPROVED_MARKERS = ("aprobado", "aprobada", "approved")
DAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SENSITIVE_PATTERNS = [
    (re.compile(r"https?://\S+", re.I), "[enlace protegido]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b"), "[email protegido]"),
    (re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"), "[teléfono protegido]"),
]


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


def sanitize_text(value, fallback=PUBLIC_FALLBACK):
    if value is None:
        return fallback
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    if not text:
        return fallback
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:500]


def public_label(record, public_key, private_key=None):
    value = record.get(public_key)
    if value:
        return sanitize_text(value)
    if private_key and record.get(private_key):
        return PUBLIC_FALLBACK
    return PUBLIC_FALLBACK


def sanitize_list(record, key):
    values = record.get(key, [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{key} debe ser una lista")
    return [sanitize_text(item) for item in values if sanitize_text(item, "")]


def sanitize_item_evidence(record):
    values = record.get("item_evidence", [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("item_evidence debe ser una lista")
    output = []
    allowed_states = {
        "declarado_por_usuario",
        "verificado_por_herramienta",
        "mixto",
        "requiere_verificación",
        "sin_evidencia_declarada",
    }
    allowed_link_statuses = {
        "provided",
        "requested_once",
        "missing_after_retry",
        "not_applicable",
    }
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("cada item_evidence debe ser un objeto")
        state = sanitize_text(item.get("estado_evidencia"), "requiere_verificación")
        if state not in allowed_states:
            state = "requiere_verificación"
        link_status = sanitize_text(item.get("documentation_link_status"), "requested_once")
        if link_status not in allowed_link_statuses:
            link_status = "requested_once"
        sequence = item.get("link_request_sequence", [])
        if sequence is None:
            sequence = []
        if not isinstance(sequence, list):
            raise ValueError("link_request_sequence debe ser una lista")
        allowed_sequence_steps = {
            "link_requested",
            "retry_requested",
            "provided",
            "missing_after_retry",
            "not_applicable",
        }
        safe_sequence = []
        for step in sequence:
            step = sanitize_text(step, "")
            if step in allowed_sequence_steps:
                safe_sequence.append(step)
        output.append({
            "item": sanitize_text(item.get("item"), "Actividad protegida"),
            "tipo": sanitize_text(item.get("tipo"), "other"),
            "referencia": sanitize_text(item.get("referencia"), PUBLIC_FALLBACK),
            "estado_evidencia": state,
            "fuente": sanitize_text(item.get("fuente"), "usuario"),
            "observacion": sanitize_text(item.get("observacion"), ""),
            "documentation_link_status": link_status,
            "documentation_reference": "[enlace protegido]" if link_status == "provided" else PUBLIC_FALLBACK,
            "link_request_sequence": safe_sequence,
        })
    return output


def sanitize_identity(record):
    identity = record.get("identity") or {}
    if identity and not isinstance(identity, dict):
        raise ValueError("identity debe ser un objeto")
    status = sanitize_text(identity.get("verification_status"), "empleado_provisional")
    allowed = {"verificado", "pendiente_de_verificación", "no_encontrado_en_odoo", "empleado_provisional"}
    if status not in allowed:
        status = "empleado_provisional"
    # Never publish a raw WhatsApp-declared name. Public datasets are static
    # GitHub Pages assets, so only an operator-provided public label may leave
    # the local/private inbox. Raw names can remain in the ignored input file.
    return {
        "source": sanitize_text(identity.get("source"), "whatsapp"),
        "verification_status": status,
        "declared_name": public_label(record, "persona_label", "persona"),
    }


def mask_name_hint(value):
    text = sanitize_text(value, "")
    if not text or text == PUBLIC_FALLBACK:
        return PUBLIC_FALLBACK
    first = text.split()[0]
    visible = first[:3] if len(first) >= 3 else first[:1]
    return f"{visible}***" if visible else PUBLIC_FALLBACK


def mask_phone_hint(value):
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) < 4:
        return PUBLIC_FALLBACK
    return f"***-{digits[-4:]}"


def sanitize_public_contact_hint(record):
    hint = record.get("public_contact_hint") or {}
    if hint and not isinstance(hint, dict):
        raise ValueError("public_contact_hint debe ser un objeto")
    name_source = hint.get("name_hint") or record.get("persona_label") or record.get("persona")
    phone_source = hint.get("phone_hint") or record.get("phone") or record.get("telefono") or record.get("whatsapp_phone")
    return {
        "name_hint": mask_name_hint(name_source),
        "phone_hint": mask_phone_hint(phone_source),
    }


def parse_date(value):
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("date debe tener formato YYYY-MM-DD") from exc


def parse_approved(record):
    status = sanitize_text(record.get("estado_aprobacion"), "")
    explicit = record.get("approved")
    approved = explicit is True or any(marker in normalized(status) for marker in APPROVED_MARKERS)
    if not approved:
        raise ValueError("el registro debe estar aprobado antes de publicarse (approved=true o estado_aprobacion aprobado)")
    return status or "Aprobado"


def validate_and_render_row(record):
    if not isinstance(record, dict):
        raise ValueError("el archivo debe contener un objeto JSON")
    if "daily_record" in record:
        record = record["daily_record"]
    day = parse_date(record.get("date"))
    objective = sanitize_text(record.get("objetivo_del_dia"), "")
    tasks = sanitize_list(record, "tickets_tareas")
    if not objective:
        raise ValueError("objetivo_del_dia es obligatorio")
    if not tasks:
        raise ValueError("tickets_tareas debe tener al menos un elemento")
    if record.get("public_sanitized") is not True:
        raise ValueError("public_sanitized=true es obligatorio para escribir datasets públicos")
    status = parse_approved(record)
    persona = public_label(record, "persona_label", "persona")
    area = public_label(record, "area_label", "area")
    evidence = record.get("evidencia") or {}
    if evidence and not isinstance(evidence, dict):
        raise ValueError("evidencia debe ser un objeto")
    record_id = sanitize_text(record.get("id"), "") or f"daily-{day.isoformat()}-{slug(persona)}-{slug(area)}"
    continuity = record.get("registro_continuidad") or {}
    if continuity and not isinstance(continuity, dict):
        raise ValueError("registro_continuidad debe ser un objeto")
    return {
        "id": slug(record_id),
        "date": day.isoformat(),
        "persona": persona,
        "area": area,
        "objetivo_del_dia": objective,
        "tickets_tareas": tasks,
        "bloqueos": sanitize_list(record, "bloqueos"),
        "interconsultas": sanitize_list(record, "interconsultas"),
        "estado_aprobacion": status,
        "estado_registro": "registrado_en_cerebro",
        "identity": sanitize_identity(record),
        "public_contact_hint": sanitize_public_contact_hint(record),
        "registro_continuidad": {
            "pendientes_anteriores": sanitize_list(continuity, "pendientes_anteriores"),
            "tareas_completadas": sanitize_list(continuity, "tareas_completadas"),
            "tareas_sin_hacer": sanitize_list(continuity, "tareas_sin_hacer"),
            "motivo_sin_hacer": sanitize_text(continuity.get("motivo_sin_hacer"), "Dato protegido"),
            "bloqueo_actual": sanitize_text(continuity.get("bloqueo_actual"), "Sin bloqueo declarado"),
            "tareas_planificadas_hoy": sanitize_list(continuity, "tareas_planificadas_hoy"),
            "proximo_seguimiento": sanitize_text(continuity.get("proximo_seguimiento"), "Retomar en la próxima daily"),
        },
        "evidencia": {
            "tipo": sanitize_text(evidence.get("tipo"), "registro aprobado"),
            "referencia": sanitize_text(evidence.get("referencia"), "Referencia protegida"),
        },
        "item_evidence": sanitize_item_evidence(record),
        "detalle": sanitize_text(record.get("detalle"), "Registro aprobado por Ale; salida pública sanitizada."),
    }


def upsert_row(rows, row):
    for index, existing in enumerate(rows):
        same_id = existing.get("id") == row["id"]
        same_person_day = existing.get("date") == row["date"] and existing.get("persona") == row["persona"] and existing.get("area") == row["area"]
        if same_id or same_person_day:
            rows[index] = row
            return "updated"
    rows.append(row)
    return "appended"


def week_window(day):
    start = day - dt.timedelta(days=day.weekday())
    return start, start + dt.timedelta(days=6)


def ensure_week(evolution, day):
    start, end = week_window(day)
    evolution.setdefault("report", {})["window"] = f"{start.isoformat()} → {end.isoformat()}"
    days = []
    for offset in range(5):
        current = start + dt.timedelta(days=offset)
        days.append({"key": DAY_KEYS[offset], "label": f"{DAY_NAMES[offset]} {current.day:02d}"})
    evolution["days"] = days
    return start, end


def to_int(value, default=0):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def update_evolution(evolution, row, source_record):
    day = parse_date(row["date"])
    start, end = ensure_week(evolution, day)
    metrics = source_record.get("metrics", {}) if isinstance(source_record, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}
    planned = to_int(metrics.get("planned"), len(row["tickets_tareas"]))
    closed = to_int(metrics.get("closed"), 0)
    blockers = len(row["bloqueos"]) or (0 if row.get("registro_continuidad", {}).get("bloqueo_actual") in ("Sin bloqueo declarado", "Dato protegido") else 1)
    consultations = len(row["interconsultas"])
    entry = {
        "day": DAY_KEYS[day.weekday()],
        "planned": planned,
        "verified": to_int(metrics.get("verified"), planned),
        "approved": to_int(metrics.get("approved"), planned),
        "in_progress": to_int(metrics.get("in_progress"), max(planned - closed, 0)),
        "closed": closed,
        "carry_over": to_int(metrics.get("carry_over"), 0),
        "blockers": blockers,
        "consultations": consultations,
        "inferred": False,
    }
    people = evolution.setdefault("people", [])
    person = next((item for item in people if item.get("person") == row["persona"] and item.get("area") == row["area"]), None)
    if not person:
        person = {"person": row["persona"], "area": row["area"], "days": []}
        people.append(person)
    days = person.setdefault("days", [])
    for index, existing in enumerate(days):
        if existing.get("day") == entry["day"]:
            days[index] = entry
            break
    else:
        days.append(entry)
    active_keys = {item["key"] for item in evolution["days"]}
    person["days"] = [item for item in days if item.get("day") in active_keys]
    recompute_metrics(evolution)
    evolution.setdefault("report", {})["updated_at"] = dt.datetime.now().astimezone().strftime("%d/%m/%Y %H:%M %z")
    evolution["report"]["mode"] = "operator-sanitized"


def recompute_metrics(evolution):
    totals = {"approved_plans": 0, "pending_plans": 0, "blockers": 0, "consultations": 0}
    for person in evolution.get("people", []):
        for day in person.get("days", []):
            planned = to_int(day.get("planned"))
            approved = to_int(day.get("approved"))
            totals["approved_plans"] += approved
            totals["pending_plans"] += max(planned - approved, 0)
            totals["blockers"] += to_int(day.get("blockers"))
            totals["consultations"] += to_int(day.get("consultations"))
    evolution["metrics"] = totals




def daily_sort_key(row):
    return (row.get("date", ""), row.get("id", ""))


def summarize_person_tracking(rows):
    people = {}
    for row in sorted(rows, key=daily_sort_key):
        key = (row.get("persona") or PUBLIC_FALLBACK, row.get("area") or PUBLIC_FALLBACK)
        continuity = row.get("registro_continuidad") or {}
        pending_items = continuity.get("tareas_sin_hacer") or continuity.get("pendientes_anteriores") or []
        blocker_text = continuity.get("bloqueo_actual") or "Sin bloqueo declarado"
        blocker_items = [] if blocker_text in ("Sin bloqueo declarado", PUBLIC_FALLBACK) else [sanitize_text(blocker_text)]
        evidence_items = row.get("item_evidence") or []
        missing_evidence = sum(
            1 for item in evidence_items
            if item.get("estado_evidencia") in ("requiere_verificación", "sin_evidencia_declarada")
            or item.get("documentation_link_status") in ("requested_once", "missing_after_retry")
        )
        identity = row.get("identity") or {}
        people[key] = {
            "persona": key[0],
            "area": key[1],
            "identity_status": sanitize_text(identity.get("verification_status"), "empleado_provisional"),
            "contact_hint": row.get("public_contact_hint", {"name_hint": PUBLIC_FALLBACK, "phone_hint": PUBLIC_FALLBACK}),
            "last_daily": row.get("date"),
            "registration_status": sanitize_text(row.get("estado_registro"), "pendiente_de_registro"),
            "open_pending": len(pending_items),
            "pending_items": [sanitize_text(item) for item in pending_items[:5]],
            "active_blockers": len(blocker_items),
            "blocker_items": blocker_items[:5],
            "missing_evidence": missing_evidence,
            "documentation_status": "links/evidencia pendientes" if missing_evidence else "sin faltantes declarados",
            "next_follow_up": sanitize_text(continuity.get("proximo_seguimiento"), "Retomar en la próxima daily"),
        }
    return sorted(people.values(), key=lambda item: (item.get("last_daily") or "", item.get("persona") or ""), reverse=True)


def update_user_tracking(rows):
    people = summarize_person_tracking(rows)
    metrics = {
        "people_count": len(people),
        "total_dailies": len(rows),
        "open_pending": sum(to_int(person.get("open_pending")) for person in people),
        "active_blockers": sum(to_int(person.get("active_blockers")) for person in people),
        "missing_evidence": sum(to_int(person.get("missing_evidence")) for person in people),
    }
    payload = {
        "report": {
            "updated_at": dt.datetime.now().astimezone().strftime("%d/%m/%Y %H:%M %z"),
            "mode": "operator-sanitized",
            "summary": "Seguimiento público sanitizado por persona; no incluye teléfonos, JID, nombres privados ni links crudos.",
        },
        "metrics": metrics,
        "people": people,
    }
    write_json(USER_TRACKING_FILE, payload)

def register_daily(input_path):
    raw = read_json(input_path)
    source_record = raw.get("daily_record", raw) if isinstance(raw, dict) else raw
    row = validate_and_render_row(raw)
    daily = read_json(DAILY_FILE)
    daily.setdefault("rows", [])
    action = upsert_row(daily["rows"], row)
    daily.setdefault("report", {})["date"] = row["date"]
    daily["report"]["updated_at"] = dt.datetime.now().astimezone().strftime("%d/%m/%Y %H:%M %z")
    daily["report"]["mode"] = "operator-sanitized"
    daily["report"]["summary"] = "Planificación diaria aprobada y sanitizada para publicación; no incluye datos privados por defecto."
    write_json(DAILY_FILE, daily)
    evolution = read_json(EVOLUTION_FILE)
    update_evolution(evolution, row, source_record)
    write_json(EVOLUTION_FILE, evolution)
    update_user_tracking(daily["rows"])
    return action, row["id"]


def main():
    parser = argparse.ArgumentParser(description="Registra una daily aprobada en data/daily_planning.json y data/planning_evolution.json")
    parser.add_argument("input", type=Path, help="JSON con un CEREBRO_DAILY_RECORD aprobado y sanitizado")
    args = parser.parse_args()
    action, row_id = register_daily(args.input)
    print(f"{action}: {row_id}")


if __name__ == "__main__":
    main()
