const AREA={soporte:{label:"Soporte",color:"#e9763b",icon:"S"},proyectos:{label:"Proyectos",color:"#3978d4",icon:"P"},comercial:{label:"Comercial",color:"#7759b4",icon:"C"},desarrollo:{label:"Desarrollo",color:"#1e6048",icon:"D"}};
const state={data:null,search:"",area:"all",date:"",timelineView:"day"};
const $=s=>document.querySelector(s);
const clean=s=>(s||"").toString().normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const dateLabel=d=>new Intl.DateTimeFormat("es-AR",{weekday:"long",day:"numeric",month:"long",year:"numeric",timeZone:"America/Argentina/Cordoba"}).format(new Date(`${d}T12:00:00`));
const filtered=()=>state.data.activities.filter(a=>(state.area==="all"||a.area===state.area)&&(!state.date||a.date===state.date)&&(!state.search||clean([a.title,a.description,a.person,a.client,a.project,a.source].join(" ")).includes(clean(state.search))));

async function init(){
  const response=await fetch("data/activities.json"); state.data=await response.json();
  state.date=state.data.report.date; $("#dateFilter").value=state.date;
  Object.entries(AREA).forEach(([key,a])=>$("#areaFilter").insertAdjacentHTML("beforeend",`<option value="${key}">${a.label}</option>`));
  $("#searchInput").addEventListener("input",e=>{state.search=e.target.value;render()});
  $("#areaFilter").addEventListener("change",e=>{state.area=e.target.value;render()});
  $("#dateFilter").addEventListener("change",e=>{state.date=e.target.value;render()});
  $("#clearFilters").addEventListener("click",()=>{state.search="";state.area="all";state.date="";$("#searchInput").value="";$("#areaFilter").value="all";$("#dateFilter").value="";render()});
  document.querySelectorAll("[data-timeline-view]").forEach(button=>button.addEventListener("click",()=>{state.timelineView=button.dataset.timelineView;document.querySelectorAll("[data-timeline-view]").forEach(x=>x.classList.toggle("active",x===button));renderTimeline(filtered())}));
  render();
}

function render(){
  const rows=filtered();
  $("#displayDate").textContent=dateLabel(state.date||state.data.report.date);
  $("#lastUpdate").textContent=`Última consolidación · ${state.data.report.updated_at}`;
  $("#summaryText").textContent=state.data.report.summary;
  renderKpis(rows);renderBars(rows);renderAlerts();renderTimeline(rows);renderPeople();renderRelations();renderGoals();renderProductivity();renderAccordions(rows);
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
  $("#periodTimeline").innerHTML=Object.entries(groups).map(([period,items],index)=>`<details class="period" ${index===0?"open":""}><summary><span class="period-name">${state.timelineView==="day"?dateLabel(period):new Intl.DateTimeFormat("es-AR",{month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(`${period}-15T12:00:00Z`))}</span><div class="period-metrics"><span><b>${items.length}</b> actividades</span><span><b>${unique(items,"person")}</b> personal</span><span><b>${unique(items,"project")}</b> proyectos</span><span><b>${unique(items,"title")}</b> tareas</span><span><b>${unique(items,"client")}</b> clientes</span></div></summary><div class="timeline">${items.map(a=>`<article class="event" style="--area:${AREA[a.area].color}"><time class="event-time">${a.time}</time><i class="event-dot"></i><div class="event-card"><span class="pill">${AREA[a.area].label}</span><strong class="event-title">${a.title}</strong><span class="event-description">${a.description}</span><span class="person">${a.person}</span><span class="source">${a.source}</span></div></article>`).join("")}</div></details>`).join("");
}
function renderPeople(){
  $("#peopleGrid").innerHTML=state.data.people.map(p=>`<article class="person-card"><header><span class="avatar">${p.name.split(" ").map(x=>x[0]).slice(0,2).join("")}</span><div><strong>${p.name}</strong><small>${p.role}</small></div><i class="traffic ${p.status}"></i></header><div class="day-split"><div><span>AYER</span><p>${p.yesterday}</p></div><div><span>HOY</span><p>${p.today}</p></div></div><footer><span>${p.area}</span><span>${p.active_tasks} tareas activas</span></footer></article>`).join("");
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
function renderProductivity(){
  const series=state.data.productivity.series; const max=100;
  $("#chartLegend").innerHTML=Object.entries(AREA).map(([k,a])=>`<span><i style="--c:${a.color}"></i>${a.label}</span>`).join("");
  $("#productivityChart").innerHTML=series.map(w=>`<div class="week"><div class="week-bars">${Object.keys(AREA).map(k=>`<i title="${AREA[k].label}: ${w[k]}" style="height:${w[k]/max*100}%;--c:${AREA[k].color}"></i>`).join("")}</div><span>${w.week}</span></div>`).join("");
}
function renderAccordions(rows){
  $("#areaAccordions").innerHTML=Object.entries(AREA).map(([key,a])=>{const items=rows.filter(x=>x.area===key);return `<details class="accordion" style="--area:${a.color}" ${items.length?"":"disabled"}><summary><span class="area-icon">${a.icon}</span><span><strong>${a.label}</strong><small>${items.length} actividades en la selección</small></span></summary><div class="accordion-content">${items.length?items.map(x=>`<div class="mini-event"><time>${x.time}</time><strong>${x.title}</strong><span>${x.person}</span></div>`).join(""):"<p>Sin actividad para los filtros actuales.</p>"}</div></details>`}).join("");
}
init().catch(()=>{$("#timeline").innerHTML="<div class='empty'><strong>No se pudieron cargar los datos</strong><p>Revisá el archivo data/activities.json.</p></div>"});
