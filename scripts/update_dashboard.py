#!/usr/bin/env python3
"""Actualiza el tablero público con datos reales sanitizados y, opcionalmente, publica."""
import argparse
import datetime as dt
import json
import os
import subprocess
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "activities.json"
GATEWAY = os.getenv("CEREBRO_ODOO_GATEWAY", "http://127.0.0.1:18765")
ORG = os.getenv("CEREBRO_GITHUB_ORG", "hito2026")
ROLE_DIRECTORY = {
    "lucas burgos": {"id":"lucas-burgos","role":"Director Comercial","area":"Comercial","manager":None},
    "alejandro sartorio": {"id":"alejandro-sartorio","role":"Director Técnico & I+D","area":"Tecnología e I+D","manager":None},
    "matias banega": {"id":"matias-banega","role":"Director de Proyectos","area":"Proyectos","manager":None},
    "ezequiel montes": {"id":"ezequiel-montes","role":"Líder de Proyectos","area":"Proyectos","manager":"matias-banega"},
    "ignacio lera": {"id":"ignacio-lera","role":"Líder de Soporte","area":"Soporte","manager":"matias-banega"},
    "nelson tontarelli": {"id":"nelson-tontarelli","role":"Líder de Post-venta","area":"Post-venta","manager":"matias-banega"},
    "francisco fiorentino": {"id":"francisco-fiorentino","role":"Desarrollador IA","area":"Tecnología e I+D","manager":"alejandro-sartorio"},
    "pablo marchionno": {"id":"pablo-marchionno","role":"Desarrollador IA","area":"Tecnología e I+D","manager":"alejandro-sartorio"},
    "genaro garcia": {"id":"genaro-garcia","role":"Desarrollador IA","area":"Tecnología e I+D","manager":"alejandro-sartorio"},
    "mateo scozzina": {"id":"mateo-scozzina","role":"Soporte Funcional","area":"Soporte","manager":"ignacio-lera"},
    "valentin markov": {"id":"valentin-markov","role":"Soporte Funcional","area":"Soporte","manager":"ignacio-lera"},
    "nahiara delgado": {"id":"nahiara-delgado","role":"Analista Funcional","area":"Proyectos","manager":"matias-banega"},
    "nahiara aylen delgado": {"id":"nahiara-delgado","role":"Analista Funcional","area":"Proyectos","manager":"matias-banega"},
    "carolina monserrat": {"id":"carolina-monserrat","role":"Analista Funcional","area":"Proyectos","manager":"matias-banega"},
    "ariadna estebenet": {"id":"ariadna-estebenet","role":"Analista Funcional","area":"Proyectos","manager":"matias-banega"},
    "lucia centurion": {"id":"lucia-centurion","role":"Administración & Finanzas","area":"Administración","manager":None},
    "jose ignacio lanser": {"id":"jose-ignacio-lanser","role":"Comercial","area":"Comercial","manager":"lucas-burgos"},
    "lanser jose ignacio": {"id":"jose-ignacio-lanser","role":"Comercial","area":"Comercial","manager":"lucas-burgos"},
}
CLOSED_STAGE_MARKERS = (
    "solved", "cancel", "done", "hecho", "cerrad", "finaliz", "completad",
    "terminad", "descartad", "listo", "implementado en produccion", "tareas padre",
)


def git(*args, capture_output=False, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def sync_with_origin():
    dirty = git("status", "--porcelain", capture_output=True).stdout.strip()
    if dirty:
        raise RuntimeError("repository has uncommitted changes; refusing to rebase")
    git("fetch", "--prune", "origin")
    git("rebase", "origin/main")


def commit_activity_update(today):
    name = git("config", "user.name", capture_output=True).stdout.strip()
    email = git("config", "user.email", capture_output=True).stdout.strip()
    if not name or not email:
        raise RuntimeError("git user.name and user.email are required for commit trailers")
    trailers = f"Co-authored-by: {name} <{email}>\nSigned-off-by: {name} <{email}>"
    git("commit", "-m", f"Update real activity data {today.isoformat()}", "-m", trailers)


def normalized(value):
    return " ".join(unicodedata.normalize("NFD", value.lower()).encode("ascii", "ignore").decode().split())


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(GATEWAY + path, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def search(model, domain, fields, limit=100):
    return request("/v1/search-read", {"model": model, "domain": domain, "fields": fields, "limit": limit, "order": "write_date desc"})["records"]


def search_all(model, domain, fields, page_size=100):
    records = []
    offset = 0
    while True:
        page = request(
            "/v1/search-read",
            {"model": model, "domain": domain, "fields": fields, "limit": page_size, "offset": offset, "order": "write_date desc"},
        )["records"]
        records.extend(page)
        if len(page) < page_size:
            return records
        offset += len(page)


def relation_name(value, fallback):
    return value[1] if isinstance(value, list) and len(value) > 1 else fallback


def stage_is_open(value):
    stage = normalized(relation_name(value, ""))
    return not any(marker in stage for marker in CLOSED_STAGE_MARKERS)


def backlog_by_person(tickets, tasks, user_names):
    backlog = {}

    def add(name, kind):
        if not name:
            return
        counts = backlog.setdefault(name, {"tickets": 0, "tasks": 0})
        counts[kind] += 1

    for ticket in tickets:
        if not ticket.get("close_date") and stage_is_open(ticket.get("stage_id")):
            user = ticket.get("user_id")
            add(user_names.get(user[0]) if isinstance(user, list) and user else None, "tickets")
    for task in tasks:
        if stage_is_open(task.get("stage_id")):
            for user_id in task.get("user_ids", []):
                add(user_names.get(user_id), "tasks")
    for counts in backlog.values():
        counts["total"] = counts["tickets"] + counts["tasks"]
    return backlog


def github_events(since):
    try:
        raw = subprocess.run(["/home/asartorio/.local/bin/gh", "api", f"/orgs/{ORG}/events?per_page=100"], check=True, capture_output=True, text=True).stdout
        events = json.loads(raw)
        return [event for event in events if event.get("created_at", "")[:10] >= since]
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return []


def main(publish=False):
    if publish:
        sync_with_origin()
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
    open_tickets = search_all("helpdesk.ticket", [["close_date", "=", False]], ["id", "stage_id", "user_id", "close_date", "write_date"])
    assigned_tasks = search_all("project.task", [["user_ids", "!=", False]], ["id", "stage_id", "user_ids", "write_date"])
    backlog = backlog_by_person(open_tickets, assigned_tasks, user_names)
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
    person_totals=Counter();person_areas={}
    for (name,area),count in people.items():
        person_totals[name]+=count
        if name not in person_areas or count>person_areas[name][1]:person_areas[name]=(area,count)
    maximum=max(person_totals.values(), default=1)
    data["activities"]=activities
    people_names=sorted(set(person_totals)|set(backlog), key=lambda name:(-backlog.get(name,{}).get("total",0), -person_totals.get(name,0), name))
    data["people"]=[{"name":name,"role":ROLE_DIRECTORY.get(normalized(name),{}).get("role","Usuario interno Odoo"),"area":ROLE_DIRECTORY.get(normalized(name),{}).get("area",person_areas.get(name,("Sin área",0))[0]),"status":"green" if person_totals.get(name,0)/maximum>=.7 else "yellow" if person_totals.get(name,0)/maximum>=.4 else "red","active_tasks":person_totals.get(name,0),"backlog":backlog.get(name,{"tickets":0,"tasks":0,"total":0}),"yesterday":f"{sum(1 for a in activities if name in a.get('users',[a['person']]) and a['date']==recent)} actividades registradas.","today":f"{sum(1 for a in activities if name in a.get('users',[a['person']]) and a['date']==today.isoformat())} actividades registradas."} for name in people_names]
    raw_org=[]
    for i,(name,count) in enumerate(person_totals.most_common(),1):
        official=ROLE_DIRECTORY.get(normalized(name),{})
        raw_org.append({"id":official.get("id",f"person-{i}"),"name":name,"role":official.get("role","Usuario interno Odoo · rol no publicado"),"area":official.get("area",person_areas[name][0]),"manager":official.get("manager"),"activity_count":count,"role_source":"hitofusion.com/jobs" if official else "Odoo"})
    available={person["id"] for person in raw_org}
    for person in raw_org:
        if person["manager"] not in available:person["manager"]=None
    data["organization"]=raw_org
    data["organization_meta"]={"roles_source":"https://www.hitofusion.com/jobs","structure_note":"Agrupación inferida por área y cargo; la fuente publica roles, no líneas formales de reporte."}
    data["report"]={"date":today.isoformat(),"updated_at":now.strftime("%d/%m/%Y %H:%M %Z"),"summary":f"Datos reales sanitizados: {len(tickets)} movimientos de soporte, {len(tasks)} tareas de proyecto y {len(gh_events)} eventos de GitHub en los últimos 30 días. Backlog actual: {sum(item['tickets'] for item in backlog.values())} tickets y {sum(item['tasks'] for item in backlog.values())} tareas asignadas sin finalizar.","mode":"real-sanitized"}
    data["source_status"]={"odoo_helpdesk":"online","odoo_projects":"online","github":"online" if gh_events else "sin eventos o no disponible","odoo_crm":"pendiente de habilitación","privacy":"datos reales sanitizados para publicación pública"}
    data["alerts"]=[{"level":"high" if sum(1 for x in tickets if x.get("priority") in ("2","3")) else "low","title":f"{sum(1 for x in tickets if x.get('priority') in ('2','3'))} tickets prioritarios","detail":"Calculado desde Odoo Helpdesk."},{"level":"medium","title":f"{sum(1 for x in tasks if x.get('date_deadline') and x['date_deadline'] < today.isoformat())} tareas vencidas","detail":"Calculado desde Odoo Proyectos."},{"level":"low","title":f"{len(gh_events)} eventos de desarrollo","detail":"Actividad observada en GitHub durante los últimos 30 días."}]
    week_start=today-dt.timedelta(days=today.weekday());week_end=week_start+dt.timedelta(days=6)
    data["weekly_plan"]["from"]=week_start.isoformat();data["weekly_plan"]["to"]=week_end.isoformat()
    for indicator in data["weekly_plan"]["indicators"]:
        if indicator["name"]=="Tickets resueltos":
            indicator["current"]=sum(1 for x in tickets if x.get("close_date") and x["close_date"][:10]>=week_start.isoformat())
    DATA_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    json.loads(DATA_FILE.read_text())
    subprocess.run(
        ["/usr/bin/python3", str(ROOT / "scripts" / "generate_recurrences.py")],
        cwd=ROOT,
        check=True,
    )
    if publish:
        git("add", "data/activities.json", "data/recurrences.json")
        changed = git("diff", "--cached", "--quiet", check=False).returncode != 0
        if changed:
            commit_activity_update(today)
            # Close the race between the initial sync and publication. If another
            # writer updated main while data was collected, replay this commit on
            # top of the new remote head before pushing.
            sync_with_origin()
            git("push", "origin", "HEAD:main")
    print(json.dumps({"ok":True,"activities":len(activities),"people":len(people),"published":bool(publish and changed),"updated_at":data["report"]["updated_at"]},ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--publish",action="store_true");args=parser.parse_args();main(args.publish)
