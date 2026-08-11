import { ENDPOINTS } from './config.js';

async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => 'Error HTTP');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => 'Error HTTP');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => getJson(ENDPOINTS.health),
  obdData: () => getJson(ENDPOINTS.obdData),
  obdStatus: () => getJson(ENDPOINTS.obdStatus),
  obdRecommendations: () => getJson(ENDPOINTS.obdRecommendations),
  obdDtcs: () => getJson(ENDPOINTS.obdDtcs),
  ledStatus: () => getJson(ENDPOINTS.ledStatus),
  ledOn: () => postJson(ENDPOINTS.ledOn),
  ledOff: () => postJson(ENDPOINTS.ledOff),
  ledColor: ({ r, g, b }) => postJson(ENDPOINTS.ledColor, { r, g, b }),
  ledBrightness: ({ brightness }) => postJson(ENDPOINTS.ledBrightness, { brightness }),
  ledAuto: ({ enabled }) => postJson(ENDPOINTS.ledAuto, { enabled }),
};
