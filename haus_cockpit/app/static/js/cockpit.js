/* ══════════════════════════════════════════════════════════════════════════
   haus-cockpit — client engine (multi-house, data-driven panels)
   ════════════════════════════════════════════════════════════════════════ */
"use strict";
const REFRESH = (window.REFRESH_SEC || 4) * 1000;

const IC = {
  network:'<path d="M12 2v6M12 16v6M5 12h14M6 5l12 14M18 5L6 19" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/>',
  cpu:'<rect x="6" y="6" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.6" fill="none"/><rect x="9.5" y="9.5" width="5" height="5" rx="1" fill="currentColor"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
  shield:'<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  bolt:'<path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" fill="currentColor"/>',
  box:'<path d="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/><path d="M4 6.5L12 11l8-4.5M12 11v9" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  bridge:'<path d="M3 8v8M21 8v8M3 12h18M6 12v4M18 12v4M9 12v3M15 12v3M12 12v3" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/><path d="M3 9c3.5 3 14.5 3 18 0" stroke="currentColor" stroke-width="1.6" fill="none"/>',
  ble:'<path d="M8 7l8 5-4 3V6l4 3-8 5" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linejoin="round" stroke-linecap="round"/>',
  chip:'<rect x="7" y="7" width="10" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  sun:'<circle cx="12" cy="12" r="4.2" stroke="currentColor" stroke-width="1.7" fill="none"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
  battery:'<rect x="3" y="8" width="16" height="9" rx="2" stroke="currentColor" stroke-width="1.6" fill="none"/><rect x="20" y="11" width="2.5" height="3" rx="1" fill="currentColor"/><path d="M10 9l-2 4h3l-2 4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  thermo:'<path d="M12 3a2.5 2.5 0 0 1 2.5 2.5v8.2a4 4 0 1 1-5 0V5.5A2.5 2.5 0 0 1 12 3z" stroke="currentColor" stroke-width="1.6" fill="none"/><circle cx="12" cy="17" r="1.8" fill="currentColor"/>',
  globe:'<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M3 12h18M12 3c3 3.5 3 14 0 18M12 3c-3 3.5-3 14 0 18" stroke="currentColor" stroke-width="1.4" fill="none"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.6" stroke="currentColor" stroke-width="1.6" fill="none"/><rect x="14" y="3" width="7" height="7" rx="1.6" stroke="currentColor" stroke-width="1.6" fill="none"/><rect x="3" y="14" width="7" height="7" rx="1.6" stroke="currentColor" stroke-width="1.6" fill="none"/><rect x="14" y="14" width="7" height="7" rx="1.6" stroke="currentColor" stroke-width="1.6" fill="none"/>',
  search:'<circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.7" fill="none"/><path d="M16 16l4.5 4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
};
const SVGICON = (n,cls)=>`<svg viewBox="0 0 24 24" class="${cls||''}">${IC[n]||IC.chip}</svg>`;

const $=(s,r=document)=>r.querySelector(s);
const el=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const nf=(v,d=0)=>v==null||isNaN(v)?"–":Number(v).toLocaleString("de-DE",{minimumFractionDigits:d,maximumFractionDigits:d});
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

function ageText(sec){
  if(sec==null||isNaN(sec))return "—";
  sec=Math.max(0,Math.floor(sec));
  if(sec<60)return `vor ${sec}s`;
  if(sec<3600)return `vor ${Math.floor(sec/60)}m ${sec%60}s`;
  if(sec<86400)return `vor ${Math.floor(sec/3600)}h ${Math.floor(sec%3600/60)}m`;
  return `vor ${Math.floor(sec/86400)}d`;
}
const upText=d=>d==null?"–":(d<1?`${Math.round(d*24)} h`:`${nf(d,1)} d`);

function countUp(node,to,dec=0,suffix=""){
  const from=parseFloat(node.dataset.val||"0");
  if(to==null||isNaN(to)){node.textContent="–";return;}
  if(from===to){node.textContent=nf(to,dec)+suffix;return;}
  node.dataset.val=to;
  const t0=performance.now(),dur=700;
  function step(t){const k=clamp((t-t0)/dur,0,1),e=1-Math.pow(1-k,3);
    node.textContent=nf(from+(to-from)*e,dec)+suffix; if(k<1)requestAnimationFrame(step);}
  requestAnimationFrame(step);
}
function gaugeColor(pct,invert){
  if(invert){ if(pct>=85)return"var(--red)"; if(pct>=68)return"var(--peach)"; return"var(--green)"; }
  if(pct>=50)return"var(--green)"; if(pct>=25)return"var(--yellow)"; return"var(--red)";
}
function reconcile(container,items,keyFn,createFn,updateFn){
  const seen=new Set(),map=container._rmap||(container._rmap=new Map());
  items.forEach((it,i)=>{const k=keyFn(it,i);seen.add(k);
    let node=map.get(k);
    if(!node){node=createFn(it,i);map.set(k,node);container.appendChild(node);}
    updateFn(node,it,i);
    if(node._order!==i){node._order=i;node.style.order=i;}});
  for(const [k,node] of map){ if(!seen.has(k)){node.remove();map.delete(k);} }
}

const R=34, CIRC=2*Math.PI*R;
function makeGauge(label){
  const g=el("div","gauge");
  g.innerHTML=`<div class="gwrap"><svg viewBox="0 0 78 78">
      <circle class="track" cx="39" cy="39" r="${R}"></circle>
      <circle class="fill" cx="39" cy="39" r="${R}" stroke-dasharray="${CIRC.toFixed(1)}" stroke-dashoffset="${CIRC.toFixed(1)}"></circle>
    </svg><div class="gv" data-val="0">–</div></div><div class="glabel">${label}</div>`;
  return g;
}
function setGauge(g,pct,valText,color){
  const fill=$(".fill",g),gv=$(".gv",g),p=clamp(pct||0,0,100);
  fill.style.strokeDashoffset=(CIRC*(1-p/100)).toFixed(1); fill.style.stroke=color; gv.style.color=color;
  const to=parseFloat(valText);
  if(!isNaN(to))countUp(gv,to,valText.includes(".")?1:0,valText.replace(/[0-9.,\-]/g,"")); else gv.textContent=valText;
}
function bigRing(id,scoreId,label){
  const c=2*Math.PI*48;
  return `<div class="rwrap"><svg viewBox="0 0 112 112">
    <circle class="track" cx="56" cy="56" r="48"></circle>
    <circle class="fill" id="${id}" cx="56" cy="56" r="48" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${c.toFixed(1)}"></circle>
    </svg><div class="rv"><b id="${scoreId}" data-val="0">–</b><span>${label}</span></div></div>`;
}
function setRing(id,pct,color){ $("#"+id).style.strokeDashoffset=(2*Math.PI*48*(1-clamp(pct||0,0,100)/100)).toFixed(1); $("#"+id).style.stroke=color; }
function setBar(node,label,val,pct,sub){
  if(!node._init){node.innerHTML=`<div class="bl"></div><div class="bv"></div><div class="btrack"><div class="bfill"></div></div><div class="bsub"></div>`;node._init=true;}
  $(".bl",node).innerHTML=label; $(".bv",node).textContent=val;
  $(".bfill",node).style.width=clamp(pct,2,100)+"%"; $(".bsub",node).textContent=sub;
}
const metaRows=rows=>rows.map(([k,v])=>`<div class="hm"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("");

/* ══ state ══ */
let serverOffset=0, activeHouse=null, builtHouse=null;
let prevSvc={}; const ageEls=new Set();

/* ── top bar ── */
function renderTop(d){
  const o=$("#overall"),map={nominal:["ov-nominal","ALLE SYSTEME NOMINAL"],degraded:["ov-degraded","DEGRADIERT"],critical:["ov-critical","KRITISCH"]};
  const [cls,txt]=map[d.overall]||map.nominal;
  o.className="overall "+cls; $("#overall-text").textContent=txt;
  const c=d.counts||{};
  $("#overall-counts").innerHTML=
    `<span class="oc"><span class="dot" style="background:var(--green)"></span><b>${c.up||0}</b> up</span>`+
    `<span class="oc"><span class="dot" style="background:var(--yellow)"></span><b>${c.stale||0}</b> stale</span>`+
    `<span class="oc"><span class="dot" style="background:var(--red)"></span><b>${c.down||0}</b> down</span>`;
  const m=d.mqtt||{},pill=$("#mqtt-pill");
  pill.className="mqtt-pill "+(m.connected?"on":"off");
  $("#mqtt-text").textContent=m.connected?`MQTT · ${m.topics_tracked} topics · ${m.reconnects} rc`:"MQTT getrennt";
  $("#foot-refresh").textContent=(d.refresh_sec||4);
  $("#foot-gen").textContent=new Date().toLocaleTimeString("de-DE");
}
const HSTATUS={nominal:"var(--green)",degraded:"var(--yellow)",critical:"var(--red)"};

/* ── tabs ── */
function renderTabs(d){
  const t=$("#tabs");
  reconcile(t,d.houses,h=>h.key,
    ()=>{const tab=el("div","tab");tab.onclick=function(){activeHouse=tab.dataset.house;syncTabs();renderViews(window._last,true);};return tab;},
    (tab,h)=>{
      tab.dataset.house=h.key; tab.classList.toggle("teal",h.accent==="teal");
      const col=HSTATUS[h.status]||"var(--overlay0)";
      const c=h.counts||{};
      tab.innerHTML=`<span class="hdot" style="background:${col};box-shadow:0 0 8px ${col}"></span>
        <div><div>${h.name}</div><div class="who">${h.who}</div></div>
        <span class="badge">${(c.up||0)}/${(h.services||[]).length}</span>`;
    });
  if(!activeHouse)activeHouse=d.houses[0].key;
  syncTabs();
}
function syncTabs(){document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("active",t.dataset.house===activeHouse));}

/* ── views ── */
function renderViews(d,force){
  window._last=d;
  const house=d.houses.find(h=>h.key===activeHouse)||d.houses[0];
  const host=$("#views");
  if(force||builtHouse!==house.key){host.innerHTML="";host._built=null;builtHouse=house.key;ageEls.clear();}
  if(house.live)renderHouse(host,house); else renderPending(host,house);
  if(typeof fetchHistory==="function" && histHouse!==activeHouse) fetchHistory(activeHouse);
}

function card(cls,icon,title,accent,tag){
  const c=el("div","card "+cls); c.style.setProperty("--accent",accent||"var(--mauve)");
  c.innerHTML=`<div class="chead"><div class="ci">${SVGICON(icon)}</div><h2>${title}</h2>${tag?`<span class="tag">${tag}</span>`:""}</div><div class="cbody"></div>`;
  return c;
}

/* panel skeleton builders keyed by name */
function buildPanel(name,h){
  const A=h.accent==="teal"?"var(--teal)":"var(--mauve)";
  if(name==="services"){const c=card("wide","chip","Service-Registry — Resilienz-Status",A);
    $(".cbody",c).innerHTML=`<div class="svc-grid" id="svc-grid"></div>`;return c;}
  if(name==="pi"){const c=card("span8","cpu",h.key==="klipphausen"?"Raspberry Pi · Mike (HAOS)":"Raspberry Pi 5 · pironman5","var(--blue)",h.key);
    $(".cbody",c).innerHTML=`<div class="hero-ring">${bigRing("pi-score-ring","pi-score","Health-Score")}<div class="hero-meta" id="pi-meta"></div></div>
      <div class="gauges" id="pi-gauges"></div><div class="chips" id="pi-chips"></div>`;return c;}
  if(name==="udm"){const c=card("half","shield",h.key==="klipphausen"?"UDM Pro SE · Sonnenrain":"UDM Pro SE · Radeberg","var(--teal)","gateway");
    $(".cbody",c).innerHTML=`<div class="hero-ring">${bigRing("udm-cli-ring","udm-clients","Clients")}<div class="hero-meta" id="udm-meta"></div></div>
      <div class="gauges" id="udm-gauges" style="grid-template-columns:repeat(3,1fr)"></div>`;return c;}
  if(name==="energy"){const c=card("half","bolt","Energie · Live","var(--yellow)","shelly");
    $(".cbody",c).innerHTML=`<div class="energy-hero"><span class="bignum" id="en-total" data-val="0">–</span><span class="unit">W</span>
      <span style="margin-left:auto;font-family:var(--mono);color:var(--peach)" id="en-cost">–</span></div>
      <div class="grid3" id="en-grid"></div><div class="barlist" id="en-bars"></div>`;return c;}
  if(name==="network"){const c=card("half","network","Netzwerk · Top-Talker","var(--sapphire)");
    $(".cbody",c).innerHTML=`<div class="tag" id="net-summary" style="margin-bottom:10px;font-family:var(--mono);font-size:.7rem;color:var(--overlay1)"></div><div class="barlist" id="net-bars"></div>`;return c;}
  if(name==="docker"){const c=card("half","box","Docker-Stack","var(--lavender)");
    $(".cbody",c).innerHTML=`<div class="dock-grid" id="dock-grid"></div>`;return c;}
  if(name==="ble"){const c=card("half","ble","BLE-Proxy-Mesh","var(--pink)","Mike");
    $(".cbody",c).innerHTML=`<div class="tag" id="ble-summary" style="margin-bottom:10px;font-family:var(--mono);font-size:.7rem;color:var(--overlay1)"></div>
      <div class="barlist" id="ble-sources"></div><div class="chips" id="ble-devices" style="margin-top:12px"></div>`;return c;}
  if(name==="solar"){const c=card("wide","sun","Solar · Huawei PV & Speicher","var(--yellow)","EMMA · LUNA2000 · SUN2000");
    $(".cbody",c).innerHTML=`<div class="solar-top">
      <div class="solar-rings">${bigRing("sol-soc-ring","sol-soc","Batterie SoC")}${bigRing("sol-aut-ring","sol-aut","Autarkie heute")}</div>
      <div class="solar-flow" id="sol-flow"></div></div>
      <div class="solar-day" id="sol-daily"></div>
      <div class="solar-strings" id="sol-strings"></div>
      <div class="chips" id="sol-chips" style="margin-top:12px"></div>
      <div class="sol-hint" id="sol-hint"></div>`;return c;}
  if(name==="security"){const c=card("span8","globe","Internet & Sicherheit","var(--sapphire)");
    $(".cbody",c).innerHTML=`<div class="sec-live" id="sec-live"></div>
      <div class="sec-cols"><div><div class="sec-h">🌍 Top-Länder</div><div class="barlist" id="sec-countries"></div></div>
      <div><div class="sec-h">🔌 Top-Dienste</div><div class="barlist" id="sec-services"></div></div></div>
      <div class="sec-nextdns" id="sec-nextdns"></div>
      <div class="sec-vlans" id="sec-vlans"></div>
      <div class="sec-note" id="sec-note"></div>`;return c;}
  if(name==="snmp"){const c=card("half","network",h.key==="klipphausen"?"UDM Ports · Sonnenrain":"UDM Ports · Radeberg","var(--sapphire)","SNMP");
    $(".cbody",c).innerHTML=`<div class="tag" id="snmp-sub" style="margin-bottom:10px;font-family:var(--mono);font-size:.7rem;color:var(--overlay1)"></div>
      <div class="snmp-list" id="snmp-ports"></div>`;return c;}
  if(name==="climate"){const c=card("half","thermo","Klima · Räume","var(--sky)");
    $(".cbody",c).innerHTML=`<div class="clima-grid" id="clima-grid"></div>`;return c;}
  if(name==="sensors"){const c=card("","grid","Alle Sensoren","var(--lavender)");
    $(".cbody",c).innerHTML=`<div class="sens-hero"><span class="bignum" id="sens-total" data-val="0">–</span><span class="unit">Entities</span>
      <span class="sens-num" id="sens-num"></span></div>
      <div class="sens-mini" id="sens-mini"></div>
      <div class="sens-rec-h">⚡ Zuletzt geändert</div>
      <div class="sens-recent" id="sens-recent"></div>
      <button class="sens-open" id="sens-open">${SVGICON("search")}<span>Alle durchsuchen</span></button>`;return c;}
  return null;
}

/* row-perfect spans per house — every row sums to 12 columns (no holes) */
const SPANS={radeberg:{services:12,security:8,snmp:4,energy:6,climate:6,pi:8,sensors:4,udm:6,network:6,docker:12},
             klipphausen:{services:12,solar:12,security:8,snmp:4,climate:6,udm:6,pi:8,ble:4,sensors:12}};
function renderHouse(host,h){
  if(!host._built){
    const g=el("div","grid");
    (h.panels||[]).forEach(p=>{const c=buildPanel(p,h);if(c){c.dataset.group=p;
      const sp=(SPANS[h.key]||{})[p]; if(sp)c.classList.add("s"+sp);
      g.appendChild(c);}});
    host.appendChild(g);
    // whole-card drill-down for data panels
    g.querySelectorAll(".card").forEach(c=>{const grp=c.dataset.group;
      if(["pi","udm","energy","network","ble"].includes(grp)){
        c.classList.add("clickable");
        c.addEventListener("click",e=>{if(e.target.closest(".svc"))return;openModal(grp);});
      }else if(grp==="solar"){
        c.classList.add("clickable"); c.addEventListener("click",()=>openSolarModal());
      }else if(grp==="security"){
        c.classList.add("clickable"); c.addEventListener("click",()=>openSecurityModal());
      }else if(grp==="sensors"||grp==="climate"){
        c.classList.add("clickable"); c.addEventListener("click",e=>{if(e.target.closest(".sr"))return;openSensorsModal(grp==="climate"?"climate":null);});
      }else if(grp==="snmp"){
        c.classList.add("clickable"); c.addEventListener("click",()=>openSnmpModal());
      }});
    // history / charts section
    const cs=el("section");
    cs.innerHTML=`<div class="sec-title"><div class="st-ic">${SVGICON("chip")}</div>
      <h2>Verlauf · History</h2><div class="st-line"></div>
      <span class="st-badge">Klick für Detail · 6 h</span></div>
      <div class="charts-grid" id="charts-host"></div>`;
    host.appendChild(cs);
    host._built=true;
  }
  updateHouse(host,h);
  updateCharts(window._last);
}

function updateHouse(host,h){
  /* services */
  const sg=$("#svc-grid");
  if(sg) reconcile(sg,h.services,s=>s.key,
    ()=>el("div","svc"),
    (n,s)=>{
      n.className="svc "+s.status;
      n.innerHTML=`<div class="svc-top"><div class="svc-ico">${SVGICON(s.icon)}</div>
          <div><div class="svc-name">${s.label}</div><div class="svc-blurb">${s.blurb}</div></div>
          <div class="svc-sdot"></div></div>
        <div class="svc-foot"><span class="svc-status">${s.status}</span>
          ${s.avail?`<span class="svc-avail ${s.avail}">${s.avail}</span>`:""}
          <span class="svc-age" data-epoch="${s.last_epoch?(s.last_epoch+serverOffset):''}">${s.age_sec!=null?ageText(s.age_sec):'—'}</span></div>`;
      const ageEl=$(".svc-age",n); if(ageEl.dataset.epoch)ageEls.add(ageEl);
      n.classList.add("clickable"); n.onclick=()=>openServiceModal(s);
      if(prevSvc[s.key]&&prevSvc[s.key]!==s.status)toast(s.label,s.status);
      prevSvc[s.key]=s.status;
    });

  if($("#pi-gauges")) updatePi(h.pi);
  if($("#udm-gauges")) updateUdm(h.udm);
  if($("#en-bars")) updateEnergy(h.energy);
  if($("#net-bars")) updateNetwork(h.network);
  if($("#dock-grid")) updateDocker(h.containers||[]);
  if($("#ble-sources")) updateBle(h.ble);
  if($("#sol-flow")) updateSolar(h.solar);
  if($("#sec-live")) updateSecurity(h.security);
  if($("#clima-grid")) updateClimate(h.climate);
  if($("#sens-mini")) updateSensors(h.sensors_summary,h.key);
  if($("#snmp-ports")) updateSnmp(h.snmp);
}

function updatePi(pi){
  if(!pi){$("#pi-meta").innerHTML=metaRows([["Status","⏳ warte auf Daten"]]);return;}
  const score=pi.health_score;
  const scol=score>=90?"var(--green)":score>=70?"var(--yellow)":"var(--red)";
  setRing("pi-score-ring",score,scol); const sc=$("#pi-score"); sc.style.color=scol;
  if(score!=null)countUp(sc,score,0); else sc.textContent="–";
  $("#pi-meta").innerHTML=metaRows([
    ["Modell",(pi.pi_model||"–").replace("Raspberry Pi ","Pi ")],
    ["Uptime",upText(pi.uptime_days)],
    ["Load",`${nf(pi.load_1m,2)} · ${nf(pi.load_5m,2)} · ${nf(pi.load_15m,2)}`],
    ["Netz",`↓ ${nf(pi.net_rx_mbs,2)} · ↑ ${nf(pi.net_tx_mbs,2)} MB/s`],
    ["Kernel",(pi.os_kernel||"–").split("-")[0]],
  ]);
  // gauge specs adapt to NVMe vs SD
  const specs=[
    ["CPU",pi.cpu_pct,nf(pi.cpu_pct,0)+"%",true],
    ["TEMP",clamp(pi.cpu_temp_c,0,85)/85*100,nf(pi.cpu_temp_c,0)+"°",true,pi.cpu_temp_c],
    ["RAM",pi.mem_pct,nf(pi.mem_pct,0)+"%",true],
    ["DISK",pi.disk_pct,nf(pi.disk_pct,0)+"%",true],
  ];
  if(pi.has_nvme){
    specs.push(["NVMe °C",clamp(pi.nvme_composite_temp_c,0,80)/80*100,nf(pi.nvme_composite_temp_c,0)+"°",true,pi.nvme_composite_temp_c]);
    specs.push(["NVMe Spare",pi.nvme_available_spare,nf(pi.nvme_available_spare,0)+"%",false]);
  }
  specs.push(["SWAP",pi.swap_pct,nf(pi.swap_pct,0)+"%",true]);
  if(pi.has_sd) specs.push(["SD-Wear",clamp(pi.sd_wear_pct,0,100),nf(pi.sd_wear_pct,0)+"%",true]);
  const gg=$("#pi-gauges");
  if(gg.childElementCount!==specs.length){gg.innerHTML="";specs.forEach(s=>gg.appendChild(makeGauge(s[0])));}
  specs.forEach((s,i)=>setGauge(gg.children[i],s[1],s[2],gaugeColor(s[1],s[3])));
  // throttle chips
  const t=pi.throttle||{};
  const chips=[["Undervolt",t.undervoltage,t.undervoltage_ever],["Throttled",t.throttled,t.throttled_ever],
    ["Freq-Cap",t.freq_capped,false],["Soft-Temp",t.soft_temp,false]]
    .map(([l,now,ever])=>`<span class="chip ${now?"bad":ever?"warn":""}"><span class="led"></span>${l}${now?" AKTIV":ever?" (war)":" ok"}</span>`).join("");
  let extra=`<span class="chip"><span class="led"></span>Disk ${nf(pi.disk_used_gb,0)}/${nf(pi.disk_total_gb,0)} GB</span>`;
  if(pi.has_nvme)extra+=`<span class="chip"><span class="led"></span>NVMe ${nf(pi.nvme_lifetime_written_tb,1)} TBW</span>`;
  if(pi.has_sd&&pi.sd_years_left!=null)extra+=`<span class="chip ${pi.sd_years_left>0&&pi.sd_years_left<3?"warn":""}"><span class="led"></span>SD ~${nf(pi.sd_years_left,0)} J</span>`;
  $("#pi-chips").innerHTML=chips+extra;
}

function updateUdm(u){
  if(!u){$("#udm-meta").innerHTML=metaRows([["Status","⏳ warte auf Daten"]]);return;}
  setRing("udm-cli-ring",clamp((u.clients||0)/50*100,0,100),"var(--teal)");
  const cl=$("#udm-clients"); cl.style.color="var(--teal)"; if(u.clients!=null)countUp(cl,u.clients,0); else cl.textContent="–";
  $("#udm-meta").innerHTML=metaRows([
    ["Modell",u.model||"–"],["WAN-IP",u.wan_ip||"–"],["Leistung",nf(u.power_w,1)+" W"],
    ["Uptime",upText(u.uptime_days)],["Version",u.version||"–"]]);
  const gg=$("#udm-gauges");
  if(!gg.childElementCount)["CPU","RAM","TEMP"].forEach(l=>gg.appendChild(makeGauge(l)));
  setGauge(gg.children[0],u.cpu_pct,nf(u.cpu_pct,0)+"%",gaugeColor(u.cpu_pct,true));
  setGauge(gg.children[1],u.mem_pct,nf(u.mem_pct,0)+"%",gaugeColor(u.mem_pct,true));
  setGauge(gg.children[2],clamp(u.temp_max,0,90)/90*100,nf(u.temp_max,0)+"°",gaugeColor(u.temp_max/90*100,true));
}

function updateEnergy(e){
  if(!e){return;}
  countUp($("#en-total"),e.total_power_w,0);
  $("#en-cost").textContent=nf(e.total_cost_today,2)+" € heute";
  $("#en-grid").innerHTML=[
    ["Spot",e.spot_price_eur_kwh!=null?nf(e.spot_price_eur_kwh*100,1)+" ct":"–"],
    ["Tarif",e.tariff_price_eur_kwh!=null?nf(e.tariff_price_eur_kwh*100,1)+" ct":"–"],
    ["CO₂",e.co2_intensity!=null?nf(e.co2_intensity,0):"–"]
  ].map(([k,v])=>`<div class="mini"><div class="mv">${v}</div><div class="mk">${k}</div></div>`).join("");
  const maxP=Math.max(...e.devices.map(d=>d.power_w),1);
  reconcile($("#en-bars"),e.devices,d=>d.id,()=>el("div","bar"),(n,d)=>{
    n.style.setProperty("--bc","var(--yellow)");
    setBar(n,d.name,nf(d.power_w,1)+" W",(d.power_w/maxP*100),`${nf(d.cost_eur_today,2)} € · ${nf(d.energy_kwh,2)} kWh · ${nf(d.voltage_v,0)} V`);
  });
}

function updateNetwork(net){
  if(!net){return;}
  $("#net-summary").textContent=`${net.online_count}/${net.device_count} Geräte online · Top ${net.rows.length}`;
  const maxT=Math.max(...net.rows.map(r=>r.total_mb),1);
  reconcile($("#net-bars"),net.rows,r=>r.ip||r.name,()=>el("div","bar"),(n,r)=>{
    n.style.setProperty("--bc","var(--sapphire)");
    const label=`<span class="online-dot ${r.online?'on':'off'}"></span>${r.name}
      <span class="vlan" style="background:rgba(137,180,250,.12);color:var(--${r.vlan_color})">${r.vlan||'?'}</span>`;
    setBar(n,label,nf(r.total_mb,1)+" MB",(r.total_mb/maxT*100),`v4 ${nf(r.ipv4_mb,1)} · v6 ${nf(r.ipv6_mb,1)} MB · ${r.flows} flows · ${r.ip||''}`);
  });
}

function updateDocker(cs){
  reconcile($("#dock-grid"),cs,c=>c.name,()=>el("div","dock"),(n,c)=>{
    n.className="dock "+(c.up?"up":"down");
    const hb=c.health?`<span class="dh ${c.health}">${c.health}</span>`:"";
    n.innerHTML=`<span class="dstate"></span><div><div class="dn">${c.name}</div><div class="ds">${c.status||c.state}</div></div>${hb}`;
  });
}

function updateBle(b){
  if(!b){$("#ble-summary").textContent="⏳ warte auf Daten";return;}
  $("#ble-summary").textContent=`${b.n_sources} Quellen · ${b.n_named_devices||0} benannte Geräte · ${b.sample_seconds||"?"}s Fenster`;
  const maxD=Math.max(...b.sources.map(s=>s.unique_devices||0),1);
  reconcile($("#ble-sources"),b.sources,s=>s.id,()=>el("div","bar"),(n,s)=>{
    n.style.setProperty("--bc","var(--pink)");
    setBar(n,`${s.name}`,`${nf(s.rssi_avg,0)} dBm`,((s.unique_devices||0)/maxD*100),`${s.unique_devices} Geräte · ${s.adverts} adv · best ${nf(s.rssi_best,0)} dBm`);
  });
  $("#ble-devices").innerHTML=(b.named_devices||[]).map(dv=>{
    const r=dv.best_rssi, cls=r>-70?"":r>-90?"warn":"bad";
    return `<span class="chip ${cls}"><span class="led"></span>${dv.name} ${nf(r,0)}</span>`;
  }).join("");
}

/* ── pending (only if a house is live:false) ── */
function renderPending(host,h){
  host.innerHTML=`<div class="grid"><div class="card wide" style="--accent:var(--teal)"><div class="pending">
    <div class="pico">${SVGICON("bridge")}</div><span class="phase-badge">MQTT-BRIDGE</span>
    <h3>${h.name} · ${h.who}</h3><p>Wartet auf die read-only MQTT-Bridge.</p></div></div></div>`;
}

/* ── toasts ── */
function toast(name,status){
  const t=el("div","toast "+status);
  const word={up:"wieder ONLINE",stale:"wird STALE",down:"ist DOWN"}[status]||status;
  t.innerHTML=`<span class="tdot"></span><span><b>${name}</b> ${word}</span>`;
  $("#toasts").appendChild(t);
  setTimeout(()=>{t.classList.add("out");setTimeout(()=>t.remove(),400);},5200);
}

/* ── clock + age ticker ── */
function tick(){
  const now=new Date();
  $("#clock-time").textContent=now.toLocaleTimeString("de-DE");
  $("#clock-date").textContent=now.toLocaleDateString("de-DE",{weekday:"short",day:"2-digit",month:"short"});
  const nowE=Date.now()/1000;
  ageEls.forEach(e=>{if(!e.isConnected){ageEls.delete(e);return;}const ep=parseFloat(e.dataset.epoch);if(!isNaN(ep))e.textContent=ageText(nowE-ep);});
}
setInterval(tick,1000);

/* ── fetch loop ── */
async function poll(){
  try{
    const r=await fetch("/api/state",{cache:"no-store"});
    const d=await r.json();
    serverOffset=Date.now()/1000-d.generated_at;
    renderTop(d); renderTabs(d); renderViews(d,false);
  }catch(err){ $("#mqtt-pill").className="mqtt-pill off"; $("#mqtt-text").textContent="cockpit offline"; }
}
tick(); poll(); setInterval(poll,REFRESH);

/* ═══════════════════════════════════════════════════════════════════════════
   v2 — charts · drill-down modals · 3D tilt · particles
   ═══════════════════════════════════════════════════════════════════════════ */
const COL={green:"#a6e3a1",yellow:"#f9e2af",peach:"#fab387",red:"#f38ba8",blue:"#89b4fa",
  mauve:"#cba6f7",teal:"#94e2d5",sky:"#89dceb",sapphire:"#74c7ec",pink:"#f5c2e7",lavender:"#b4befe",maroon:"#eba0ac"};

/* metric key → presentation. dynamic keys (energy.dev.*, ble.*) derived below */
const CSPEC={
  "pi.cpu_pct":{l:"CPU",u:"%",c:COL.blue,g:"Pi"},
  "pi.cpu_temp_c":{l:"CPU-Temp",u:"°C",c:COL.peach,g:"Pi"},
  "pi.mem_pct":{l:"RAM",u:"%",c:COL.mauve,g:"Pi"},
  "pi.disk_pct":{l:"Disk",u:"%",c:COL.lavender,g:"Pi"},
  "pi.swap_pct":{l:"Swap",u:"%",c:COL.maroon,g:"Pi"},
  "pi.load_1m":{l:"Load 1m",u:"",c:COL.sky,g:"Pi",d:2},
  "pi.health_score":{l:"Health-Score",u:"",c:COL.green,g:"Pi"},
  "pi.nvme_composite_temp_c":{l:"NVMe-Temp",u:"°C",c:COL.peach,g:"Pi"},
  "pi.sd_wear_pct":{l:"SD-Wear",u:"%",c:COL.yellow,g:"Pi"},
  "pi.net_rx_mbs":{l:"Netz ↓",u:"MB/s",c:COL.teal,g:"Pi",d:2},
  "pi.net_tx_mbs":{l:"Netz ↑",u:"MB/s",c:COL.sapphire,g:"Pi",d:2},
  "udm.clients":{l:"Clients",u:"",c:COL.teal,g:"UDM"},
  "udm.temp_max":{l:"UDM-Temp",u:"°C",c:COL.peach,g:"UDM"},
  "udm.mem_pct":{l:"UDM-RAM",u:"%",c:COL.mauve,g:"UDM"},
  "udm.cpu_pct":{l:"UDM-CPU",u:"%",c:COL.blue,g:"UDM"},
  "udm.power_w":{l:"UDM-Leistung",u:"W",c:COL.yellow,g:"UDM",d:1},
  "energy.total_power_w":{l:"Gesamt-Leistung",u:"W",c:COL.yellow,g:"Energie"},
  "energy.spot_price_eur_kwh":{l:"Spot-Preis",u:"€/kWh",c:COL.green,g:"Energie",d:3},
  "energy.co2_intensity":{l:"Netz-CO₂",u:"g/kWh",c:COL.overlay1||"#7f849c",g:"Energie"},
  "energy.total_cost_today":{l:"Kosten heute",u:"€",c:COL.peach,g:"Energie",d:2},
  "net.online":{l:"Geräte online",u:"",c:COL.sapphire,g:"Netzwerk"},
  "net.total_mb":{l:"Traffic-Summe",u:"MB",c:COL.blue,g:"Netzwerk"},
  "solar.pv_w":{l:"PV-Leistung",u:"W",c:COL.yellow,g:"Solar"},
  "solar.house_w":{l:"Hausverbrauch",u:"W",c:COL.blue,g:"Solar"},
  "solar.battery_soc":{l:"Batterie SoC",u:"%",c:COL.green,g:"Solar"},
  "solar.battery_power_w":{l:"Batterie-Leistung",u:"W",c:COL.teal,g:"Solar",d:0},
  "solar.grid_feed_w":{l:"Einspeisung",u:"W",c:COL.peach,g:"Solar"},
  "solar.inverter_ac_w":{l:"Wechselrichter AC",u:"W",c:COL.mauve,g:"Solar"},
  "solar.efficiency":{l:"WR-Effizienz",u:"%",c:COL.sky,g:"Solar",d:1},
  "solar.daily_pv_kwh":{l:"PV-Ertrag heute",u:"kWh",c:COL.yellow,g:"Solar",d:1},
  "solar.daily_consume_kwh":{l:"Verbrauch heute",u:"kWh",c:COL.blue,g:"Solar",d:1},
  "solar.daily_feed_kwh":{l:"Einspeisung heute",u:"kWh",c:COL.peach,g:"Solar",d:1},
  "solar.daily_grid_kwh":{l:"Netzbezug heute",u:"kWh",c:COL.red,g:"Solar",d:1},
  "solar.autarky":{l:"Autarkie heute",u:"%",c:COL.green,g:"Solar",d:0},
  "sec.live_mbits":{l:"WAN-Durchsatz",u:"Mbit/s",c:COL.sapphire,g:"Sicherheit",d:1},
  "sec.total_gb":{l:"Traffic gesamt",u:"GB",c:COL.blue,g:"Sicherheit",d:1},
  "sec.host_count":{l:"Aktive Hosts",u:"",c:COL.sky,g:"Sicherheit"},
  "sec.v6_share":{l:"IPv6-Anteil",u:"%",c:COL.mauve,g:"Sicherheit",d:1},
  "sec.nd_block_pct":{l:"NextDNS blockiert",u:"%",c:COL.red,g:"Sicherheit",d:1},
  "snmp.in_mbits":{l:"Ports ↓ Summe",u:"Mbit/s",c:COL.sapphire,g:"UDM",d:1},
  "snmp.out_mbits":{l:"Ports ↑ Summe",u:"Mbit/s",c:COL.teal,g:"UDM",d:1},
  "snmp.ports_up":{l:"Ports aktiv",u:"",c:COL.green,g:"UDM"},
};
function specFor(key){
  if(CSPEC[key])return CSPEC[key];
  if(key.startsWith("energy.dev.")){return {l:"⚡ "+key.split(".").pop(),u:"W",c:COL.yellow,g:"Energie",d:1};}
  if(key.startsWith("ble.")){const p=key.split(".");
    if(p[2]==="dev")return {l:"BLE "+p[1]+" Geräte",u:"",c:COL.pink,g:"BLE"};
    return {l:"BLE "+p[1]+" RSSI",u:"dBm",c:COL.mauve,g:"BLE",d:0};}
  return {l:key,u:"",c:COL.blue,g:"Sonstige"};
}
const GORDER=["Solar","Energie","Sicherheit","Pi","UDM","Netzwerk","BLE","Sonstige"];

/* client mirror of backend extract_metrics → live current values (4s) */
function extractMetrics(h){
  const m={},pi=h.pi,u=h.udm,e=h.energy,n=h.network,b=h.ble;
  if(pi)["cpu_pct","cpu_temp_c","mem_pct","disk_pct","load_1m","health_score","net_rx_mbs","net_tx_mbs","nvme_composite_temp_c","sd_wear_pct","swap_pct"].forEach(k=>{if(typeof pi[k]==="number")m["pi."+k]=pi[k];});
  if(u)["cpu_pct","mem_pct","temp_max","clients","power_w"].forEach(k=>{if(typeof u[k]==="number")m["udm."+k]=u[k];});
  if(e){if(typeof e.total_power_w==="number")m["energy.total_power_w"]=e.total_power_w;
    ["spot_price_eur_kwh","tariff_price_eur_kwh","co2_intensity","total_cost_today"].forEach(k=>{if(typeof e[k]==="number")m["energy."+k]=e[k];});
    (e.devices||[]).forEach(d=>{if(typeof d.power_w==="number")m["energy.dev."+d.id]=d.power_w;});}
  if(n){m["net.online"]=n.online_count;m["net.total_mb"]=Math.round((n.rows||[]).reduce((a,r)=>a+r.total_mb,0));}
  if(b)(b.sources||[]).forEach(s=>{if(typeof s.unique_devices==="number")m["ble."+s.id+".dev"]=s.unique_devices;if(typeof s.rssi_avg==="number")m["ble."+s.id+".rssi"]=s.rssi_avg;});
  const sol=h.solar;
  if(sol){["pv_w","house_w","battery_soc","battery_power_w","grid_feed_w","inverter_ac_w","efficiency"].forEach(k=>{const v=(sol.now||{})[k];if(typeof v==="number")m["solar."+k]=v;});
    ["pv_kwh","consume_kwh","feed_kwh","grid_kwh"].forEach(k=>{const v=(sol.daily||{})[k];if(typeof v==="number")m["solar.daily_"+k]=v;});
    if(typeof sol.autarky_today_pct==="number")m["solar.autarky"]=sol.autarky_today_pct;}
  const sc=h.security;
  if(sc)["live_mbits","total_gb","host_count","nd_block_pct","v6_share"].forEach(k=>{if(typeof sc[k]==="number")m["sec."+k]=sc[k];});
  const sn=h.snmp;
  if(sn&&sn.ports&&sn.ports.length){
    m["snmp.in_mbits"]=+sn.ports.reduce((a,p)=>a+(p.in_mbits||0),0).toFixed(2);
    m["snmp.out_mbits"]=+sn.ports.reduce((a,p)=>a+(p.out_mbits||0),0).toFixed(2);
    m["snmp.ports_up"]=sn.ports.filter(p=>p.oper==="up").length;
  }
  return m;
}

/* ── history data ── */
let histData={}, histHouse=null;
async function fetchHistory(house){
  try{
    const r=await fetch("/api/history?house="+house,{cache:"no-store"});
    const d=await r.json(); histData=d.series||{}; histHouse=house;
    if(builtHouse===house) updateCharts(window._last);
  }catch(e){}
}

/* ── canvas sparkline ── */
function hex(c,a){ // append alpha to #rrggbb
  const n=Math.round(clamp(a,0,1)*255).toString(16).padStart(2,"0"); return c+n;
}
function drawSpark(canvas,pts,color,grow){
  const dpr=Math.min(window.devicePixelRatio||1,2);
  const w=canvas.clientWidth||200,h=canvas.clientHeight||60;
  canvas.width=w*dpr;canvas.height=h*dpr;
  const ctx=canvas.getContext("2d");ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  if(!pts||pts.length<2){ctx.strokeStyle=hex(color,.25);ctx.beginPath();ctx.moveTo(4,h/2);ctx.lineTo(w-4,h/2);ctx.stroke();return;}
  const g=grow==null?1:grow;
  const N=Math.max(2,Math.floor(pts.length*g));
  const use=pts.slice(0,N);
  const xs=use.map(p=>p[0]),ys=use.map(p=>p[1]);
  let mn=Math.min(...ys),mx=Math.max(...ys);if(mn===mx){mn-=1;mx+=1;}
  const pad=5,x0=xs[0],xr=(xs[xs.length-1]-x0)||1;
  const X=t=>pad+(t-x0)/xr*(w-2*pad),Y=v=>h-pad-(v-mn)/(mx-mn)*(h-2*pad);
  const grd=ctx.createLinearGradient(0,0,0,h);grd.addColorStop(0,hex(color,.42));grd.addColorStop(1,hex(color,0));
  ctx.beginPath();ctx.moveTo(X(xs[0]),Y(ys[0]));for(let i=1;i<use.length;i++)ctx.lineTo(X(xs[i]),Y(ys[i]));
  ctx.lineTo(X(xs[xs.length-1]),h-pad);ctx.lineTo(X(xs[0]),h-pad);ctx.closePath();ctx.fillStyle=grd;ctx.fill();
  ctx.beginPath();ctx.moveTo(X(xs[0]),Y(ys[0]));for(let i=1;i<use.length;i++)ctx.lineTo(X(xs[i]),Y(ys[i]));
  ctx.strokeStyle=color;ctx.lineWidth=1.7;ctx.lineJoin="round";ctx.shadowColor=color;ctx.shadowBlur=7;ctx.stroke();ctx.shadowBlur=0;
  const lx=X(xs[xs.length-1]),ly=Y(ys[ys.length-1]);
  ctx.beginPath();ctx.arc(lx,ly,3,0,7);ctx.fillStyle=color;ctx.shadowColor=color;ctx.shadowBlur=10;ctx.fill();ctx.shadowBlur=0;
  ctx.beginPath();ctx.arc(lx,ly,5.5,0,7);ctx.strokeStyle=hex(color,.4);ctx.lineWidth=1;ctx.stroke();
}

/* ── charts section (per house) ── */
function chartKeysForHouse(){
  const keys=Object.keys(histData);
  // also include live metric keys not yet in history (so tiles appear immediately)
  const live=window._last?extractMetrics(window._last.houses.find(h=>h.key===activeHouse)||{}):{};
  Object.keys(live).forEach(k=>{if(!keys.includes(k))keys.push(k);});
  keys.sort((a,b)=>{const ga=GORDER.indexOf(specFor(a).g),gb=GORDER.indexOf(specFor(b).g);return ga-gb||a.localeCompare(b);});
  return keys;
}
function updateCharts(d){
  const host=$("#charts-host"); if(!host)return;
  const h=d.houses.find(x=>x.key===activeHouse); if(!h)return;
  const live=extractMetrics(h);
  const keys=chartKeysForHouse();
  reconcile(host,keys,k=>k,
    (k)=>{const sp=specFor(k);const t=el("div","chart-tile clickable");
      t.innerHTML=`<div class="cth"><span class="ctname">${sp.l}</span><span class="ctval" data-val="0">–</span></div>
        <canvas></canvas><div class="cth" style="margin-top:3px"><span class="ctsub">6 h</span><span class="ctrend flat" style="margin-left:auto">–</span></div>`;
      t.onclick=()=>openGroupModal(specFor(k).g,k);
      return t;},
    (t,k)=>{const sp=specFor(k),ser=histData[k]||[];
      const cv=live[k]!=null?live[k]:(ser.length?ser[ser.length-1][1]:null);
      const vnode=$(".ctval",t);vnode.style.color=sp.c;
      if(cv!=null)countUp(vnode,cv,sp.d||0,sp.u?(" "+sp.u):"");else vnode.textContent="–";
      const cv2=drawSpark($("canvas",t),ser,sp.c, t._drawn?1:undefined);t._drawn=true;
      // trend
      const tr=$(".ctrend",t);
      if(ser.length>2){const first=ser[0][1],last=ser[ser.length-1][1],dp=first!==0?((last-first)/Math.abs(first)*100):0;
        const dir=Math.abs(dp)<3?"flat":dp>0?"up":"down";tr.className="ctrend "+dir;
        tr.textContent=(dp>0?"▲":dp<0?"▼":"→")+" "+nf(Math.abs(dp),0)+"%";}
      else{tr.className="ctrend flat";tr.textContent="sammle…";}
    });
}

/* ── big chart (modal) with hover + animated pulse ── */
let modalRAF=null;
function drawBigChart(canvas,pts,color,tipEl){
  const dpr=Math.min(window.devicePixelRatio||1,2);
  function render(hoverX){
    const w=canvas.clientWidth,h=canvas.clientHeight;
    canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext("2d");ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    if(!pts||pts.length<2){ctx.fillStyle="#7f849c";ctx.font="12px monospace";ctx.fillText("sammle Daten…",w/2-40,h/2);return;}
    const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);let mn=Math.min(...ys),mx=Math.max(...ys);if(mn===mx){mn-=1;mx+=1;}
    const padL=44,padR=10,padT=14,padB=22,x0=xs[0],xr=(xs[xs.length-1]-x0)||1;
    const X=t=>padL+(t-x0)/xr*(w-padL-padR),Y=v=>h-padB-(v-mn)/(mx-mn)*(h-padT-padB);
    // grid + y labels
    ctx.strokeStyle="rgba(180,190,254,.08)";ctx.fillStyle="#6c7086";ctx.font="10px ui-monospace,monospace";ctx.lineWidth=1;
    for(let i=0;i<=4;i++){const v=mn+(mx-mn)*i/4,y=Y(v);ctx.beginPath();ctx.moveTo(padL,y);ctx.lineTo(w-padR,y);ctx.stroke();
      ctx.fillText(nf(v,(mx-mn)<5?2:0),4,y+3);}
    // area + line
    const grd=ctx.createLinearGradient(0,padT,0,h-padB);grd.addColorStop(0,hex(color,.4));grd.addColorStop(1,hex(color,0));
    ctx.beginPath();ctx.moveTo(X(xs[0]),Y(ys[0]));for(let i=1;i<pts.length;i++)ctx.lineTo(X(xs[i]),Y(ys[i]));
    ctx.lineTo(X(xs[xs.length-1]),h-padB);ctx.lineTo(X(xs[0]),h-padB);ctx.closePath();ctx.fillStyle=grd;ctx.fill();
    ctx.beginPath();ctx.moveTo(X(xs[0]),Y(ys[0]));for(let i=1;i<pts.length;i++)ctx.lineTo(X(xs[i]),Y(ys[i]));
    ctx.strokeStyle=color;ctx.lineWidth=2;ctx.lineJoin="round";ctx.shadowColor=color;ctx.shadowBlur=9;ctx.stroke();ctx.shadowBlur=0;
    // pulsing endpoint
    const lx=X(xs[xs.length-1]),ly=Y(ys[ys.length-1]);const t=(Date.now()%2000)/2000,pr=3+Math.sin(t*6.283)*1.5;
    ctx.beginPath();ctx.arc(lx,ly,pr+5,0,7);ctx.fillStyle=hex(color,.15);ctx.fill();
    ctx.beginPath();ctx.arc(lx,ly,3.2,0,7);ctx.fillStyle=color;ctx.shadowColor=color;ctx.shadowBlur=12;ctx.fill();ctx.shadowBlur=0;
    // hover crosshair
    if(hoverX!=null){
      let bi=0,bd=1e18;for(let i=0;i<pts.length;i++){const dx=Math.abs(X(xs[i])-hoverX);if(dx<bd){bd=dx;bi=i;}}
      const hx=X(xs[bi]),hy=Y(ys[bi]);
      ctx.strokeStyle="rgba(205,214,244,.25)";ctx.beginPath();ctx.moveTo(hx,padT);ctx.lineTo(hx,h-padB);ctx.stroke();
      ctx.beginPath();ctx.arc(hx,hy,4,0,7);ctx.fillStyle="#cdd6f4";ctx.fill();
      if(tipEl){const dt=new Date(xs[bi]*1000);tipEl.classList.add("on");
        tipEl.style.left=hx+"px";tipEl.style.top=hy+"px";
        tipEl.textContent=nf(ys[bi],2)+"  ·  "+dt.toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit"});}
    }else if(tipEl)tipEl.classList.remove("on");
  }
  canvas._render=render; render(null);
  if(modalRAF)cancelAnimationFrame(modalRAF);
  (function loop(){render(canvas._hoverX);modalRAF=requestAnimationFrame(loop);})();
  canvas.onmousemove=ev=>{const r=canvas.getBoundingClientRect();canvas._hoverX=ev.clientX-r.left;};
  canvas.onmouseleave=()=>{canvas._hoverX=null;};
}

/* ── drill-down modal ── */
const GROUP_META={pi:{icon:"cpu",title:"Raspberry Pi",accent:"var(--blue)"},
  udm:{icon:"shield",title:"UDM Pro SE",accent:"var(--teal)"},
  energy:{icon:"bolt",title:"Energie",accent:"var(--yellow)"},
  network:{icon:"network",title:"Netzwerk",accent:"var(--sapphire)"},
  ble:{icon:"ble",title:"BLE-Proxy-Mesh",accent:"var(--pink)"}};
function fmtVal(v){
  if(typeof v==="boolean")return v?"JA":"nein";
  if(typeof v==="number")return nf(v,Number.isInteger(v)?0:2);
  return String(v);
}
function rawGrid(obj){
  // obj flat dict OR dict-of-dicts (energy/ble)
  const vals=Object.values(obj);
  const nested=vals.length&&vals.every(v=>v&&typeof v==="object"&&!Array.isArray(v));
  if(nested){
    return Object.entries(obj).map(([sub,d])=>
      `<div class="modal-section-t">${sub}</div><div class="modal-metrics">`+
      Object.entries(d).filter(([k,v])=>typeof v!=="object").map(([k,v],i)=>
        `<div class="mm" style="animation-delay:${i*18}ms"><div class="mk">${k}</div><div class="mv">${fmtVal(v)}</div></div>`).join("")+
      `</div>`).join("");
  }
  return `<div class="modal-metrics">`+Object.entries(obj).filter(([k,v])=>typeof v!=="object").map(([k,v],i)=>
    `<div class="mm" style="animation-delay:${i*14}ms"><div class="mk">${k}</div><div class="mv">${fmtVal(v)}</div></div>`).join("")+`</div>`;
}
function openModal(group,focusKey){
  const h=window._last.houses.find(x=>x.key===activeHouse);if(!h)return;
  const meta=GROUP_META[group]||GROUP_META.pi;
  const raw=(h.raw||{})[group];
  // chart keys of this group present in history/live
  const keys=chartKeysForHouse().filter(k=>{const g=specFor(k).g.toLowerCase();
    return group==="pi"?g==="pi":group==="udm"?g==="udm":group==="energy"?g==="energie":group==="ble"?g==="ble":group==="network"?g==="netzwerk":false;});
  let focus=focusKey&&keys.includes(focusKey)?focusKey:keys[0];
  const ov=el("div","modal-overlay");
  ov.style.setProperty("--accent",meta.accent);
  ov.innerHTML=`<div class="modal">
    <div class="modal-head"><div class="mi">${SVGICON(meta.icon)}</div>
      <div><h2>${meta.title}</h2><div class="msub">${h.name} · Klick auf einen Wert wechselt den Plot</div></div>
      <button class="modal-close" aria-label="schließen">✕</button></div>
    <div class="modal-body">
      <div class="chart-switch" style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:6px"></div>
      <div class="modal-hero-chart"><canvas></canvas><div class="chart-tip"></div></div>
      <div class="raw-wrap"></div>
    </div></div>`;
  document.body.appendChild(ov);
  const canvas=$("canvas",ov),tip=$(".chart-tip",ov),sw=$(".chart-switch",ov);
  function drawFocus(){
    keys.forEach(k=>{const b=$(`[data-k="${k}"]`,sw);if(b)b.classList.toggle("on",k===focus);});
    const sp=specFor(focus);ov.style.setProperty("--accent",sp.c);
    drawBigChart(canvas,histData[focus]||[],sp.c,tip);
  }
  sw.innerHTML=keys.map(k=>{const sp=specFor(k);return `<span class="db" data-k="${k}" style="cursor:pointer;font-family:var(--mono);font-size:.66rem;padding:5px 10px;border-radius:9px;background:var(--card-bg);border:1px solid var(--card-brd)">${sp.l}</span>`;}).join("");
  sw.querySelectorAll("[data-k]").forEach(b=>b.onclick=()=>{focus=b.dataset.k;drawFocus();});
  // decorate the selected switch chip
  const style=document.createElement("style");style.textContent=".chart-switch .db.on{border-color:var(--card-brd-hi)!important;color:var(--text)!important;background:linear-gradient(180deg,rgba(180,190,254,.14),rgba(49,50,68,.4))!important}";ov.appendChild(style);
  $(".raw-wrap",ov).innerHTML=raw?(`<div class="modal-section-t">Alle Sensorwerte</div>`+rawGrid(raw)):"";
  if(focus)drawFocus();
  function close(){ov.classList.add("closing");if(modalRAF){cancelAnimationFrame(modalRAF);modalRAF=null;}setTimeout(()=>ov.remove(),240);}
  $(".modal-close",ov).onclick=close;
  ov.onclick=e=>{if(e.target===ov)close();};
  document.addEventListener("keydown",function esc(e){if(e.key==="Escape"){close();document.removeEventListener("keydown",esc);}});
}

/* service drill-down (simpler) */
function openServiceModal(svc){
  const ov=el("div","modal-overlay");ov.style.setProperty("--accent","var(--mauve)");
  const rows=[["Status",svc.status],["Verfügbarkeit",svc.avail||"—"],["Alter",svc.age_sec!=null?ageText(svc.age_sec):"—"],["Haus",svc.house],["Key",svc.key]];
  ov.innerHTML=`<div class="modal"><div class="modal-head"><div class="mi">${SVGICON(svc.icon)}</div>
    <div><h2>${svc.label}</h2><div class="msub">${svc.blurb}</div></div><button class="modal-close">✕</button></div>
    <div class="modal-body"><div class="modal-metrics">${rows.map((r,i)=>`<div class="mm" style="animation-delay:${i*20}ms"><div class="mk">${r[0]}</div><div class="mv" style="font-size:.92rem">${r[1]}</div></div>`).join("")}</div></div></div>`;
  document.body.appendChild(ov);
  function close(){ov.classList.add("closing");setTimeout(()=>ov.remove(),240);}
  $(".modal-close",ov).onclick=close;ov.onclick=e=>{if(e.target===ov)close();};
}

/* ── 3D tilt + glare (delegated) ── */
function initTilt(){
  const host=$("#views");
  host.addEventListener("mousemove",e=>{
    const card=e.target.closest(".card");if(!card)return;
    const r=card.getBoundingClientRect();const px=(e.clientX-r.left)/r.width,py=(e.clientY-r.top)/r.height;
    const rx=(py-.5)*-6,ry=(px-.5)*8;
    card.style.transform=`rotateX(${rx}deg) rotateY(${ry}deg) translateZ(0)`;
    card.classList.add("tilt");card.style.setProperty("--gx",(px*100)+"%");card.style.setProperty("--gy",(py*100)+"%");
  });
  host.addEventListener("mouseleave",e=>{},true);
  host.addEventListener("mouseout",e=>{const card=e.target.closest(".card");
    if(card&&!card.contains(e.relatedTarget)){card.style.transform="";card.classList.remove("tilt");}});
}

/* ── particle constellation background ── */
function initParticles(){
  if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;
  const cv=document.createElement("canvas");cv.id="bg-particles";document.body.appendChild(cv);
  const ctx=cv.getContext("2d");let W,H,parts=[];const dpr=Math.min(window.devicePixelRatio||1,1.5);
  function resize(){W=cv.width=innerWidth*dpr;H=cv.height=innerHeight*dpr;cv.style.width=innerWidth+"px";cv.style.height=innerHeight+"px";
    const n=Math.min(70,Math.floor(innerWidth*innerHeight/26000));parts=[];
    for(let i=0;i<n;i++)parts.push({x:Math.random()*W,y:Math.random()*H,vx:(Math.random()-.5)*.12*dpr,vy:(Math.random()-.5)*.12*dpr,r:(Math.random()*1.6+.6)*dpr});}
  const PC=["203,166,247","137,180,250","148,226,213","245,194,231"];
  function frame(){
    ctx.clearRect(0,0,W,H);
    for(const p of parts){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>W)p.vx*=-1;if(p.y<0||p.y>H)p.vy*=-1;}
    for(let i=0;i<parts.length;i++){for(let j=i+1;j<parts.length;j++){
      const a=parts[i],b=parts[j],dx=a.x-b.x,dy=a.y-b.y,dd=dx*dx+dy*dy,md=(130*dpr)**2;
      if(dd<md){const al=(1-dd/md)*.16;ctx.strokeStyle=`rgba(180,190,254,${al})`;ctx.lineWidth=dpr*.5;
        ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}}}
    for(let i=0;i<parts.length;i++){const p=parts[i],c=PC[i%PC.length];
      ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,7);ctx.fillStyle=`rgba(${c},.5)`;ctx.fill();}
    requestAnimationFrame(frame);
  }
  addEventListener("resize",resize);resize();frame();
}

/* ═══════════════════════════════════════════════════════════════════════════
   v3 — Solar · Internet & Security · exhaustive sensor explorer
   ═══════════════════════════════════════════════════════════════════════════ */

/* group → modal dispatcher (charts route here) */
function openGroupModal(g,focusKey){
  g=(g||"").toLowerCase();
  if(g==="solar")return openSolarModal(focusKey);
  if(g==="sicherheit")return openSecurityModal(focusKey);
  const map={pi:"pi",udm:"udm",energie:"energy",netzwerk:"network",ble:"ble"};
  openModal(map[g]||"pi",focusKey);
}

/* ── Solar panel ─────────────────────────────────────────────────────────── */
const socColor=s=>s>=60?"var(--green)":s>=30?"var(--yellow)":"var(--red)";
function flowNode(id,ic,label,color){
  return `<div class="sf-node" id="${id}"><div class="sf-ic" style="color:${color}">${SVGICON(ic)}</div>
    <div class="sf-body"><span class="sf-v" data-val="0">–</span><span class="sf-dir"></span></div>
    <div class="sf-l">${label}</div></div>`;
}
function updateSolar(sol){
  const hint=$("#sol-hint");
  if(!sol){ if(hint)hint.textContent="⏳ warte auf Solar-Daten…"; return; }
  const now=sol.now||{}, daily=sol.daily||{}, txt=sol.text||{};
  // rings
  const soc=now.battery_soc;
  setRing("sol-soc-ring",soc,socColor(soc)); const scn=$("#sol-soc");
  if(scn){scn.style.color=socColor(soc); if(soc!=null)countUp(scn,soc,0,"%"); else scn.textContent="–";}
  const aut=sol.autarky_today_pct;
  setRing("sol-aut-ring",aut,"var(--green)"); const an=$("#sol-aut");
  if(an){an.style.color="var(--green)"; if(aut!=null)countUp(an,aut,0,"%"); else an.textContent="–";}
  // flow nodes
  const flow=$("#sol-flow");
  if(!flow._init){flow.innerHTML=
    flowNode("sf-pv","sun","PV-Erzeugung","var(--yellow)")+`<div class="sf-arrow">→</div>`+
    flowNode("sf-house","box","Hausverbrauch","var(--blue)")+`<div class="sf-arrow">→</div>`+
    flowNode("sf-bat","battery","Batterie","var(--green)")+`<div class="sf-arrow">→</div>`+
    flowNode("sf-grid","bolt","Netz","var(--peach)");
    flow._init=true;}
  const setNode=(id,val,dir,color)=>{const n=$("#"+id);if(!n)return;
    const v=$(".sf-v",n);v.style.color=color; if(val!=null)countUp(v,Math.abs(val),0," W");else v.textContent="–";
    $(".sf-dir",n).textContent=dir; $(".sf-ic",n).style.color=color;};
  setNode("sf-pv",now.pv_w,now.pv_w>2?"▲ erzeugt":"— Nacht","var(--yellow)");
  setNode("sf-house",now.house_w,"▼ Verbrauch","var(--blue)");
  const bp=now.battery_power_w;
  setNode("sf-bat",bp,bp>20?`▼ lädt · ${nf(soc,0)}%`:bp<-20?`▲ entlädt · ${nf(soc,0)}%`:`● ${nf(soc,0)}%`,
          bp>20?"var(--green)":bp<-20?"var(--teal)":"var(--overlay1)");
  const gf=now.grid_feed_w;
  setNode("sf-grid",gf,gf>20?"▲ Einspeisung":(daily.grid_kwh?"▼ Bezug":"— neutral"),gf>20?"var(--peach)":"var(--sapphire)");
  // daily energy minis
  const dl=[["PV-Ertrag",daily.pv_kwh,"var(--yellow)"],["Verbrauch",daily.consume_kwh,"var(--blue)"],
    ["Einspeisung",daily.feed_kwh,"var(--peach)"],["Netzbezug",daily.grid_kwh,"var(--red)"],
    ["Akku geladen",daily.charge_kwh,"var(--green)"],["Akku entladen",daily.discharge_kwh,"var(--teal)"]];
  $("#sol-daily").innerHTML=dl.map(([k,v,c])=>
    `<div class="mini"><div class="mv" style="color:${c}">${v!=null?nf(v,1):"–"}<span class="mun">kWh</span></div><div class="mk">${k}</div></div>`).join("");
  // strings
  const st=sol.strings||[];
  const maxS=Math.max(...st.map(s=>s.power_w||0),1);
  reconcile($("#sol-strings"),st,s=>s.name,()=>el("div","bar"),(n,s)=>{
    n.style.setProperty("--bc","var(--yellow)");
    setBar(n,`☀️ ${s.name}`,nf(s.power_w,0)+" W",((s.power_w||0)/maxS*100),`${nf(s.voltage_v,1)} V · ${nf(s.current_a,2)} A`);
  });
  // status chips
  const chips=[];
  if(now.efficiency!=null)chips.push(["WR-Effizienz "+nf(now.efficiency,1)+"%",now.efficiency>=95?"":"warn"]);
  if(now.peak_today_w!=null)chips.push(["Peak heute "+nf(now.peak_today_w/1000,1)+" kW",""]);
  if(txt.grid_status)chips.push([txt.grid_status,txt.grid_status.includes("On-grid")?"":"warn"]);
  if(txt.inverter_status)chips.push([txt.inverter_status.split(",")[0],""]);
  if(txt.pv_link)chips.push([txt.pv_link,""]);
  if(now.battery_cap_wh)chips.push([`Kapazität ${nf(now.battery_cap_wh/1000,1)} kWh`,""]);
  $("#sol-chips").innerHTML=chips.map(([l,c])=>`<span class="chip ${c}"><span class="led"></span>${l}</span>`).join("");
  if(hint)hint.textContent=txt.battery_hint||"";
}

/* solar drill-down modal */
function openSolarModal(focusKey){
  const h=window._last.houses.find(x=>x.key===activeHouse);if(!h||!h.solar)return;
  const keys=chartKeysForHouse().filter(k=>specFor(k).g==="Solar");
  const s=h.solar,now=s.now||{},life=s.lifetime||{},txt=s.text||{};
  const raw={};
  const put=(o,pre)=>Object.entries(o||{}).forEach(([k,v])=>{if(v!=null&&typeof v!=="object")raw[pre+k]=v;});
  put(now,"jetzt · ");put(s.daily,"heute · ");put(life,"gesamt · ");put(txt,"status · ");
  chartModal({icon:"sun",title:"Solar · Huawei PV & Speicher",sub:`${h.name} · EMMA · LUNA2000 · SUN2000`,
    accent:"var(--yellow)",keys,focusKey,raw,rawTitle:"Alle Solar-Werte"});
}

/* ── generic chart modal (switch chips + big chart + raw grid) ───────────── */
function chartModal({icon,title,sub,accent,keys,focusKey,raw,rawTitle}){
  let focus=focusKey&&keys.includes(focusKey)?focusKey:keys[0];
  const ov=el("div","modal-overlay");ov.style.setProperty("--accent",accent||"var(--mauve)");
  ov.innerHTML=`<div class="modal">
    <div class="modal-head"><div class="mi">${SVGICON(icon)}</div>
      <div><h2>${title}</h2><div class="msub">${sub||""}</div></div>
      <button class="modal-close">✕</button></div>
    <div class="modal-body">
      ${keys.length?`<div class="chart-switch"></div><div class="modal-hero-chart"><canvas></canvas><div class="chart-tip"></div></div>`:""}
      <div class="raw-wrap"></div></div></div>`;
  document.body.appendChild(ov);
  const canvas=$("canvas",ov),tip=$(".chart-tip",ov),sw=$(".chart-switch",ov);
  if(sw){
    sw.innerHTML=keys.map(k=>`<span class="db" data-k="${k}">${specFor(k).l}</span>`).join("");
    sw.querySelectorAll("[data-k]").forEach(b=>b.onclick=()=>{focus=b.dataset.k;draw();});
  }
  function draw(){
    if(!canvas)return;
    keys.forEach(k=>{const b=$(`[data-k="${k}"]`,sw);if(b)b.classList.toggle("on",k===focus);});
    const sp=specFor(focus);ov.style.setProperty("--accent",sp.c);
    drawBigChart(canvas,histData[focus]||[],sp.c,tip);
  }
  if(raw)$(".raw-wrap",ov).innerHTML=`<div class="modal-section-t">${rawTitle||"Werte"}</div>`+rawGrid(raw);
  if(keys.length)draw();
  wireClose(ov);
  return ov;
}
function wireClose(ov){
  function close(){ov.classList.add("closing");if(modalRAF){cancelAnimationFrame(modalRAF);modalRAF=null;}setTimeout(()=>ov.remove(),240);}
  $(".modal-close",ov).onclick=close; ov.onclick=e=>{if(e.target===ov)close();};
  document.addEventListener("keydown",function esc(e){if(e.key==="Escape"){close();document.removeEventListener("keydown",esc);}});
  return close;
}

/* ── Internet & Security panel ───────────────────────────────────────────── */
function updateSecurity(sec){
  if(!sec){return;}
  const note=$("#sec-note");
  // live minis
  const live=$("#sec-live");
  const minis=[];
  if(sec.live_mbits!=null)minis.push(["WAN","▼ "+nf(sec.live_mbits,1),"Mbit/s","var(--sapphire)"]);
  if(sec.total_gb!=null)minis.push(["Traffic",nf(sec.total_gb,1),"GB","var(--blue)"]);
  if(sec.v6_share!=null)minis.push(["IPv6",nf(sec.v6_share,0),"%","var(--mauve)"]);
  if(sec.host_count!=null)minis.push(["Hosts",nf(sec.host_count,0),"aktiv","var(--sky)"]);
  if(sec.unifi&&sec.unifi.download_mbit!=null)minis.push(["UniFi ↓",nf(sec.unifi.download_mbit,1),"Mbit/s","var(--teal)"]);
  if(sec.nd_block_pct!=null)minis.push(["NextDNS",nf(sec.nd_block_pct,1),"% blk","var(--red)"]);
  live.innerHTML=minis.map(([k,v,u,c])=>`<div class="mini"><div class="mv" style="color:${c}">${v}<span class="mun">${u}</span></div><div class="mk">${k}</div></div>`).join("");
  // top countries + services need the /api/security detail; pull it lazily
  if(sec.flow_enabled){ ensureSecDetail(); const det=secDetail[activeHouse];
    if(det&&det.flow){
      const cc=det.flow.countries||[],maxC=Math.max(...cc.map(c=>c.mb||0),1);
      reconcile($("#sec-countries"),cc.slice(0,6),c=>c.cc,()=>el("div","bar"),(n,c)=>{
        n.style.setProperty("--bc",c.foreign?"var(--peach)":"var(--green)");
        setBar(n,`${c.flag} ${c.cc}${c.foreign?' <span class="foreign">Ausland</span>':''}`,fmtMB(c.mb),((c.mb||0)/maxC*100),"");
      });
      const sv=det.flow.services||[],maxV=Math.max(...sv.map(s=>s.mb||0),1);
      reconcile($("#sec-services"),sv.slice(0,6),s=>s.name,()=>el("div","bar"),(n,s)=>{
        n.style.setProperty("--bc","var(--sapphire)");
        setBar(n,s.name,fmtMB(s.mb),((s.mb||0)/maxV*100),"");
      });
    }
  } else {
    $("#sec-countries").innerHTML=`<div class="sec-empty">flow-collector nicht aktiv — nur UniFi-WAN.<br>NetFlow auf UDM → dieser Host aktivieren.</div>`;
    $("#sec-services").innerHTML="";
  }
  // VLAN chips on the main card (from the lazy detail)
  const vl=$("#sec-vlans");
  if(vl){
    const det=secDetail[activeHouse];
    const vs=(sec.flow_enabled&&det&&det.flow&&det.flow.vlans)?det.flow.vlans.slice(0,8):[];
    vl.innerHTML=vs.map(v=>`<span class="chip"><span class="led" style="background:var(--lavender);box-shadow:0 0 7px var(--lavender)"></span>${v.name||v.id} · ${fmtMB(v.mb)}${v.hosts?` · ${v.hosts} Hosts`:""}</span>`).join("");
  }
  // NextDNS section (prominent)
  const ndhost=$("#sec-nextdns");
  if(ndhost){
    const det=secDetail[activeHouse]; const nd=det&&det.nextdns;
    if(sec.nextdns_enabled && (nd || sec.nd_block_pct!=null)){
      const pct=(nd&&nd.block_pct!=null)?nd.block_pct:sec.nd_block_pct;
      const q=(nd&&nd.queries!=null)?nd.queries:sec.nd_queries, b=(nd&&nd.blocked!=null)?nd.blocked:sec.nd_blocked;
      const blk=(nd&&nd.top_blocked)||[];
      ndhost.innerHTML=`<div class="ndx-head"><span class="ndx-ic">🛡</span><b>NextDNS</b>
        <span class="ndx-stat">${nf(q,0)} Anfragen · <span class="ndx-b">${nf(b,0)} blockiert</span> · <b>${pct!=null?nf(pct,1):'–'}%</b></span></div>
        <div class="ndx-bar"><div class="ndx-fill" style="width:${clamp(pct||0,1.5,100)}%"></div></div>
        ${blk.length?`<div class="ndx-chips">`+blk.slice(0,8).map(x=>`<span class="chip bad"><span class="led"></span>${x.domain}</span>`).join("")+`</div>`:''}`;
    } else if(sec.nextdns_enabled){
      ndhost.innerHTML=`<div class="ndx-head"><span class="ndx-ic">🛡</span><b>NextDNS</b><span class="ndx-stat">lädt…</span></div>`;
    } else { ndhost.innerHTML=""; }
  }
  const parts=[];
  parts.push(sec.flow_enabled?"🟢 flow-collector":"⚪ flow-collector aus");
  parts.push(sec.nextdns_enabled?"🟢 NextDNS":"⚪ NextDNS");
  if(sec.top_country)parts.push(`Top ${sec.top_country_flag||""} ${sec.top_country}`);
  if(sec.top_service)parts.push(`Dienst ${sec.top_service}`);
  note.innerHTML=parts.join(" · ")+' <span class="sec-more">Klick für Ziel-IPs, Länder, VLANs →</span>';
}
function fmtMB(mb){ if(mb==null)return "–"; if(mb>=1000)return nf(mb/1000,2)+" GB"; return nf(mb,0)+" MB"; }

/* security detail cache (fetched from /api/security) */
let secDetail={}, secDetailTs={};
function ensureSecDetail(force){
  const h=activeHouse; const now=Date.now();
  if(!force && secDetailTs[h] && now-secDetailTs[h]<12000) return;
  secDetailTs[h]=now;
  fetch("/api/security?house="+h,{cache:"no-store"}).then(r=>r.json()).then(d=>{
    secDetail[h]=d.security||{}; if(builtHouse===h) updateSecurity((window._last.houses.find(x=>x.key===h)||{}).security);
  }).catch(()=>{});
}
function openSecurityModal(focusKey){
  const h=window._last.houses.find(x=>x.key===activeHouse);if(!h)return;
  ensureSecDetail(true);
  const keys=chartKeysForHouse().filter(k=>specFor(k).g==="Sicherheit");
  let focus=focusKey&&keys.includes(focusKey)?focusKey:keys[0];
  const ov=el("div","modal-overlay");ov.style.setProperty("--accent","var(--sapphire)");
  ov.innerHTML=`<div class="modal modal-lg">
    <div class="modal-head"><div class="mi">${SVGICON("globe")}</div>
      <div><h2>Internet & Sicherheit</h2><div class="msub">${h.name} · GeoIP · Ziel-Länder · Top-Hosts</div></div>
      <button class="modal-close">✕</button></div>
    <div class="modal-body">
      ${keys.length?`<div class="chart-switch"></div><div class="modal-hero-chart"><canvas></canvas><div class="chart-tip"></div></div>`:""}
      <div id="sec-detail-body"><div class="sec-loading">lade GeoIP-Details…</div></div>
    </div></div>`;
  document.body.appendChild(ov);
  const canvas=$("canvas",ov),tip=$(".chart-tip",ov),sw=$(".chart-switch",ov);
  if(sw){sw.innerHTML=keys.map(k=>`<span class="db" data-k="${k}">${specFor(k).l}</span>`).join("");
    sw.querySelectorAll("[data-k]").forEach(b=>b.onclick=()=>{focus=b.dataset.k;drawF();});}
  function drawF(){if(!canvas)return;keys.forEach(k=>{const b=$(`[data-k="${k}"]`,sw);if(b)b.classList.toggle("on",k===focus);});
    const sp=specFor(focus);ov.style.setProperty("--accent",sp.c);drawBigChart(canvas,histData[focus]||[],sp.c,tip);}
  if(keys.length)drawF();
  function renderBody(){
    const d=secDetail[activeHouse]||{}; const body=$("#sec-detail-body",ov); if(!body)return;
    const F=d.flow, nd=d.nextdns, uni=d.unifi;
    let html="";
    if(F){
      html+=`<div class="modal-section-t">🌍 Top-Ziel-Länder</div><div class="sec-country-grid">`+
        (F.countries||[]).map(c=>`<div class="sec-cc ${c.foreign?'foreign':''}"><span class="cflag">${c.flag}</span>
          <span class="ccc">${c.cc}</span><span class="cmb">${fmtMB(c.mb)}</span></div>`).join("")+`</div>`;
      html+=`<div class="modal-section-t">🔌 Top-Dienste</div><div class="chips">`+
        (F.services||[]).map(s=>`<span class="chip"><span class="led"></span>${s.name} · ${fmtMB(s.mb)}</span>`).join("")+`</div>`;
      html+=`<div class="modal-section-t">📡 Top-Hosts & Auslandsziele</div><div class="sec-hosts">`+
        (F.hosts||[]).map(hst=>`<div class="sec-host"><div class="sh-top">
          <span class="sh-name">${hst.name||hst.ip}</span>
          ${hst.vlan?`<span class="vlan">${hst.vlan}</span>`:""}
          <span class="sh-tot">${fmtMB(hst.total_mb)}</span></div>
          <div class="sh-meta">${hst.top_service?`⚙ ${hst.top_service} · `:""}${hst.flows||0} flows${hst.foreign_mb?` · <span class="foreign">${fmtMB(hst.foreign_mb)} Ausland</span>`:""}</div>
          <div class="sh-dests">${(hst.countries||[]).map(c=>`<span class="sh-cc">${c.flag} ${fmtMB(c.mb)}</span>`).join("")}</div>
          <div class="sh-ips">${(hst.dests||[]).slice(0,4).map(dd=>`<span class="sh-ip">${dd.ip} · ${fmtMB(dd.mb)}</span>`).join("")}</div>
        </div>`).join("")+`</div>`;
      html+=`<div class="modal-section-t">🧩 VLANs</div><div class="barlist">`+
        (function(){const mx=Math.max(...(F.vlans||[]).map(v=>v.mb||0),1);
        return (F.vlans||[]).map(v=>`<div class="bar" style="--bc:var(--lavender)"><div class="bl">${v.name||v.id}</div>
          <div class="bv">${fmtMB(v.mb)}</div><div class="btrack"><div class="bfill" style="width:${clamp((v.mb||0)/mx*100,2,100)}%"></div></div>
          <div class="bsub">${v.hosts||0} Hosts</div></div>`).join("");})()+`</div>`;
    }
    if(nd){
      html+=`<div class="modal-section-t">🛡 NextDNS (24h)</div><div class="modal-metrics">
        <div class="mm"><div class="mk">Anfragen</div><div class="mv">${nf(nd.queries,0)}</div></div>
        <div class="mm"><div class="mk">Blockiert</div><div class="mv" style="color:var(--red)">${nf(nd.blocked,0)}</div></div>
        <div class="mm"><div class="mk">Block-Quote</div><div class="mv">${nd.block_pct!=null?nf(nd.block_pct,1)+"%":"–"}</div></div></div>`;
      if((nd.top_blocked||[]).length)html+=`<div class="modal-section-t">Meist blockiert</div><div class="chips">`+
        nd.top_blocked.map(x=>`<span class="chip bad"><span class="led"></span>${x.domain} · ${nf(x.queries,0)}</span>`).join("")+`</div>`;
    } else if(d.nextdns_enabled===false && activeHouse==="radeberg"){
      html+=`<div class="modal-section-t">🛡 NextDNS</div><div class="sec-empty">Kein API-Key hinterlegt. In <b>my.nextdns.io</b> → Account → API-Key + Profil-ID holen und als <code>NEXTDNS_API_KEY</code> / <code>NEXTDNS_PROFILE</code> setzen — dann erscheinen hier Anfragen, Block-Quote & Top-Domains.</div>`;
    }
    if(uni){
      html+=`<div class="modal-section-t">📶 UniFi WAN</div><div class="modal-metrics">
        ${uni.download_mbit!=null?`<div class="mm"><div class="mk">Download</div><div class="mv">${nf(uni.download_mbit,1)} Mbit/s</div></div>`:""}
        ${uni.upload_mbit!=null?`<div class="mm"><div class="mk">Upload</div><div class="mv">${nf(uni.upload_mbit,1)} Mbit/s</div></div>`:""}
        ${uni.wan_ip?`<div class="mm"><div class="mk">WAN-IP</div><div class="mv" style="font-size:.9rem">${uni.wan_ip}</div></div>`:""}</div>`;
    }
    if(!html)html=`<div class="sec-empty">Keine Detail-Daten verfügbar.</div>`;
    body.innerHTML=html;
  }
  renderBody();
  const iv=setInterval(()=>{if(!ov.isConnected){clearInterval(iv);return;}renderBody();},2500);
  wireClose(ov);
}

/* ── exhaustive sensor explorer ──────────────────────────────────────────── */
function updateSensors(sum,house){
  if(!sum){return;}
  countUp($("#sens-total"),sum.total,0);
  $("#sens-num").textContent=`${nf(sum.numeric,0)} numerisch · ${nf(sum.sensors,0)} sensor`;
  const bd=sum.by_domain||{};
  const top=Object.entries(bd).sort((a,b)=>b[1]-a[1]).slice(0,8);
  $("#sens-mini").innerHTML=top.map(([dom,n])=>`<span class="sdchip"><b>${n}</b> ${dom}</span>`).join("");
  // live activity ticker — most recently changed entities, click = drill-down
  const rec=$("#sens-recent");
  if(rec){
    reconcile(rec,sum.recent||[],r=>r.entity_id,
      ()=>{const d=el("div","sr clickable");d.onclick=()=>{if(d._it)openEntityModal(house,d._it);};return d;},
      (d,r)=>{d._it=r;
        const isNum=(typeof r.num==="number");
        const val=isNum?nf(r.num,Number.isInteger(r.num)?0:1):(r.state||"–");
        d.innerHTML=`<span class="sr-dot ${r.domain}"></span>
          <span class="sr-n" title="${r.entity_id}">${r.name}</span>
          <span class="sr-v">${val}${r.unit?`<span class="si-u">${r.unit}</span>`:""}</span>
          <span class="sr-t">${ageText(r.ago_sec)}</span>`;
      });
  }
}
let sensCache={};
function openSensorsModal(focusGroup){
  const h=window._last.houses.find(x=>x.key===activeHouse);if(!h)return;
  const house=activeHouse;
  const ov=el("div","modal-overlay");ov.style.setProperty("--accent","var(--lavender)");
  ov.innerHTML=`<div class="modal modal-lg">
    <div class="modal-head"><div class="mi">${SVGICON("grid")}</div>
      <div><h2>Alle Sensoren · ${h.name}</h2><div class="msub" id="sens-sub">lade Inventar…</div></div>
      <button class="modal-close">✕</button></div>
    <div class="modal-body">
      <div class="sens-search"><span class="ss-ic">${SVGICON("search")}</span>
        <input type="text" id="sens-q" placeholder="Sensor, Wert oder Raum suchen … (z. B. temperatur, batterie, wohnzimmer)"/>
        <span class="ss-count" id="sens-count"></span></div>
      <div id="sens-groups" class="sens-groups"><div class="sec-loading">lade ${h.name} Sensoren…</div></div>
    </div></div>`;
  document.body.appendChild(ov);
  const close=wireClose(ov);
  const q=$("#sens-q",ov); if(q&&q.focus)q.focus();
  // ── lazy per-sensor sparklines: fetch history only for visible rows, batched ──
  const pending=new Map(); let flushT=null;
  function schedule(){ if(!flushT) flushT=setTimeout(flush,160); }
  function flush(){
    flushT=null;
    const batch=[...pending.keys()].slice(0,40);
    if(!batch.length)return;
    const rows=batch.map(e=>{const r=pending.get(e);pending.delete(e);return [e,r];});
    fetchEntityHistory(house,batch,6).then(series=>{
      rows.forEach(([eid,row])=>{
        if(!row.isConnected)return;
        const cv=row.querySelector(".si-spark"); if(!cv)return;
        const pts=(series&&series[eid])||[];
        row._drawn=true; drawSpark(cv,pts,sparkColorFor(row),1);
        if(!pts.length)row.classList.add("no-hist");
      });
    }).catch(()=>{});
    if(pending.size)flushT=setTimeout(flush,160);
  }
  if(typeof IntersectionObserver==="function"){
    ov._sensObs=new IntersectionObserver((entries)=>{
      entries.forEach(en=>{
        if(!en.isIntersecting)return;
        const row=en.target; if(row._drawn)return;
        const eid=row.dataset.eid, cv=row.querySelector(".si-spark"); if(!cv)return;
        const cached=entHistCache[house+"|"+eid+"|6"];
        if(cached && Date.now()-cached.ts<60000){ row._drawn=true; drawSpark(cv,cached.pts,sparkColorFor(row),1); if(!cached.pts.length)row.classList.add("no-hist"); ov._sensObs.unobserve(row); return; }
        pending.set(eid,row); ov._sensObs.unobserve(row); schedule();
      });
    },{root:$(".modal",ov),rootMargin:"140px 0px"});
  }
  const _origClose=close;
  function render(data){
    const groups=(data.explorer&&data.explorer.groups)||[];
    const total=(data.explorer&&data.explorer.total)||0;
    $("#sens-sub",ov).textContent=`${nf(total,0)} Entities · ${groups.length} Gruppen · ${focusGroup?"Klima zuerst":"nach Raum"}`;
    const term=(q.value||"").trim().toLowerCase();
    let shown=0;
    const host=$("#sens-groups",ov);
    if(ov._sensObs) ov._sensObs.disconnect();   // release old row observations before rebuild
    host.innerHTML="";
    let gs=groups.slice();
    if(focusGroup==="climate")gs.sort((a,b)=>(b.name.includes("Klima")|| /grad|°/.test(b.name))-(a.name.includes("Klima")));
    gs.forEach(g=>{
      const items=g.items.filter(it=>!term ||
        (it.name||"").toLowerCase().includes(term) ||
        (it.entity_id||"").toLowerCase().includes(term) ||
        (g.name||"").toLowerCase().includes(term) ||
        String(it.state||"").toLowerCase().includes(term));
      if(!items.length)return;
      shown+=items.length;
      const sec=el("div","sens-group");
      sec.innerHTML=`<div class="sg-head">${g.is_room?"🏠 ":""}${g.name}<span class="sg-n">${items.length}</span></div>
        <div class="sg-items"></div>`;
      const box=$(".sg-items",sec);
      items.forEach(it=>{
        const isNum=(typeof it.num==="number");
        const val=isNum?nf(it.num,Number.isInteger(it.num)?0:2):(it.state||"–");
        const unit=it.unit?`<span class="si-u">${it.unit}</span>`:"";
        const d=el("div","si "+it.domain+(isNum?" num":""));
        d.dataset.eid=it.entity_id; if(isNum)d.dataset.num="1";
        d.innerHTML=`<span class="si-n" title="${it.entity_id}">${it.name||it.entity_id}</span>
          ${isNum?'<canvas class="si-spark"></canvas>':'<span class="si-spark-x"></span>'}
          <span class="si-v">${val}${unit}</span>`;
        d.onclick=()=>openEntityModal(house,it);
        box.appendChild(d);
        if(isNum && ov._sensObs) ov._sensObs.observe(d);
      });
      host.appendChild(sec);
    });
    if(!shown)host.innerHTML=`<div class="sec-empty">Nichts gefunden für „${term}".</div>`;
    $("#sens-count",ov).textContent=term?`${shown} Treffer`:`${nf(total,0)} Entities`;
  }
  function load(){
    if(sensCache[house]){render(sensCache[house]);return;}
    fetch("/api/sensors?house="+house,{cache:"no-store"}).then(r=>r.json()).then(d=>{
      sensCache[house]=d; render(d);
    }).catch(()=>{$("#sens-groups",ov).innerHTML=`<div class="sec-empty">Konnte Sensoren nicht laden.</div>`;});
  }
  let deb; q.oninput=()=>{clearTimeout(deb);deb=setTimeout(()=>{if(sensCache[house])render(sensCache[house]);},150);};
  load();
  // refresh values every 30s while open — preserve scroll position across rebuild
  const iv=setInterval(()=>{if(!ov.isConnected){clearInterval(iv);if(ov._sensObs)ov._sensObs.disconnect();return;}
    fetch("/api/sensors?house="+house,{cache:"no-store"}).then(r=>r.json()).then(d=>{
      sensCache[house]=d; var mo=$(".modal",ov), st=mo?mo.scrollTop:0; render(d); if(mo)mo.scrollTop=st;
    }).catch(()=>{});},30000);
}

/* ── Climate panel ───────────────────────────────────────────────────────── */
function tempColor(t){return t==null?"var(--overlay1)":t<18?"var(--sapphire)":t<24?"var(--green)":t<27?"var(--yellow)":"var(--peach)";}
function updateClimate(rooms){
  if(!rooms){$("#clima-grid").innerHTML=`<div class="sec-empty" style="grid-column:1/-1">⏳ warte auf Klima-Daten…</div>`;return;}
  reconcile($("#clima-grid"),rooms,r=>r.area,()=>el("div","clima"),(n,r)=>{
    const climState=(r.climate&&r.climate[0])?r.climate[0]:null;
    n.innerHTML=`<div class="cl-area">${r.area}</div>
      <div class="cl-temp" style="color:${tempColor(r.temp_avg)}">${r.temp_avg!=null?nf(r.temp_avg,1):"–"}<span>°C</span></div>
      <div class="cl-sub">${r.humid_avg!=null?`💧 ${nf(r.humid_avg,0)}%`:""}${climState?` · 🎯 ${climState.target!=null?nf(climState.target,1)+"°":climState.state}`:""}</div>
      <div class="cl-n">${r.n} Sensor${r.n===1?"":"en"}</div>`;
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   v4 — per-sensor history (every entity), entity drill-down, SNMP per-port
   ═══════════════════════════════════════════════════════════════════════════ */
const entHistCache={};   // "house|eid|hours" -> {pts:[[t,v]], ts}
function fetchEntityHistory(house,eids,hours){
  hours=hours||6; const now=Date.now(), out={}, need=[];
  eids.forEach(e=>{const c=entHistCache[house+"|"+e+"|"+hours];
    if(c && now-c.ts<60000){out[e]=c.pts;} else need.push(e);});
  if(!need.length) return Promise.resolve(out);
  const url="/api/entity_history?house="+encodeURIComponent(house)+"&hours="+hours+
            "&entities="+encodeURIComponent(need.join(","));
  return fetch(url,{cache:"no-store"}).then(r=>r.json()).then(d=>{
    const series=d.series||{};
    need.forEach(e=>{const pts=series[e]||[]; entHistCache[house+"|"+e+"|"+hours]={pts,ts:Date.now()}; out[e]=pts;});
    return out;
  }).catch(()=>out);
}
function sparkColorFor(row){
  const e=((row&&row.dataset&&row.dataset.eid)||"").toLowerCase();
  if(/temp|klima|thermo/.test(e))return COL.peach;
  if(/power|leistung|energie|energy|watt|_w$|kwh|current|strom|voltage|spannung/.test(e))return COL.yellow;
  if(/batter|akku|soc/.test(e))return COL.green;
  if(/cpu|load|mem|ram|disk|swap|nvme/.test(e))return COL.blue;
  if(/humid|feucht|co2|luft|pm/.test(e))return COL.sky;
  if(/rssi|signal|wifi|ble|dbm/.test(e))return COL.mauve;
  return COL.lavender;
}
/* per-entity drill-down with switchable range */
function openEntityModal(house,it){
  const ov=el("div","modal-overlay");ov.style.setProperty("--accent","var(--lavender)");
  const cur=(typeof it.num==="number")?nf(it.num,Number.isInteger(it.num)?0:2):(it.state||"–");
  ov.innerHTML=`<div class="modal"><div class="modal-head"><div class="mi">${SVGICON("chip")}</div>
    <div><h2>${it.name||it.entity_id}</h2><div class="msub">${it.entity_id}</div></div>
    <button class="modal-close">✕</button></div>
    <div class="modal-body">
      <div class="ent-cur"><span class="ent-v">${cur}</span><span class="ent-u">${it.unit||""}</span>
        <span class="ent-dc">${it.device_class||it.domain||""}</span></div>
      <div class="ent-range">${[["6","6 h"],["24","24 h"],["72","3 d"],["168","7 d"]].map(([h,l])=>`<span data-h="${h}"${h==="24"?' class="on"':''}>${l}</span>`).join("")}</div>
      <div class="modal-hero-chart"><canvas></canvas><div class="chart-tip"></div></div>
    </div></div>`;
  document.body.appendChild(ov);
  const canvas=$("canvas",ov),tip=$(".chart-tip",ov); let hours=24;
  const col=sparkColorFor({dataset:{eid:it.entity_id}});
  function draw(){ ov.style.setProperty("--accent",col);
    fetchEntityHistory(house,[it.entity_id],hours).then(s=>drawBigChart(canvas,s[it.entity_id]||[],col,tip)); }
  ov.querySelectorAll(".ent-range span").forEach(b=>b.onclick=()=>{
    hours=+b.dataset.h; ov.querySelectorAll(".ent-range span").forEach(x=>x.classList.toggle("on",x===b)); draw();});
  draw(); wireClose(ov);
}

/* ── SNMP per-port panel — every port gets a live sparkline ── */
const snmpHist={};      // "house|port" -> [[epoch, in+out Mbit/s], ...] rolling client buffer
const snmpLastPush={};  // house -> epoch of last stored sample
function updateSnmp(snmp){
  const host=$("#snmp-ports"); if(!host)return;
  if(!snmp||!snmp.ports||!snmp.ports.length){$("#snmp-sub").textContent="⏳ warte auf SNMP…";return;}
  const ti=snmp.ports.reduce((a,p)=>a+(p.in_mbits||0),0), to=snmp.ports.reduce((a,p)=>a+(p.out_mbits||0),0);
  $("#snmp-sub").textContent=`${snmp.model||"UDM"} · ${snmp.ports.length} Ports · Σ ↓${nf(ti,1)} ↑${nf(to,1)} Mbit/s`;
  // one history sample per backend poll (dedup by sample epoch)
  const sampleEp=Math.round(Date.now()/1000-(snmp.age_sec||0)), hk=activeHouse;
  if(snmpLastPush[hk]==null||sampleEp>snmpLastPush[hk]){
    snmpLastPush[hk]=sampleEp;
    snmp.ports.forEach(p=>{
      const k=hk+"|"+p.name, buf=snmpHist[k]||(snmpHist[k]=[]);
      buf.push([sampleEp,(p.in_mbits||0)+(p.out_mbits||0)]);
      if(buf.length>240)buf.shift();
    });
  }
  reconcile(host,snmp.ports,p=>p.name,()=>el("div","sp-row"),(n,p)=>{
    const up=p.oper==="up", tot=(p.in_mbits||0)+(p.out_mbits||0);
    if(!n._init){n.innerHTML=`<div class="sp-l"><span class="online-dot"></span><span class="sp-name"></span><span class="vlan sp-speed"></span></div>
      <canvas class="sp-spark"></canvas><div class="sp-v"></div>`;n._init=true;}
    n.classList.toggle("down",!up);
    $(".online-dot",n).className="online-dot "+(up?"on":"off");
    $(".sp-name",n).textContent=p.name;
    const spd=$(".sp-speed",n);
    if(p.speed_mbit){spd.style.display="";spd.textContent=p.speed_mbit>=1000?(p.speed_mbit/1000)+"G":p.speed_mbit+"M";}
    else spd.style.display="none";
    $(".sp-v",n).innerHTML=`<b style="color:var(--sapphire)">↓${nf(p.in_mbits,1)}</b> <b style="color:var(--teal)">↑${nf(p.out_mbits,1)}</b><span class="sp-tot">${nf(tot,1)} Mbit/s</span>`;
    drawSpark($(".sp-spark",n),snmpHist[hk+"|"+p.name]||[],up?COL.sapphire:"#6c7086",1);
  });
}
/* SNMP drill-down: summed-rate charts + raw per-port grid */
function openSnmpModal(){
  const h=window._last.houses.find(x=>x.key===activeHouse); if(!h||!h.snmp)return;
  const keys=chartKeysForHouse().filter(k=>k.startsWith("snmp."));
  const raw={};
  (h.snmp.ports||[]).forEach(p=>{raw[p.name]={status:p.oper,speed_mbit:p.speed_mbit,in_mbits:p.in_mbits,out_mbits:p.out_mbits};});
  chartModal({icon:"network",title:"UDM Ports · SNMP",sub:`${h.name} · ${h.snmp.model||"UDM"} · ${h.snmp.host||""}`,
    accent:"var(--sapphire)",keys,raw,rawTitle:"Alle Ports (live)"});
}

/* ── v2/v3/v4 init ── */
initParticles();
initTilt();
setInterval(()=>{ if(activeHouse) fetchHistory(activeHouse); }, 15000);
