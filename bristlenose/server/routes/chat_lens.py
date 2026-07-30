"""Chat-lens lab — flag-gated cited-question-box experiment (serve mode).

One route plus one lab page, per ``docs/design-chat-lens.md`` §6 as
corrected by §5a. The page is deliberately ugly (codebook-lab precedent):
what the prototype tests is not "can it answer" but "are the citations
honest", so cited quotes render next to their claims, invalid citations
are flagged visibly, and every cited claim carries a support-check verdict
(flag, never gate). §5a contests inline-under-claim as the obviously-right
layout — a persistent aligned sidebar was the only condition that
preserved critical engagement in the one controlled study — so the page
offers both layouts behind a toggle, which is itself the experiment.

Mounted in ``app.py`` behind the ``experimental_chat_lens`` flag — NOT on
``--dev`` — so it ships in the bundled desktop sidecar and plain ``serve``
(same shipping shape as the codebook lab). The page lives outside ``/api``
so a plain browser navigation isn't blocked by the bearer-token middleware;
it embeds the token for its own fetches.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from bristlenose.server.grounding import CorpusQuote

logger = logging.getLogger(__name__)

# Same /api/dev prefix as the codebook lab: experiment endpoints share the
# dev namespace even when mounted in non-dev serves.
chat_lens_router = APIRouter(prefix="/api/dev")


class _AskRequest(BaseModel):
    question: str = ""
    project_id: int = 1


def _quote_payload(quote: CorpusQuote) -> dict[str, object]:
    """Everything the page needs to render a cited quote."""
    return {
        "id": quote.dom_id,
        "participant_id": quote.participant_id,
        "session_id": quote.session_id,
        "text": quote.text,
        "sentiment": quote.sentiment,
        "tags": quote.tags,
        "starred": quote.starred,
        "where": quote.where,
        "start_timecode": quote.start_timecode,
    }


@chat_lens_router.post("/chat-lens/ask")
async def chat_lens_ask(request: Request, body: _AskRequest) -> dict[str, object]:
    """Answer one question from the project corpus, citations validated.

    The response keeps the shared vocabulary (``claims[].text``,
    ``claims[].quote_ids``, ``unsupported`` — design-chat-lens.md §7).
    The model itself cites server-constructed integer indices (§5a
    Correction 2); the server maps them back to stable quote ids here, so
    ``quote_ids`` carries only resolved ids, with fabrications split out
    as ``invalid_citations`` (the out-of-range integers). Each cited claim
    also carries the §5a Correction 1 support verdict.
    """
    from bristlenose.config import load_settings
    from bristlenose.server.chat_lens import ask_question
    from bristlenose.server.models import Project

    # app.state.settings-or-load_settings seam (per server/CLAUDE.md) so an
    # injected settings object is honoured in tests.
    settings = getattr(request.app.state, "settings", None) or load_settings()

    db = request.app.state.db_factory()
    try:
        project = db.query(Project).filter_by(id=body.project_id).first()
        if project is None:
            raise HTTPException(
                status_code=404, detail=f"Project {body.project_id} not found"
            )
        try:
            result = await ask_question(body.question, settings, db, body.project_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("chat_lens_ask_failed")
            raise HTTPException(
                status_code=502, detail=f"{type(exc).__name__}: {exc}"
            ) from exc
    finally:
        db.close()

    return {
        "claims": [
            {
                "text": claim.text,
                "quote_ids": [q.dom_id for q in claim.quotes],
                "invalid_citations": claim.invalid_citations,
                "citation_exempt": claim.citation_exempt,
                "support": claim.support,
                "quotes": [_quote_payload(q) for q in claim.quotes],
            }
            for claim in result.claims
        ],
        "unsupported": result.unsupported,
        "abstain_reason": result.abstain_reason,
        "corpus": {
            "quote_count": result.corpus.quote_count,
            "total_quotes": result.corpus.total_quotes,
            "hidden_excluded": result.corpus.hidden_excluded,
            "truncated": result.corpus.truncated,
            "char_count": result.corpus.char_count,
            "approx_tokens": result.corpus.char_count // 4,
        },
        "call": {
            "provider": result.provider,
            "model": result.model,
            "elapsed_ms": result.elapsed_ms,
            "prompt_version": result.prompt_version,
        },
    }


def build_chat_lens_html(auth_token: str = "") -> str:
    """Return the bare chat-lens experiment page.

    Served at ``/chat-lens`` (outside ``/api`` so a plain browser navigation
    isn't blocked by the bearer-token middleware); the embedded token lets
    the page's own fetch() calls authenticate against ``/api/dev``.
    """
    token_js = json.dumps(auth_token)
    return _CHAT_LENS_HTML.replace("__TOKEN__", token_js)


_CHAT_LENS_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chat lens (experiment)</title>
<style>
  body { font: 14px/1.5 system-ui, sans-serif; margin: 0; padding: 16px; color: #111; max-width: 1060px; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .muted { color: #666; font-size: 12px; }
  fieldset { border: 1px solid #ccc; border-radius: 6px; margin: 12px 0; padding: 10px 12px; }
  legend { font-weight: 600; padding: 0 6px; }
  textarea { width: 100%; box-sizing: border-box; font: inherit; padding: 6px; border: 1px solid #bbb; border-radius: 4px; resize: vertical; }
  button { font: inherit; padding: 6px 12px; border: 1px solid #888; border-radius: 4px; background: #f3f3f3; cursor: pointer; }
  button.primary { background: #1f6feb; color: #fff; border-color: #1f6feb; }
  button:disabled { opacity: .5; cursor: default; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
  .pill { display: inline-block; font-size: 11px; background: #eee; border-radius: 10px; padding: 1px 8px; }
  .chip { font-size: 12px; border: 1px solid #bbb; border-radius: 12px; background: #fafafa; padding: 2px 10px; cursor: pointer; }
  .chip:hover { background: #eef; }

  /* Claims — inline layout (default) and aligned-sidebar layout. */
  .claim { border: 1px solid #d0d7de; border-radius: 6px; padding: 10px 12px; margin: 10px 0; }
  .layout-sidebar .claim { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 4px 16px; }
  .layout-sidebar .claim .c-head { grid-column: 1; }
  .layout-sidebar .claim .c-evidence { grid-column: 2; grid-row: 1 / span 2; border-left: 1px solid #d0d7de; padding-left: 12px; }
  .layout-sidebar .claim .c-invalid { grid-column: 1; }
  .c-text { font-weight: 600; }
  .claim.exempt .c-text { font-weight: 400; color: #555; }
  .cited-quote { border-left: 3px solid #1f6feb; background: #f6f8fa; border-radius: 0 6px 6px 0; padding: 6px 10px; margin: 8px 0; }
  .layout-inline .cited-quote { margin-left: 12px; }
  .cited-quote .q-text { font-style: italic; }
  .cited-quote .q-meta { font-size: 12px; color: #555; margin-top: 2px; }

  .badge { display: inline-block; font-size: 11px; border-radius: 8px; padding: 0 6px; margin-left: 6px; color: #fff; vertical-align: 1px; }
  .badge-supported { background: #1a7f37; }
  .badge-unsupported { background: #cf222e; }
  .badge-unchecked { background: #6e7781; }
  .badge-uncited { background: #d4a72c; }
  .badge-invalid { background: #cf222e; }
  .badge-exempt { background: #eee; color: #666; }

  .invalid-box { border: 1px dashed #cf222e; border-radius: 6px; background: #fff5f5; padding: 6px 10px; margin: 8px 0; font-size: 12px; }
  .invalid-id { color: #a40e26; font-family: ui-monospace, monospace; }
  .abstain { border: 1px solid #d0d7de; border-radius: 6px; background: #f6f8fa; padding: 10px 12px; margin: 10px 0; }
  .abstain .a-head { font-weight: 600; }
  .abstain .a-coach { font-size: 12px; color: #555; margin-top: 4px; }
  .unsupported-note { color: #444; margin-top: 6px; }
  .qid { font-family: ui-monospace, monospace; font-size: 12px; color: #1f6feb; }
  .star { color: #b58900; }
  pre { background: #0d1117; color: #c9d1d9; padding: 10px; border-radius: 6px; overflow: auto; font-size: 12px; white-space: pre-wrap; }
  .meta-line { font-size: 12px; color: #666; margin-top: 6px; }
  .warn { background: #fff8c5; border: 1px solid #d4a72c; padding: 6px 10px; border-radius: 6px; font-size: 12px; margin: 8px 0; }
</style>
</head>
<body>
<h1>Chat lens <span class="pill">experiment</span></h1>
<div class="muted">Ask one question about this project's quotes. No history, no streaming. Each ask sends the whole curated corpus to your configured LLM provider on your own key, plus a second small support-check call. What this lab is testing: <b>are the citations honest</b> — every cited claim shows its quotes and a support verdict, and both layouts (inline vs sidebar) are here to compare, because the prior art contests which one keeps you critical.</div>

<fieldset>
  <legend>Question</legend>
  <textarea id="question" rows="2" placeholder="What did participants struggle with?"></textarea>
  <div class="row">
    <button class="primary" id="btnAsk">Ask →</button>
    <span class="muted">⌘⏎ / Ctrl⏎ also asks</span>
    <span style="flex:1"></span>
    <label class="muted" style="cursor:pointer"><input type="radio" name="layout" value="inline" checked> quotes inline</label>
    <label class="muted" style="cursor:pointer"><input type="radio" name="layout" value="sidebar"> quotes in a sidebar</label>
  </div>
  <div class="row" id="examples">
    <span class="muted">try:</span>
  </div>
</fieldset>

<fieldset>
  <legend>Answer</legend>
  <div id="answer" class="layout-inline"><div class="muted">no question asked yet.</div></div>
  <div id="metaLine" class="meta-line"></div>
  <div class="muted" id="judgeNote" style="display:none">support verdicts come from a second model call that is right roughly three times in four — they flag, they never hide. An unsupported flag means: read the quotes yourself.</div>
</fieldset>

<fieldset>
  <legend>Raw / log</legend>
  <pre id="log">ready.</pre>
</fieldset>

<script>
const TOKEN = __TOKEN__;
const H = { "Content-Type": "application/json", "Authorization": "Bearer " + TOKEN };
const $ = id => document.getElementById(id);
const log = (x) => { $("log").textContent = (typeof x === "string" ? x : JSON.stringify(x, null, 2)); };
function esc(s){ return (""+(s??"")).replace(/[&<>"]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function setBusy(b){ $("btnAsk").disabled = b; }

const EXAMPLES = [
  "What did participants struggle with most?",
  "Where did the navigation confuse people?",
  "Which moments delighted participants?",
];
EXAMPLES.forEach(q => {
  const b = document.createElement("button");
  b.className = "chip"; b.textContent = q;
  b.onclick = () => { $("question").value = q; $("question").focus(); };
  $("examples").appendChild(b);
});

const ABSTAIN = {
  out_of_scope: {
    head: "This question isn’t about this study’s interviews.",
    coach: "Ask about what participants said, did, or struggled with in these sessions.",
  },
  no_evidence: {
    head: "Nothing in this study’s quotes addresses this.",
    coach: "That can be a finding in itself. Try a different area of the study, or broaden the question.",
  },
  ungroundable: {
    head: "Some quotes touch this, but none actually support an answer.",
    coach: "Try narrowing the question to what participants actually discussed.",
  },
};

const SUPPORT_BADGE = {
  supported: '<span class="badge badge-supported">supported</span>',
  unsupported: '<span class="badge badge-unsupported">citations don’t support this as stated</span>',
  unchecked: '<span class="badge badge-unchecked">support unchecked</span>',
};

let LAST_RESPONSE = null;

function quoteCard(q){
  const bits = [
    '<span class="qid">' + esc(q.id) + '</span>',
    esc(q.participant_id),
    q.where ? esc(q.where) : "",
    q.sentiment ? esc(q.sentiment) : "",
    q.tags && q.tags.length ? "tags: " + esc(q.tags.join(", ")) : "",
    q.starred ? '<span class="star">★ starred</span>' : "",
  ].filter(Boolean).join(" · ");
  return '<div class="cited-quote"><div class="q-text">“' + esc(q.text) + '”</div>'
       + '<div class="q-meta">' + bits + '</div></div>';
}

function renderAnswer(j){
  LAST_RESPONSE = j;
  const layout = document.querySelector('input[name="layout"]:checked').value;
  const box = $("answer");
  box.className = layout === "sidebar" ? "layout-sidebar" : "layout-inline";
  let html = "";
  let anyChecked = false;

  (j.claims || []).forEach(c => {
    const uncited = !c.citation_exempt
      && (!c.quotes || !c.quotes.length)
      && (!c.invalid_citations || !c.invalid_citations.length);
    let badges = "";
    if (c.citation_exempt) badges += '<span class="badge badge-exempt">connective</span>';
    if (uncited) badges += '<span class="badge badge-uncited">uncited claim</span>';
    if (c.invalid_citations && c.invalid_citations.length) badges += '<span class="badge badge-invalid">invalid citation</span>';
    if (c.support && SUPPORT_BADGE[c.support]) { badges += SUPPORT_BADGE[c.support]; anyChecked = true; }

    html += '<div class="claim' + (c.citation_exempt ? " exempt" : "") + '">'
          + '<div class="c-head"><span class="c-text">' + esc(c.text) + '</span>' + badges + '</div>';
    html += '<div class="c-evidence">';
    (c.quotes || []).forEach(q => { html += quoteCard(q); });
    html += '</div>';
    if (c.invalid_citations && c.invalid_citations.length) {
      html += '<div class="c-invalid"><div class="invalid-box">cited '
            + c.invalid_citations.map(n => '<span class="invalid-id">[' + esc(n) + ']</span>').join(" ")
            + ' — not in the corpus it was shown</div></div>';
    }
    html += '</div>';
  });

  if (!(j.claims || []).length) {
    const a = ABSTAIN[j.abstain_reason] || ABSTAIN.no_evidence;
    html += '<div class="abstain"><div class="a-head">' + esc(a.head) + '</div>'
          + (j.unsupported ? '<div class="unsupported-note">' + esc(j.unsupported) + '</div>' : "")
          + '<div class="a-coach">' + esc(a.coach) + '</div></div>';
  } else if (j.unsupported) {
    html += '<div class="abstain"><div class="a-head">Partly outside this study’s quotes</div>'
          + '<div class="unsupported-note">' + esc(j.unsupported) + '</div></div>';
  }

  box.innerHTML = html;
  $("judgeNote").style.display = anyChecked ? "" : "none";

  const co = j.corpus || {}, call = j.call || {};
  $("metaLine").textContent =
    "corpus: " + co.quote_count + " of " + co.total_quotes + " quotes"
    + (co.hidden_excluded ? " (" + co.hidden_excluded + " hidden excluded)" : "")
    + (co.truncated ? " · TRUNCATED" : "")
    + " · ~" + (co.approx_tokens || 0) + " input tokens"
    + " · " + (call.provider || "?") + "/" + (call.model || "?")
    + " · " + (call.elapsed_ms || 0) + " ms · prompt v" + (call.prompt_version || "?");
}

document.querySelectorAll('input[name="layout"]').forEach(r => {
  r.onchange = () => { if (LAST_RESPONSE) renderAnswer(LAST_RESPONSE); };
});

async function ask(){
  const question = $("question").value.trim();
  if (!question) { log("type a question first."); return; }
  setBusy(true); log("asking… (answer call, then a support-check call)");
  try {
    const r = await fetch("/api/dev/chat-lens/ask", {
      method: "POST", headers: H,
      body: JSON.stringify({ question: question, project_id: 1 }),
    });
    const j = await r.json().catch(() => ({ detail: "(no json)" }));
    if (!r.ok) throw new Error(j.detail || r.status);
    renderAnswer(j); log(j);
  } catch(e){
    $("answer").innerHTML = '<div class="warn">ask failed: ' + esc(e.message) + '</div>';
    log("ERROR: " + e.message);
  } finally { setBusy(false); }
}

$("btnAsk").onclick = ask;
$("question").addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") ask();
});
</script>
</body>
</html>
"""
