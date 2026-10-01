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
