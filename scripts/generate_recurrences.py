#!/usr/bin/env python3
"""Genera un radar público sanitizado desde la KB histórica y Helpdesk reciente."""
import argparse
import datetime as dt
import html
import json
import os
import re
import unicodedata
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KB = Path(
    os.getenv(
        "CEREBRO_RECURRENCE_KB",
        "/home/asartorio/buzz-agent-cerebro/workspace/"
        "jinzo-soporte/knowledge/patterns/index.json",
    )
)
DEFAULT_GATEWAY = os.getenv("CEREBRO_ODOO_GATEWAY", "http://127.0.0.1:18765")
DEFAULT_OUTPUT = ROOT / "data" / "recurrences.json"
ISSUE_TYPES = {"BUG", "CONFIG", "INTEGRATION"}
TEST_MARKERS = {"prueba", "test", "solicitud de meet", "reunion de prueba"}
STOPWORDS = {
    "para", "como", "con", "del", "desde", "donde", "error", "esta", "este",
    "esto", "las", "los", "por", "que", "una", "uno", "unos", "unas", "sin",
    "the", "and", "ticket", "odoo", "cliente", "problema", "incidente", "solicitud",
}
MODULE_LABELS = {
    "account": "Contabilidad y facturación",
    "sale": "Ventas y precios",
    "crm": "CRM y automatizaciones",
    "purchase": "Compras",
    "inventory": "Inventario y logística",
    "mrp": "Producción",
    "mercadolibre": "Integraciones de e-commerce",
    "project": "Proyectos",
    "unknown": "Flujos transversales",
}


def normalized(value):
    value = unicodedata.normalize("NFD", str(value or "").lower())
    return " ".join(value.encode("ascii", "ignore").decode().split())


def plain_text(value):
    value = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", value).strip()


def tokens(value):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized(plain_text(value)))
        if len(token) >= 3 and token not in STOPWORDS and not token.isdigit()
    }


def request_records(gateway, since):
    rows = []
    offset = 0
    while True:
        payload = {
            "model": "helpdesk.ticket",
            "domain": [["write_date", ">=", since]],
            "fields": [
                "id", "name", "description", "partner_id", "stage_id", "team_id",
                "priority", "create_date", "write_date", "close_date", "tag_ids",
            ],
            "limit": 100,
            "offset": offset,
            "order": "write_date desc",
        }
        req = urllib.request.Request(
            gateway.rstrip("/") + "/v1/search-read",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            page = json.load(response)["records"]
        rows.extend(page)
        if len(page) < 100:
            return rows
        offset += len(page)


def cluster_dates(cluster):
    dates = []
    for pattern in cluster.get("patterns", []):
        stamp = str(pattern.get("date", ""))[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
            dates.append(stamp)
    return dates


def eligible(cluster):
    title = normalized(cluster.get("title"))
    return (
        int(cluster.get("size", 0)) >= 2
        and str(cluster.get("issue_type", "")).upper() in ISSUE_TYPES
        and not any(marker in title for marker in TEST_MARKERS)
    )


def cluster_tokens(cluster):
    fields = [cluster.get("title", ""), *cluster.get("symptoms", []), *cluster.get("search_terms", [])]
    return tokens(" ".join(map(str, fields)))


def match_recent_tickets(clusters, tickets):
    prepared = [(cluster, cluster_tokens(cluster)) for cluster in clusters]
    matches = {cluster["cluster_id"]: [] for cluster in clusters}
    for ticket in tickets:
        ticket_tokens = tokens(f"{ticket.get('name', '')} {ticket.get('description', '')}")
        if len(ticket_tokens) < 2:
            continue
        best = None
        for cluster, reference in prepared:
            overlap = len(ticket_tokens & reference)
            if overlap < 2:
                continue
            similarity = overlap / max(1, len(ticket_tokens | reference))
            if best is None or similarity > best[0]:
                best = (similarity, cluster)
        if best and best[0] >= 0.16:
            matches[best[1]["cluster_id"]].append(ticket)
    return matches


def recurrence_score(cluster, recent_count):
    size = int(cluster.get("size", 0))
    reuse = float(cluster.get("reusability_rate", 0) or 0)
    score = 35 + min(size, 6) * 5 + min(reuse, 0.8) * 20
    score += 8 if cluster.get("multi_client") else 0
    score += 5 if cluster.get("cause") else 0
    score += min(recent_count, 4) * 4
    return min(99, round(score))


def public_topic(cluster):
    topic = plain_text(cluster.get("title", ""))
    for client in sorted(cluster.get("clients", []), key=lambda value: len(str(value)), reverse=True):
        if client:
            topic = re.sub(re.escape(str(client)), "", topic, flags=re.IGNORECASE)
            company_words = [word for word in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9]+", str(client)) if len(word) >= 4]
            if company_words:
                topic = re.sub(r"\b" + r"\W+".join(map(re.escape, company_words)) + r"\b", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", "", topic, flags=re.IGNORECASE)
    topic = re.sub(
        r"\b(?:usuario|contacto)\s+.+?(\s+(?:error|falla|problema|configuraci[oó]n)\b)",
        r"\1",
        topic,
        flags=re.IGNORECASE,
    )
    topic = re.sub(r"^(?:re:\s*)?(?:incidente|ticket|caso)\s*[-:]*\s*", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"^(?:s\.?\s*r\.?\s*l\.?|s\.?\s*a\.?)\s*[-:]*\s*", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"^\[[^]]+\]\s*", "", topic)
    topic = re.sub(r"\s+[-–—:]\s+", " · ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" ·-:[]")
    return topic[:110].rstrip() if len(tokens(topic)) >= 2 else "Patrón operativo recurrente"


def public_family(cluster):
    module = str(cluster.get("module", "unknown"))
    return f"{MODULE_LABELS.get(module, MODULE_LABELS['unknown'])} · {public_topic(cluster)}"


def build_report(kb, tickets, now):
    candidates = [cluster for cluster in kb if eligible(cluster)]
    matches = match_recent_tickets(candidates, tickets)
    ranked = []
    for cluster in candidates:
        recent = matches[cluster["cluster_id"]]
        score = recurrence_score(cluster, len(recent))
        dates = cluster_dates(cluster) + [str(ticket.get("write_date", ""))[:10] for ticket in recent]
        dates = [date for date in dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)]
        clients = {normalized(client) for client in cluster.get("clients", []) if client and "prueba" not in normalized(client)}
        clients.update(
            normalized(ticket["partner_id"][1])
            for ticket in recent
            if isinstance(ticket.get("partner_id"), list) and len(ticket["partner_id"]) > 1
        )
        ranked.append(
            {
                "client": "Varios clientes" if len(clients) > 1 else "Cliente protegido",
                "family": public_family(cluster),
                "status": "revisión prioritaria" if score >= 85 else "candidato automático" if score >= 70 else "señal débil",
                "score": score,
                "score_basis": "Heurística explicable: frecuencia, reutilización, alcance y coincidencias recientes",
                "episodes": int(cluster.get("size", 0)) + len(recent),
                "window": f"{min(dates)} → {max(dates)}" if dates else "Ventana histórica",
                "reason": (
                    f"{int(cluster.get('size', 0))} episodios históricos en la familia; "
                    f"{len(recent)} coincidencias en Helpdesk reciente."
                ),
                "evidence": "KB histórica + metadatos Helpdesk; chatter pendiente",
                "module": cluster.get("module", "unknown"),
                "issue_type": cluster.get("issue_type", "UNKNOWN"),
                "cluster_id": cluster.get("cluster_id"),
                "recent_matches": len(recent),
            }
        )
    ranked.sort(key=lambda item: (item["score"], item["recent_matches"], item["episodes"]), reverse=True)
    clusters = ranked[:12]
    probable = sum(item["score"] >= 70 for item in clusters)
    modules = len({item["module"] for item in clusters})
    return {
        "report": {
            "updated_at": now.strftime("%d/%m/%Y %H:%M %Z"),
            "mode": "automatic-sanitized",
            "status": "Detector automático · requiere validación humana",
            "corpus": f"{len(kb)} clusters históricos y {len(tickets)} tickets recientes",
        },
        "metrics": [
            {"label": "Clusters analizados", "value": len(candidates), "note": "bugs, configuración e integraciones", "tone": "orange"},
            {"label": "Candidatos publicados", "value": len(clusters), "note": f"{modules} módulos representados", "tone": "blue"},
            {"label": "Sobre el umbral", "value": probable, "note": "requieren revisión humana", "tone": "green"},
            {"label": "Fuente chatter", "value": "pendiente", "note": "radar parcial y explícito", "tone": "purple"},
        ],
        "threshold": 70,
        "steps": [
            "Filtrar clusters históricos de bug, configuración e integración.",
            "Comparar títulos y descripciones sanitizadas de Helpdesk reciente.",
            "Puntuar frecuencia, reutilización, alcance y coincidencias recientes.",
            "Soporte valida cada candidato: repetido, relacionado o distinto.",
        ],
        "clusters": clusters,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB)
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--days", type=int, default=120)
    args = parser.parse_args()
    now = dt.datetime.now().astimezone()
    since = (now.date() - dt.timedelta(days=max(1, args.days))).isoformat()
    kb = json.loads(args.kb.read_text())
    tickets = request_records(args.gateway, since)
    report = build_report(kb, tickets, now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": True, "clusters": len(report["clusters"]), "tickets": len(tickets), "updated_at": report["report"]["updated_at"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
