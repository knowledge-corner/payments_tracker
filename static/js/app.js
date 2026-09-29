/* Payments Tracker - small progressive enhancements (works without JS too). */
(function () {
  "use strict";

  // Register the service worker (PWA / offline page).
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
    });
  }

  // Android/desktop Chrome: show an "Install app" menu item when installable.
  var deferredPrompt = null;
  var installLink = document.getElementById("install-app");
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    if (installLink) installLink.classList.remove("d-none");
  });
  if (installLink) {
    installLink.addEventListener("click", function (e) {
      e.preventDefault();
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt = null;
      installLink.classList.add("d-none");
    });
  }

  // Add Case: pre-fill fee from the selected hospital's default fee.
  var hospital = document.getElementById("id_hospital");
  var fee = document.getElementById("id_fee");
  if (hospital && fee) {
    var lastAutoFee = fee.value;
    hospital.addEventListener("change", function () {
      var opt = hospital.options[hospital.selectedIndex];
      var defaultFee = opt ? opt.getAttribute("data-fee") : null;
      // Only overwrite the fee if the doctor has not typed a custom amount.
      if (defaultFee && (fee.value === "" || fee.value === lastAutoFee || parseFloat(fee.value) === parseFloat(lastAutoFee))) {
        fee.value = defaultFee;
        lastAutoFee = defaultFee;
        fee.classList.add("is-valid");
        setTimeout(function () { fee.classList.remove("is-valid"); }, 800);
      }
    });
  }

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
