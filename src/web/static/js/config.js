const API_BASE = '';

export const ENDPOINTS = {
  health: `${API_BASE}/api/health`,
  obdData: `${API_BASE}/api/obd/data`,
  obdStatus: `${API_BASE}/api/obd/status`,
  obdAlerts: `${API_BASE}/api/obd/alerts`,
  obdRecommendations: `${API_BASE}/api/obd/recommendations`,
  obdDtcs: `${API_BASE}/api/obd/dtcs`,
  ledStatus: `${API_BASE}/api/leds/status`,
  ledOn: `${API_BASE}/api/leds/on`,
  ledOff: `${API_BASE}/api/leds/off`,
  ledColor: `${API_BASE}/api/leds/color`,
  ledBrightness: `${API_BASE}/api/leds/brightness`,
  ledAuto: `${API_BASE}/api/leds/auto`,
};

export const WS_URL = (() => {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
})();

export const PID_LABELS = {
  RPM: 'Revoluciones',
  SPEED: 'Velocidad',
  COOLANT_TEMP: 'Temp. refrigerante',
  ENGINE_LOAD: 'Carga motor',
  THROTTLE_POS: 'Acelerador',
  INTAKE_TEMP: 'Temp. admisión',
  FUEL_LEVEL: 'Combustible',
};

export const PID_UNITS = {
  RPM: 'rpm',
  SPEED: 'km/h',
  COOLANT_TEMP: '°C',
  ENGINE_LOAD: '%',
  THROTTLE_POS: '%',
  INTAKE_TEMP: '°C',
  FUEL_LEVEL: '%',
};

export const PRIMARY_PIDS = ['SPEED', 'RPM'];
