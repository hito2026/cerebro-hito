const AREA={soporte:{label:"Soporte",color:"#e9763b",icon:"S"},proyectos:{label:"Proyectos",color:"#3978d4",icon:"P"},comercial:{label:"Comercial",color:"#7759b4",icon:"C"},desarrollo:{label:"Desarrollo",color:"#1e6048",icon:"D"}};
const state={data:null,recurrences:null,search:"",area:"all",dateFrom:"",dateTo:"",timelineView:"day",goalView:"current"};
const $=s=>document.querySelector(s);
const clean=s=>(s||"").toString().normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const esc=value=>(value??"").toString().replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const dateLabel=d=>new Intl.DateTimeFormat("es-AR",{weekday:"long",day:"numeric",month:"long",year:"numeric",timeZone:"America/Argentina/Cordoba"}).format(new Date(`${d}T12:00:00`));
const shiftDate=(date,days)=>{const value=new Date(`${date}T12:00:00`);value.setDate(value.getDate()+days);return value.toISOString().slice(0,10)};
const filtered=()=>state.data.activities.filter(a=>(state.area==="all"||a.area===state.area)&&(!state.dateFrom||a.date>=state.dateFrom)&&(!state.dateTo||a.date<=state.dateTo)&&(!state.search||clean([a.title,a.description,a.person,a.client,a.project,a.source].join(" ")).includes(clean(state.search))));

async function init(){
  const activityResponse=await fetch("data/activities.json");state.data=await activityResponse.json();
  state.recurrences=await fetch("data/recurrences.json").then(response=>response.ok?response.json():Promise.reject()).catch(()=>null);
  setupSectionAccordions();
  state.dateTo=state.data.report.date;state.dateFrom=shiftDate(state.dateTo,-5);$("#dateFrom").value=state.dateFrom;$("#dateTo").value=state.dateTo;
  Object.entries(AREA).forEach(([key,a])=>$("#areaFilter").insertAdjacentHTML("beforeend",`<option value="${key}">${a.label}</option>`));
  $("#searchInput").addEventListener("input",e=>{state.search=e.target.value;render()});
  $("#areaFilter").addEventListener("change",e=>{state.area=e.target.value;render()});
  $("#dateFrom").addEventListener("change",e=>{state.dateFrom=e.target.value;state.dateTo=shiftDate(state.dateFrom,5);$("#dateTo").value=state.dateTo;render()});
  $("#dateTo").addEventListener("change",e=>{state.dateTo=e.target.value;state.dateFrom=shiftDate(state.dateTo,-5);$("#dateFrom").value=state.dateFrom;render()});
  $("#clearFilters").addEventListener("click",()=>{state.search="";state.area="all";state.dateTo=state.data.report.date;state.dateFrom=shiftDate(state.dateTo,-5);$("#searchInput").value="";$("#areaFilter").value="all";$("#dateFrom").value=state.dateFrom;$("#dateTo").value=state.dateTo;render()});
  document.querySelectorAll("[data-timeline-view]").forEach(button=>button.addEventListener("click",()=>{state.timelineView=button.dataset.timelineView;document.querySelectorAll("[data-timeline-view]").forEach(x=>x.classList.toggle("active",x===button));renderTimeline(filtered())}));
  document.querySelectorAll("[data-goal-view]").forEach(button=>button.addEventListener("click",()=>{state.goalView=button.dataset.goalView;document.querySelectorAll("[data-goal-view]").forEach(x=>x.classList.toggle("active",x===button));renderWeeklyTargets()}));
  render();
}

function setupSectionAccordions(){
  document.querySelectorAll("main > section.section").forEach(section=>{
    const title=section.querySelector(":scope > .section-title");
    if(!title)return;
    const open=section.id==="actividad";
    section.classList.add("collapsible");
    section.classList.toggle("collapsed",!open);
    title.setAttribute("role","button");title.setAttribute("tabindex","0");title.setAttribute("aria-expanded",String(open));
    title.insertAdjacentHTML("beforeend",`<span class="section-toggle" aria-hidden="true">${open?"−":"+"}</span>`);
    const toggle=force=>{const expand=force??section.classList.contains("collapsed");section.classList.toggle("collapsed",!expand);title.setAttribute("aria-expanded",String(expand));title.querySelector(".section-toggle").textContent=expand?"−":"+"};
    title.addEventListener("click",()=>toggle());
    title.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle()}});
    document.querySelectorAll(`.topbar a[href="#${section.id}"]`).forEach(link=>link.addEventListener("click",()=>toggle(true)));
  });
}

function render(){
  const rows=filtered();
  $("#displayDate").textContent=`Desde ${dateLabel(state.dateFrom)} · Hasta ${dateLabel(state.dateTo)}`;
  $("#lastUpdate").textContent=`Última consolidación · ${state.data.report.updated_at}`;
  $("#dataMode").textContent=state.data.report.mode==="real-sanitized"?"live.sanitized":"demo.mode";
  $("#summaryText").textContent=state.data.report.summary;
  renderCompanyState(rows);renderKpis(rows);renderBars(rows);renderAlerts();renderRecurrences();renderTimeline(rows);renderPeople();renderOrganization();renderRelations();renderWeeklyTargets();renderGoals();renderProductivity();renderAccordions(rows);
}

function renderRecurrences(){
  const report=state.recurrences;
  if(!report){$("#recurrenceUpdated").textContent="Datos del radar no disponibles";$("#recurrenceKpis").innerHTML="<article class='empty'><strong>Radar sin datos</strong><p>El resto del tablero continúa disponible.</p></article>";$("#recurrenceClusters").textContent="";return}
  $("#recurrenceUpdated").textContent=`${report.report.status} · ${report.report.updated_at}`;
  $("#recurrenceThreshold").textContent=`${report.threshold} / 100`;
  const tones=new Set(["orange","blue","green","purple"]);
  $("#recurrenceKpis").innerHTML=report.metrics.map(metric=>`<article class="recurrence-kpi ${tones.has(metric.tone)?metric.tone:"green"}"><span>${esc(metric.label)}</span><strong>${esc(metric.value)}${esc(metric.suffix)}</strong><small>${esc(metric.note)}</small></article>`).join("");
  $("#recurrenceCount").textContent=`${report.clusters.length} clusters observados`;
  $("#recurrenceSteps").innerHTML=report.steps.map(step=>`<li>${esc(step)}</li>`).join("");
  $("#recurrenceClusters").innerHTML=report.clusters.map(cluster=>`<article class="recurrence-row"><div class="recurrence-score ${cluster.score>=85?"high":cluster.score>=70?"medium":"low"}" title="${esc(cluster.score_basis)}"><strong>${esc(cluster.score)}</strong><span>/100*</span></div><div class="recurrence-main"><header><span>${esc(cluster.client)}</span><strong>${esc(cluster.family)}</strong><i>${esc(cluster.status)}</i></header><p>${esc(cluster.reason)}</p><div class="recurrence-meta"><span>${esc(cluster.episodes)} episodios</span><span>${esc(cluster.window)}</span><span>${esc(cluster.evidence)}</span><span>${esc(cluster.score_basis)}</span></div></div></article>`).join("");
}

function renderCompanyState(rows){
  const indicators=state.data.weekly_plan.indicators;
  const progress=Math.round(indicators.reduce((sum,x)=>sum+Math.min(100,x.current/x.target*100),0)/indicators.length);
  const activity=Object.entries(AREA).map(([key,value])=>({name:value.label,count:rows.filter(x=>x.area===key).length})).sort((a,b)=>b.count-a.count);
  const high=state.data.alerts.filter(x=>x.level==="high").length;
  const mood=progress>=90?"La compañía viene muy bien":progress>=75?"La compañía avanza a buen ritmo":"La compañía está avanzando, aunque todavía tiene trabajo por ordenar";
  const focus=activity[0]?.count?`${activity[0].name} concentra hoy la mayor actividad (${activity[0].count})`:`Todavía no hay actividad para la selección actual`;
  const attention=high?`Hay ${high} señal${high>1?"es":""} crítica${high>1?"s":""} que conviene resolver primero.`:"No aparecen señales críticas en este momento.";
  $("#companyState").textContent=`${mood}: lleva un ${progress}% promedio de sus metas semanales. ${focus}. ${attention}`;
}

function renderKpis(rows){
  const values=Object.keys(AREA).map(key=>({key,value:rows.filter(a=>a.area===key).length,...AREA[key]}));
  $("#kpiGrid").innerHTML=values.map(x=>`<article class="kpi" style="--accent:${x.color}"><span>${x.label}</span><strong>${x.value}</strong><small>${x.value===1?"actividad registrada":"actividades registradas"}</small></article>`).join("");
}
function renderBars(rows){
  const max=Math.max(1,...Object.keys(AREA).map(k=>rows.filter(a=>a.area===k).length));
  $("#totalEvents").textContent=`${rows.length} eventos`;
  $("#areaBars").innerHTML=Object.entries(AREA).map(([k,a])=>{const n=rows.filter(x=>x.area===k).length;return `<div><div class="bar-label"><span>${a.label}</span><strong>${n}</strong></div><div class="bar-track"><div class="bar-fill" style="--color:${a.color};width:${n/max*100}%"></div></div></div>`}).join("");
}
function renderAlerts(){
  $("#alertsList").innerHTML=state.data.alerts.map(a=>`<div class="alert" style="--color:${a.level==="high"?"#d94b3d":a.level==="medium"?"#e99b37":"#3978d4"}"><i></i><div><strong>${a.title}</strong><span>${a.detail}</span></div></div>`).join("");
}
function renderTimeline(rows){
  const ordered=[...rows].sort((a,b)=>`${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));
  $("#resultsCount").textContent=`${ordered.length} resultados`;
  $("#emptyState").hidden=ordered.length>0;
  const groups=ordered.reduce((out,a)=>{const key=state.timelineView==="day"?a.date:a.date.slice(0,7);(out[key]??=[]).push(a);return out},{});
  const unique=(items,key)=>new Set(items.map(x=>x[key]).filter(Boolean)).size;
  $("#periodTimeline").innerHTML=Object.entries(groups).map(([period,items],index)=>`<details class="period" ${index===0?"open":""}><summary><span class="period-name">${state.timelineView==="day"?dateLabel(period):new Intl.DateTimeFormat("es-AR",{month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(`${period}-15T12:00:00Z`))}</span><div class="period-metrics"><span><b>${items.length}</b> actividades</span><span><b>${unique(items,"person")}</b> personal</span><span><b>${unique(items,"project")}</b> proyectos</span><span><b>${unique(items,"title")}</b> tareas</span><span><b>${unique(items,"client")}</b> clientes</span></div></summary><div class="timeline">${items.map(a=>`<article class="event" style="--area:${AREA[a.area].color}"><time class="event-time">${a.time}</time><i class="event-dot"></i><div class="event-card"><span class="pill">${AREA[a.area].label}</span><strong class="event-title">${a.title}</strong><span class="event-description">${a.description}</span><span class="event-users"><b>usuarios:</b> ${(a.users||[a.person]).join(", ")}</span><span class="source">${a.source}</span></div></article>`).join("")}</div></details>`).join("");
}
function renderPeople(){
  const today=state.data.report.date,yesterday=shiftDate(today,-1),activities=state.data.activities;
  const topic=a=>{if(a.source==="GitHub")return (a.project||"GitHub").split(/[\s_-]+/).slice(0,2).join(" ");const stage=(a.description||"").match(/Estado:\s*([^·.]+)/i)?.[1]?.trim();return (stage||a.project||AREA[a.area].label).split(/\s+/).slice(0,2).join(" ")};
  const cell=(name,date)=>{const rows=activities.filter(a=>a.date===date&&(a.users||[a.person]).includes(name));if(!rows.length)return `<span class="activity-cell empty-cell">0 · sin actividad</span>`;const counts=rows.reduce((out,a)=>{out[a.area]=(out[a.area]||0)+1;return out},{});const dominant=Object.entries(counts).sort((a,b)=>b[1]-a[1])[0][0];return `<details class="person-activity" style="--activity:${AREA[dominant].color}"><summary><span class="activity-cell"><b>${rows.length}</b> · ${AREA[dominant].label.toLowerCase()}</span></summary><div class="activity-topics">${rows.map(a=>`<span title="${a.title}">${topic(a)}</span>`).join("")}</div></details>`};
  const people=state.data.people.map(p=>`<tr><td><span class="table-person"><i>${p.name.split(" ").map(x=>x[0]).slice(0,2).join("")}</i><span><strong>${p.name}</strong><small>${p.area}</small></span></span></td><td>${cell(p.name,yesterday)}</td><td>${cell(p.name,today)}</td></tr>`);
  const midpoint=Math.ceil(people.length/2),table=rows=>`<div class="people-table-shell"><table class="people-table"><thead><tr><th>Persona</th><th>Ayer</th><th>Hoy</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
  $("#peopleGrid").innerHTML=table(people.slice(0,midpoint))+table(people.slice(midpoint));
}
function renderOrganization(){
  const people=state.data.organization;
  const maximum=Math.max(...people.map(p=>p.activity_count));
  const byManager=people.reduce((out,p)=>{const key=p.manager||"root";(out[key]??=[]).push(p);return out},{});
  const card=p=>{const level=Math.max(1,p.activity_count/maximum*10);return `<article class="org-person"><header><span class="avatar">${p.name.split(" ").map(x=>x[0]).slice(0,2).join("")}</span><div><strong>${p.name}</strong><small>${p.role}</small></div></header><div class="activity-score"><strong>${level.toFixed(1)}</strong><span>/ 10</span></div><div class="activity-track"><i style="width:${level*10}%"></i></div><footer><span>${p.area}</span><b>${p.activity_count} actividades</b></footer></article>`};
  const branch=p=>`<div class="org-branch"><div class="org-node">${card(p)}</div>${byManager[p.id]?.length?`<div class="org-children">${byManager[p.id].map(branch).join("")}</div>`:""}</div>`;
  $("#orgScale").textContent=`Máximo: ${maximum} actividades = 10,0/10 · roles: hitofusion.com/jobs`;
  $("#orgChart").innerHTML=(byManager.root||[]).map(branch).join("");
}
function renderRelations(){
  const nodes=state.data.relations.nodes; const links=state.data.relations.links;
  $("#relationStats").textContent=`${nodes.length} nodes · ${links.length} links`;
  const pos={}; nodes.forEach((n,i)=>{const angle=(Math.PI*2*i/nodes.length)-Math.PI/2;const radius=n.type==="topic"?22:n.type==="person"?42:34;pos[n.id]={x:50+Math.cos(angle)*radius,y:50+Math.sin(angle)*radius}});
  const lines=links.map(l=>`<line x1="${pos[l.from].x}%" y1="${pos[l.from].y}%" x2="${pos[l.to].x}%" y2="${pos[l.to].y}%"></line>`).join("");
  $("#relationMap").innerHTML=`<svg aria-hidden="true">${lines}</svg>${nodes.map(n=>`<button class="graph-node ${n.type}" style="left:${pos[n.id].x}%;top:${pos[n.id].y}%" title="${n.detail}"><span>${n.label}</span><small>${n.type}</small></button>`).join("")}`;
}
function renderGoals(){
  $("#goalsGrid").innerHTML=state.data.goals.map(g=>`<article class="goal"><div class="goal-top"><span class="pill" style="--area:${AREA[g.area].color}">${AREA[g.area].label}</span><strong>${g.progress}%</strong></div><h3>${g.title}</h3><p>${g.current} / ${g.target} ${g.unit}</p><div class="goal-track"><i style="width:${g.progress}%;--goal:${AREA[g.area].color}"></i></div><small>${g.note}</small></article>`).join("");
}
function renderWeeklyTargets(){
  const week=state.data.weekly_plan;
  $("#currentGoals").hidden=state.goalView!=="current";$("#historicalGoals").hidden=state.goalView!=="history";
  $("#weekRange").textContent=state.goalView==="current"?`${dateLabel(week.from)} → ${dateLabel(week.to)} · datos demo`:`${state.data.weekly_history.length} períodos cerrados · datos demo`;
  $("#weeklyTargets").innerHTML=week.indicators.map(x=>{const progress=Math.min(100,Math.round(x.current/x.target*100));const status=progress>=90?"green":progress>=65?"yellow":"red";return `<div class="week-goal-row"><div><strong>${x.name}</strong><small>${x.area}</small></div><span>${x.target} ${x.unit}</span><span>${x.current} ${x.unit}</span><div class="week-progress"><i style="width:${progress}%"></i><b>${progress}%</b></div><span class="state-label ${status}"><i></i>${status==="green"?"en objetivo":status==="yellow"?"en progreso":"requiere atención"}</span></div>`}).join("");
  $("#historicalGoals").innerHTML=state.data.weekly_history.map((w,index)=>`<details class="history-week" ${index===0?"open":""}><summary><div><strong>${dateLabel(w.from)} → ${dateLabel(w.to)}</strong><small>${w.closed_at}</small></div><div class="history-summary"><span><b>${w.score}%</b> cumplimiento</span><span><b>${w.completed}</b> / ${w.total} metas</span><span class="state-label ${w.score>=90?"green":w.score>=70?"yellow":"red"}"><i></i>${w.score>=90?"objetivo alcanzado":w.score>=70?"cumplimiento parcial":"bajo objetivo"}</span></div></summary><div class="history-detail">${w.indicators.map(x=>`<div><span>${x.name}</span><span>${x.result}</span><b>${x.progress}%</b></div>`).join("")}</div></details>`).join("");
}
function renderProductivity(){
  const series=state.data.productivity.series; const max=100;
  $("#chartLegend").innerHTML=Object.entries(AREA).map(([k,a])=>`<span><i style="--c:${a.color}"></i>${a.label}</span>`).join("");
  $("#productivityChart").innerHTML=series.map(w=>`<div class="week"><div class="week-bars">${Object.keys(AREA).map(k=>`<i title="${AREA[k].label}: ${w[k]}" style="height:${w[k]/max*100}%;--c:${AREA[k].color}"></i>`).join("")}</div><span>${w.week}</span></div>`).join("");
}
function renderAccordions(rows){
  $("#areaAccordions").innerHTML=Object.entries(AREA).map(([key,a])=>{const items=rows.filter(x=>x.area===key);return `<details class="accordion" style="--area:${a.color}" ${items.length?"":"disabled"}><summary><span class="area-icon">${a.icon}</span><span><strong>${a.label}</strong><small>${items.length} actividades en la selección</small></span></summary><div class="accordion-content">${items.length?items.map(x=>`<div class="mini-event"><time>${x.time}</time><strong>${x.title}</strong><span>${x.person}</span></div>`).join(""):"<p>Sin actividad para los filtros actuales.</p>"}</div></details>`}).join("");
}
const ACCESS_HASH="28e910d2c7fa4c4d175906f5d8d0b030c8ce593777eef446f222863341ab5d0f";
async function digest(value){const bytes=new TextEncoder().encode(value);const hash=await crypto.subtle.digest("SHA-256",bytes);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,"0")).join("")}
function start(){document.body.classList.remove("locked");$("#accessGate").hidden=true;init().catch(()=>{$("#periodTimeline").innerHTML="<div class='empty'><strong>No se pudieron cargar los datos</strong><p>Revisá el archivo data/activities.json.</p></div>"})}
if(sessionStorage.getItem("cerebro_access")==="granted")start();
else $("#accessForm").addEventListener("submit",async e=>{e.preventDefault();const valid=await digest($("#accessKey").value)===ACCESS_HASH;if(valid){sessionStorage.setItem("cerebro_access","granted");start()}else{$("#accessError").textContent="Clave incorrecta";$("#accessKey").select()}});
