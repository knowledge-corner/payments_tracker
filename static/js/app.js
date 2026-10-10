/* Payments Tracker - small progressive enhancements (works without JS too). */
(function () {
  "use strict";

  // Register the service worker (PWA / offline page).
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
    });
  }

  // "Install app": Android/desktop Chrome use the browser prompt; iPhone gets instructions.
  var installEls = document.querySelectorAll("[data-install-app]");
  var deferredPrompt = null;
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  function showInstall() { installEls.forEach(function (el) { el.classList.remove("d-none"); }); }
  function hideInstall() { installEls.forEach(function (el) { el.classList.add("d-none"); }); }
  if (!standalone) {
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      showInstall();
    });
    if (isIOS) showInstall();
  }
  window.addEventListener("appinstalled", hideInstall);
  installEls.forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.preventDefault();
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () { deferredPrompt = null; hideInstall(); });
      } else {
        var help = document.getElementById("install-help");
        if (help) help.classList.toggle("d-none");
        else alert("To install: tap the Share button, then 'Add to Home Screen'.");
      }
    });
  });

  var fee = document.getElementById("id_fee");

  // "Payment already received" switch reveals amount + mode.
  var paidNow = document.getElementById("id_paid_now");
  var paidBox = document.getElementById("paid-now-fields");
  if (paidNow && paidBox) {
    var sync = function () {
      paidBox.classList.toggle("d-none", !paidNow.checked);
      var amount = document.getElementById("id_paid_amount");
      if (paidNow.checked && amount && !amount.value && fee) amount.placeholder = fee.value || "Amount";
    };
    paidNow.addEventListener("change", sync);
    sync();
  }

  // Auto-hide success messages.
  document.querySelectorAll(".toast-stack .alert-success, .toast-stack .alert-info").forEach(function (el) {
    setTimeout(function () {
      if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(el).close();
    }, 3500);
  });

  // Confirm dangerous actions.
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) e.preventDefault();
    });
  });
})();

/* "Pick from phone contacts": fills name + mobile from the phone's address book.
 * Uses the Contact Picker API (Chrome on Android, HTTPS). Where the browser does
 * not support it (iPhone, desktop) no button is shown and fields are typed as usual.
 * Markup: <button data-contact-pick data-name="#id_name" data-phone="#id_phone" hidden>
 */
(function () {
  "use strict";
  var supported = "contacts" in navigator && "ContactsManager" in window &&
                  typeof navigator.contacts.select === "function";
  var PERMISSION_HELP = "Your phone did not let the app read contacts.\n\n" +
    "Allow it: phone Settings > Apps > Chrome > Permissions > Contacts > Allow.\n" +
    "Then close the app fully, open it again and tap 'Pick from phone contacts'.\n\n" +
    "You can also type the name and number.";
  document.querySelectorAll("[data-contact-pick]").forEach(function (btn) {
    if (!supported) return;
    btn.hidden = false;
    btn.addEventListener("click", function () {
      var busy = btn.innerHTML;
      btn.disabled = true;
      var done = function () { btn.disabled = false; btn.innerHTML = busy; };
      var picking;
      try {
        picking = navigator.contacts.select(["name", "tel"], { multiple: false });
      } catch (err) {
        done();
        alert(PERMISSION_HELP);
        return;
      }
      picking.then(function (picked) {
        done();
        if (!picked || !picked.length) return;  // closed without choosing
        var c = picked[0];
        var name = document.querySelector(btn.dataset.name);
        var phone = document.querySelector(btn.dataset.phone);
        if (name && c.name && c.name.length) name.value = c.name[0];
        if (phone) {
          if (c.tel && c.tel.length) phone.value = c.tel[0].replace(/[^\d+]/g, "").slice(0, 20);
          else alert("This contact has no phone number saved. Please type the number.");
        }
        [name, phone].forEach(function (el) { if (el) el.dispatchEvent(new Event("input", { bubbles: true })); });
      }).catch(function (err) {
        done();
        if (err && err.name === "InvalidStateError") return;  // picker already open
        alert(PERMISSION_HELP);
      });
    });
  });
})();
