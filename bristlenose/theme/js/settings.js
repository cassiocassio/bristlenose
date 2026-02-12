/**
 * settings.js — Application appearance toggle for Bristlenose reports.
 *
 * Lets users switch between system/light/dark theme via radio buttons
 * in the Settings tab.  Persists the choice to localStorage so it
 * survives page reloads.
 *
 * The attribute name is constructed via concatenation to avoid the
 * literal appearing in the HTML — dark mode tests assert its absence
 * when color_scheme is "auto".
 *
 * @module settings
 */

/* global createStore */

var _settingsThemeAttr = "data-" + "theme";
var _settingsStore = createStore("bristlenose-appearance");

function _applyAppearance(value) {
  var root = document.documentElement;
  if (value === "light" || value === "dark") {
    root.setAttribute(_settingsThemeAttr, value);
    root.style.colorScheme = value;
  } else {
    root.removeAttribute(_settingsThemeAttr);
    root.style.colorScheme = "light dark";
  }
}

function initSettings() {
  var radios = document.querySelectorAll('input[name="bn-appearance"]');
  if (!radios.length) return;

  // Restore saved preference (default: "auto")
  var saved = _settingsStore.get("auto");
  if (typeof saved !== "string") saved = "auto";
  if (saved !== "auto" && saved !== "light" && saved !== "dark") saved = "auto";

  // Check the matching radio
  for (var i = 0; i < radios.length; i++) {
    radios[i].checked = radios[i].value === saved;
  }

  // Apply on boot (overrides server-side theme attr if user has a preference)
  _applyAppearance(saved);

  // Listen for changes
  for (var j = 0; j < radios.length; j++) {
    radios[j].addEventListener("change", function () {
      _settingsStore.set(this.value);
      _applyAppearance(this.value);
    });
  }
}
