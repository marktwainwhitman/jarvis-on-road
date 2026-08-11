export async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) {
    console.warn('Service Worker no soportado');
    return;
  }

  try {
    const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    console.log('Service Worker registrado:', registration.scope);
  } catch (err) {
    console.error('Error registrando Service Worker:', err);
  }
}

export function initInstallPrompt() {
  let deferredPrompt = null;

  const installBtn = document.getElementById('install-btn');
  if (installBtn) {
    installBtn.classList.add('hidden');
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;
    if (installBtn) installBtn.classList.remove('hidden');
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    if (installBtn) installBtn.classList.add('hidden');
  });

  if (!installBtn) return;

  installBtn.addEventListener('click', async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    installBtn.classList.add('hidden');
  });
}

export async function requestNotificationPermission() {
  if (!('Notification' in window)) return 'unsupported';
  if (Notification.permission === 'granted') return 'granted';
  if (Notification.permission !== 'default') return Notification.permission;

  try {
    const permission = await Notification.requestPermission();
    return permission;
  } catch (err) {
    console.error('Error solicitando permiso de notificaciones:', err);
    return 'denied';
  }
}

export function showNotification(title, options = {}) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;

  try {
    new Notification(title, {
      icon: '/static/icons/icon.svg',
      badge: '/static/icons/icon.svg',
      ...options,
    });
  } catch (err) {
    console.error('Error mostrando notificación:', err);
  }
}
