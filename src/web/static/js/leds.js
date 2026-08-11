import { api } from './api.js';

const elements = {
  section: null,
  status: null,
  onBtn: null,
  offBtn: null,
  colorInput: null,
  brightnessInput: null,
  autoToggle: null,
  autoInfo: null,
};

let colorTimeout;
let brightnessTimeout;

function rgbToHex(rgb) {
  if (!Array.isArray(rgb) || rgb.length < 3) return '#ffffff';
  return '#' + rgb.slice(0, 3).map((c) => c.toString(16).padStart(2, '0')).join('');
}

function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function updateAutoUi(auto) {
  if (!elements.autoToggle) return;
  if (!auto) {
    elements.autoToggle.checked = false;
    elements.autoToggle.disabled = true;
    if (elements.autoInfo) elements.autoInfo.textContent = 'Automatización no disponible.';
    return;
  }
  elements.autoToggle.disabled = false;
  elements.autoToggle.checked = auto.auto_enabled;
  if (elements.autoInfo) {
    const moment = auto.is_night ? 'Noche' : 'Día';
    elements.autoInfo.textContent =
      `${moment} · Amanecer ${formatTime(auto.sunrise)} · Atardecer ${formatTime(auto.sunset)}` +
      ` · Encendido a las ${formatTime(auto.light_on_time)}`;
  }
}

function updateUi(state) {
  if (!state.enabled) {
    elements.section.innerHTML = `
      <h2>Luces LED</h2>
      <div class="led-disabled">Control de LEDs deshabilitado en el backend.</div>
    `;
    return;
  }

  elements.status.textContent = state.on ? 'Encendidas' : 'Apagadas';
  if (state.color) elements.colorInput.value = rgbToHex(state.color);
  if (state.brightness !== undefined) elements.brightnessInput.value = state.brightness;
  updateAutoUi(state.auto);
}

async function callLedApi(path, body) {
  try {
    const data = body ? await api[path](body) : await api[path]();
    if (data.state) updateUi(data.state);
    return data.success;
  } catch (err) {
    console.error('Error LED API:', err);
    elements.status.textContent = 'Error de conexión';
    return false;
  }
}

async function toggleAuto(enabled) {
  try {
    const data = await api.ledAuto({ enabled });
    updateAutoUi(data.state);
    return data.success;
  } catch (err) {
    console.error('Error en la automatización de LEDs:', err);
    if (elements.autoInfo) elements.autoInfo.textContent = 'Error de conexión';
    return false;
  }
}

export async function initLeds() {
  elements.section = document.getElementById('led-section');
  elements.status = document.getElementById('led-status');
  elements.onBtn = document.getElementById('led-on');
  elements.offBtn = document.getElementById('led-off');
  elements.colorInput = document.getElementById('led-color');
  elements.brightnessInput = document.getElementById('led-brightness');
  elements.autoToggle = document.getElementById('led-auto');
  elements.autoInfo = document.getElementById('led-auto-info');

  if (!elements.section) return;

  try {
    const state = await api.ledStatus();
    updateUi(state);
    if (!state.enabled) return;
  } catch {
    elements.section.innerHTML = `
      <h2>Luces LED</h2>
      <div class="led-disabled">No se pudo cargar el estado de las luces.</div>
    `;
    return;
  }

  elements.onBtn.addEventListener('click', () => callLedApi('ledOn'));
  elements.offBtn.addEventListener('click', () => callLedApi('ledOff'));

  elements.colorInput.addEventListener('input', (e) => {
    clearTimeout(colorTimeout);
    colorTimeout = setTimeout(() => {
      const hex = e.target.value;
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      callLedApi('ledColor', { r, g, b });
    }, 200);
  });

  elements.brightnessInput.addEventListener('input', (e) => {
    clearTimeout(brightnessTimeout);
    brightnessTimeout = setTimeout(() => {
      callLedApi('ledBrightness', { brightness: parseInt(e.target.value, 10) });
    }, 200);
  });

  if (elements.autoToggle) {
    elements.autoToggle.addEventListener('change', (e) => {
      toggleAuto(e.target.checked);
    });
  }
}
