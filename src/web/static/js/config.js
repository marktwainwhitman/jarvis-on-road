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
  MAF: 'Caudal de aire',
  INTAKE_PRESSURE: 'Presión admisión',
  SHORT_FUEL_TRIM_1: 'Ajuste corto combustible',
  LONG_FUEL_TRIM_1: 'Ajuste largo combustible',
  FUEL_PRESSURE: 'Presión combustible',
  CONTROL_MODULE_VOLTAGE: 'Tensión ECU',
  TIMING_ADVANCE: 'Avance encendido',
  EGR_ERROR: 'Error EGR',
  RUN_TIME: 'Tiempo motor encendido',
  FUEL_LEVEL: 'Combustible',
  O2_B1S1: 'O2 B1S1',
  O2_B1S2: 'O2 B1S2',
  CATALYST_TEMP_B1S1: 'Temp. catalizador B1S1',
  CATALYST_TEMP_B1S2: 'Temp. catalizador B1S2',
  STATUS: 'Estado OBD',
};

export const PID_UNITS = {
  RPM: 'rpm',
  SPEED: 'km/h',
  COOLANT_TEMP: '°C',
  ENGINE_LOAD: '%',
  THROTTLE_POS: '%',
  INTAKE_TEMP: '°C',
  MAF: 'g/s',
  INTAKE_PRESSURE: 'kPa',
  SHORT_FUEL_TRIM_1: '%',
  LONG_FUEL_TRIM_1: '%',
  FUEL_PRESSURE: 'kPa',
  CONTROL_MODULE_VOLTAGE: 'V',
  TIMING_ADVANCE: '°',
  EGR_ERROR: '%',
  RUN_TIME: 's',
  FUEL_LEVEL: '%',
  O2_B1S1: 'V',
  O2_B1S2: 'V',
  CATALYST_TEMP_B1S1: '°C',
  CATALYST_TEMP_B1S2: '°C',
};

export const PRIMARY_PIDS = ['SPEED', 'RPM'];
