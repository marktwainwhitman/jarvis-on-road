import { JarvisSocket } from './ws.js';
import { api } from './api.js';
import { loadRecommendations, render, setConnectionStatus } from './dashboard.js';
import { initLeds } from './leds.js';
import { registerServiceWorker, initInstallPrompt } from './pwa.js';

function initTabs() {
  const buttons = document.querySelectorAll('nav button[data-tab]');
  const tabs = document.querySelectorAll('.tab');

  function showTab(targetId) {
    tabs.forEach((tab) => tab.classList.toggle('active', tab.id === targetId));
    buttons.forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === targetId));
  }

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });
}

function startWebSocket() {
  const socket = new JarvisSocket();

  socket.onopen = () => setConnectionStatus('connected');
  socket.onclose = () => setConnectionStatus('disconnected');
  socket.onerror = () => setConnectionStatus('disconnected');
  socket.onmessage = (raw) => {
    try {
      const data = JSON.parse(raw);
      render(data);
    } catch (err) {
      console.error('Error parseando datos del WebSocket:', err);
    }
  };

  socket.connect();
  return socket;
}

async function fallbackPolling() {
  try {
    const data = await api.obdData();
    render(data);
    setConnectionStatus('connected');
  } catch (err) {
    console.error('Error en polling REST:', err);
    setConnectionStatus('disconnected');
  }
}

async function init() {
  initTabs();

  await registerServiceWorker();
  initInstallPrompt();

  // La arquitectura para notificaciones del sistema está lista en pwa.js.
  // Se solicitará permiso en respuesta a una interacción del usuario en fases futuras.

  await loadRecommendations();
  await initLeds();

  if (window.WebSocket) {
    const socket = startWebSocket();

    // Cuando el documento se vuelve visible, forzar una actualización inmediata.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        fallbackPolling();
      }
    });

    window.addEventListener('beforeunload', () => socket.close());
  } else {
    await fallbackPolling();
    setInterval(fallbackPolling, 1000);
  }
}

init().catch((err) => console.error('Error iniciando la app:', err));
