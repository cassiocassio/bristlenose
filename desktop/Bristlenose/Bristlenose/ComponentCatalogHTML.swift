#if DEBUG
import Foundation

// MARK: - Catalogue web column HTML
//
// The real bn design-system components rendered with the real light-mode token
// values (from bristlenose/theme/tokens.css). Self-contained so the catalogue
// window needs no running serve. Kept deliberately parallel to the native column
// in ComponentCatalogView (same order, same labels) so the two line up on screen.
//
// A later slice can swap this inline CSS for a <link> to the live serve's
// /report/assets/bristlenose-theme.css for pixel-perfect fidelity; inline values
// are the pragmatic v1.

enum ComponentCatalogHTML {
    static let page = """
    <!doctype html><html><head><meta charset="utf-8">
    <style>
      :root{
        --bg:#ffffff; --text:#1a1a1a; --muted:#6b7280; --border:#e5e7eb;
        --quote-bg:#f9fafb; --badge-bg:#f3f4f6; --badge-text:#374151;
        --code-bg:#f3f4f6; --code-text:#374151; --name-bg:#f9fafb;
        --font:"Inter","Segoe UI Variable",system-ui,-apple-system,sans-serif;
        --mono:"SF Mono",ui-monospace,Menlo,monospace;
      }
      *{box-sizing:border-box;}
      body{margin:0;padding:20px;font-family:var(--font);color:var(--text);
        background:var(--bg);-webkit-font-smoothing:antialiased;}
      .comp{margin-bottom:28px;}
      .lbl{display:flex;gap:8px;align-items:baseline;margin-bottom:8px;}
      .lbl b{font-size:12px;font-weight:600;}
      .lbl code{font-family:var(--mono);font-size:10px;color:var(--muted);}

      /* quote card */
      .quote-card{background:var(--quote-bg);border-left:2px solid #059669;
        border-radius:0 6px 6px 0;padding:10px 12px;max-width:340px;position:relative;
        box-shadow:0 1px 2px rgba(0,0,0,.04);}
      .quote-card .ctx{font-size:11px;color:var(--muted);}
      .quote-card .body{font-size:15px;line-height:1.5;color:var(--text);margin-top:2px;}
      .quote-card .star{position:absolute;top:9px;right:11px;color:#c9ccd1;font-size:13px;}
      .quote-card .row{display:flex;align-items:center;gap:8px;margin-top:6px;}

      /* tags — sentiment and codebook share one treatment */
      .tag{display:inline-flex;align-items:center;gap:4px;font-family:var(--mono);
        font-size:11px;border-radius:3px;padding:2px 7px;margin-right:6px;}
      .tag .x{opacity:0;transition:opacity .12s;font-size:9.5px;}
      .tag:hover .x{opacity:.5;}

      /* person badge — two-tone split */
      .person{display:inline-flex;font-size:0;border-radius:3px;overflow:hidden;
        border:1px solid rgba(0,0,0,.14);}
      .person .code{font-family:var(--mono);font-size:11px;background:var(--code-bg);
        color:var(--code-text);padding:2px 6px;}
      .person .name{font-size:13px;font-weight:490;background:var(--name-bg);
        color:var(--text);padding:2px 8px;}
      .person:hover .name{background:var(--bg);}

      /* data badge */
      .badge{display:inline-block;font-family:var(--mono);font-size:11px;
        background:var(--badge-bg);color:var(--badge-text);border-radius:3px;
        padding:2px 7px;margin-right:6px;}

      /* spacing rhythm */
      .spacing{display:flex;align-items:flex-end;gap:14px;}
      .sp{display:flex;flex-direction:column;align-items:center;gap:4px;}
      .sp i{display:block;background:rgba(0,122,255,.16);
        border:1px solid rgba(0,122,255,.45);border-radius:2px;}
      .sp b{font-family:var(--mono);font-size:9px;font-weight:500;color:var(--muted);}
    </style></head><body>

      <div class="comp">
        <div class="lbl"><b>Spacing rhythm</b><code>--bn-space-* (rem-derived)</code></div>
        <div class="spacing">
          <div class="sp"><i style="width:2.4px;height:2.4px"></i><b>2.4</b></div>
          <div class="sp"><i style="width:5.6px;height:5.6px"></i><b>5.6</b></div>
          <div class="sp"><i style="width:12px;height:12px"></i><b>12</b></div>
          <div class="sp"><i style="width:24px;height:24px"></i><b>24</b></div>
          <div class="sp"><i style="width:32px;height:32px"></i><b>32</b></div>
        </div>
      </div>

      <div class="comp">
        <div class="lbl"><b>Quote card</b><code>.quote-card</code></div>
        <div class="quote-card">
          <span class="star">\u{2606}</span>
          <div class="ctx">Checkout \u{00B7} <span style="color:#ea580c">frustration</span></div>
          <div class="body">\u{201C}I couldn\u{2019}t tell if it had actually saved.\u{201D}</div>
          <div class="row">
            <span class="person"><span class="code">P3</span><span class="name">12:04</span></span>
            <span class="tag" style="background:#fbe6ec;color:#8a2f52">friction<span class="x">\u{2715}</span></span>
          </div>
        </div>
      </div>

      <div class="comp">
        <div class="lbl"><b>Sentiment / codebook tag</b><code>.badge-user</code></div>
        <span class="tag" style="background:#fff7ed;color:#ea580c">frustration<span class="x">\u{2715}</span></span>
        <span class="tag" style="background:#e3edfb;color:#1f4f8a">onboarding<span class="x">\u{2715}</span></span>
      </div>

      <div class="comp">
        <div class="lbl"><b>Person badge</b><code>.bn-speaker-badge--split</code></div>
        <span class="person"><span class="code">P1</span><span class="name">Rachel</span></span>
      </div>

      <div class="comp">
        <div class="lbl"><b>Data badge</b><code>.badge</code></div>
        <span class="badge">AI</span><span class="badge">0.82</span>
      </div>

    </body></html>
    """
}
#endif
