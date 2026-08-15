const AREA={soporte:{label:"Soporte",color:"#e9763b",icon:"S"},proyectos:{label:"Proyectos",color:"#3978d4",icon:"P"},comercial:{label:"Comercial",color:"#7759b4",icon:"C"},desarrollo:{label:"Desarrollo",color:"#1e6048",icon:"D"}};
const state={data:null,search:"",area:"all",date:""};
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
  $("#clearFilters").addEventListener("click",()=>{state.search="";state.area="all";state.date=state.data.report.date;$("#searchInput").value="";$("#areaFilter").value="all";$("#dateFilter").value=state.date;render()});
  render();
}

function render(){
  const rows=filtered();
  $("#displayDate").textContent=dateLabel(state.date||state.data.report.date);
  $("#lastUpdate").textContent=`Última consolidación · ${state.data.report.updated_at}`;
  $("#summaryText").textContent=state.data.report.summary;
  renderKpis(rows);renderBars(rows);renderAlerts();renderTimeline(rows);renderAccordions(rows);
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
  $("#timeline").innerHTML=ordered.map(a=>`<article class="event" style="--area:${AREA[a.area].color}"><time class="event-time">${a.time}</time><i class="event-dot"></i><div class="event-card"><div><div class="event-meta"><span class="pill">${AREA[a.area].label}</span><span class="source">${a.source}</span></div><h3>${a.title}</h3><p>${a.description}</p></div><span class="person">${a.person}</span></div></article>`).join("");
}
function renderAccordions(rows){
  $("#areaAccordions").innerHTML=Object.entries(AREA).map(([key,a])=>{const items=rows.filter(x=>x.area===key);return `<details class="accordion" style="--area:${a.color}" ${items.length?"":"disabled"}><summary><span class="area-icon">${a.icon}</span><span><strong>${a.label}</strong><small>${items.length} actividades en la selección</small></span></summary><div class="accordion-content">${items.length?items.map(x=>`<div class="mini-event"><time>${x.time}</time><strong>${x.title}</strong><span>${x.person}</span></div>`).join(""):"<p>Sin actividad para los filtros actuales.</p>"}</div></details>`}).join("");
}
init().catch(()=>{$("#timeline").innerHTML="<div class='empty'><strong>No se pudieron cargar los datos</strong><p>Revisá el archivo data/activities.json.</p></div>"});
