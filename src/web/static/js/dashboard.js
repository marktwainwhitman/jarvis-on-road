import { PID_LABELS, PID_UNITS, PRIMARY_PIDS } from './config.js';
import { api } from './api.js';

let recommendations = {};

export async function loadRecommendations() {
  try {
    const list = await api.obdRecommendations();
    recommendations = Object.fromEntries(list.map((r) => [r.pid, r]));
  } catch (err) {
    console.error('No se pudieron cargar recomendaciones:', err);
  }
}

function formatRange(pid) {
  const rec = recommendations[pid];
  if (!rec) return '';
  const parts = [];
  if (rec.min !== null && rec.min !== undefined) parts.push(`mín ${rec.min}`);
  if (rec.max !== null && rec.max !== undefined) parts.push(`máx ${rec.max}`);
  if (!parts.length) return '';
  return `Recomendado: ${parts.join(' / ')} ${PID_UNITS[pid] || rec.unit || ''}`.trim();
}

function formatLabel(pid) {
  return PID_LABELS[pid] || pid.replace(/_/g, ' ');
}

function formatValue(value) {
  if (value === null || value === undefined) return '—';
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return Number.isInteger(num) ? num : num.toFixed(1);
}

function ensureCard(pid, container, isPrimary = false) {
  let card = document.getElementById(`card-${pid}`);
  if (!card) {
    card = document.createElement('div');
    card.className = 'card';
    card.id = `card-${pid}`;
    card.innerHTML = `
      <div class="label"></div>
      <div class="value">—</div>
      <div class="unit"></div>
      <div class="range"></div>
      <div class="message"></div>
    `;
    container.appendChild(card);
  }
  if (isPrimary) card.classList.add('primary');
  return card;
}

function getOrCreateGrid() {
  let grid = document.getElementById('obd-grid');
  if (!grid) {
    grid = document.createElement('div');
    grid.id = 'obd-grid';
    grid.className = 'card-grid';
    const tab = document.getElementById('tab-dashboard');
    if (tab) tab.prepend(grid);
  }
  return grid;
}

function renderCards(data, pidStatus) {
  const grid = getOrCreateGrid();
  const rendered = new Set();

  for (const [pid, value] of Object.entries(data)) {
    if (
      pid.startsWith('_') ||
      pid === 'connected' ||
      pid === 'alerts' ||
      pid === 'dtcs' ||
      value === null ||
      value === undefined
    ) {
      continue;
    }

    const isPrimary = PRIMARY_PIDS.includes(pid);
    const card = ensureCard(pid, grid, isPrimary);
    const status = (pidStatus && pidStatus[pid]) || { level: 'unknown', message: null };

    card.className = `card ${status.level}`;
    card.classList.toggle('primary', isPrimary);

    card.querySelector('.label').textContent = formatLabel(pid);
    card.querySelector('.value').textContent = formatValue(value);
    card.querySelector('.unit').textContent = PID_UNITS[pid] || '';
    card.querySelector('.range').textContent = formatRange(pid);
    card.querySelector('.message').textContent = status.message || '';

    rendered.add(pid);
  }

  grid.querySelectorAll('.card').forEach((card) => {
    const pid = card.id.replace('card-', '');
    if (!rendered.has(pid)) {
      card.remove();
    }
  });
}

function renderAlerts(alerts, level) {
  const chip = document.getElementById('alert-chip');
  const list = document.getElementById('alerts-list');
  const count = document.getElementById('alerts-count');

  if (chip) {
    chip.className = `status-chip ${level}`;
    chip.querySelector('strong').textContent =
      level === 'ok' ? 'Sin alertas' : level === 'critical' ? 'Crítico' : 'Advertencia';
  }

  if (!list) return;
  list.innerHTML = '';

  if (count) {
    count.textContent = alerts.length || '0';
  }

  if (!alerts || alerts.length === 0) {
    list.innerHTML = '<div class="empty-state">No hay alertas activas</div>';
    return;
  }

  for (const alert of alerts) {
    const div = document.createElement('div');
    div.className = 'alert-item';
    div.innerHTML = `
      <span class="badge ${alert.level}">${alert.level}</span>
      <span><strong>${alert.label}</strong>: ${formatValue(alert.value)}${alert.unit || ''} — ${alert.message}</span>
    `;
    list.appendChild(div);
  }

  if (level === 'critical' && navigator.vibrate) {
    navigator.vibrate([200, 100, 200]);
  }
}

function renderDtcs(dtcs) {
  const list = document.getElementById('dtcs-list');
  const chip = document.getElementById('dtc-chip');
  if (!list) return;

  list.innerHTML = '';

  if (chip) {
    chip.className = `status-chip ${dtcs && dtcs.length ? 'critical' : 'ok'}`;
    chip.querySelector('strong').textContent = dtcs && dtcs.length ? `${dtcs.length} código(s)` : 'Sin DTCs';
  }

  if (!dtcs || dtcs.length === 0) {
    list.innerHTML = '<div class="empty-state">No hay códigos de avería</div>';
    return;
  }

  for (const dtc of dtcs) {
    const div = document.createElement('div');
    div.className = 'dtc-item';
    div.innerHTML = `
      <span class="dtc-code">${dtc.code}</span>
      <span>${dtc.description || 'Descripción no disponible'}</span>
    `;
    list.appendChild(div);
  }
}

export function render(data) {
  const connected = data.connected === true;

  const obdChip = document.getElementById('obd-chip');
  if (obdChip) {
    obdChip.className = `status-chip ${connected ? 'ok' : 'critical'}`;
    obdChip.querySelector('strong').textContent = connected ? 'Conectado' : 'Desconectado';
  }

  const lastUpdate = document.getElementById('last-update');
  if (lastUpdate && data._last_update) {
    const d = new Date(data._last_update);
    lastUpdate.textContent = 'Actualizado: ' + d.toLocaleTimeString();
  }

  const alertsObj = data.alerts || { level: 'ok', alerts: [], pids: {} };
  renderAlerts(alertsObj.alerts, alertsObj.level);
  renderDtcs(data.dtcs);
  renderCards(data, alertsObj.pids);
}

export function setConnectionStatus(status) {
  const dot = document.getElementById('connection-dot');
  const text = document.getElementById('connection-text');
  if (!dot || !text) return;

  dot.className = 'status-dot ' + status;
  if (status === 'connected') {
    text.textContent = 'En vivo';
  } else if (status === 'connecting') {
    text.textContent = 'Reconectando…';
  } else {
    text.textContent = 'Desconectado';
  }
}
