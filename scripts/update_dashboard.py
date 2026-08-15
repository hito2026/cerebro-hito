#!/usr/bin/env python3
"""Actualiza el tablero público con datos reales sanitizados y, opcionalmente, publica."""
import argparse
import datetime as dt
import json
import os
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "activities.json"
GATEWAY = os.getenv("CEREBRO_ODOO_GATEWAY", "http://127.0.0.1:18765")
ORG = os.getenv("CEREBRO_GITHUB_ORG", "hito2026")


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(GATEWAY + path, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def search(model, domain, fields, limit=100):
    return request("/v1/search-read", {"model": model, "domain": domain, "fields": fields, "limit": limit, "order": "write_date desc"})["records"]


def relation_name(value, fallback):
    return value[1] if isinstance(value, list) and len(value) > 1 else fallback


def github_events(since):
    try:
        raw = subprocess.run(["/home/asartorio/.local/bin/gh", "api", f"/orgs/{ORG}/events?per_page=100"], check=True, capture_output=True, text=True).stdout
        events = json.loads(raw)
        return [event for event in events if event.get("created_at", "")[:10] >= since]
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return []


def main(publish=False):
    now = dt.datetime.now().astimezone()
    today = now.date()
    since = (today - dt.timedelta(days=30)).isoformat()
    recent = (today - dt.timedelta(days=1)).isoformat()
    data = json.loads(DATA_FILE.read_text())
    tickets = search("helpdesk.ticket", [["write_date", ">=", since]], ["id", "stage_id", "team_id", "user_id", "priority", "write_date", "close_date"])
    tasks = search("project.task", [["write_date", ">=", since]], ["id", "project_id", "user_ids", "stage_id", "priority", "write_date", "date_deadline"])
    projects = search("project.project", [["write_date", ">=", since]], ["id", "user_id", "stage_id", "task_count", "open_task_count", "write_date"])
    internal_users=search("res.users", [["share", "=", False], ["active", "=", True]], ["id", "name", "login"], limit=100)
    user_names={user["id"]:user["name"] for user in internal_users}
    internal_names=set(user_names.values())
    github_users={str(user.get("login","")).split("@",1)[0].lower():user["name"] for user in internal_users if user.get("login")}
    gh_events = github_events(since)
    activities = []
    people = Counter()

    for item in tickets:
        stamp=item["write_date"].replace(" ", "T")
        candidate=relation_name(item.get("user_id"), "")
        person=candidate if candidate in internal_names else "Sin usuario interno asignado"
        if person in internal_names:people[(person,"Soporte")]+=1
        activities.append({"id":f"odoo-ticket-{item['id']}","date":stamp[:10],"time":stamp[11:16],"area":"soporte","source":"Odoo Helpdesk","person":person,"users":[person],"client":"Dato protegido","project":"Soporte","title":f"Ticket #{item['id']} actualizado","description":f"Estado: {relation_name(item.get('stage_id'),'sin etapa')} · equipo: {relation_name(item.get('team_id'),'sin equipo')}."})
    for item in tasks:
        stamp=item["write_date"].replace(" ", "T")
        users=[user_names[uid] for uid in item.get("user_ids",[]) if uid in user_names] or ["Sin usuario interno asignado"]
        person=users[0]
        for assigned in users:
            if assigned in internal_names:people[(assigned,"Proyectos")]+=1
        activities.append({"id":f"odoo-task-{item['id']}","date":stamp[:10],"time":stamp[11:16],"area":"proyectos","source":"Odoo Proyectos","person":person,"users":users,"client":"Dato protegido","project":f"Proyecto #{item.get('project_id',[item['id']])[0] if item.get('project_id') else item['id']}","title":f"Tarea #{item['id']} actualizada","description":f"Estado: {relation_name(item.get('stage_id'),'sin etapa')}."})
    for event in gh_events:
        stamp=event.get("created_at","")
        actor=event.get("actor",{}).get("login","")
        person=github_users.get(actor.lower(),"Sin usuario interno vinculado")
        repo=event.get("repo",{}).get("name","repositorio").split("/")[-1]
        if person in internal_names:people[(person,"Desarrollo")]+=1
        activities.append({"id":f"github-{event.get('id')}","date":stamp[:10],"time":stamp[11:16],"area":"desarrollo","source":"GitHub","person":person,"users":[person],"client":"Interno","project":repo,"title":f"{event.get('type','Actividad')} en {repo}","description":"Actividad técnica registrada en GitHub; contenido omitido en la vista pública."})

    activities.sort(key=lambda x:(x["date"],x["time"]), reverse=True)
    maximum=max(people.values(), default=1)
    data["activities"]=activities
    data["people"]=[{"name":name,"role":f"Actividad registrada en {area}","area":area,"status":"green" if count/maximum>=.7 else "yellow" if count/maximum>=.4 else "red","active_tasks":count,"yesterday":f"{sum(1 for a in activities if a['person']==name and a['date']==recent)} actividades registradas.","today":f"{sum(1 for a in activities if a['person']==name and a['date']==today.isoformat())} actividades registradas."} for (name,area),count in people.most_common()]
    data["organization"]=[{"id":f"person-{i}","name":name,"role":"Usuario con actividad registrada","area":area,"manager":None,"activity_count":count} for i,((name,area),count) in enumerate(people.most_common(),1)]
    data["report"]={"date":today.isoformat(),"updated_at":now.strftime("%d/%m/%Y %H:%M %Z"),"summary":f"Datos reales sanitizados: {len(tickets)} movimientos de soporte, {len(tasks)} tareas de proyecto y {len(gh_events)} eventos de GitHub en los últimos 30 días.","mode":"real-sanitized"}
    data["source_status"]={"odoo_helpdesk":"online","odoo_projects":"online","github":"online" if gh_events else "sin eventos o no disponible","odoo_crm":"pendiente de habilitación","privacy":"datos reales sanitizados para publicación pública"}
    data["alerts"]=[{"level":"high" if sum(1 for x in tickets if x.get("priority") in ("2","3")) else "low","title":f"{sum(1 for x in tickets if x.get('priority') in ('2','3'))} tickets prioritarios","detail":"Calculado desde Odoo Helpdesk."},{"level":"medium","title":f"{sum(1 for x in tasks if x.get('date_deadline') and x['date_deadline'] < today.isoformat())} tareas vencidas","detail":"Calculado desde Odoo Proyectos."},{"level":"low","title":f"{len(gh_events)} eventos de desarrollo","detail":"Actividad observada en GitHub durante los últimos 30 días."}]
    week_start=today-dt.timedelta(days=today.weekday());week_end=week_start+dt.timedelta(days=6)
    data["weekly_plan"]["from"]=week_start.isoformat();data["weekly_plan"]["to"]=week_end.isoformat()
    for indicator in data["weekly_plan"]["indicators"]:
        if indicator["name"]=="Tickets resueltos":
            indicator["current"]=sum(1 for x in tickets if x.get("close_date") and x["close_date"][:10]>=week_start.isoformat())
    DATA_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    json.loads(DATA_FILE.read_text())
    if publish:
        subprocess.run(["git","add","data/activities.json"],cwd=ROOT,check=True)
        changed=subprocess.run(["git","diff","--cached","--quiet"],cwd=ROOT).returncode!=0
        if changed:
            subprocess.run(["git","commit","-m",f"Update real activity data {today.isoformat()}"],cwd=ROOT,check=True)
            subprocess.run(["git","push","origin","main"],cwd=ROOT,check=True)
    print(json.dumps({"ok":True,"activities":len(activities),"people":len(people),"published":bool(publish and changed),"updated_at":data["report"]["updated_at"]},ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--publish",action="store_true");args=parser.parse_args();main(args.publish)
