/* Push notifications: turn on/off for this device and keep the server's copy of the subscription fresh. */
(function () {
  "use strict";
  var cfg = document.getElementById("push-config");
  if (!cfg) return;
  var urls = { key: cfg.dataset.keyUrl, sub: cfg.dataset.subscribeUrl, unsub: cfg.dataset.unsubscribeUrl };

  var supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function post(url, data) {
    return fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(data),
    });
  }
  function keyBytes(b64) {
    var pad = "=".repeat((4 - (b64.length % 4)) % 4);
    var raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function currentSubscription() {
    return navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); });
  }

  function enable() {
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") throw new Error("denied");
      return Promise.all([navigator.serviceWorker.ready, fetch(urls.key).then(function (r) { return r.json(); })]);
    }).then(function (res) {
      return res[0].pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(res[1].publicKey) });
    }).then(function (sub) {
      return post(urls.sub, sub.toJSON());
    });
  }
  function disable() {
    return currentSubscription().then(function (sub) {
      if (!sub) return;
      return post(urls.unsub, { endpoint: sub.endpoint }).then(function () { return sub.unsubscribe(); });
    });
  }

  // Keep the server in sync (e.g. after signing in again on the same phone).
  if (supported && Notification.permission === "granted") {
    currentSubscription().then(function (sub) { if (sub) post(urls.sub, sub.toJSON()); }).catch(function () {});
  }

  // ---- Settings page widget -------------------------------------------------
  var box = document.getElementById("push-device");
  function render(state) {
    if (!box) return;
    var text = box.querySelector("[data-status]");
    var on = box.querySelector("[data-enable]");
    var off = box.querySelector("[data-disable]");
    var hint = box.querySelector("[data-hint]");
    on.classList.add("d-none"); off.classList.add("d-none"); hint.textContent = "";
    if (state === "unsupported") {
      text.innerHTML = '<i class="bi bi-x-circle text-muted"></i> This browser does not support notifications.';
      if (isIOS && !standalone) hint.textContent = "On iPhone: open this site in Safari, tap Share > Add to Home Screen, then open the app from its icon and come back here (iOS 16.4 or later).";
    } else if (state === "blocked") {
      text.innerHTML = '<i class="bi bi-slash-circle text-danger"></i> Blocked in this browser’s settings.';
      hint.textContent = "Allow notifications for this site in the browser/phone settings, then reload this page.";
    } else if (state === "on") {
      text.innerHTML = '<i class="bi bi-bell-fill text-success"></i> On for this device.';
      off.classList.remove("d-none");
    } else {
      text.innerHTML = '<i class="bi bi-bell-slash text-muted"></i> Off for this device.';
      on.classList.remove("d-none");
    }
  }
  function refresh() {
    if (!supported) return render("unsupported");
    if (Notification.permission === "denied") return render("blocked");
    currentSubscription().then(function (sub) { render(sub ? "on" : "off"); }).catch(function () { render("off"); });
  }
  if (box) {
    refresh();
    box.querySelector("[data-enable]").addEventListener("click", function (e) {
      e.target.disabled = true;
      enable().then(function () { location.reload(); })
        .catch(function () { e.target.disabled = false; refresh(); });
    });
    box.querySelector("[data-disable]").addEventListener("click", function (e) {
      e.target.disabled = true;
      disable().then(function () { location.reload(); });
    });
  }

  // ---- Dashboard prompt ------------------------------------------------------
  var banner = document.getElementById("push-banner");
  var dismissed = false;
  try { dismissed = localStorage.getItem("pushBannerDismissed") === "1"; } catch (e) {}
  if (banner && supported && Notification.permission === "default" && !dismissed) {
    banner.classList.remove("d-none");
    banner.querySelector("[data-enable]").addEventListener("click", function () {
      enable().then(function () { banner.classList.add("d-none"); }).catch(function () { banner.classList.add("d-none"); });
    });
    banner.querySelector("[data-dismiss]").addEventListener("click", function () {
      try { localStorage.setItem("pushBannerDismissed", "1"); } catch (e) {}
      banner.classList.add("d-none");
    });
  }
})();
