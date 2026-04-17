(function () {
  const installButtons = Array.from(document.querySelectorAll('[data-install-app]'));
  const notifyButtons = Array.from(document.querySelectorAll('[data-enable-notifications]'));
  let deferredPrompt = null;

  const setInstallVisibility = (visible) => {
    installButtons.forEach((button) => {
      button.hidden = !visible;
      button.setAttribute('aria-hidden', visible ? 'false' : 'true');
    });
  };

  const setNotifyState = (text, disabled = false) => {
    notifyButtons.forEach((button) => {
      button.textContent = text;
      button.disabled = disabled;
    });
  };

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch((error) => console.error('serviceWorker registration failed', error));
    });
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;
    setInstallVisibility(true);
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    setInstallVisibility(false);
  });

  installButtons.forEach((button) => {
    button.addEventListener('click', async () => {
      if (!deferredPrompt) {
        return;
      }
      deferredPrompt.prompt();
      await deferredPrompt.userChoice.catch(() => null);
      deferredPrompt = null;
      setInstallVisibility(false);
    });
  });

  if ('Notification' in window) {
    if (Notification.permission === 'granted') {
      setNotifyState('Notifications enabled', true);
    } else if (Notification.permission === 'denied') {
      setNotifyState('Notifications blocked', true);
    } else {
      setNotifyState('Enable notifications');
    }

    notifyButtons.forEach((button) => {
      button.addEventListener('click', async () => {
        const permission = await Notification.requestPermission();
        if (permission === 'granted') {
          setNotifyState('Notifications enabled', true);
        } else if (permission === 'denied') {
          setNotifyState('Notifications blocked', true);
        }
      });
    });
  } else {
    setNotifyState('Notifications unavailable', true);
  }
})();