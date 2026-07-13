(function () {
  'use strict';

  // ------------------------------------------------------------------
  // Configuration
  // ------------------------------------------------------------------
  const API_BASE = window.STADIUMOS_API_BASE
    || (location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? 'http://localhost:8000/api/v1'
      : 'https://newfootball-1.onrender.com/api/v1');
  const FETCH_TIMEOUT_MS = 15000;

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  async function callApi(path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(API_BASE + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) throw new Error('API error ' + res.status);
      return await res.json();
    } catch (err) {
      clearTimeout(timer);
      console.error(`StadiumOS API request failed: ${path}`, err);
      return null; // resilient offline fallback
    }
  }

  // ------------------------------------------------------------------
  // Backend availability indicator
  // ------------------------------------------------------------------
  let backendOnline = false;
  async function checkHealth() {
    const pill = document.getElementById('apiStatus');
    const text = document.getElementById('apiStatusText');
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 2500);
      const res = await fetch(API_BASE + '/health', { signal: controller.signal });
      clearTimeout(timer);
      if (res.ok) {
        const data = await res.json();
        backendOnline = true;
        pill.dataset.state = 'online';
        text.textContent = data.genai_available ? 'Live GenAI connected' : 'Backend connected (fallback mode)';
        return;
      }
      throw new Error('not ok');
    } catch (e) {
      backendOnline = false;
      pill.dataset.state = 'offline';
      text.textContent = 'Offline demo mode (local logic)';
    }
  }
  checkHealth();

  // ------------------------------------------------------------------
  // Accessibility toolbar controls
  // ------------------------------------------------------------------
  const html = document.documentElement;
  document.getElementById('contrastToggle').addEventListener('click', function (e) {
    const pressed = e.target.getAttribute('aria-pressed') === 'true';
    e.target.setAttribute('aria-pressed', String(!pressed));
    html.dataset.contrast = !pressed ? 'high' : 'normal';
  });
  document.getElementById('textSizeToggle').addEventListener('click', function (e) {
    const sizes = ['normal', 'large', 'xlarge'];
    const current = html.dataset.textsize || 'normal';
    const next = sizes[(sizes.indexOf(current) + 1) % sizes.length];
    html.dataset.textsize = next;
    e.target.setAttribute('aria-pressed', String(next !== 'normal'));
    e.target.textContent = next === 'normal' ? 'Large text' : (next === 'large' ? 'Larger text ✓' : 'Largest text ✓✓');
  });

  function currentLang() { return document.getElementById('langSelect').value; }

  // ------------------------------------------------------------------
  // Tab / module switching (full keyboard support: arrow keys, home/end)
  // ------------------------------------------------------------------
  const tabs = Array.from(document.querySelectorAll('.module-tab'));
  function selectTab(tab) {
    tabs.forEach(t => {
      const selected = t === tab;
      t.setAttribute('aria-selected', String(selected));
      const panel = document.getElementById(t.getAttribute('aria-controls'));
      if (panel) panel.hidden = !selected;
    });
    tab.focus();
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', (e) => {
      let idx = null;
      if (e.key === 'ArrowDown' || e.key === 'ArrowRight') idx = (i + 1) % tabs.length;
      else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') idx = (i - 1 + tabs.length) % tabs.length;
      else if (e.key === 'Home') idx = 0;
      else if (e.key === 'End') idx = tabs.length - 1;
      if (idx !== null) { e.preventDefault(); selectTab(tabs[idx]); }
    });
  });

  // ------------------------------------------------------------------
  // Overview — hero clock + quick-jump tiles
  // ------------------------------------------------------------------
  function tickHeroClock() {
    const now = new Date();
    const dateEl = document.getElementById('heroDate');
    const timeEl = document.getElementById('heroTime');
    if (dateEl) dateEl.textContent = now.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
    if (timeEl) timeEl.textContent = now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  tickHeroClock();
  setInterval(tickHeroClock, 1000);

  document.querySelectorAll('.quick-tile[data-jump]').forEach(function (tile) {
    tile.addEventListener('click', function () {
      const target = document.getElementById(tile.getAttribute('data-jump'));
      if (target) selectTab(target);
    });
  });

  document.querySelectorAll('.suggestion-chip[data-fill]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      const input = document.getElementById('chatInput');
      input.value = chip.getAttribute('data-fill');
      input.focus();
      document.getElementById('chatForm').requestSubmit();
    });
  });

  // ------------------------------------------------------------------
  // Local (offline) fallback logic — mirrors backend rule-based fallback
  // so the console is fully demoable with zero backend / zero API key.
  // ------------------------------------------------------------------
  const STADIUM_GRAPH = {
    gate_a: { name: 'Gate A (Main Entrance)', accessible: true, neighbors: [['concourse_north', 2]] },
    gate_b: { name: 'Gate B (East Entrance)', accessible: true, neighbors: [['concourse_east', 2]] },
    gate_c: { name: 'Gate C (West Entrance)', accessible: false, neighbors: [['concourse_west', 2]] },
    concourse_north: { name: 'North Concourse', accessible: true, neighbors: [['gate_a', 2], ['section_101_120', 3], ['food_court_north', 1], ['concourse_east', 4]] },
    concourse_east: { name: 'East Concourse', accessible: true, neighbors: [['gate_b', 2], ['section_201_220', 3], ['family_zone', 2], ['concourse_north', 4], ['concourse_south', 4]] },
    concourse_west: { name: 'West Concourse', accessible: false, neighbors: [['gate_c', 2], ['section_301_320', 4], ['press_zone', 2], ['concourse_south', 4]] },
    concourse_south: { name: 'South Concourse', accessible: true, neighbors: [['section_401_420', 3], ['accessible_seating', 1], ['medical_station', 1], ['concourse_east', 4], ['concourse_west', 4]] },
    section_101_120: { name: 'Lower Bowl North (101-120)', accessible: true, neighbors: [['concourse_north', 3]] },
    section_201_220: { name: 'Lower Bowl East (201-220)', accessible: true, neighbors: [['concourse_east', 3]] },
    section_301_320: { name: 'Upper Bowl West (301-320)', accessible: false, neighbors: [['concourse_west', 4]] },
    section_401_420: { name: 'Lower Bowl South (401-420)', accessible: true, neighbors: [['concourse_south', 3]] },
    accessible_seating: { name: 'Accessible Seating Platform', accessible: true, neighbors: [['concourse_south', 1]] },
    family_zone: { name: 'Family & Fan Zone', accessible: true, neighbors: [['concourse_east', 2]] },
    food_court_north: { name: 'North Food Court', accessible: true, neighbors: [['concourse_north', 1]] },
    medical_station: { name: 'Medical Station', accessible: true, neighbors: [['concourse_south', 1]] },
    press_zone: { name: 'Media & Press Zone', accessible: false, neighbors: [['concourse_west', 2]] },
  };
  function slug(s) { return s.trim().toLowerCase().replace(/[\s-]+/g, '_'); }
  function localShortestPath(origin, dest, avoid) {
    avoid = avoid || [];
    if (!STADIUM_GRAPH[origin] || !STADIUM_GRAPH[dest]) return null;
    const dist = { [origin]: 0 }, prev = {}, visited = new Set();
    const queue = [[0, origin]];
    while (queue.length) {
      queue.sort((a, b) => a[0] - b[0]);
      const [d, node] = queue.shift();
      if (visited.has(node)) continue;
      visited.add(node);
      if (node === dest) break;
      for (const [nb, w] of STADIUM_GRAPH[node].neighbors) {
        if (avoid.includes(nb) && nb !== dest) continue;
        const nd = d + w;
        if (dist[nb] === undefined || nd < dist[nb]) { dist[nb] = nd; prev[nb] = node; queue.push([nd, nb]); }
      }
    }
    if (dist[dest] === undefined) return null;
    const path = [dest];
    while (path[path.length - 1] !== origin) path.push(prev[path[path.length - 1]]);
    path.reverse();
    return { path, minutes: dist[dest] };
  }

  // ------------------------------------------------------------------
  // CHAT
  // ------------------------------------------------------------------
  const chatLog = document.getElementById('chatLog');
  const chatActions = document.getElementById('chatActions');
  function addChatMsg(from, text) {
    const div = document.createElement('div');
    div.className = 'chat-msg';
    div.dataset.from = from;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }
  addChatMsg('ana', "Hi! I'm Ana, your matchday assistant. Ask me about directions, accessibility, crowds, or transport.");

  const ACTION_LABELS = {
    open_navigation: '🧭 Open Navigate', open_accessibility: '♿ Open Accessibility',
    open_crowd_dashboard: '📊 Open Crowd Pulse', open_transport: '🚌 Open Transport',
  };
  function renderChatActions(actions) {
    chatActions.innerHTML = '';
    (actions || []).forEach(a => {
      if (!ACTION_LABELS[a]) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = ACTION_LABELS[a];
      btn.addEventListener('click', () => {
        const map = { open_navigation: 'tab-navigate', open_accessibility: 'tab-accessibility', open_crowd_dashboard: 'tab-crowd', open_transport: 'tab-transport' };
        selectTab(document.getElementById(map[a]));
      });
      chatActions.appendChild(btn);
    });
  }

  function localChatFallback(message) {
    const m = message.toLowerCase();
    const actions = [];
    if (/(gate|seat|section|where|get to)/.test(m)) actions.push('open_navigation');
    if (/(wheelchair|accessible|disab|hearing|vision)/.test(m)) actions.push('open_accessibility');
    if (/(crowd|busy|queue|line)/.test(m)) actions.push('open_crowd_dashboard');
    if (/(bus|train|parking|shuttle|transport)/.test(m)) actions.push('open_transport');
    return {
      reply: "I can help with directions, accessibility, crowd conditions, and transport. Try the module tabs on the left, or ask me something like 'How do I get to Gate B?'",
      suggested_actions: actions,
    };
  }

  document.getElementById('chatForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;
    addChatMsg('user', msg);
    input.value = '';
    addChatMsg('ana', 'Thinking…');
    const thinkingEl = chatLog.lastChild;

    const apiResult = await callApi('/chat', { message: msg, language: currentLang(), role: 'fan' });
    const result = apiResult || localChatFallback(msg);
    thinkingEl.remove();
    addChatMsg('ana', result.reply);
    renderChatActions(result.suggested_actions);
  });

  // ------------------------------------------------------------------
  // NAVIGATE
  // ------------------------------------------------------------------
  document.getElementById('navForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const origin = document.getElementById('navOrigin').value;
    const dest = document.getElementById('navDest').value;
    const wheelchair = document.getElementById('needWheelchair').checked;
    const resultBox = document.getElementById('navResult');
    resultBox.innerHTML = '<p class="loading-dot">Finding route</p>';

    const apiResult = await callApi('/navigate', {
      origin, destination: dest,
      accessibility_needs: wheelchair ? ['wheelchair'] : [],
      language: currentLang(),
    });

    let payload = apiResult;
    if (!payload) {
      const o = slug(origin), d = slug(dest);
      const avoid = wheelchair ? Object.keys(STADIUM_GRAPH).filter(k => !STADIUM_GRAPH[k].accessible) : [];
      const found = localShortestPath(o, d, avoid);
      if (!found) {
        payload = { steps: [], narrative: `I couldn't find a match for "${origin}" or "${dest}" on the venue map. Try a gate name or a landmark like "Family Zone".`, source: 'fallback' };
      } else {
        const steps = [];
        for (let i = 0; i < found.path.length - 1; i++) {
          const cur = found.path[i], nxt = found.path[i + 1];
          const weight = STADIUM_GRAPH[cur].neighbors.find(n => n[0] === nxt)[1];
          steps.push({ instruction: `From ${STADIUM_GRAPH[cur].name}, proceed to ${STADIUM_GRAPH[nxt].name}.`, estimated_minutes: weight, crowd_level: ['low', 'moderate', 'high'][Math.floor(Math.random() * 3)] });
        }
        payload = { steps, total_minutes: found.minutes, narrative: steps.map(s => s.instruction).join(' '), source: 'fallback', accessible: found.path.every(z => STADIUM_GRAPH[z].accessible) };
      }
    }

    if (!payload.steps || !payload.steps.length) {
      resultBox.innerHTML = `<div class="result-box"><span class="source-tag" data-source="${payload.source}">${payload.source}</span><p>${escapeHtml(payload.narrative)}</p></div>`;
      return;
    }
    const stepsHtml = payload.steps.map(s => `<li><span>${escapeHtml(s.instruction)}</span><span class="crowd-chip" data-level="${escapeHtml(s.crowd_level)}">${escapeHtml(s.crowd_level)}</span></li>`).join('');
    resultBox.innerHTML = `
      <div class="result-box">
        <span class="source-tag" data-source="${payload.source}">${payload.source}</span>
        <p>${escapeHtml(payload.narrative)}</p>
        <ul class="step-list">${stepsHtml}</ul>
        <p style="font-family:var(--font-mono); font-size:0.8rem; margin-top:0.5rem;">Est. total time: ${payload.total_minutes} min ${payload.accessible ? '· ♿ Step-free route' : ''}</p>
      </div>`;
  });

  // ------------------------------------------------------------------
  // CROWD
  // ------------------------------------------------------------------
  const zoneRows = document.getElementById('zoneRows');
  let zoneCount = 0;
  function addZoneRow(name, occ) {
    zoneCount++;
    const id = 'zone' + zoneCount;
    const wrap = document.createElement('div');
    wrap.className = 'zone-input-grid';
    wrap.style.marginBottom = '0.5rem';
    wrap.innerHTML = `
      <div><label for="${id}-name">Zone name</label><input type="text" id="${id}-name" value="${escapeHtml(name)}" /></div>
      <div><label for="${id}-occ">Occupancy %</label><input type="text" inputmode="numeric" id="${id}-occ" value="${occ}" /></div>
      <div><button type="button" class="btn-primary" style="background:var(--pitch-green-700); color:var(--floodlight); padding:0.55rem 0.7rem;" aria-label="Remove this zone">✕</button></div>`;
    wrap.querySelector('button').addEventListener('click', () => wrap.remove());
    zoneRows.appendChild(wrap);
  }
  addZoneRow('Gate A', 65);
  addZoneRow('Concourse North', 92);
  document.getElementById('addZoneBtn').addEventListener('click', () => addZoneRow('New Zone', 50));

  function classifyOccupancy(occ) {
    if (occ >= 95) return ['critical', 'Immediate action required: halt inflow and open overflow route.'];
    if (occ >= 85) return ['high', 'Deploy additional stewards and open an alternate concourse.'];
    if (occ >= 70) return ['medium', 'Monitor closely; consider soft crowd redirection.'];
    return ['low', 'No action required.'];
  }

  function updatePulse(avg) {
    const circle = document.getElementById('pulseCircle');
    const circumference = 377;
    const offset = circumference - (Math.min(avg, 100) / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    if (avg >= 85) circle.style.stroke = 'var(--alert-critical)';
    else if (avg >= 70) circle.style.stroke = 'var(--alert-medium)';
    else circle.style.stroke = 'var(--gold)';
    document.getElementById('pulseLabel').textContent = Math.round(avg) + '%';
  }

  document.getElementById('crowdForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const rows = Array.from(zoneRows.children);
    const zones = rows.map(r => ({
      zone_id: r.querySelector('input[id$="-name"]').value || 'zone',
      occupancy_percent: Math.max(0, Math.min(100, parseFloat(r.querySelector('input[id$="-occ"]').value) || 0)),
    })).filter(z => z.zone_id);

    const resultBox = document.getElementById('crowdResult');
    resultBox.innerHTML = '<p class="loading-dot">Analyzing</p>';

    if (zones.length) {
      updatePulse(zones.reduce((a, z) => a + z.occupancy_percent, 0) / zones.length);
    }

    const apiResult = await callApi('/crowd/analyze', { zones, event_phase: 'in-match' });
    let payload = apiResult;
    if (!payload) {
      const alerts = zones.map(z => {
        const [severity, action] = classifyOccupancy(z.occupancy_percent);
        return severity === 'low' ? null : { zone_id: z.zone_id, severity, message: `${z.zone_id} is at ${z.occupancy_percent.toFixed(0)}% capacity.`, recommended_action: action };
      }).filter(Boolean);
      const order = { critical: 0, high: 1, medium: 2 };
      alerts.sort((a, b) => order[a.severity] - order[b.severity]);
      const summary = alerts.length ? `${alerts.length} zone(s) require attention. Highest priority: ${alerts[0].message}` : 'All monitored zones are within safe capacity thresholds.';
      payload = { alerts, overall_summary: summary, source: 'fallback' };
    }

    document.getElementById('pulseSummaryLine').textContent = payload.overall_summary;
    const alertsHtml = payload.alerts.length
      ? payload.alerts.map(a => `<div class="alert-item" data-severity="${escapeHtml(a.severity)}"><div class="alert-item__meta">${escapeHtml(a.severity)} · ${escapeHtml(a.zone_id)}</div><div>${escapeHtml(a.message)}</div><div style="margin-top:0.3rem; font-weight:600;">→ ${escapeHtml(a.recommended_action)}</div></div>`).join('')
      : '<p>No active alerts. All zones nominal.</p>';
    resultBox.innerHTML = `<div class="result-box" data-severity="${payload.alerts[0] ? payload.alerts[0].severity : 'low'}"><span class="source-tag" data-source="${payload.source}">${payload.source}</span><p>${escapeHtml(payload.overall_summary)}</p>${alertsHtml}</div>`;
  });

  // ------------------------------------------------------------------
  // TRANSPORT — local fallback mirrors app/data/transit.py + app/services/transport.py
  // ------------------------------------------------------------------
  const PARKING_LOTS = {
    lot_north: { name: 'North Lot (P1)', capacity: 1200, occupied: 1140, walkMinutes: 6, gate: 'Gate A', accessibleSpaces: 40, accessibleOccupied: 22 },
    lot_east: { name: 'East Lot (P2)', capacity: 900, occupied: 540, walkMinutes: 8, gate: 'Gate B', accessibleSpaces: 30, accessibleOccupied: 11 },
    lot_south_overflow: { name: 'South Overflow Lot (P3)', capacity: 1500, occupied: 300, walkMinutes: 15, gate: 'Gate C', accessibleSpaces: 25, accessibleOccupied: 4 },
  };
  const TRANSIT_LINES = {
    shuttle_1: { name: 'Shuttle Line 1 — Downtown Hub', mode: 'shuttle', frequency: 8, walkMinutes: 2, pickup: 'North Transit Hub', gate: 'Gate A', accessible: true, status: 'on_time' },
    shuttle_2: { name: 'Shuttle Line 2 — Riverside Park & Ride', mode: 'shuttle', frequency: 8, walkMinutes: 2, pickup: 'Riverside Park & Ride', gate: 'Gate B', accessible: true, status: 'on_time' },
    metro_blue: { name: 'Metro Blue Line — Stadium Station', mode: 'transit', frequency: 6, walkMinutes: 9, pickup: 'Stadium Station', gate: 'Gate B', accessible: true, status: 'on_time' },
    rail_express: { name: 'Regional Rail Express — Matchday Special', mode: 'transit', frequency: 20, walkMinutes: 12, pickup: 'Central Station', gate: 'Gate C', accessible: false, status: 'on_time' },
  };
  function localTransportOptions(mode, needsAccessible) {
    const options = [];
    if (!mode || mode === 'car') {
      Object.entries(PARKING_LOTS).forEach(([id, lot]) => {
        const occPct = Math.round((lot.occupied / lot.capacity) * 1000) / 10;
        const freeAccessible = Math.max(0, lot.accessibleSpaces - lot.accessibleOccupied);
        if (needsAccessible && freeAccessible <= 0) return;
        const status = occPct >= 98 ? 'full' : (occPct >= 90 ? 'near_full' : 'available');
        let detail = `${occPct.toFixed(0)}% full, ${lot.walkMinutes} min walk to ${lot.gate}.`;
        if (needsAccessible) detail += ` ${freeAccessible} accessible space(s) free.`;
        options.push({ option_id: id, mode: 'car', name: lot.name, detail, eta_minutes: lot.walkMinutes, accessible: freeAccessible > 0, status });
      });
    }
    ['shuttle', 'transit'].forEach(m => {
      if (mode && mode !== m) return;
      Object.entries(TRANSIT_LINES).filter(([, l]) => l.mode === m).forEach(([id, line]) => {
        if (needsAccessible && !line.accessible) return;
        const eta = Math.round((line.frequency / 2 + line.walkMinutes) * 10) / 10;
        const detail = `Every ${line.frequency} min from ${line.pickup}, ${line.walkMinutes} min walk to ${line.gate}.`;
        options.push({ option_id: id, mode: m, name: line.name, detail, eta_minutes: eta, accessible: line.accessible, status: line.status });
      });
    });
    const bad = new Set(['full', 'suspended']);
    options.sort((a, b) => (bad.has(a.status) ? 1 : 0) - (bad.has(b.status) ? 1 : 0) || a.eta_minutes - b.eta_minutes);
    return options;
  }
  const MODE_ICON = { car: '🚗', shuttle: '🚌', transit: '🚆' };
  document.getElementById('transportForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const mode = document.getElementById('transportMode').value || null;
    const partySize = Math.max(1, Math.min(20, parseInt(document.getElementById('transportParty').value, 10) || 1));
    const kickoffRaw = document.getElementById('transportKickoff').value;
    const minutesToKickoff = kickoffRaw === '' ? null : Math.max(0, parseInt(kickoffRaw, 10) || 0);
    const needsAccessible = document.getElementById('transportWheelchair').checked;
    const resultBox = document.getElementById('transportResult');
    resultBox.innerHTML = '<p class="loading-dot">Comparing options</p>';

    const apiResult = await callApi('/transport', {
      mode, party_size: partySize, minutes_to_kickoff: minutesToKickoff,
      accessibility_needs: needsAccessible ? ['wheelchair'] : [], language: currentLang(),
    });
    let payload = apiResult;
    if (!payload) {
      const options = localTransportOptions(mode, needsAccessible);
      const best = options[0];
      const summary = !options.length
        ? (needsAccessible ? 'No accessible transport options currently match your needs. Please check with Guest Services.' : 'No transport options currently match your filters.')
        : `Best option: ${best.name} — ${best.detail}`;
      payload = { options, recommended_option_id: best ? best.option_id : null, summary, source: 'fallback' };
    }

    const optionsHtml = payload.options.map(o => `
      <div class="alert-item" data-severity="${o.status === 'full' || o.status === 'suspended' ? 'critical' : (o.status === 'near_full' || o.status === 'delayed' ? 'medium' : 'low')}">
        <div class="alert-item__meta">${MODE_ICON[o.mode] || ''} ${escapeHtml(o.mode)} · ${escapeHtml(o.status.replace('_', ' '))}${o.option_id === payload.recommended_option_id ? ' · ★ recommended' : ''}</div>
        <div style="font-weight:600;">${escapeHtml(o.name)}</div>
        <div>${escapeHtml(o.detail)}</div>
      </div>`).join('');
    resultBox.innerHTML = `<div class="result-box"><span class="source-tag" data-source="${payload.source}">${payload.source}</span><p>${escapeHtml(payload.summary)}</p>${optionsHtml || '<p>No matching options.</p>'}</div>`;
  });

  // ------------------------------------------------------------------
  // ACCESSIBILITY
  // ------------------------------------------------------------------
  const STATIC_RESOURCES = [
    'Accessible Seating Platform — South Concourse, step-free from Gate A/B/D',
    'Sensory Room — quiet, low-light space near the Family Zone for neurodivergent fans',
    'Wheelchair loan desk — Gate A Guest Services, no reservation required',
    'Assistive listening devices — available at any Guest Services desk',
    'Companion/carer free-entry policy — present accessibility documentation at any gate',
  ];
  document.getElementById('accForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const query = document.getElementById('accQuery').value;
    const needs = Array.from(document.querySelectorAll('.accNeed:checked')).map(c => c.value);
    const resultBox = document.getElementById('accResult');
    resultBox.innerHTML = '<p class="loading-dot">Looking that up</p>';

    const apiResult = await callApi('/accessibility', { query, needs, language: currentLang() });
    const payload = apiResult || {
      guidance: `For ${needs.length ? needs.join(', ') : 'your accessibility needs'}, the Accessible Seating Platform on the South Concourse is step-free from Gates A, B and D. Guest Services desks near every gate can arrange a wheelchair escort, assistive listening device, or sensory-room access on request.`,
      resources: STATIC_RESOURCES, source: 'fallback',
    };
    resultBox.innerHTML = `<div class="result-box"><span class="source-tag" data-source="${payload.source}">${payload.source}</span><p>${escapeHtml(payload.guidance)}</p><ul class="step-list">${payload.resources.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul></div>`;
  });

  // ------------------------------------------------------------------
  // SUSTAINABILITY
  // ------------------------------------------------------------------
  document.getElementById('susForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const context = document.getElementById('susContext').value;
    const resultBox = document.getElementById('susResult');
    resultBox.innerHTML = '<p class="loading-dot">Thinking of ideas</p>';

    const apiResult = await callApi('/sustainability', { context });
    const payload = apiResult || {
      tips: [
        'Use the reusable cup scheme at any concession stand to skip single-use plastics.',
        'Take the shuttle or metro — parking near the stadium is limited and transit cuts per-fan emissions sharply.',
        'Sort waste at the clearly marked tri-bin stations throughout the concourse.',
      ], source: 'fallback',
    };
    resultBox.innerHTML = `<div class="result-box"><span class="source-tag" data-source="${payload.source}">${payload.source}</span><ul class="step-list">${payload.tips.map(t => `<li>🌱 ${escapeHtml(t)}</li>`).join('')}</ul></div>`;
  });

  // ------------------------------------------------------------------
  // EMERGENCY
  // ------------------------------------------------------------------
  const ESCALATE_KEYWORDS = ['fire', 'collapse', 'weapon', 'gun', 'knife', 'unconscious', 'cardiac', 'chest pain', 'seizure', 'bleeding', 'stampede', 'crush', 'bomb', 'explosion'];
  document.getElementById('emergForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const situation = document.getElementById('emergSituation').value;
    const zone = document.getElementById('emergZone').value;
    const resultBox = document.getElementById('emergResult');
    resultBox.innerHTML = '<p class="loading-dot">Getting guidance</p>';

    const apiResult = await callApi('/emergency', { situation, zone_id: zone || null, language: currentLang() });
    const mustEscalate = ESCALATE_KEYWORDS.some(k => situation.toLowerCase().includes(k));
    const payload = apiResult || {
      instructions: mustEscalate
        ? ['This situation requires immediate human responder attention — contact the control room now.', 'Stay calm and move away from the immediate area if safe to do so.', 'Alert the nearest steward or staff member in a high-visibility vest.']
        : ['Stay calm and move away from the immediate area if safe to do so.', 'Alert the nearest steward or staff member in a high-visibility vest.', 'Do not re-enter a cleared area until stewards confirm it is safe.'],
      escalate_to_human: mustEscalate, hotline: 'Stadium Emergency Control Room: internal ext. 4444 / radio channel 1', source: 'fallback',
    };
    resultBox.innerHTML = `
      <div class="result-box" data-severity="${payload.escalate_to_human ? 'critical' : 'low'}">
        <span class="source-tag" data-source="${payload.source}">${payload.source}</span>
        ${payload.escalate_to_human ? '<p style="color:var(--alert-critical); font-weight:700;">⚠ HUMAN RESPONDER REQUIRED</p>' : ''}
        <ul class="step-list">${payload.instructions.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>
        <p style="font-family:var(--font-mono); font-size:0.8rem; margin-top:0.5rem;">${escapeHtml(payload.hotline)}</p>
      </div>`;
  });

})();
