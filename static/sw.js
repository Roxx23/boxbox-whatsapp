/* Service worker: shows browser notifications for incoming WhatsApp messages.
   Served at /sw.js (site root) so it covers every page. No caching / offline. */

self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (event) { event.waitUntil(self.clients.claim()); });

self.addEventListener('push', function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data ? event.data.text() : '' }; }
  var title = data.title || 'New WhatsApp message';
  var options = {
    body: data.body || '',
    tag: data.tag || 'inbox',
    renotify: true,                     // buzz again when the same customer sends another message
    icon: '/static/icons/icon-192.png',
    data: { url: data.url || '/inbox' }
  };
  var jobs = [self.registration.showNotification(title, options)];
  if (typeof data.unread === 'number' && self.navigator && 'setAppBadge' in self.navigator) {
    jobs.push(self.navigator.setAppBadge(data.unread).catch(function () {}));
  }
  event.waitUntil(Promise.all(jobs));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = new URL((event.notification.data && event.notification.data.url) || '/inbox', self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (wins) {
      // Reuse an open dashboard tab: navigate it to the thread, then focus it.
      // navigate() fails on a tab this worker doesn't control; open a new one then.
      for (var i = 0; i < wins.length; i++) {
        var w = wins[i];
        if (new URL(w.url).origin === self.location.origin && 'navigate' in w) {
          return w.navigate(url)
            .then(function (nw) { return (nw || w).focus(); })
            .catch(function () { return self.clients.openWindow(url); });
        }
      }
      return self.clients.openWindow(url);
    })
  );
});

// The push service rotated the subscription: subscribe again and tell the server.
self.addEventListener('pushsubscriptionchange', function (event) {
  event.waitUntil(
    fetch('/api/push/config', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (cfg) {
        if (!cfg.enabled || !cfg.public_key) return;
        return self.registration.pushManager.subscribe({
          userVisibleOnly: true, applicationServerKey: urlB64ToUint8Array(cfg.public_key)
        }).then(function (sub) {
          return fetch('/api/push/subscribe', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sub)
          });
        });
      }).catch(function () {})
  );
});

function urlB64ToUint8Array(b64) {
  var pad = '='.repeat((4 - b64.length % 4) % 4);
  var raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  var out = new Uint8Array(raw.length);
  for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}
