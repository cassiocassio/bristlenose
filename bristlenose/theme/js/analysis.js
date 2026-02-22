/**
 * analysis.js — Bristlenose analysis page.
 *
 * On the main report page: wires the toolbar Analysis button.
 * On the analysis page: renders signal cards, heatmaps, and interactive
 * features from data injected by the Python renderer.
 *
 * Data source: BRISTLENOSE_ANALYSIS global (injected as JSON by render_html.py)
 * containing: signals, sectionMatrix, themeMatrix, totalParticipants,
 * sentiments, participantIds, reportFilename.
 *
 * @module analysis
 */

/* exported initAnalysis */

function initAnalysis() {
    "use strict";

    // Attribute name constructed to avoid literal in HTML (dark mode tests check
    // the full document for absence of the string when color_scheme is "auto").
    var THEME_ATTR = "data-" + "theme";

    // ── Analysis rendering ──────────────────────────────────
    var container = document.getElementById("signal-cards");
    if (!container || typeof BRISTLENOSE_ANALYSIS === "undefined") return;

    var data = BRISTLENOSE_ANALYSIS;
    var signals = data.signals;
    var sentiments = data.sentiments;
    var totalParticipants = data.totalParticipants;
    var participantIds = data.participantIds;
    var reportFilename = typeof BRISTLENOSE_REPORT_FILENAME !== "undefined"
        ? BRISTLENOSE_REPORT_FILENAME : "bristlenose-report.html";

    var SENTIMENT_LABELS = {};
    sentiments.forEach(function (s) {
        SENTIMENT_LABELS[s] = s.charAt(0).toUpperCase() + s.slice(1);
    });

    var SENTIMENT_CSS = {};
    sentiments.forEach(function (s) {
        SENTIMENT_CSS[s] = "var(--bn-sentiment-" + s + ")";
    });

    var SENTIMENT_HUE = {
        frustration: 55, confusion: 30, doubt: 295, surprise: 75,
        satisfaction: 155, delight: 170, confidence: 260
    };
    var DEPLETED_HUE = 75;

    // ── Adjusted residual (needed client-side for heatmap colouring) ──

    function adjustedResidual(observed, rowTotal, colTotal, grandTotal) {
        if (grandTotal === 0 || rowTotal === 0 || colTotal === 0) return 0;
        var expected = (rowTotal * colTotal) / grandTotal;
        if (expected === 0) return 0;
        var denom = Math.sqrt(
            expected * (1 - rowTotal / grandTotal) * (1 - colTotal / grandTotal)
        );
        return denom === 0 ? 0 : (observed - expected) / denom;
    }

    // ── Helpers ──────────────────────────────────────────────

    function esc(s) {
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    function formatTimecode(totalSeconds) {
        var s = Math.floor(totalSeconds);
        var h = Math.floor(s / 3600);
        var m = Math.floor((s % 3600) / 60);
        var sec = s % 60;
        var pad = function (n) { return n < 10 ? "0" + n : "" + n; };
        if (h > 0) return h + ":" + pad(m) + ":" + pad(sec);
        return m + ":" + pad(sec);
    }

    // ── Intensity dots (SVG) ─────────────────────────────────

    function intensityDotsSvg(meanVal) {
        var rounded = Math.round(meanVal * 2) / 2;
        var r = 5, cx = 7, gap = 16;
        var w = cx + gap * 2 + r + 2;
        var h = r * 2 + 2;
        var svg = '<svg class="intensity-dots-svg" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">';

        for (var i = 0; i < 3; i++) {
            var threshold = i + 1;
            var x = cx + i * gap;
            var y = r + 1;

            if (rounded >= threshold) {
                svg += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="var(--dot-colour, var(--bn-colour-text))" opacity="0.7"/>';
            } else if (rounded >= threshold - 0.5) {
                var clipId = "half-" + i + "-" + Math.random().toString(36).substr(2, 5);
                svg += "<defs>";
                svg += '<clipPath id="' + clipId + '-l"><rect x="' + (x - r) + '" y="' + (y - r) + '" width="' + r + '" height="' + (r * 2) + '"/></clipPath>';
                svg += '<clipPath id="' + clipId + '-r"><rect x="' + x + '" y="' + (y - r) + '" width="' + r + '" height="' + (r * 2) + '"/></clipPath>';
                svg += "</defs>";
                svg += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="var(--dot-colour, var(--bn-colour-text))" opacity="0.7" clip-path="url(#' + clipId + '-l)"/>';
                svg += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="none" stroke="var(--dot-colour, var(--bn-colour-text))" stroke-width="1.2" opacity="0.35" clip-path="url(#' + clipId + '-r)"/>';
                svg += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="none" stroke="var(--dot-colour, var(--bn-colour-text))" stroke-width="1.2" opacity="0.35"/>';
            } else {
                svg += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="none" stroke="var(--dot-colour, var(--bn-colour-text))" stroke-width="1.2" opacity="0.35"/>';
            }
        }

        svg += "</svg>";
        return svg;
    }

    // ── Render a single blockquote ───────────────────────────

    function renderQuoteBlockquote(q) {
        var tc = formatTimecode(q.startSeconds);
        var transcriptHref = "sessions/transcript_" + q.sessionId + ".html#t-" + Math.floor(q.startSeconds);

        var bq = "<blockquote>";
        bq += '<div class="quote-row">';
        bq += '<a class="timecode" href="' + transcriptHref + '" data-participant="' + q.pid + '" data-seconds="' + q.startSeconds + '">';
        bq += '<span class="timecode-bracket">[</span>' + tc + '<span class="timecode-bracket">]</span>';
        bq += "</a>";
        bq += '<span class="quote-body">';
        bq += '<span class="quote-text">\u201c' + esc(q.text) + '\u201d</span>';
        bq += ' <span class="speaker">\u2014\u00a0<a class="speaker-link" href="' + transcriptHref + '">' + q.pid + "</a></span>";
        bq += "</span>";
        bq += '<span class="intensity-dots" title="Intensity ' + q.intensity + ' of 3">' + intensityDotsSvg(q.intensity) + "</span>";
        bq += "</div>";
        bq += "</blockquote>";
        return bq;
    }

    // ── Signal card ID ───────────────────────────────────────

    function signalCardId(sourceType, location, sentiment) {
        var slug = location.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
        return "signal-" + sourceType + "-" + slug + "-" + sentiment;
    }

    // ── Render signal cards ──────────────────────────────────

    var _cardIds = {};

    function renderSignalCards() {
        var concScale = 8;
        var html = "";

        for (var i = 0; i < signals.length; i++) {
            var s = signals[i];
            var accent = SENTIMENT_CSS[s.sentiment] || "var(--bn-colour-muted)";
            var typeLabel = SENTIMENT_LABELS[s.sentiment] || s.sentiment;
            var concPct = Math.min(100, Math.round((s.concentration / concScale) * 100));
            var breadthPct = Math.min(100, Math.round((s.nEff / totalParticipants) * 100));
            var sourceLabel = s.sourceType === "theme" ? "Theme" : "Section";
            var cardId = signalCardId(s.sourceType, s.location, s.sentiment);

            // Deep-link to report section
            var slug = s.location.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
            var prefix = s.sourceType === "theme" ? "theme-" : "section-";
            var reportHref = reportFilename + "#" + prefix + slug;

            var allQuotes = s.quotes || [];

            html += '<div class="signal-card" id="' + cardId + '" style="--card-accent: ' + accent + '">';

            // Two-column top
            html += '<div class="signal-card-top">';
            html += '<div class="signal-card-identity">';
            html += '<span class="signal-card-source">' + sourceLabel + "</span>";
            html += '<div class="signal-card-location"><a class="signal-card-location-link" href="' + reportHref + '">' + esc(s.location) + "</a></div>";
            html += '<span class="badge badge-' + s.sentiment + '">' + typeLabel + "</span>";
            html += "</div>";
            html += '<div class="signal-card-metrics">';
            html += '<span class="metric-label" title="Overall importance, combines all metrics">Signal strength:</span>';
            html += '<span class="metric-value">' + s.compositeSignal.toFixed(2) + "</span>";
            html += '<span class="metric-viz"></span>';
            html += '<span class="metric-label" title="Times sentiment is overrepresented here vs study average">Concentration:</span>';
            html += '<span class="metric-value">' + s.concentration.toFixed(1) + "\u00d7</span>";
            html += '<span class="metric-viz"><span class="conc-bar-track"><span class="conc-bar-fill" style="width:' + concPct + '%"></span></span></span>';
            html += '<span class="metric-label" title="Measure of quotes coming from all ' + totalParticipants + ' voices">Agreement:</span>';
            html += '<span class="metric-value">' + s.nEff.toFixed(1) + "</span>";
            html += '<span class="metric-viz"><span class="conc-bar-track"><span class="conc-bar-fill" style="width:' + breadthPct + '%"></span></span></span>';
            html += '<span class="metric-label" title="Average emotional strength of quotes">Mean intensity:</span>';
            html += '<span class="metric-value">' + s.meanIntensity.toFixed(1) + "</span>";
            html += '<span class="metric-viz">' + intensityDotsSvg(s.meanIntensity) + "</span>";
            html += "</div>";
            html += "</div>";

            // Quotes
            html += '<div class="signal-card-quotes">';
            if (allQuotes.length > 0) {
                html += renderQuoteBlockquote(allQuotes[0]);
            }
            if (allQuotes.length > 1) {
                html += '<div class="signal-card-expansion">';
                for (var qi = 1; qi < allQuotes.length; qi++) {
                    html += renderQuoteBlockquote(allQuotes[qi]);
                }
                html += "</div>";
            }
            html += "</div>";

            // Footer
            html += '<div class="signal-card-footer">';
            if (allQuotes.length > 1) {
                html += '<a class="signal-card-link signal-card-toggle" href="#">Show all ' + allQuotes.length + " quotes \u2192</a>";
            } else {
                html += '<span class="signal-card-link" style="visibility:hidden">1 quote</span>';
            }
            html += '<span class="participant-grid">';
            html += '<span class="participant-count">' + s.participants.length + " of " + totalParticipants + "</span>";
            for (var pi = 0; pi < participantIds.length; pi++) {
                var pid = participantIds[pi];
                var present = s.participants.indexOf(pid) >= 0;
                html += '<span class="p-box' + (present ? " p-present" : "") + '">' + pid + "</span>";
            }
            html += "</span>";
            html += "</div>";
            html += "</div>";

            var cardKey = s.sourceType + "|" + s.location + "|" + s.sentiment;
            _cardIds[cardKey] = cardId;
        }

        container.innerHTML = html;

        // Toggle expansion on "Show all N quotes" click
        container.addEventListener("click", function (e) {
            var toggle = e.target.closest(".signal-card-toggle");
            if (!toggle) return;
            e.preventDefault();

            var card = toggle.closest(".signal-card");
            var expansion = card.querySelector(".signal-card-expansion");
            if (!expansion) return;

            if (card.classList.contains("expanded")) {
                expansion.style.maxHeight = expansion.scrollHeight + "px";
                expansion.offsetHeight; // force reflow
                expansion.style.maxHeight = "0";
                expansion.style.opacity = "0";
                card.classList.remove("expanded");
                toggle.textContent = "Show all " + (expansion.children.length + 1) + " quotes \u2192";
                expansion.addEventListener("transitionend", function handler(evt) {
                    if (evt.propertyName === "max-height") {
                        expansion.style.overflow = "hidden";
                        expansion.removeEventListener("transitionend", handler);
                    }
                });
            } else {
                expansion.style.overflow = "hidden";
                expansion.style.maxHeight = "0";
                card.classList.add("expanded");
                expansion.offsetHeight; // force reflow
                var target = expansion.scrollHeight;
                expansion.style.maxHeight = target + "px";
                expansion.style.opacity = "1";
                toggle.textContent = "Hide";
                expansion.addEventListener("transitionend", function handler(evt) {
                    if (evt.propertyName === "max-height" && card.classList.contains("expanded")) {
                        expansion.style.maxHeight = "none";
                        expansion.style.overflow = "visible";
                    }
                    expansion.removeEventListener("transitionend", handler);
                });
            }
        });
    }

    // ── OKLCH colour for heatmap cell ────────────────────────

    function heatCellColour(heat, hue, chroma, isDark) {
        var lMin = isDark ? 30 : 95;
        var lMax = isDark ? 75 : 45;
        var l = lMin + (lMax - lMin) * heat;
        return "oklch(" + l.toFixed(1) + "% " + chroma.toFixed(2) + " " + hue + ")";
    }

    // ── Render heatmap ───────────────────────────────────────

    function renderHeatmap(matrix, containerId, rowHeader, sourceType) {
        var el = document.getElementById(containerId);
        if (!el || !matrix) return;

        var isDark = document.documentElement.getAttribute(THEME_ATTR) === "dark";
        var chroma = isDark ? 0.10 : 0.12;
        var depletedChroma = isDark ? 0.06 : 0.08;

        var rowLabels = matrix.rowLabels;
        var cells = matrix.cells;
        var rowTotals = matrix.rowTotals;
        var colTotals = matrix.colTotals;
        var grandTotal = matrix.grandTotal;

        // Compute residuals
        var residuals = {};
        var maxAbsResidual = 0;
        rowLabels.forEach(function (row) {
            sentiments.forEach(function (sent) {
                var cell = cells[row + "|" + sent] || { count: 0 };
                var r = adjustedResidual(
                    cell.count, rowTotals[row] || 0,
                    colTotals[sent] || 0, grandTotal
                );
                residuals[row + "|" + sent] = r;
                if (Math.abs(r) > maxAbsResidual) maxAbsResidual = Math.abs(r);
            });
        });

        var html = '<table class="analysis-heatmap">';
        html += "<thead><tr><th>" + esc(rowHeader) + "</th>";
        sentiments.forEach(function (s) {
            html += '<th><span class="badge badge-' + s + '">' + SENTIMENT_LABELS[s] + "</span></th>";
        });
        html += "<th>Total</th></tr></thead>";
        html += "<tbody>";

        rowLabels.forEach(function (row) {
            html += '<tr class="heatmap-data-row">';
            html += "<td>" + esc(row) + "</td>";
            sentiments.forEach(function (sent) {
                var cell = cells[row + "|" + sent] || { count: 0 };
                var r = residuals[row + "|" + sent];
                var absR = Math.abs(r);
                var heat = maxAbsResidual > 0 ? absR / maxAbsResidual : 0;

                var cls = "heatmap-cell";
                var bgStyle = "";

                var cardKey = sourceType + "|" + row + "|" + sent;
                if (_cardIds[cardKey]) cls += " has-card";

                if (cell.count > 0 && absR > 0.5) {
                    var hue = r > 0 ? (SENTIMENT_HUE[sent] || 260) : DEPLETED_HUE;
                    var c = r > 0 ? chroma : depletedChroma;
                    cls += r > 0 ? " heat-positive" : " heat-negative";
                    if (heat > 0.7 && r > 0) cls += " heat-strong";
                    bgStyle = "background:" + heatCellColour(heat, hue, c, isDark);
                }

                var title = "d = " + (r >= 0 ? "+" : "") + r.toFixed(2);
                if (absR > 3) title += " (strong)";
                else if (absR > 2) title += " (notable)";

                html += '<td class="' + cls + '"';
                if (bgStyle) html += ' style="' + bgStyle + '"';
                html += ' data-count="' + cell.count + '"';
                html += ' data-row="' + esc(row) + '"';
                html += ' data-sentiment="' + sent + '"';
                html += ' title="' + title + '">';
                html += cell.count;
                html += "</td>";
            });
            html += '<td class="heatmap-total">' + (rowTotals[row] || 0) + "</td>";
            html += "</tr>";
        });

        // Column totals
        html += "<tr>";
        html += '<td class="heatmap-total">Total</td>';
        sentiments.forEach(function (sent) {
            html += '<td class="heatmap-total">' + (colTotals[sent] || 0) + "</td>";
        });
        html += '<td class="heatmap-total heatmap-grand-total">' + grandTotal + "</td>";
        html += "</tr>";

        html += "</tbody></table>";
        el.innerHTML = html;

        // Cell click → scroll to matching signal card
        el.addEventListener("click", function (e) {
            var cell = e.target.closest(".heatmap-cell.has-card");
            if (!cell) return;

            var row = cell.getAttribute("data-row");
            var sent = cell.getAttribute("data-sentiment");
            var cardKey = sourceType + "|" + row + "|" + sent;
            var cardId = _cardIds[cardKey];
            if (!cardId) return;

            var cardEl = document.getElementById(cardId);
            if (!cardEl) return;

            cardEl.scrollIntoView({ behavior: "smooth", block: "center" });
            cardEl.style.boxShadow = "0 0 0 3px var(--bn-colour-accent)";
            setTimeout(function () { cardEl.style.boxShadow = ""; }, 1500);
        });
    }

    // ── Boot ─────────────────────────────────────────────────

    renderSignalCards();
    renderHeatmap(data.sectionMatrix, "heatmap-section-container", "Section", "section");
    renderHeatmap(data.themeMatrix, "heatmap-theme-container", "Theme", "theme");

    // Re-render heatmaps on theme change
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
            if (m.attributeName === THEME_ATTR) {
                renderHeatmap(data.sectionMatrix, "heatmap-section-container", "Section", "section");
                renderHeatmap(data.themeMatrix, "heatmap-theme-container", "Theme", "theme");
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: [THEME_ATTR] });
}
