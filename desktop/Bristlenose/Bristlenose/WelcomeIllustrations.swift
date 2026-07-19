import SwiftUI
import WebKit
import Combine

// MARK: - Welcome science-cell illustrations
//
// One tiny looping illustration per "Scientific background" pool item
// (design-welcome-screen.md §Cell 2). Decisions (agreed with Martin, TF-play):
//   1 Seven sentiments      → native SwiftUI fan (SentimentFanView)
//   2 Signals               → webview (the real signal card + trainboard flip)
//   3 Dignity               → webview (the strike-and-collapse quote)
//   4 Framework authors     → native SwiftUI book fan (BookFanView)
//   5 Emergent themes       → reuse the existing ShoalView murmuration
// Native pieces use exact-ish fonts (SF Mono for the chips); the two webviews
// reuse the mockup CSS/JS verbatim — slight font-rendering differences accepted.
// All are decorative: accessibilityHidden, inert, reduce-motion aware.

/// Which illustration a science slot carries (nil case = plain text slot).
enum ScienceIllustration: Equatable {
    case none, sentimentFan, bookFan, shoal, quote, signal
}

/// sRGB colour from a 0xRRGGBB literal (file-private helper).
private func rgb(_ v: UInt) -> Color {
    Color(.sRGB,
          red: Double((v >> 16) & 0xff) / 255,
          green: Double((v >> 8) & 0xff) / 255,
          blue: Double(v & 0xff) / 255)
}

// MARK: - 1 · Sentiment fan (native)

/// The seven sentiment chips, hinged at the left, opening like a hand-fan:
/// rotation for the fan look + an explicit vertical offset so every word reads,
/// only just overlapping at full open. Chip typography matches the report badge
/// (SF Mono + the sentiment colour tokens).
struct SentimentFanView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var open = false

    private struct Chip { let name: String; let fgL, fgD, bgL, bgD: UInt }
    private let chips: [Chip] = [
        .init(name: "frustration",  fgL: 0xea580c, fgD: 0xfb923c, bgL: 0xfff7ed, bgD: 0x2d1d0e),
        .init(name: "confusion",    fgL: 0xdc2626, fgD: 0xf87171, bgL: 0xfef2f2, bgD: 0x2d1515),
        .init(name: "doubt",        fgL: 0x7c3aed, fgD: 0xa78bfa, bgL: 0xf5f3ff, bgD: 0x1e1533),
        .init(name: "surprise",     fgL: 0xd97706, fgD: 0xfbbf24, bgL: 0xfffbeb, bgD: 0x2d2305),
        .init(name: "satisfaction", fgL: 0x16a34a, fgD: 0x4ade80, bgL: 0xf0fdf4, bgD: 0x0f2918),
        .init(name: "delight",      fgL: 0x059669, fgD: 0x34d399, bgL: 0xecfdf5, bgD: 0x0d261c),
        .init(name: "confidence",   fgL: 0x2563eb, fgD: 0x60a5fa, bgL: 0xeff6ff, bgD: 0x111d2e),
    ]
    private let aMax = 34.0     // max fan angle (mockup detail, trimmed 15%)
    private let vStep = 15.0    // per-chip vertical separation at full open
    private let timer = Timer.publish(every: 2, on: .main, in: .common).autoconnect()

    var body: some View {
        let n = chips.count
        ZStack(alignment: .leading) {
            ForEach(chips.indices, id: \.self) { i in
                let chip = chips[i]
                let angle = -aMax + (Double(i) / Double(n - 1)) * 2 * aMax
                let vy = (Double(i) - Double(n - 1) / 2) * vStep
                Text(chip.name)
                    .font(.system(size: 11, weight: .regular, design: .monospaced))
                    .foregroundStyle(scheme == .dark ? rgb(chip.fgD) : rgb(chip.fgL))
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(RoundedRectangle(cornerRadius: 3)
                        .fill(scheme == .dark ? rgb(chip.bgD) : rgb(chip.bgL)))
                    .shadow(color: .black.opacity(scheme == .dark ? 0.45 : 0.12), radius: 1, y: 0.5)
                    .fixedSize()
                    .zIndex(Double(i))
                    .rotationEffect(.degrees(open ? angle : 0), anchor: .leading)
                    .offset(x: open ? 16 : 4, y: open ? vy : 0)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .padding(.leading, 12)
        .accessibilityHidden(true)
        .onAppear { if reduceMotion { open = true } }
        .onReceive(timer) { _ in
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1)) { open.toggle() }
        }
    }
}

// MARK: - 4 · Book fan (native)

/// A single fan of the books behind the codebook frameworks: covers overlap and
/// slide over each other (no rotation), one moving to the front at a time.
/// Typographic placeholder covers pending real cover art.
struct BookFanView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var front = 0

    private struct Book { let title, author: String; let spine: UInt }
    private let books: [Book] = [
        .init(title: "The Design of Everyday Things", author: "Don Norman",     spine: 0x334155),
        .init(title: "Usability Engineering",         author: "Jakob Nielsen",   spine: 0x0f5c9e),
        .init(title: "Thematic Analysis",             author: "Braun & Clarke",  spine: 0x7c3aed),
        .init(title: "Emotion & Adaptation",          author: "Richard Lazarus", spine: 0xb45309),
    ]
    private let off = 18.0
    private let timer = Timer.publish(every: 2.4, on: .main, in: .common).autoconnect()

    var body: some View {
        let n = books.count
        ZStack {
            ForEach(books.indices, id: \.self) { i in
                let book = books[i]
                let d = ((i - front) % n + n) % n
                bookCard(book)
                    .offset(x: Double(d) * off)
                    .opacity(d > 2 ? 0 : 1 - Double(d) * 0.16)
                    .zIndex(Double(100 - d))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
        .accessibilityHidden(true)
        .onReceive(timer) { _ in
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 0.8)) { front = (front + 1) % n }
        }
    }

    private func bookCard(_ b: Book) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(b.title).font(.system(size: 9.5, weight: .semibold)).foregroundStyle(.white)
            Spacer(minLength: 0)
            Text(b.author).font(.system(size: 8)).foregroundStyle(.white.opacity(0.82))
        }
        .padding(EdgeInsets(top: 9, leading: 11, bottom: 8, trailing: 8))
        .frame(width: 80, height: 114, alignment: .leading)
        .background(
            LinearGradient(colors: [rgb(b.spine), rgb(b.spine).opacity(0.72)],
                           startPoint: .topLeading, endPoint: .bottomTrailing),
            in: RoundedRectangle(cornerRadius: 4)
        )
        .overlay(alignment: .leading) {
            Rectangle().fill(.white.opacity(0.22)).frame(width: 1).padding(.leading, 4)
        }
        .shadow(color: .black.opacity(0.22), radius: 6, y: 4)
    }
}

// MARK: - 5 · Emergent themes (the mockup's simple two-theme swoop, via webview)

/// The clear, simple murmuration from the mockup: demo quote-fragments swirl as
/// one flock, swoop into two labelled themes, then rejoin — induction, looping.
/// Deliberately NOT the real `ShoalView` (that's the delight / analysing
/// screensaver — it wants a big canvas and is for fun; this cell has to make a
/// point). Reuses the approved mockup verbatim, so the feel is preserved exactly.
struct EmergentThemesView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        IllustrationWebView(html: WelcomeIllustrationHTML.emergentThemes(dark: scheme == .dark, reduce: reduceMotion))
            .id("themes-\(scheme)-\(reduceMotion)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

// MARK: - 2 & 3 · Webview-backed illustrations

/// Transparent, inert WKWebView that renders a self-contained HTML illustration.
/// No external resources (loadHTMLString, baseURL nil) — sandbox-clean; fonts are
/// the system stack. Transparency via the documented `drawsBackground` KVC.
private struct IllustrationWebView: NSViewRepresentable {
    let html: String

    func makeNSView(context: Context) -> WKWebView {
        let wv = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        wv.setValue(false, forKey: "drawsBackground")   // paint transparent (see WebView.swift)
        wv.loadHTMLString(html, baseURL: nil)
        return wv
    }
    func updateNSView(_ nsView: WKWebView, context: Context) {}
}

/// #3 — the dignity strike-and-collapse quote.
struct QuoteIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        IllustrationWebView(html: WelcomeIllustrationHTML.quote(dark: scheme == .dark, reduce: reduceMotion))
            .id("quote-\(scheme)-\(reduceMotion)")   // reload on appearance / reduce-motion change
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// #2 — the real analysis signal card ticking through examples.
struct SignalIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        IllustrationWebView(html: WelcomeIllustrationHTML.signal(dark: scheme == .dark, palette: palette, reduce: reduceMotion))
            .id("signal-\(scheme)-\(palette)-\(reduceMotion)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

// MARK: - Embedded HTML (ported verbatim from docs/mockups/welcome-science-animations.html)

enum WelcomeIllustrationHTML {

    static func quote(dark: Bool, reduce: Bool) -> String {
        """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{ --ink:#1a1a1a; --faint:#6b7280; --danger:#dc2626; }
          html[data-appearance="dark"]{ --ink:#e5e7eb; --faint:#9ca3af; --danger:#f87171; }
          html,body{ margin:0; height:100%; background:transparent; }
          body{ display:flex; align-items:center; justify-content:center; padding:6px 12px;
                font-family:-apple-system,"SF Pro Text",system-ui,sans-serif; color:var(--ink); }
          .q{ font-size:15px; line-height:1.5; }
          .qm{ color:var(--faint); }
          .tok{ display:inline; }
          .tok.trim{ display:inline-block; white-space:pre; max-width:20ch; opacity:1;
                     transition:max-width .5s cubic-bezier(.6,.02,.2,1), opacity .35s ease, color .3s ease, text-decoration-color .3s ease;
                     text-decoration:line-through; text-decoration-color:transparent; }
          .q.marked .tok.trim{ color:var(--danger); text-decoration-color:var(--danger); }
          .q.tidied .tok.trim{ max-width:0; opacity:0; }
          @media (prefers-reduced-motion:reduce){ *{ transition:none !important; } }
        </style></head>
        <body><div class="q" id="q"></div>
        <script>
          var R = document.documentElement.getAttribute("data-reduce")==="1" || matchMedia("(prefers-reduced-motion:reduce)").matches;
          var T=[{t:"So, ",x:1},{t:"um, ",x:1},{t:"The checkout",k:1},{t:", like,",x:1},{t:" was",k:1},
                 {t:" honestly,",x:1},{t:" the—the",x:1},{t:" confusing",k:1},{t:", you know?",x:1},
                 {t:" I couldn’t",k:1},{t:" actually",x:1},{t:" figure out where to",k:1},{t:" pay.",k:1}];
          var q=document.getElementById("q");
          q.innerHTML='<span class="qm">“</span>';
          T.forEach(function(o){ var s=document.createElement("span"); s.className="tok "+(o.x?"trim":"kept"); s.textContent=o.t; q.appendChild(s); });
          var c=document.createElement("span"); c.className="qm"; c.textContent="”"; q.appendChild(c);
          var S=[["",3800],["marked",3000],["marked tidied",4800],["marked",1400],["",1000]];
          var i=0;
          function set(){ q.className="q "+S[i][0]; }
          if(R){ i=1; set(); } else { set(); (function loop(){ setTimeout(function(){ i=(i+1)%S.length; set(); loop(); }, S[i][1]); })(); }
        </script></body></html>
        """
    }

    static func signal(dark: Bool, palette: String, reduce: Bool) -> String {
        let accent = palette == "edo" ? (dark ? "#4d9fe0" : "#0f5c9e") : (dark ? "#0a84ff" : "#007aff")
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{
            --ink:#1a1a1a; --faint:#6b7280; --line:#e5e7eb; --paper:#fff; --card:#f9f9fa;
            --accent:\(accent);
            --mono:"SF Mono",ui-monospace,Menlo,monospace;
            --badge-bg:#f3f4f6; --badge-text:#374151;
            --bn-sentiment-frustration:#ea580c; --bn-sentiment-frustration-bg:#fff7ed;
            --bn-sentiment-confusion:#dc2626;   --bn-sentiment-confusion-bg:#fef2f2;
            --bn-sentiment-doubt:#7c3aed;       --bn-sentiment-doubt-bg:#f5f3ff;
            --bn-sentiment-surprise:#d97706;    --bn-sentiment-surprise-bg:#fffbeb;
            --bn-sentiment-satisfaction:#16a34a;--bn-sentiment-satisfaction-bg:#f0fdf4;
            --bn-sentiment-delight:#059669;     --bn-sentiment-delight-bg:#ecfdf5;
            --bn-sentiment-confidence:#2563eb;  --bn-sentiment-confidence-bg:#eff6ff;
          }
          html[data-appearance="dark"]{
            --ink:#e5e7eb; --faint:#9ca3af; --line:#2d2d2d; --paper:#1c1c1e; --card:#232326;
            --badge-bg:#252525; --badge-text:#d1d5db;
            --bn-sentiment-frustration:#fb923c; --bn-sentiment-frustration-bg:#2d1d0e;
            --bn-sentiment-confusion:#f87171;   --bn-sentiment-confusion-bg:#2d1515;
            --bn-sentiment-doubt:#a78bfa;       --bn-sentiment-doubt-bg:#1e1533;
            --bn-sentiment-surprise:#fbbf24;    --bn-sentiment-surprise-bg:#2d2305;
            --bn-sentiment-satisfaction:#4ade80;--bn-sentiment-satisfaction-bg:#0f2918;
            --bn-sentiment-delight:#34d399;     --bn-sentiment-delight-bg:#0d261c;
            --bn-sentiment-confidence:#60a5fa;  --bn-sentiment-confidence-bg:#111d2e;
          }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }  /* clip → never a scrollbar */
          body{ font-family:-apple-system,"SF Pro Text",system-ui,sans-serif; color:var(--ink); position:relative; }
          .badge{ display:inline-block; font-family:var(--mono); font-size:0.72rem; padding:0.15rem 0.45rem; border-radius:3px; background:var(--badge-bg); color:var(--badge-text); line-height:1.35; white-space:nowrap; }
          .badge-frustration{ background:var(--bn-sentiment-frustration-bg); color:var(--bn-sentiment-frustration); }
          .badge-confusion{ background:var(--bn-sentiment-confusion-bg); color:var(--bn-sentiment-confusion); }
          .badge-doubt{ background:var(--bn-sentiment-doubt-bg); color:var(--bn-sentiment-doubt); }
          .badge-surprise{ background:var(--bn-sentiment-surprise-bg); color:var(--bn-sentiment-surprise); }
          .badge-satisfaction{ background:var(--bn-sentiment-satisfaction-bg); color:var(--bn-sentiment-satisfaction); }
          .badge-delight{ background:var(--bn-sentiment-delight-bg); color:var(--bn-sentiment-delight); }
          .badge-confidence{ background:var(--bn-sentiment-confidence-bg); color:var(--bn-sentiment-confidence); }
          /* Fixed natural size, centred, then uniformly scaled to fit (see fit()).
             Absolute (not a flex item) so width is honoured exactly — a flex item's
             default min-width:auto would inflate it to min-content and reflow. */
          .signal-card{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); transform-origin:center;
                        border:1px solid var(--line); border-radius:3px; padding:1rem; background:var(--paper); width:440px; }
          .signal-card-top{ display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
          .signal-card-identity{ flex:1; min-width:0; }
          .signal-card-source{ display:block; font-size:0.72rem; font-weight:420; text-transform:uppercase; letter-spacing:0.04em; color:var(--faint); margin-bottom:0.1rem; }
          .signal-card-location{ font-size:18px; line-height:1.3; font-weight:490; margin-bottom:0.35rem; color:var(--ink); }
          .signal-card-tags{ display:flex; gap:0.35rem; align-items:center; flex-wrap:wrap; }
          .signal-card-metrics{ flex-shrink:0; display:grid; grid-template-columns:auto auto auto; gap:0.2rem 0.6rem; align-items:center; font-size:0.8125rem; white-space:nowrap; }
          .metric-label{ color:var(--faint); text-align:right; }
          .metric-value{ font-family:var(--mono); font-size:0.8125rem; color:var(--ink); text-align:right; }
          .metric-viz{ display:flex; align-items:center; }
          .conc-bar-track{ display:block; width:96px; height:6px; background:var(--line); border-radius:3px; overflow:hidden; }
          .conc-bar-fill{ display:block; height:100%; border-radius:3px; background:var(--ink); opacity:0.45; transition:width 0.3s ease; }
          .intensity-dots-svg{ display:flex; align-items:center; gap:2px; width:46px; }
          .signal-sparkbars{ display:inline-flex; align-items:flex-end; gap:2px; height:28px; width:96px; }
          .signal-sparkbar{ width:12px; border-radius:1px 1px 0 0; }
          .pattern-label{ display:inline-block; font-family:var(--mono); font-size:0.72rem; font-weight:520; text-transform:uppercase; letter-spacing:0.06em; padding:0.15rem 0.45rem; border-radius:3px; opacity:0.9; }
          .pattern-success{ background:#dcfce7; color:#166534; } .pattern-tension{ background:#fef3c7; color:#92400e; }
          .pattern-gap{ background:#fee2e2; color:#991b1b; } .pattern-recovery{ background:#e0f2fe; color:#075985; }
          html[data-appearance="dark"] .pattern-success{ background:#14532d; color:#86efac; }
          html[data-appearance="dark"] .pattern-tension{ background:#451a03; color:#fcd34d; }
          html[data-appearance="dark"] .pattern-gap{ background:#450a0a; color:#fca5a5; }
          html[data-appearance="dark"] .pattern-recovery{ background:#0c4a6e; color:#7dd3fc; }
          .flap{ display:inline-block; overflow:hidden; vertical-align:bottom; }
          .flap .roll{ display:block; }
          .flap.flip .roll{ animation:flap-flip .3s ease-in; }
          @keyframes flap-flip{ 0%{ transform:translateY(-105%); opacity:.15; } 100%{ transform:translateY(0); opacity:1; } }
          @media (prefers-reduced-motion:reduce){ .flap.flip .roll{ animation:none !important; } .conc-bar-fill{ transition:none !important; } }
        </style></head>
        <body>
          <div class="signal-card">
            <div class="signal-card-top">
              <div class="signal-card-identity">
                <span class="signal-card-source" data-src></span>
                <div class="signal-card-location" data-loc></div>
                <div class="signal-card-tags"><span class="badge" data-tag></span><span class="pattern-label" data-pat></span></div>
              </div>
              <div class="signal-card-metrics">
                <span class="metric-label" title="Composite signal strength">Signal</span>
                <span class="metric-value" data-mv="signal"></span>
                <span class="metric-viz"><span class="signal-sparkbars" data-spark></span></span>
                <span class="metric-label" title="Concentration ratio — how overrepresented vs study average">Concentration</span>
                <span class="metric-value" data-mv="conc"></span>
                <span class="metric-viz"><span class="conc-bar-track"><span class="conc-bar-fill" data-cbar></span></span></span>
                <span class="metric-label" title="Agreement — effective number of voices (Simpson's diversity)">Agreement</span>
                <span class="metric-value" data-mv="agree"></span>
                <span class="metric-viz"><span class="conc-bar-track"><span class="conc-bar-fill" data-abar></span></span></span>
                <span class="metric-label" title="Mean emotional intensity (0–3)">Intensity</span>
                <span class="metric-value" data-mv="intensity"></span>
                <span class="metric-viz" data-dots></span>
              </div>
            </div>
          </div>
        <script>
          var R = document.documentElement.getAttribute("data-reduce")==="1" || matchMedia("(prefers-reduced-motion:reduce)").matches;
          function flapWord(host, word){
            host.innerHTML="";
            String(word).split("").forEach(function(ch,i){
              var f=document.createElement("span"); f.className="flap";
              var r=document.createElement("span"); r.className="roll";
              r.textContent = ch===" " ? " " : ch;
              f.appendChild(r); host.appendChild(f);
              if(!R) setTimeout(function(){ f.classList.add("flip"); setTimeout(function(){ f.classList.remove("flip"); },300); }, i*40);
            });
          }
          var SIGNALS=[
            { src:"SECTION", loc:"Onboarding",     tag:["badge-confusion","confusion"],     accent:"var(--bn-sentiment-confusion)",   pat:["pattern-gap","GAP"],           signal:"2.41", conc:"3.2×", concPct:64, agree:"4.1", agreePct:68, intensity:2.5 },
            { src:"THEME",   loc:"Search results", tag:["badge-delight","delight"],         accent:"var(--bn-sentiment-delight)",     pat:["pattern-success","SUCCESS"],   signal:"1.98", conc:"2.6×", concPct:52, agree:"5.3", agreePct:88, intensity:2.1 },
            { src:"THEME",   loc:"Checkout",       tag:["badge-frustration","frustration"], accent:"var(--bn-sentiment-frustration)", pat:["pattern-tension","TENSION"],   signal:"3.12", conc:"4.3×", concPct:86, agree:"3.4", agreePct:57, intensity:2.8 },
            { src:"SECTION", loc:"Settings",       tag:["badge-doubt","doubt"],             accent:"var(--bn-sentiment-doubt)",       pat:["pattern-recovery","RECOVERY"], signal:"1.74", conc:"1.9×", concPct:38, agree:"2.2", agreePct:37, intensity:1.6 }
          ];
          var VALS=SIGNALS.map(function(s){ return parseFloat(s.signal); });
          function sparkbars(idx, accent){
            var max=Math.max.apply(null,VALS), maxH=28, n=VALS.length, barW=Math.floor((96-(n-1)*2)/n);
            return VALS.map(function(v,i){
              var h=Math.max(2,(v/max)*maxH), op=i===idx?1:Math.max(0.09,(v/max)*0.45), bg=i===idx?accent:"var(--ink)";
              return '<div class="signal-sparkbar" style="height:'+h+'px;width:'+barW+'px;background:'+bg+';opacity:'+op+'"></div>';
            }).join("");
          }
          function dotsSVG(value){
            var r=5,cx0=7,gap=16,w=cx0+gap*2+r+2,h=r*2+2,y=r+1,col="var(--ink)",rd=Math.round(value*2)/2,out="";
            for(var i=0;i<3;i++){ var th=i+1,x=cx0+i*gap;
              if(rd>=th) out+='<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+col+'" opacity="0.7"/>';
              else if(rd>=th-0.5) out+='<clipPath id="c'+i+'"><rect x="'+(x-r)+'" y="'+(y-r)+'" width="'+r+'" height="'+(r*2)+'"/></clipPath><circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+col+'" opacity="0.7" clip-path="url(#c'+i+')"/><circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="none" stroke="'+col+'" stroke-width="1.2" opacity="0.35"/>';
              else out+='<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="none" stroke="'+col+'" stroke-width="1.2" opacity="0.35"/>';
            }
            return '<svg class="intensity-dots-svg" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'">'+out+'</svg>';
          }
          function q(sel){ return document.querySelector(sel); }
          var idx=0;
          function set(){
            var s=SIGNALS[idx];
            q("[data-src]").textContent=s.src;
            q("[data-tag]").className="badge "+s.tag[0]; q("[data-tag]").textContent=s.tag[1];
            q("[data-pat]").className="pattern-label "+s.pat[0];
            q("[data-spark]").innerHTML=sparkbars(idx,s.accent);
            q("[data-cbar]").style.width=s.concPct+"%"; q("[data-abar]").style.width=s.agreePct+"%";
            q("[data-dots]").innerHTML=dotsSVG(s.intensity);
            if(R){
              q("[data-loc]").textContent=s.loc; q("[data-pat]").textContent=s.pat[1];
              q('[data-mv="signal"]').textContent=s.signal; q('[data-mv="conc"]').textContent=s.conc;
              q('[data-mv="agree"]').textContent=s.agree;  q('[data-mv="intensity"]').textContent=s.intensity.toFixed(1);
              return;
            }
            flapWord(q("[data-loc]"), s.loc);
            flapWord(q("[data-pat]"), s.pat[1]);
            flapWord(q('[data-mv="signal"]'), s.signal);
            flapWord(q('[data-mv="conc"]'), s.conc);
            flapWord(q('[data-mv="agree"]'), s.agree);
            flapWord(q('[data-mv="intensity"]'), s.intensity.toFixed(1));
          }
          // Scale the whole card to fit the cell — aspect preserved, max 90% (like the
          // tools-cell images), shrinking further when narrower. Never wraps (internal
          // layout is a fixed 440px), never scrolls (body overflow hidden).
          function fit(){
            var c=document.querySelector('.signal-card');
            var s=Math.min(0.9,(window.innerWidth-8)/c.offsetWidth,(window.innerHeight-8)/c.offsetHeight);
            if(isFinite(s) && s>0) c.style.transform='translate(-50%,-50%) scale('+s+')';
          }
          set();
          requestAnimationFrame(fit);
          window.addEventListener('resize', fit);
          if(!R) setInterval(function(){ idx=(idx+1)%SIGNALS.length; set(); }, 2800);
        </script>
        </body></html>
        """
    }

    static func emergentThemes(dark: Bool, reduce: Bool) -> String {
        """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{ --ink:#1a1a1a; --faint:#6b7280; }
          html[data-appearance="dark"]{ --ink:#e5e7eb; --faint:#9ca3af; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ font-family:-apple-system,"SF Pro Text",system-ui,sans-serif; }
          .fish{ position:absolute; left:0; top:0; font-size:11px; font-weight:420; color:var(--ink); white-space:nowrap; transform:translate(-50%,-50%); }
          .tl{ position:absolute; left:0; top:0; transform:translate(-50%,-50%); text-align:center; opacity:0; transition:opacity .6s ease; pointer-events:none; }
          .tl .n{ font-size:12px; font-weight:600; color:var(--ink); white-space:nowrap; }
          .tl.on{ opacity:1; }
        </style></head>
        <body>
        <script>
          var R = document.documentElement.getAttribute("data-reduce")==="1" || matchMedia("(prefers-reduced-motion:reduce)").matches;
          var SH={ A:{ name:"Getting started is a struggle", words:["“where do I start?”","confusing","too many steps","I gave up"] },
                   B:{ name:"Found it in seconds",           words:["“found it fast”","really clear","one tap","obvious"] } };
          var host=document.body, fishes=[], labels={};
          ["A","B"].forEach(function(key){ SH[key].words.forEach(function(txt){
            var el=document.createElement("span"); el.className="fish"; el.textContent=txt; host.appendChild(el);
            fishes.push({ el:el, key:key, phase:Math.random()*6.28, freq:0.6+Math.random()*0.6, amp:8+Math.random()*6 });
          }); });
          ["A","B"].forEach(function(key){ var l=document.createElement("div"); l.className="tl"; l.innerHTML='<div class="n">'+SH[key].name+'</div>'; host.appendChild(l); labels[key]=l; });
          function homes(W,H){ var cx=W/2, cy=H/2;
            var flock=fishes.map(function(f,i){ return { x:cx+Math.cos(i*1.7)*44, y:cy+Math.sin(i*2.3)*28 }; });
            var split=fishes.map(function(f){ var g=SH[f.key].words, idx=g.indexOf(f.el.textContent), n=g.length;
              var colX=f.key==="A"?W*0.30:W*0.70; var y0=cy-(n-1)/2*20+idx*20+8; return { x:colX, y:y0 }; });
            return { flock:flock, split:split };
          }
          function posLabels(){ var W=host.clientWidth||300; labels.A.style.left=(W*0.30)+"px"; labels.A.style.top="14px"; labels.B.style.left=(W*0.70)+"px"; labels.B.style.top="14px"; }
          if(R){
            var W0=host.clientWidth||300, H0=host.clientHeight||140, h0=homes(W0,H0);
            fishes.forEach(function(f,i){ f.el.style.transform="translate(-50%,-50%) translate("+h0.split[i].x+"px,"+h0.split[i].y+"px)"; });
            posLabels(); labels.A.classList.add("on"); labels.B.classList.add("on");
          } else {
            var CYCLE=8200, SWOOP=1600, t0=performance.now();
            function ease(x){ return x<0.5 ? 2*x*x : 1-Math.pow(-2*x+2,2)/2; }
            function tick(now){ var W=host.clientWidth||300, H=host.clientHeight||140, hm=homes(W,H); posLabels();
              var p=((now-t0)%CYCLE)/CYCLE, blend, show;
              if(p<SWOOP/CYCLE){ blend=ease(p/(SWOOP/CYCLE)); show=false; }
              else if(p<0.5){ blend=1; show=true; }
              else if(p<0.5+SWOOP/CYCLE){ blend=1-ease((p-0.5)/(SWOOP/CYCLE)); show=false; }
              else { blend=0; show=false; }
              labels.A.classList.toggle("on",show); labels.B.classList.toggle("on",show);
              var ts=now/1000;
              fishes.forEach(function(f,i){
                var hx=hm.flock[i].x+(hm.split[i].x-hm.flock[i].x)*blend;
                var hy=hm.flock[i].y+(hm.split[i].y-hm.flock[i].y)*blend;
                var j=f.amp*(1-blend*0.7);
                var x=hx+Math.cos(ts*f.freq+f.phase)*j, y=hy+Math.sin(ts*f.freq*1.3+f.phase)*j*0.8;
                f.el.style.transform="translate(-50%,-50%) translate("+x+"px,"+y+"px)";
              });
              requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
          }
        </script>
        </body></html>
        """
    }
}
