const DOW = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
const DOW_SHORT = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
const MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
                'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];

const PAGE_DURATION_MS = window.PAGE_ROTATE_MS || 22000;
const FETCH_INTERVAL_MS = 12000;

/* ───── Clocks ───── */
function clock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  document.getElementById('clock-time').innerHTML = `${h}<span class="colon">:</span>${m}`;
  document.getElementById('clock-time-mini').textContent = `${h}:${m}`;
  const dateStr = `${DOW[now.getDay()]}, ${now.getDate()}. ${MONTHS[now.getMonth()]} ${now.getFullYear()}`;
  document.getElementById('clock-date').textContent = dateStr;
  document.getElementById('clock-date-mini').textContent = `${DOW_SHORT[now.getDay()]} ${String(now.getDate()).padStart(2,'0')}.${String(now.getMonth()+1).padStart(2,'0')}.`;
  const start = new Date(now.getFullYear(), 0, 1);
  const dayOfYear = Math.ceil((now - start) / 86400000);
  const totalDays = ((now.getFullYear() % 4 === 0 && now.getFullYear() % 100 !== 0) || now.getFullYear() % 400 === 0) ? 366 : 365;
  const week = (function() {
    const target = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    const dayNr = (target.getUTCDay() + 6) % 7;
    target.setUTCDate(target.getUTCDate() - dayNr + 3);
    const firstThursday = target.getTime();
    target.setUTCMonth(0, 1);
    if (target.getUTCDay() !== 4) {
      target.setUTCMonth(0, 1 + ((4 - target.getUTCDay()) + 7) % 7);
    }
    return 1 + Math.ceil((firstThursday - target.getTime()) / 604800000);
  })();
  document.getElementById('clock-sub').textContent = `Tag ${dayOfYear} von ${totalDays}  ·  KW ${week}`;
}

/* ───── Helpers ───── */
function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${DOW_SHORT[d.getDay()]} ${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.`;
}
function classifyRoomTemp(t) {
  if (t == null) return '';
  if (t > 28) return 'hot';
  if (t > 24) return 'warm';
  if (t < 19) return 'cold';
  return 'ok';
}

/* ───── Smooth number swap ───── */
function setNum(id, newText) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.textContent === newText) return;
  el.classList.add('changing');
  setTimeout(() => {
    el.textContent = newText;
    el.classList.remove('changing');
  }, 200);
}

/* ───── Weather Icon ───── */
function setWeatherIcon(cond, isNight) {
  const el = document.getElementById('weather-icon-anim');
  let html = '';
  if (isNight && cond !== 'rainy' && cond !== 'pouring' && cond !== 'snowy') {
    html = `<div class="wi-moon"><div class="moon"></div></div>`;
  } else if (cond === 'sunny') {
    let rays = '';
    for (let i = 0; i < 8; i++) {
      rays += `<div class="ray" style="transform: translateX(-50%) rotate(${i * 45}deg);"></div>`;
    }
    html = `<div class="wi-sun"><div class="rays">${rays}</div><div class="core"></div></div>`;
  } else if (cond === 'partlycloudy') {
    html = `<div class="wi-partly"><div class="sun-mini"></div><div class="cloud-shape"></div></div>`;
  } else if (cond === 'rainy' || cond === 'pouring' || cond === 'lightning-rainy') {
    let drops = '';
    for (let i = 0; i < 6; i++) {
      drops += `<div class="drop" style="left:${20 + i*10}%; top:60%; animation-delay:${i*0.15}s;"></div>`;
    }
    html = `<div class="wi-rain">${drops}<div class="cloud-shape"></div></div>`;
  } else {
    html = `<div class="wi-cloud"><div class="cloud-shape"></div></div>`;
  }
  el.innerHTML = html;
}

/* ───── Sun arc dot ───── */
function updateSunArc(sunRise, sunSet) {
  const dot = document.getElementById('sun-dot');
  if (!dot) return;
  const r = sunRise ? new Date(sunRise) : null;
  const s = sunSet ? new Date(sunSet) : null;
  if (!r || !s) return;
  const now = new Date();
  let dayR = r;
  let dayS = s;
  if (r > s) {
    dayR = new Date(r.getTime() - 86400000);
  }
  let progress = (now - dayR) / (dayS - dayR);
  if (progress < 0) progress = 0;
  if (progress > 1) progress = 1;
  const t = progress;
  const x = 10 + 180 * t;
  const a = 1 - 2*t;
  const y = 55 - 80 * (1 - a*a);
  dot.setAttribute('cx', x.toFixed(1));
  dot.setAttribute('cy', y.toFixed(1));

  const pct = Math.round(progress * 100);
  const progEl = document.getElementById('sun-progress');
  if (progEl) progEl.textContent = `${pct}%`;
}

/* ───── Renders ───── */
function renderForecast(forecast) {
  const el = document.getElementById('forecast');
  if (!forecast || forecast.length === 0) { el.innerHTML = '<div class="muted dim">—</div>'; return; }
  el.innerHTML = forecast.slice(0, 5).map(f => {
    const d = f.date ? new Date(f.date) : null;
    const dow = d ? DOW_SHORT[d.getDay()] : '—';
    const hi = f.high != null ? Math.round(f.high) + '°' : '—';
    const lo = f.low != null ? Math.round(f.low) + '°' : '';
    const pp = f.precip ? `${Math.round(f.precip)}mm` : '';
    return `<div class="forecast-day">
      <div class="dow">${dow}</div>
      <div class="icon">${f.icon}</div>
      <div class="hi">${hi}</div>
      <div class="lo">${lo}</div>
      <div class="pp">${pp}</div>
    </div>`;
  }).join('');

  const big = document.getElementById('forecast-big');
  if (big) {
    big.innerHTML = forecast.slice(0, 5).map(f => {
      const d = f.date ? new Date(f.date) : null;
      const dow = d ? DOW_SHORT[d.getDay()] : '—';
      const hi = f.high != null ? Math.round(f.high) + '°' : '—';
      const lo = f.low != null ? Math.round(f.low) + '°' : '';
      return `<div class="forecast-big-row">
        <span class="icon">${f.icon}</span>
        <span class="dow">${dow}</span>
        <span class="label">${f.label}</span>
        <span class="hi">${hi}</span>
        <span class="lo">${lo}</span>
      </div>`;
    }).join('');
  }
}

function renderPersons(persons) {
  document.getElementById('persons-list').innerHTML = persons.map(p =>
    `<div class="person ${p.home ? 'home' : 'away'}">
      <span class="dot"></span>
      <span class="name">${p.name}</span>
      <span class="state-text">${p.home ? 'zuhause' : (p.state === 'not_home' ? 'unterwegs' : p.state)}</span>
    </div>`
  ).join('');
}

function renderWindows(w) {
  const countEl = document.getElementById('window-count');
  const subEl = document.getElementById('window-sub');
  const listEl = document.getElementById('mini-window-list');
  setNum('window-count', String(w.count_open));
  countEl.classList.toggle('has-open', w.count_open > 0);
  countEl.classList.toggle('all-closed', w.count_open === 0);
  if (w.count_open === 0) {
    subEl.textContent = 'alle geschlossen';
  } else {
    subEl.textContent = `von ${w.count_total} offen`;
  }
  if (listEl) {
    if (w.count_open === 0) {
      listEl.innerHTML = '<div class="muted dim">alle zu</div>';
    } else {
      listEl.innerHTML = w.open.map(n => `<div class="window-chip">${n}</div>`).join('');
    }
  }
}

function renderPower(p) {
  setNum('energy-today', p.today_kwh.toFixed(1));
  setNum('cost-today', p.today_eur.toFixed(2));
  setNum('power-now', String(Math.round(p.now_w)));
  renderSparkline(p.history || []);
}

function renderSparkline(history) {
  const svg = document.getElementById('sparkline');
  if (!svg) return;
  if (history.length < 2) { svg.innerHTML = ''; return; }
  const W = 400, H = 80;

  const raw = history.map(h => h.v);
  const win = 5;
  const smoothed = raw.map((_, i) => {
    const lo = Math.max(0, i - win), hi = Math.min(raw.length, i + win + 1);
    const slice = raw.slice(lo, hi);
    return slice.reduce((a,b) => a+b, 0) / slice.length;
  });

  const sorted = [...smoothed].sort((a,b) => a-b);
  const minV = sorted[Math.floor(sorted.length * 0.02)];
  const maxV = sorted[Math.floor(sorted.length * 0.98)];
  const range = Math.max(maxV - minV, 1);

  const pts = smoothed.map((v, i) => {
    const clamped = Math.max(minV, Math.min(maxV, v));
    const x = (i / (smoothed.length - 1)) * W;
    const y = H - ((clamped - minV) / range) * (H - 6) - 3;
    return [x, y];
  });

  let pathD = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i-1], p1 = pts[i];
    const xc = (p0[0] + p1[0]) / 2;
    pathD += ` Q ${p0[0]},${p0[1]} ${xc},${(p0[1]+p1[1])/2}`;
  }
  pathD += ` T ${pts[pts.length-1][0]},${pts[pts.length-1][1]}`;
  const areaD = pathD + ` L${W},${H} L0,${H} Z`;

  svg.innerHTML = `
    <defs>
      <linearGradient id="spark-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#cba6f7" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="#cba6f7" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="${areaD}" fill="url(#spark-grad)"/>
    <path d="${pathD}" fill="none" stroke="#cba6f7" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.95"/>
  `;
}

function renderRooms(rooms, outdoorTemp) {
  const big = document.getElementById('rooms-big');
  if (!big) return;
  const all = rooms.map(r => ({...r, kind: 'room'}));
  if (outdoorTemp != null) {
    all.push({name: '☀️ Draußen', temp: outdoorTemp, soll: null, kind: 'outdoor'});
  }
  big.classList.remove('cols-3');
  big.innerHTML = all.map(r => {
    const cls = classifyRoomTemp(r.temp);
    const t = r.temp == null ? '—' : r.temp.toFixed(1) + '°';
    const soll = r.soll == null ? '' : `<span class="soll">/ ${r.soll}°</span>`;
    const outdoorCls = r.kind === 'outdoor' ? ' is-outdoor' : '';
    return `<div class="room-big ${cls}${outdoorCls}">
      <span class="name">${r.name}</span>
      <span class="temp ${cls}">${t}${soll}</span>
    </div>`;
  }).join('');
}

function renderGarbage(garbage) {
  const el = document.getElementById('garbage-list');
  if (!el) return;
  if (!garbage || garbage.length === 0) { el.innerHTML = '<div class="muted dim">—</div>'; return; }
  el.innerHTML = garbage.slice(0, 3).map(g => {
    let cls = 'normal';
    if (g.days <= 1) cls = 'urgent';
    else if (g.days <= 3) cls = 'soon';
    const dayStr = g.days === 0 ? 'heute'
      : g.days === 1 ? 'morgen' : `in ${g.days} Tagen`;
    return `<div class="garbage-row ${cls}" style="color:${g.color};">
      <span class="label"><span class="icon">${g.icon}</span><span>${g.label}</span></span>
      <span class="when"><span class="day">${dayStr}</span>${fmtDate(g.date)}</span>
    </div>`;
  }).join('');
}

function renderVacation(v) {
  const labelEl = document.getElementById('vacation-label');
  if (!v) {
    markMissing('vacation');
    if (labelEl) labelEl.textContent = 'kein Urlaub geplant';
    setNum('vacation-days', '—');
    document.getElementById('vacation-range').textContent = '';
    document.getElementById('vacation-bar-fill').style.width = '0%';
    return;
  }
  markHave('vacation');
  labelEl.textContent = v.label;
  setNum('vacation-days', v.active ? '✈︎' : String(v.days_until));
  const start = fmtDate(v.start), end = fmtDate(v.end);
  document.getElementById('vacation-range').textContent = `${start} – ${end} · ${v.duration} Tage`;
  const today = new Date();
  const start_d = new Date(v.start);
  const created_d = new Date(start_d.getTime() - 60 * 86400000);
  const total = (start_d - created_d) / 86400000;
  const elapsed = Math.max(0, Math.min(total, (today - created_d) / 86400000));
  const pct = total > 0 ? (elapsed / total) * 100 : 0;
  document.getElementById('vacation-bar-fill').style.width = `${pct}%`;
}

function renderWeather(o) {
  setNum('weather-temp', o.temp.toFixed(1) + '°');
  document.getElementById('weather-label').textContent = o.label;
  document.getElementById('sun-rise').textContent = fmtTime(o.sun_rise);
  document.getElementById('sun-set').textContent = fmtTime(o.sun_set);
  setWeatherIcon(o.raw, o.is_night);
  updateSunArc(o.sun_rise, o.sun_set);
  if (window.bgSetMode) window.bgSetMode(o.raw, o.is_night);

  if (o.outdoor_humidity != null) {
    setNum('outdoor-humid', String(Math.round(o.outdoor_humidity)));
    markHave('outdoor-humid');
  }
  if (o.wind_speed != null) {
    setNum('wind-speed', o.wind_speed.toFixed(1));
    const dir = (o.wind_dir || '').toString().toUpperCase();
    const ARROW = { N: '↑', NE: '↗', E: '→', SE: '↘', S: '↓', SW: '↙', W: '←', NW: '↖' };
    const arrow = ARROW[dir] || '·';
    const lbl = document.getElementById('wind-dir-label');
    if (lbl) lbl.textContent = `${arrow} ${dir || '—'}`;
    markHave('wind');
  }
  if (o.rain_today != null) {
    setNum('rain-today', o.rain_today.toFixed(1));
    const lbl = document.getElementById('rain-now-label');
    if (lbl) lbl.textContent = (o.rain_now != null && o.rain_now > 0) ? `regnet ${o.rain_now.toFixed(1)} mm/h` : 'trocken';
    markHave('rain');
  }
}

function markHave(needName) {
  document.querySelectorAll(`[data-need="${needName}"]`).forEach(el => el.classList.remove('tile-empty'));
}
function markMissing(needName) {
  document.querySelectorAll(`[data-need="${needName}"]`).forEach(el => el.classList.add('tile-empty'));
}

function renderIndoor(ind) {
  if (ind.humidity != null) setNum('indoor-hum', ind.humidity.toFixed(0));
  if (ind.pressure != null) {
    setNum('indoor-pressure', ind.pressure.toFixed(0));
    setNum('pressure', ind.pressure.toFixed(0));
    const trend = document.getElementById('pressure-trend');
    if (trend) trend.textContent = ind.pressure > 1020 ? 'Hoch' : ind.pressure < 1005 ? 'Tief' : 'Normal';
    markHave('pressure');
  } else {
    markMissing('pressure');
  }
  if (ind.co2 != null) setNum('status-co2', String(Math.round(ind.co2)));
  if (ind.noise != null) setNum('status-noise', String(Math.round(ind.noise)));
  if (ind.grid_co2 != null) {
    const v = Math.round(ind.grid_co2);
    setNum('grid-co2', String(v));
    const fill = document.getElementById('co2-bar-fill');
    const rating = document.getElementById('co2-rating');
    let cls = 'mid', label = 'mittel';
    if (v < 150) { cls = 'low'; label = 'sauber'; }
    else if (v > 350) { cls = 'high'; label = 'dreckig'; }
    const pct = Math.min(100, (v / 600) * 100);
    fill.className = `co2-bar-fill ${cls}`;
    fill.style.width = `${pct}%`;
    rating.textContent = label;
  }
}

function renderEvents(events) {
  const el = document.getElementById('events-list');
  if (!el) return;
  if (!events || events.length === 0) {
    el.innerHTML = '<div class="events-empty">— keine Termine in den nächsten 7 Tagen —<div class="events-empty-sub">Genieß den freien Kopf</div></div>';
    return;
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today.getTime() + 86400000);
  const fewEvents = events.length <= 3;
  el.classList.toggle('events-list-large', fewEvents);
  el.innerHTML = events.slice(0, 8).map(e => {
    const s = new Date(e.start);
    const day0 = new Date(s); day0.setHours(0,0,0,0);
    const isToday = day0.getTime() === today.getTime();
    const isTomorrow = day0.getTime() === tomorrow.getTime();
    const dayCls = isToday ? 'today' : (isTomorrow ? 'tomorrow' : '');
    const dayStr = isToday ? 'heute'
      : isTomorrow ? 'morgen'
      : `${DOW_SHORT[s.getDay()]} ${String(s.getDate()).padStart(2,'0')}.${String(s.getMonth()+1).padStart(2,'0')}.`;
    const timeStr = e.all_day ? '<span class="time allday">ganztag</span>'
      : `<span class="time">${String(s.getHours()).padStart(2,'0')}:${String(s.getMinutes()).padStart(2,'0')}</span>`;
    return `<div class="event-row ${dayCls} cal-${e.calendar}">
      <span class="day">${dayStr}</span>
      ${timeStr}
      <span class="summary">${e.summary || '—'}</span>
      <span class="cal-name">${e.calendar}</span>
    </div>`;
  }).join('');
}

function renderSunBig(o) {
  const el = document.getElementById('sun-info');
  if (!el) return;
  const r = o.sun_rise ? new Date(o.sun_rise) : null;
  const s = o.sun_set ? new Date(o.sun_set) : null;
  let dayLen = '—';
  if (r && s) {
    let dur = s - r;
    if (dur < 0) dur += 86400000;
    const h = Math.floor(dur / 3600000);
    const m = Math.floor((dur % 3600000) / 60000);
    dayLen = `${h} h ${m} min`;
  }
  const now = new Date();
  let timeUntilSet = '—';
  if (s) {
    let diff = s - now;
    if (diff < 0) diff += 86400000;
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    timeUntilSet = `${h} h ${m} min`;
  }
  el.innerHTML = `
    <div class="sun-info-row"><span class="key">Sonnenaufgang</span><span class="val">${fmtTime(o.sun_rise)}</span></div>
    <div class="sun-info-row"><span class="key">Sonnenuntergang</span><span class="val">${fmtTime(o.sun_set)}</span></div>
    <div class="sun-info-row"><span class="key">Tageslänge</span><span class="val">${dayLen}</span></div>
    <div class="sun-info-row"><span class="key">Bis Untergang</span><span class="val">${timeUntilSet}</span></div>
    <div class="sun-info-row"><span class="key">Status</span><span class="val">${o.is_night ? '🌙 Nacht' : '☀️ Tag'}</span></div>
  `;
}

/* ───── Page Rotator ───── */
const profile = document.body.dataset.profile || 'mike';
const allPages = document.querySelectorAll('.page');
const pagesArr = Array.from(allPages).filter(p => {
  if (p.classList.contains('profile-only-robert') && profile !== 'robert') return false;
  if (p.classList.contains('profile-only-mike') && profile !== 'mike') return false;
  return true;
});
pagesArr.forEach(p => { p.style.display = ''; });
const indicator = document.getElementById('pageindicator');
if (indicator) {
  indicator.innerHTML = pagesArr.map((_, i) => `<span class="indicator-dot" data-idx="${i}"></span>`).join('');
}
const dots = document.querySelectorAll('.indicator-dot');
let currentPage = 0;
function showPage(idx) {
  pagesArr.forEach((p, i) => p.classList.toggle('active', i === idx));
  dots.forEach((d, i) => d.classList.toggle('active', i === idx));
  currentPage = idx;
}
function nextPage() {
  showPage((currentPage + 1) % pagesArr.length);
}

const urlPage = new URLSearchParams(window.location.search).get('page');
const pinPage = urlPage != null ? Math.max(0, Math.min(pagesArr.length - 1, parseInt(urlPage, 10) || 0)) : null;

/* ───── Fetch loop ───── */
async function fetchData() {
  try {
    const res = await fetch('/api/data', { cache: 'no-store' });
    if (!res.ok) throw new Error('http ' + res.status);
    const data = await res.json();
    applyData(data);
    document.getElementById('live-text').textContent = 'Live';
    document.getElementById('live-dot').style.background = 'var(--green)';
  } catch (e) {
    console.error('fetch error', e);
    document.getElementById('live-text').textContent = 'offline';
    document.getElementById('live-dot').style.background = 'var(--red)';
  }
}
function applyData(data) {
  window.lastOutdoor = data.outdoor;
  renderWeather(data.outdoor);
  renderForecast(data.forecast);
  renderPersons(data.persons);
  renderWindows(data.windows);
  renderPower(data.power);
  renderGarbage(data.garbage);
  renderVacation(data.vacation);
  renderEvents(data.events || []);

  renderOutdoorChart(data.outdoor_history || [], data.outdoor);
  renderSunDetail(data.outdoor, data.sun_elevation, data.sun_azimuth);
  renderForecastBigRow(data.forecast);
  renderIndoor(data.indoor || {});

  renderEnergyBig(data.power);
  renderCO2Big(data.co2_rate, data.co2_kumuliert, data.indoor);
  renderEnergySubs(data.energy_subs || []);

  renderRoomsGrid(data.rooms, data.rooms_history || {}, data.outdoor);

  renderBatteries(data.batteries || []);
  renderThread(data.thread_rssi);
  renderBackup(data.backup_last, data.backup_next);
  renderEventsMini(data.events || []);
  renderInternet(data.internet);
  renderSolar(data.solar);
  renderPool(data.pool);
  renderStatusWeather(data.outdoor);
}

function renderSolar(s) {
  if (!s) return;
  if (s.pv_power != null) setNum('solar-pv-power', String(Math.round(s.pv_power)));
  if (s.house_load_w != null) setNum('solar-house', String(Math.round(s.house_load_w)));
  if (s.battery_soc != null) setNum('solar-bat-soc', String(Math.round(s.battery_soc)));
  if (s.grid_w != null) {
    setNum('solar-grid', String(Math.abs(Math.round(s.grid_w))));
    const lbl = document.getElementById('solar-grid-label');
    if (lbl) lbl.textContent = s.grid_w < 0 ? '↑ Einspeisung' : '↓ Bezug';
  }
  if (s.battery_power != null) {
    const lbl = document.getElementById('solar-bat-flow');
    if (lbl) lbl.textContent = s.battery_power > 50 ? '↑ lädt ' + Math.abs(Math.round(s.battery_power)) + ' W'
      : s.battery_power < -50 ? '↓ entlädt ' + Math.abs(Math.round(s.battery_power)) + ' W'
      : 'ruht';
  }
  if (s.pv_today_kwh != null) setNum('solar-pv-today', s.pv_today_kwh.toFixed(1));
  if (s.feed_today_kwh != null) setNum('solar-feed-today', s.feed_today_kwh.toFixed(2));
  if (s.draw_today_kwh != null) setNum('solar-draw-today', s.draw_today_kwh.toFixed(2));
  if (s.battery_charge_today_kwh != null) setNum('solar-bat-charge', s.battery_charge_today_kwh.toFixed(2));
  if (s.battery_discharge_today_kwh != null) setNum('solar-bat-discharge', s.battery_discharge_today_kwh.toFixed(2));
  if (s.wallbox_total_kwh != null) setNum('wallbox-total', s.wallbox_total_kwh.toFixed(1));
  if (s.wallbox_temp != null) setNum('wallbox-temp', s.wallbox_temp.toFixed(0));

  const chart = document.getElementById('solar-chart');
  if (chart) chart.innerHTML = svgSpark(s.history || [], 800, 200, '#f9e2af', 4);
  const batChart = document.getElementById('solar-bat-chart');
  if (batChart) batChart.innerHTML = svgSpark(s.battery_history || [], 200, 40, '#a6e3a1', 3);
}

function renderPool(p) {
  if (!p) return;
  if (p.wassertemp != null) setNum('pool-temp', p.wassertemp.toFixed(1));
  if (p.ph != null) {
    setNum('pool-ph', p.ph.toFixed(2));
    const rating = document.getElementById('pool-ph-rating');
    const cell = document.getElementById('pool-ph-value');
    let cls = 'good', label = '🟢 Ideal';
    if (p.ph < 6.8 || p.ph > 7.6) { cls = 'bad'; label = '🔴 Kritisch'; }
    else if (p.ph < 7.0 || p.ph > 7.4) { cls = 'mid'; label = '🟡 OK'; }
    if (rating) rating.textContent = label;
    if (cell) { cell.classList.remove('pool-value-good','pool-value-mid','pool-value-bad'); cell.classList.add(`pool-value-${cls}`); }
  }
  if (p.orp != null) {
    setNum('pool-orp', String(Math.round(p.orp)));
    const rating = document.getElementById('pool-orp-rating');
    const cell = document.getElementById('pool-orp-value');
    let cls = 'good', label = '🟢 Ideal';
    if (p.orp < 500 || p.orp > 850) { cls = 'bad'; label = '🔴 Kritisch'; }
    else if (p.orp < 650 || p.orp > 800) { cls = 'mid'; label = '🟡 OK'; }
    if (rating) rating.textContent = label;
    if (cell) { cell.classList.remove('pool-value-good','pool-value-mid','pool-value-bad'); cell.classList.add(`pool-value-${cls}`); }
  }

  const stateEl = document.getElementById('pool-pump-state');
  if (stateEl) {
    stateEl.textContent = p.pumpe_on ? '💧 läuft' : '⏸ aus';
    stateEl.className = `pool-pump-state ${p.pumpe_on ? 'on' : 'off'}`;
  }
  if (p.laufzeit_h != null) setNum('pool-laufzeit', p.laufzeit_h.toFixed(1));
  const sollEl = document.getElementById('pool-soll');
  if (sollEl && p.soll_h != null) sollEl.textContent = p.soll_h.toFixed(1);
  const fillEl = document.getElementById('pool-laufzeit-fill');
  if (fillEl && p.soll_h && p.laufzeit_h != null) {
    const pct = Math.min(100, (p.laufzeit_h / p.soll_h) * 100);
    fillEl.style.width = pct + '%';
  }
  const status = document.getElementById('pool-status');
  if (status && p.status) status.textContent = p.status;

  const log = document.getElementById('pool-log');
  if (log && p.aktion_log) {
    log.textContent = p.aktion_log.replace(/ · /g, '\n');
  }

  const tempChart = document.getElementById('pool-temp-chart');
  if (tempChart) tempChart.innerHTML = svgSpark(p.wassertemp_history || [], 200, 40, '#89b4fa', 2);
  const phChart = document.getElementById('pool-ph-chart');
  if (phChart) phChart.innerHTML = svgSpark(p.ph_history || [], 200, 40, '#cba6f7', 2);
  const orpChart = document.getElementById('pool-orp-chart');
  if (orpChart) orpChart.innerHTML = svgSpark(p.orp_history || [], 200, 40, '#94e2d5', 2);
}

function buildSparkPath(history, W, H, opts = {}) {
  if (!history || history.length < 2) return { path: '', area: '' };
  const values = history.map(h => h.v);
  const smoothed = values.map((_, i) => {
    const w = opts.smooth || 3;
    const lo = Math.max(0, i - w), hi = Math.min(values.length, i + w + 1);
    const slice = values.slice(lo, hi);
    return slice.reduce((a,b) => a+b, 0) / slice.length;
  });
  const sorted = [...smoothed].sort((a,b)=>a-b);
  const minV = opts.fixedMin != null ? opts.fixedMin : sorted[Math.floor(sorted.length * 0.02)];
  const maxV = opts.fixedMax != null ? opts.fixedMax : sorted[Math.floor(sorted.length * 0.98)];
  const range = Math.max(maxV - minV, 0.5);
  const pts = smoothed.map((v, i) => {
    const c = Math.max(minV, Math.min(maxV, v));
    const x = (i / (smoothed.length - 1)) * W;
    const y = H - ((c - minV) / range) * (H - 6) - 3;
    return [x, y];
  });
  let path = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i-1], p1 = pts[i];
    const xc = (p0[0] + p1[0]) / 2;
    path += ` Q ${p0[0]},${p0[1]} ${xc},${(p0[1]+p1[1])/2}`;
  }
  path += ` T ${pts[pts.length-1][0]},${pts[pts.length-1][1]}`;
  const area = path + ` L${W},${H} L0,${H} Z`;
  return { path, area, minV, maxV };
}

function svgSpark(history, W, H, color, smooth) {
  const { path, area } = buildSparkPath(history, W, H, { smooth: smooth || 3 });
  if (!path) return '';
  const id = 'g' + Math.random().toString(36).slice(2, 8);
  return `
    <defs>
      <linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="${area}" fill="url(#${id})"/>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" opacity="0.95"/>
  `;
}

function renderOutdoorChart(history, outdoor) {
  const svg = document.getElementById('outdoor-chart');
  if (!svg) return;
  if (!history || history.length < 2) { svg.innerHTML = ''; return; }
  const W = 800, H = 280;
  const { path, area, minV, maxV } = buildSparkPath(history, W, H, { smooth: 2 });
  if (!path) { svg.innerHTML = ''; return; }
  svg.innerHTML = `
    <defs>
      <linearGradient id="og" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#fab387" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="#fab387" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="${area}" fill="url(#og)"/>
    <path d="${path}" fill="none" stroke="#fab387" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  `;
  const minEl = document.getElementById('outdoor-min');
  const maxEl = document.getElementById('outdoor-max');
  if (minEl) minEl.textContent = `${minV.toFixed(1)}° → ${(outdoor && outdoor.temp) ? outdoor.temp.toFixed(1) + '°' : '—'} → ${maxV.toFixed(1)}°`;
  if (maxEl) maxEl.textContent = '';

  const iconBig = document.getElementById('weather-icon-big');
  if (iconBig && outdoor) {
    const cl = iconBig.innerHTML.length;
    const html = document.getElementById('weather-icon-anim').innerHTML;
    if (cl === 0 || html) iconBig.innerHTML = html;
  }
  if (outdoor) {
    const tb = document.getElementById('weather-temp-big');
    const lb = document.getElementById('weather-label-big');
    if (tb) tb.textContent = outdoor.temp.toFixed(1) + '°';
    if (lb) lb.textContent = outdoor.label;
  }
}

function renderSunDetail(outdoor, elev, azim) {
  if (elev != null) setNum('sun-elevation', elev.toFixed(0));
  const az = document.getElementById('sun-azimuth');
  if (az && azim != null) az.textContent = azim.toFixed(0);
  if (!outdoor) return;
  const r = outdoor.sun_rise ? new Date(outdoor.sun_rise) : null;
  const s = outdoor.sun_set ? new Date(outdoor.sun_set) : null;
  if (r && s) {
    let dur = s - r;
    if (dur < 0) dur += 86400000;
    const h = Math.floor(dur / 3600000);
    const m = Math.floor((dur % 3600000) / 60000);
    const dh = document.getElementById('daylight-hours');
    if (dh) dh.innerHTML = `${h}<span class="unit">h</span> ${m}<span class="unit">m</span>`;
  }
  const now = new Date();
  const prog = document.getElementById('daylight-progress');
  if (prog && r && s) {
    let dayR = r;
    if (r > s) dayR = new Date(r.getTime() - 86400000);
    let pct = Math.max(0, Math.min(100, ((now - dayR) / (s - dayR)) * 100));
    prog.textContent = `${Math.round(pct)} % vergangen`;
  }
}

function renderForecastBigRow(forecast) {
  const el = document.getElementById('forecast-big-row');
  if (!el || !forecast) return;
  el.innerHTML = forecast.slice(0, 5).map(f => {
    const d = f.date ? new Date(f.date) : null;
    const dow = d ? DOW_SHORT[d.getDay()] : '—';
    const hi = f.high != null ? Math.round(f.high) + '°' : '—';
    const lo = f.low != null ? Math.round(f.low) + '°' : '';
    const pp = f.precip ? `${Math.round(f.precip)}mm` : '';
    return `<div class="forecast-big-row">
      <span class="icon">${f.icon}</span>
      <span class="dow">${dow}</span>
      <span class="label">${f.label}</span>
      ${pp ? `<span class="lo">${pp}</span>` : ''}
      <span class="hi">${hi}</span>
      <span class="lo">${lo}</span>
    </div>`;
  }).join('');
}

function renderEnergyBig(p) {
  if (!p) return;
  setNum('energy-today-big', p.today_kwh.toFixed(1));
  setNum('cost-today-big', p.today_eur.toFixed(2));
  setNum('power-now-big', String(Math.round(p.now_w)));
  const svg = document.getElementById('power-chart-big');
  if (svg) svg.innerHTML = svgSpark(p.history || [], 800, 200, '#cba6f7', 5);
}

function renderCO2Big(rate, kumuliert, indoor) {
  if (rate != null) setNum('co2-rate', rate.toFixed(1));
  if (kumuliert != null) setNum('co2-kumuliert', kumuliert.toFixed(1));
  if (indoor && indoor.grid_co2 != null) {
    setNum('grid-co2-big', String(Math.round(indoor.grid_co2)));
    const fill = document.getElementById('co2-bar-fill');
    const rating = document.getElementById('co2-rating');
    let cls = 'mid', label = 'mittel';
    if (indoor.grid_co2 < 150) { cls = 'low'; label = 'sauber'; }
    else if (indoor.grid_co2 > 350) { cls = 'high'; label = 'dreckig'; }
    const pct = Math.min(100, (indoor.grid_co2 / 600) * 100);
    if (fill) { fill.className = `co2-bar-fill ${cls}`; fill.style.width = `${pct}%`; }
    if (rating) rating.textContent = label;
  }
}

const SUB_COLORS = ['#cba6f7', '#fab387', '#89b4fa', '#a6e3a1'];
function renderEnergySubs(subs) {
  for (let i = 0; i < 4; i++) {
    const s = subs[i];
    const labelEl = document.getElementById(`sub-label-${i}`);
    if (!s) {
      if (labelEl) labelEl.textContent = '—';
      continue;
    }
    if (labelEl) labelEl.textContent = '⚡ ' + s.label;
    setNum(`sub-energy-${i}`, s.energy_kwh.toFixed(2));
    const c = document.getElementById(`sub-cost-${i}`);
    if (c) c.textContent = s.cost_eur.toFixed(2);
    const p = document.getElementById(`sub-power-${i}`);
    if (p) p.textContent = Math.round(s.power_w);
    const spark = document.getElementById(`sub-spark-${i}`);
    if (spark) spark.innerHTML = svgSpark(s.history || [], 200, 40, SUB_COLORS[i], 3);
  }
}

function renderRoomsGrid(rooms, histories, outdoor) {
  const el = document.getElementById('grid-rooms');
  if (!el) return;
  const all = rooms.map(r => ({ ...r, kind: 'room', history: histories[r.name] || [] }));
  if (outdoor && outdoor.temp != null) {
    all.push({ name: '☀️ Draußen', temp: outdoor.temp, soll: null, kind: 'outdoor', history: window.lastOutdoorHistory || [] });
  }
  el.innerHTML = all.map(r => {
    const cls = classifyRoomTemp(r.temp);
    const t = r.temp == null ? '—' : r.temp.toFixed(1) + '°';
    const soll = r.soll == null ? '' : `<span class="room-card-soll">/ ${r.soll}°</span>`;
    const sparkColor = cls === 'hot' ? '#fab387'
      : cls === 'warm' ? '#f9e2af'
      : cls === 'cold' ? '#89dceb'
      : cls === 'ok'   ? '#a6e3a1' : '#cba6f7';

    let badgeHtml = '';
    let targetHtml = '';
    if (r.kind === 'room') {
      const target = r.trv_target != null ? r.trv_target.toFixed(1) + '°' : '—';
      const ventil = r.ventil != null ? Math.round(r.ventil) : 0;
      let badge = 'idle', badgeText = 'bereit';
      if (r.trv_state === 'off') { badge = 'off'; badgeText = 'aus'; }
      else if (r.heating || (r.ventil != null && r.ventil > 0)) { badge = 'heating'; badgeText = '🔥 heizt'; }
      badgeHtml = `<span class="room-card-badge ${badge}">${badgeText}</span>`;
      targetHtml = `
        <div class="room-card-target">
          <span>TRV ${target}</span>
          <div class="ventil-bar"><div class="ventil-fill" style="width:${ventil}%;"></div></div>
          <span>${ventil}%</span>
        </div>`;
    }

    return `<div class="tile room-card span-1">
      <div class="room-card-head">
        <div class="room-card-name">${r.name}</div>
        ${badgeHtml}
      </div>
      <div class="room-card-row">
        <span class="room-card-temp ${cls}">${t}</span>
        ${soll}
      </div>
      ${targetHtml}
      <svg class="room-card-spark" viewBox="0 0 200 50" preserveAspectRatio="none">${svgSpark(r.history, 200, 50, sparkColor, 2)}</svg>
    </div>`;
  }).join('');
}

function renderInternet(net) {
  if (!net) return;
  if (net.down_mbit != null) setNum('net-down', net.down_mbit.toFixed(2));
  if (net.up_mbit != null) setNum('net-up', net.up_mbit.toFixed(2));
  const downSvg = document.getElementById('net-down-chart');
  const upSvg = document.getElementById('net-up-chart');
  if (downSvg) downSvg.innerHTML = svgSpark(net.down_history || [], 800, 200, '#89b4fa', 3);
  if (upSvg) upSvg.innerHTML = svgSpark(net.up_history || [], 800, 200, '#cba6f7', 3);

  const el = document.getElementById('clients-list');
  if (el) {
    if (!net.clients || net.clients.length === 0) {
      el.innerHTML = '<div class="muted dim">— kein Traffic erkannt —</div>';
    } else {
      el.innerHTML = net.clients.map(c => `
        <div class="client-row">
          <span class="name">${c.name}</span>
          <span class="val down">↓ ${c.down.toFixed(2)}<span class="unit">Mbit/s</span></span>
          <span class="val up">↑ ${c.up.toFixed(2)}<span class="unit">Mbit/s</span></span>
        </div>`).join('');
    }
  }
}

const KIND_LABEL = { trv: 'Thermostat', window: 'Fenster', dimmer: 'Schalter', klima: 'Klima' };
function renderBatteries(batteries) {
  const el = document.getElementById('batteries-grid');
  if (!el) return;
  if (!batteries || batteries.length === 0) { el.innerHTML = '<div class="muted dim">—</div>'; return; }
  el.innerHTML = batteries.map(b => {
    return `<div class="battery-card ${b.level}">
      <div class="battery-head">
        <span class="battery-name">${b.label}</span>
        <span class="battery-kind">${KIND_LABEL[b.kind] || b.kind}</span>
      </div>
      <div class="battery-bar"><div class="battery-fill ${b.level}" style="width:${Math.max(2, b.value)}%;"></div></div>
      <div class="battery-val">${Math.round(b.value)} %</div>
    </div>`;
  }).join('');
}

function renderThread(rssi) {
  if (!rssi) { markMissing('thread'); return; }
  const ids = ['best', 'avg', 'worst'];
  const anyVal = ids.some(k => rssi[k] != null);
  if (!anyVal) { markMissing('thread'); return; }
  markHave('thread');
  ids.forEach(k => {
    const v = rssi[k];
    const numEl = document.getElementById(`thread-${k}`);
    const fillEl = document.getElementById(`thread-fill-${k}`);
    if (v == null) {
      if (numEl) numEl.textContent = '—';
      if (fillEl) fillEl.style.width = '0%';
      return;
    }
    if (numEl) numEl.textContent = Math.round(v);
    if (fillEl) {
      const pct = Math.max(0, Math.min(100, ((v + 100) / 50) * 100));
      let cls = 'good';
      if (v < -85) cls = 'weak';
      else if (v < -75) cls = 'mid';
      fillEl.className = `thread-fill ${cls}`;
      fillEl.style.width = `${pct}%`;
    }
  });
}

function renderStatusWeather(outdoor) {
  if (!outdoor) return;
  if (outdoor.wind_speed != null) {
    setNum('status-wind', outdoor.wind_speed.toFixed(1));
    const dir = (outdoor.wind_dir || '').toString().toUpperCase();
    const lbl = document.getElementById('status-wind-dir');
    if (lbl) lbl.textContent = dir ? `Wind aus ${dir}` : 'Wind';
  }
  if (outdoor.rain_today != null) setNum('status-rain', outdoor.rain_today.toFixed(1));
}

function renderBackup(last, next) {
  const ll = document.getElementById('backup-last');
  const nn = document.getElementById('backup-next');
  if (ll) ll.textContent = last ? fmtRelative(last) : '—';
  if (nn) nn.textContent = next ? fmtRelative(next) : '—';
}

function fmtRelative(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = (d - now) / 1000;
  const abs = Math.abs(diff);
  if (abs < 60) return diff > 0 ? 'in <1 min' : 'gerade eben';
  if (abs < 3600) {
    const m = Math.round(abs / 60);
    return diff > 0 ? `in ${m} min` : `vor ${m} min`;
  }
  if (abs < 86400) {
    const h = Math.round(abs / 3600);
    return diff > 0 ? `in ${h} h` : `vor ${h} h`;
  }
  const days = Math.round(abs / 86400);
  return diff > 0 ? `in ${days} Tagen` : `vor ${days} Tagen`;
}

function renderEventsMini(events) {
  const el = document.getElementById('events-mini');
  if (!el) return;
  const today = new Date(); today.setHours(0,0,0,0);
  const tomorrow = new Date(today.getTime() + 86400000);
  const dayAfter = new Date(today.getTime() + 86400000 * 2);
  const filtered = (events || []).filter(e => {
    const d = new Date(e.start); d.setHours(0,0,0,0);
    return d < dayAfter;
  }).slice(0, 4);
  if (filtered.length === 0) {
    el.innerHTML = '<div class="events-mini-empty">— nichts heute/morgen —</div>';
    return;
  }
  el.innerHTML = filtered.map(e => {
    const s = new Date(e.start);
    const d0 = new Date(s); d0.setHours(0,0,0,0);
    const dayStr = d0.getTime() === today.getTime() ? 'heute'
      : d0.getTime() === tomorrow.getTime() ? 'morgen'
      : `${DOW_SHORT[s.getDay()]}`;
    const timeStr = e.all_day ? 'ganztag' : `${String(s.getHours()).padStart(2,'0')}:${String(s.getMinutes()).padStart(2,'0')}`;
    return `<div class="event-mini-row">
      <div class="when">${dayStr} · ${timeStr}</div>
      <div class="summary">${e.summary || '—'}</div>
    </div>`;
  }).join('');
}

/* ───── Init ───── */
clock();
setInterval(clock, 1000);
setInterval(() => {
  if (window.bgUpdateTime) window.bgUpdateTime();
}, 60000);
fetchData();
setInterval(fetchData, FETCH_INTERVAL_MS);

showPage(pinPage != null ? pinPage : 0);
if (pinPage == null) {
  setInterval(nextPage, PAGE_DURATION_MS);
}

setInterval(() => {
  const o = window.lastOutdoor;
  if (o) updateSunArc(o.sun_rise, o.sun_set);
}, 60000);
