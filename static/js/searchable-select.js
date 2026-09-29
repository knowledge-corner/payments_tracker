/* Searchable select ("type to search") for long dropdowns such as hospitals.
 *
 * Usage: <select data-searchable data-placeholder="Search hospital">...</select>
 *
 * The original <select> stays in the form (hidden) so normal form submission,
 * validation and "change" listeners keep working. Matching is "contains"
 * anywhere in the text, case-insensitive; with several words, every word must
 * appear somewhere (e.g. "ruby cl" finds "Ruby Hall Clinic").
 */
(function () {
  "use strict";

  function normalise(text) {
    return (text || "").toLowerCase().replace(/[^a-z0-9ऀ-ॿ]+/g, " ").trim();
  }

  function escapeHtml(text) {
    return text.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function highlight(label, tokens) {
    var html = escapeHtml(label);
    tokens.forEach(function (token) {
      if (!token) return;
      var re = new RegExp("(" + token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
      html = html.replace(re, "<mark>$1</mark>");
    });
    return html;
  }

  function enhance(select) {
    if (select.dataset.searchableReady) return;
    select.dataset.searchableReady = "1";

    var wrapper = document.createElement("div");
    wrapper.className = "combo";
    var input = document.createElement("input");
    input.type = "text";
    input.className = "form-control combo-input" + (select.classList.contains("form-select-sm") ? " form-control-sm" : "");
    input.autocomplete = "off";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-autocomplete", "list");
    input.placeholder = select.dataset.placeholder || "Type to search";
    if (select.id) {
      input.id = select.id + "_search";
      var label = document.querySelector('label[for="' + select.id + '"]');
      if (label) label.setAttribute("for", input.id);
    }
    var caret = document.createElement("i");
    caret.className = "bi bi-search combo-caret";
    var menu = document.createElement("div");
    menu.className = "combo-menu";
    menu.setAttribute("role", "listbox");

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(input);
    wrapper.appendChild(caret);
    wrapper.appendChild(menu);
    wrapper.appendChild(select);
    select.classList.add("d-none");
    select.tabIndex = -1;

    var options = Array.prototype.map.call(select.options, function (o) {
      return { value: o.value, label: o.text, key: normalise(o.text), empty: o.value === "" };
    });
    var visible = [];
    var active = -1;

    function selectedLabel() {
      var opt = select.options[select.selectedIndex];
      return opt && opt.value !== "" ? opt.text : "";
    }

    function render(query) {
      var tokens = normalise(query).split(" ").filter(Boolean);
      visible = options.filter(function (o) {
        if (o.empty) return tokens.length === 0; // "All hospitals" only when not searching
        return tokens.every(function (t) { return o.key.indexOf(t) !== -1; });
      });
      if (!visible.length) {
        menu.innerHTML = '<div class="combo-empty">No match for "' + escapeHtml(query) + '"</div>';
      } else {
        menu.innerHTML = visible.map(function (o, i) {
          var cls = "combo-item" + (o.value === select.value ? " selected" : "") + (o.empty ? " text-muted" : "");
          return '<div class="' + cls + '" role="option" data-index="' + i + '">' + highlight(o.label, tokens) + "</div>";
        }).join("");
      }
      active = visible.length ? 0 : -1;
      paintActive();
    }

    function paintActive() {
      var items = menu.querySelectorAll(".combo-item");
      items.forEach(function (el, i) { el.classList.toggle("active", i === active); });
      if (items[active]) items[active].scrollIntoView({ block: "nearest" });
    }

    function open() {
      wrapper.classList.add("open");
      input.setAttribute("aria-expanded", "true");
    }

    function close() {
      wrapper.classList.remove("open");
      input.setAttribute("aria-expanded", "false");
    }

    function choose(option) {
      var changed = select.value !== option.value;
      select.value = option.value;
      input.value = option.empty ? "" : option.label;
      close();
      if (changed) select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    input.value = selectedLabel();

    input.addEventListener("focus", function () {
      input.select();
      render("");
      open();
    });
    input.addEventListener("input", function () {
      render(input.value);
      open();
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!wrapper.classList.contains("open")) { render(input.value); open(); }
        active = Math.min(active + 1, visible.length - 1);
        paintActive();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        active = Math.max(active - 1, 0);
        paintActive();
      } else if (e.key === "Enter") {
        if (wrapper.classList.contains("open") && visible[active]) {
          e.preventDefault();
          choose(visible[active]);
        }
      } else if (e.key === "Escape") {
        input.value = selectedLabel();
        close();
      }
    });
    // mousedown (not click) so it fires before the input loses focus
    menu.addEventListener("mousedown", function (e) {
      var item = e.target.closest(".combo-item");
      if (!item) return;
      e.preventDefault();
      choose(visible[parseInt(item.dataset.index, 10)]);
    });
    input.addEventListener("blur", function () {
      setTimeout(function () {
        if (!wrapper.classList.contains("open")) return;
        // Typed text that exactly matches one option selects it; otherwise restore.
        var typed = normalise(input.value);
        var exact = options.filter(function (o) { return !o.empty && o.key === typed; });
        if (exact.length === 1) {
          choose(exact[0]);
        } else if (!typed && options.some(function (o) { return o.empty; })) {
          choose(options.filter(function (o) { return o.empty; })[0]);
        } else {
          input.value = selectedLabel();
          close();
        }
      }, 120);
    });
    select.addEventListener("change", function () {
      if (document.activeElement !== input) input.value = selectedLabel();
    });
  }

  document.querySelectorAll("select[data-searchable]").forEach(enhance);
  window.enhanceSearchableSelect = enhance;
})();
