/* Optional "Dictate this case" add-on (dictation app).
 * Uses the phone/browser's built-in speech recognition (free), sends the text to
 * /dictation/parse/ and fills the Add Case form. Nothing is saved until the
 * doctor taps "Save case". If the browser has no speech recognition, the doctor
 * can type, or use the microphone key on the phone keyboard, in the text box.
 */
(function () {
  "use strict";
  var panel = document.getElementById("dictation");
  var form = document.getElementById("case-form");
  if (!panel || !form) return;

  var mic = document.getElementById("dictation-mic");
  var status = document.getElementById("dictation-status");
  var body = document.getElementById("dictation-body");
  var box = document.getElementById("dictation-text");
  var result = document.getElementById("dictation-result");
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognizer = null, listening = false, finalText = "";

  function $(id) { return document.getElementById(id); }
  function showBody() { body.classList.remove("d-none"); }
  function esc(t) { return String(t || "").replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  $("dictation-toggle").addEventListener("click", function () { showBody(); box.focus(); });
  $("dictation-clear").addEventListener("click", function () { box.value = ""; finalText = ""; result.innerHTML = ""; box.focus(); });
  $("dictation-fill").addEventListener("click", fill);

  if (!Recognition) {
    mic.disabled = true;
    status.textContent = "Voice not supported in this browser - tap “Type instead” and use the mic key on your keyboard.";
  }

  function setListening(on) {
    listening = on;
    mic.classList.toggle("btn-danger", on);
    mic.classList.toggle("btn-outline-primary", !on);
    mic.innerHTML = on ? '<i class="bi bi-stop-fill"></i>' : '<i class="bi bi-mic-fill"></i>';
    status.textContent = on ? "Listening... tap again when done." : "Tap the mic and say it in one go.";
  }

  mic.addEventListener("click", function () {
    if (!Recognition) return;
    if (listening) { recognizer.stop(); return; }
    showBody();
    recognizer = new Recognition();
    recognizer.lang = "en-IN";
    recognizer.interimResults = true;
    recognizer.continuous = true;
    finalText = box.value ? box.value.trim() + " " : "";
    recognizer.onresult = function (e) {
      var interim = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript.trim() + " ";
        else interim += e.results[i][0].transcript;
      }
      box.value = (finalText + interim).trim();
    };
    recognizer.onerror = function (e) {
      status.textContent = e.error === "not-allowed" || e.error === "service-not-allowed"
        ? "Microphone blocked - allow it in the browser settings, or type instead."
        : (e.error === "no-speech" ? "Didn't hear anything - try again." : "Voice stopped (" + e.error + ").");
    };
    recognizer.onend = function () {
      var wasListening = listening;
      setListening(false);
      if (wasListening && box.value.trim()) fill();
    };
    try { recognizer.start(); setListening(true); } catch (err) { setListening(false); }
  });

  function csrf() {
    var input = form.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function fill() {
    var text = box.value.trim();
    if (!text) { box.focus(); return; }
    result.innerHTML = '<span class="text-muted">Reading...</span>';
    var payload = { text: text };
    if ($("id_doctor") && $("id_doctor").value) payload.doctor = $("id_doctor").value;
    fetch(panel.dataset.parseUrl, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); }).then(apply).catch(function () {
      result.innerHTML = '<span class="text-danger">Could not read that - please fill the form by hand.</span>';
    });
  }

  function mark(el) {
    if (!el) return;
    // Searchable selects are hidden behind a text box - highlight that box instead.
    var target = el.classList.contains("d-none") ? (el.parentNode.querySelector(".combo-input") || el) : el;
    target.classList.add("dictated");
    setTimeout(function () { target.classList.remove("dictated"); }, 2500);
  }

  function setValue(id, value) {
    var el = $(id);
    if (!el || value === null || value === undefined || value === "") return;
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    mark(el);
  }

  function setHospital(h) {
    var select = $("id_hospital");
    if (!select || !h) return;
    if (!select.querySelector('option[value="' + h.id + '"]')) {
      var opt = document.createElement("option");
      opt.value = h.id;
      opt.text = h.sub ? h.label + " - " + h.sub : h.label;
      select.appendChild(opt);
    }
    select.value = String(h.id);
    select.dispatchEvent(new Event("change", { bubbles: true }));
    mark(select);
  }

  function apply(data) {
    var f = data.fields || {};
    setValue("id_case_date", f.case_date);
    setValue("id_fee", f.fee);
    setValue("id_due_date", f.due_date);
    setValue("id_procedure_type", f.procedure_type);
    setValue("id_patient_reference", f.patient_reference);
    if (f.department) setValue("id_department", f.department);
    if (f.contact) setValue("id_contact", f.contact);
    if (f.new_contact_name) {
      var newBox = $("new-contact-fields");
      if (newBox) newBox.classList.remove("d-none");
      if ($("id_contact")) $("id_contact").value = "";
      setValue("id_new_contact_name", f.new_contact_name);
      setValue("id_new_contact_phone", f.new_contact_phone);
    }
    if (f.notes && $("id_notes")) {
      var notes = $("id_notes");
      notes.value = notes.value ? notes.value + "\n" + f.notes : f.notes;
      var details = notes.closest("details");
      if (details) details.open = true;
      mark(notes);
    }
    if (f.hospital) setHospital(f.hospital);

    var html = "";
    if (data.filled && data.filled.length) {
      html += '<div class="text-success mb-1"><i class="bi bi-check2-circle"></i> Filled - please check before saving:</div><ul class="mb-1 ps-3">';
      data.filled.forEach(function (x) { html += "<li><strong>" + esc(x.label) + ":</strong> " + esc(x.value) + "</li>"; });
      html += "</ul>";
    } else {
      html += '<div class="text-warning">Couldn’t pick out any details - try saying the hospital name and fee.</div>';
    }
    var alts = data.hospital_alternatives || [];
    if (alts.length) {
      html += '<div class="mb-1">' + (f.hospital ? "Not this hospital? " : "Which hospital? ");
      alts.forEach(function (h, i) {
        html += '<button type="button" class="btn btn-outline-secondary btn-sm me-1 mb-1" data-alt="' + i + '">' + esc(h.label) + "</button>";
      });
      html += "</div>";
    }
    if (data.missing && data.missing.length) {
      html += '<div class="text-danger"><i class="bi bi-exclamation-circle"></i> Still needed: ' + esc(data.missing.join(", ")) + "</div>";
    }
    result.innerHTML = html;
    result.querySelectorAll("[data-alt]").forEach(function (btn) {
      btn.addEventListener("click", function () { setHospital(alts[parseInt(btn.dataset.alt, 10)]); btn.classList.add("active"); });
    });
  }
})();
