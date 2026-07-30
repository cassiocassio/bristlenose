"""Chat-lens lab — flag-gated cited-question-box experiment (serve mode).

One route plus one lab page, per ``docs/design-chat-lens.md`` §6. The page
is deliberately ugly (codebook-lab precedent): what the prototype tests is
not "can it answer" but "are the citations honest", so every cited quote
renders inline beneath its claim — a wrong citation is obvious without a
click — and every id the model returned that does not resolve against the
corpus is flagged, visibly, as invalid.

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
    """Everything the page needs to render a cited quote inline."""
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
    ``claims[].quote_ids``, ``unsupported`` — design-chat-lens.md §7);
    ``claims[].quote_ids`` carries only ids that resolved against the
    corpus, with the model's failures split out as ``invalid_quote_ids``
    and the resolved quotes inlined as ``quotes``.
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
                "invalid_quote_ids": claim.invalid_quote_ids,
                "quotes": [_quote_payload(q) for q in claim.quotes],
            }
            for claim in result.claims
        ],
        "unsupported": result.unsupported,
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
  body { font: 14px/1.5 system-ui, sans-serif; margin: 0; padding: 16px; color: #111; max-width: 860px; }
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
  .claim { border: 1px solid #d0d7de; border-radius: 6px; padding: 10px 12px; margin: 10px 0; }
  .claim .c-text { font-weight: 600; }
  .cited-quote { border-left: 3px solid #1f6feb; background: #f6f8fa; border-radius: 0 6px 6px 0; padding: 6px 10px; margin: 8px 0 8px 12px; }
  .cited-quote .q-text { font-style: italic; }
  .cited-quote .q-meta { font-size: 12px; color: #555; margin-top: 2px; }
  .badge-invalid { display: inline-block; font-size: 11px; background: #cf222e; color: #fff; border-radius: 8px; padding: 0 6px; margin-left: 6px; }
  .badge-uncited { display: inline-block; font-size: 11px; background: #d4a72c; color: #fff; border-radius: 8px; padding: 0 6px; margin-left: 6px; }
  .invalid-id { text-decoration: line-through; color: #a40e26; font-family: ui-monospace, monospace; font-size: 12px; }
  .invalid-box { border: 1px dashed #cf222e; border-radius: 6px; background: #fff5f5; padding: 6px 10px; margin: 8px 0 8px 12px; font-size: 12px; }
  .unsupported { border: 1px solid #d0d7de; border-radius: 6px; background: #f6f8fa; padding: 8px 12px; margin: 10px 0; color: #444; }
  .unsupported .u-title { font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: .03em; }
  .qid { font-family: ui-monospace, monospace; font-size: 12px; color: #1f6feb; }
  .star { color: #b58900; }
  pre { background: #0d1117; color: #c9d1d9; padding: 10px; border-radius: 6px; overflow: auto; font-size: 12px; white-space: pre-wrap; }
  .meta-line { font-size: 12px; color: #666; margin-top: 6px; }
  .warn { background: #fff8c5; border: 1px solid #d4a72c; padding: 6px 10px; border-radius: 6px; font-size: 12px; margin: 8px 0; }
</style>
</head>
<body>
<h1>Chat lens <span class="pill">experiment</span></h1>
<div class="muted">Ask one question about this project's quotes. No history, no streaming. Each ask sends the whole curated corpus to your configured LLM provider on your own key (~cost shown after each answer). What this lab is testing: <b>are the citations honest</b> — every claim's quotes render inline so a wrong citation is obvious.</div>

<fieldset>
  <legend>Question</legend>
  <textarea id="question" rows="2" placeholder="What do participants think about the navigation?"></textarea>
  <div class="row">
    <button class="primary" id="btnAsk">Ask →</button>
    <span class="muted">⌘⏎ / Ctrl⏎ also asks</span>
    <span id="status" class="muted"></span>
  </div>
</fieldset>

<fieldset>
  <legend>Answer</legend>
  <div id="answer"><div class="muted">no question asked yet.</div></div>
  <div id="metaLine" class="meta-line"></div>
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
function setBusy(b){ $("btnAsk").disabled = b; $("status").textContent = b ? "asking… (one live LLM call)" : ""; }

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
  const box = $("answer"); box.innerHTML = "";
  let html = "";
  (j.claims || []).forEach(c => {
    const uncited = (!c.quotes || !c.quotes.length) && (!c.invalid_quote_ids || !c.invalid_quote_ids.length);
    html += '<div class="claim"><div class="c-text">' + esc(c.text)
          + (uncited ? '<span class="badge-uncited">uncited claim</span>' : "")
          + ((c.invalid_quote_ids && c.invalid_quote_ids.length) ? '<span class="badge-invalid">invalid citation</span>' : "")
          + '</div>';
    (c.quotes || []).forEach(q => { html += quoteCard(q); });
    if (c.invalid_quote_ids && c.invalid_quote_ids.length) {
      html += '<div class="invalid-box">cited ids that do not exist in this corpus: '
            + c.invalid_quote_ids.map(id => '<span class="invalid-id">' + esc(id) + '</span>').join(" ")
            + '</div>';
    }
    html += '</div>';
  });
  if (j.unsupported) {
    html += '<div class="unsupported"><div class="u-title">Not covered by this study’s quotes</div>'
          + esc(j.unsupported) + '</div>';
  }
  if (!html) html = '<div class="muted">the model returned no claims and no coverage note.</div>';
  box.innerHTML = html;

  const co = j.corpus || {}, call = j.call || {};
  $("metaLine").textContent =
    "corpus: " + co.quote_count + " of " + co.total_quotes + " quotes"
    + (co.hidden_excluded ? " (" + co.hidden_excluded + " hidden excluded)" : "")
    + (co.truncated ? " · TRUNCATED" : "")
    + " · ~" + (co.approx_tokens || 0) + " input tokens"
    + " · " + (call.provider || "?") + "/" + (call.model || "?")
    + " · " + (call.elapsed_ms || 0) + " ms · prompt v" + (call.prompt_version || "?");
}

async function ask(){
  const question = $("question").value.trim();
  if (!question) { log("type a question first."); return; }
  setBusy(true); log("asking…");
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
