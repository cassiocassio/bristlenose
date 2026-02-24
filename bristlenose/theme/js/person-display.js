/**
 * person-display.js — Person display mode toggle.
 *
 * Lets users switch between "code and name" and "code only" display
 * for speaker badges.  Persists the choice to localStorage so it
 * survives page reloads.
 *
 * The attribute name is constructed via concatenation to avoid the
 * literal appearing in the HTML — same pattern as settings.js.
 *
 * @module person-display
 */

/* global createStore */

var _personDisplayAttr = "data-" + "person-display";
var _personDisplayStore = createStore("bristlenose-person-display");

function _applyPersonDisplay(value) {
  var root = document.documentElement;
  if (value === "code") {
    root.setAttribute(_personDisplayAttr, value);
  } else {
    root.removeAttribute(_personDisplayAttr);
  }
}

function initPersonDisplay() {
  var radios = document.querySelectorAll('input[name="bn-person-display"]');
  if (!radios.length) return;

  // Restore saved preference (default: "code-and-name")
  var saved = _personDisplayStore.get("code-and-name");
  if (typeof saved !== "string") saved = "code-and-name";
  if (saved !== "code-and-name" && saved !== "code") saved = "code-and-name";

  // Check the matching radio
  for (var i = 0; i < radios.length; i++) {
    radios[i].checked = radios[i].value === saved;
  }

  // Apply on boot
  _applyPersonDisplay(saved);

  // Listen for changes
  for (var j = 0; j < radios.length; j++) {
    radios[j].addEventListener("change", function () {
      _personDisplayStore.set(this.value);
      _applyPersonDisplay(this.value);
    });
  }
}
