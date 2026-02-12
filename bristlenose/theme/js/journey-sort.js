/**
 * journey-sort.js — Sortable columns for the user journeys table.
 *
 * Adds click-to-sort on the Session column.
 * Default sort: Session ascending.  Click to toggle direction.
 *
 * @module journey-sort
 */

/* exported initJourneySort */

function initJourneySort() {
  var table = document.querySelector('.bn-journey-table');
  if (!table) return;

  var headers = table.querySelectorAll('th.bn-sortable');
  if (!headers.length) return;

  function updateArrows() {
    for (var i = 0; i < headers.length; i++) {
      var h = headers[i];
      var arrow = h.querySelector('.bn-sort-arrow');
      if (!arrow) continue;

      arrow.textContent = h.classList.contains('bn-sorted-asc') ? '\u25B2' :
                          h.classList.contains('bn-sorted-desc') ? '\u25BC' :
                          arrow.textContent;
    }
  }

  function sortTable(th) {
    var tbody = table.querySelector('tbody');
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var colIdx = Array.prototype.indexOf.call(th.parentNode.children, th);
    var isAsc = th.classList.contains('bn-sorted-asc');

    var newAsc = !isAsc;

    rows.sort(function(a, b) {
      var aVal = parseFloat(a.children[colIdx].textContent) || 0;
      var bVal = parseFloat(b.children[colIdx].textContent) || 0;
      return newAsc ? aVal - bVal : bVal - aVal;
    });

    // Re-append sorted rows
    for (var i = 0; i < rows.length; i++) {
      tbody.appendChild(rows[i]);
    }

    // Update header classes
    for (var j = 0; j < headers.length; j++) {
      headers[j].classList.remove('bn-sorted-asc', 'bn-sorted-desc');
    }
    th.classList.add(newAsc ? 'bn-sorted-asc' : 'bn-sorted-desc');

    updateArrows();
  }

  // Initial state
  updateArrows();

  for (var i = 0; i < headers.length; i++) {
    headers[i].addEventListener('click', (function(th) {
      return function() { sortTable(th); };
    })(headers[i]));
  }
}
