#!/usr/bin/env python3
"""Mock terminal sessions for the any-llm provider (docs/design-any-llm.md, v1).

Run:      .venv/bin/python docs/mockups/any-llm-cli-session.py
Creates:  docs/mockups/any-llm-cli-session.html

Every frame is printed through Rich, with the CLI's real glyphs and colours
(bristlenose/ui_kinds.py), so the output looks the way the shipped CLI will.
Lines copied from today's output (doctor rows, the pipeline view, the run
summary, configure's "Stored in…") keep their real wording. New any-llm copy
is proposed wording, listed in the commentary under each frame.
"""

from __future__ import annotations

import html
import io
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.terminal_theme import TerminalTheme

OUT = Path(__file__).with_suffix(".html")

# macOS Terminal "Pro"-like palette: dark ground, the stock ANSI hues.
THEME = TerminalTheme(
    (30, 30, 30),
    (229, 229, 229),
    [
        (0, 0, 0), (232, 98, 92), (102, 204, 125), (231, 196, 91),
        (98, 160, 234), (194, 129, 215), (88, 199, 214), (199, 199, 199),
    ],
    [
        (102, 102, 102), (255, 123, 114), (126, 231, 135), (255, 214, 102),
        (121, 192, 255), (210, 168, 255), (118, 227, 234), (255, 255, 255),
    ],
)

OK = "[green]✓[/green]"
INFO = "[cyan]ℹ[/cyan]"
WARN = "[yellow]⚠[/yellow]"
ERR = "[red]✗[/red]"
SKIP = "[dim]—[/dim]"
PROMPT = "[bold blue]~/research[/bold blue] [bold]$[/bold] "
VERSION = "0.43.0"
HW = "Apple M2 Max · MLX"


def cmd(c: Console, text: str) -> None:
    c.print(f"{PROMPT}[bold white]{escape(text)}[/bold white]", highlight=False)


SCENES: list[tuple[str, str, object, list[str]]] = []


def scene(title: str, chrome: str, notes: list[str]):
    def wrap(fn):
        SCENES.append((title, chrome, fn, notes))
        return fn
    return wrap


# ── 1 ────────────────────────────────────────────────────────────────────
@scene(
    "1 · First run, no provider yet",
    "bristlenose run — first run",
    [
        "Existing output (<code>_print_provider_guidance</code>). The only change is the last line.",
        "New line: <em>For Mistral, OpenRouter and others:</em> + the configure command.",
    ],
)
def s1(c: Console) -> None:
    cmd(c, "bristlenose run interviews/")
    c.print()
    c.print("[bold]No LLM provider configured.[/bold]")
    c.print()
    c.print("Set one up once — [bold cyan]bristlenose configure <provider>[/bold cyan] validates your")
    c.print("key and stores it securely (Keychain):")
    c.print()
    for name, url in (
        ("Claude", "https://console.anthropic.com/settings/keys"),
        ("ChatGPT", "https://platform.openai.com/api-keys"),
        ("Gemini", "https://aistudio.google.com/apikey"),
        ("Azure", "https://portal.azure.com"),
    ):
        c.print(f"  {name.ljust(9)}[link={url}]{url}[/link]")
    c.print()
    c.print("For local models via Ollama:  [bold cyan]bristlenose configure local[/bold cyan]")
    c.print(
        "For Mistral, OpenRouter and others:  "
        "[bold cyan]bristlenose configure any-llm[/bold cyan]"
    )
    c.print()


# ── 2 ────────────────────────────────────────────────────────────────────
@scene(
    "2 · The extra isn't installed",
    "configure any-llm — not installed",
    [
        "Install hint picks the channel (pipx here; pip / uv / Homebrew otherwise), as <code>voice_install_hint</code> does.",
        "Exit 1. The brackets are escaped so Rich doesn't eat <code>[any-llm]</code> (review finding 15b).",
        "Under Homebrew it says nothing of the sort: the formula carries the extra (owner, 23 Oct).",
    ],
)
def s2(c: Console) -> None:
    cmd(c, "bristlenose configure any-llm")
    c.print()
    c.print(f"{ERR} any-llm isn't installed in this copy of Bristlenose.")
    c.print("  Add it:  [bold]pipx install --force \"bristlenose\\[any-llm]\"[/bold]")
    c.print()
    cmd(c, 'pipx install --force "bristlenose[any-llm]"')
    c.print("  installed package [bold]bristlenose[/bold] 0.43.0, installed using Python 3.12.13")
    c.print("  These apps are now globally available")
    c.print("    - bristlenose")
    c.print("done! ✨ 🌟 ✨")
    c.print()


# ── 3 ────────────────────────────────────────────────────────────────────
@scene(
    "3 · configure any-llm — key already in the shell",
    "configure any-llm — Mistral, key from environment",
    [
        "Asks one thing: the model. The key was already exported, so nothing is stored (the shell wins, then the store).",
        "Checks with the run preflight's own inert request, so green means the run will start (Fable 1, 4). The destination is named: the host when any-llm's provider class carries one, else the provider (Fable 8).",
        "Ends with the existing <code>_set_current_provider</code> lines, word for word.",
    ],
)
def s3(c: Console) -> None:
    cmd(c, "export MISTRAL_API_KEY=…")
    cmd(c, "bristlenose configure any-llm")
    c.print()
    c.print("Which model? Write it as [bold]provider:model[/bold], e.g. mistral:mistral-large-latest", highlight=False)
    c.print("[bold]Model:[/bold] mistral:mistral-large-latest", highlight=False)
    c.print("Using the Mistral key from your environment (MISTRAL_API_KEY).", highlight=False)
    c.print("Checking with Mistral (~$0.0001, no transcript content)...", end=" ")
    c.print(f"{OK} Valid")
    c.print("[dim]Transcripts will go to Mistral, through any-llm 1.27.0.[/dim]", highlight=False)
    c.print()
    c.print("any-llm is now your provider for analysis (was Claude).")
    c.print("Switch back any time:  [bold]bristlenose use claude[/bold]")
    c.print("Run it with:  [bold]bristlenose run <folder>[/bold]")
    c.print()


# ── 4 ────────────────────────────────────────────────────────────────────
@scene(
    "4 · configure any-llm — no key yet, so it's stored",
    "configure any-llm — DeepSeek, key stored in Keychain",
    [
        "No <code>DEEPSEEK_API_KEY</code> in the shell, so it asks (hidden input), checks, stores, reads back. DeepSeek rides on the OpenAI SDK Bristlenose already ships, so it needs no add-on.",
        "Stored per inner provider, under a Bristlenose name (\"…(any-llm)\") so Keychain Access shows whose it is.",
        "<code>Stored in Keychain as …</code> is today's wording; on Linux it says Secret Service, elsewhere config file.",
    ],
)
def s4(c: Console) -> None:
    cmd(c, "bristlenose configure any-llm")
    c.print()
    c.print("Which model? Write it as [bold]provider:model[/bold], e.g. mistral:mistral-large-latest", highlight=False)
    c.print("[bold]Model:[/bold] deepseek:deepseek-flash", highlight=False)
    c.print()
    c.print("[bold]Enter your DeepSeek API key:[/bold] ")
    c.print("Checking with DeepSeek (~$0.0001, no transcript content)...", end=" ")
    c.print(f"{OK} Valid")
    c.print(f'{OK} Stored in Keychain as "Bristlenose DeepSeek API Key (any-llm)"')
    c.print("[dim]Transcripts will go to DeepSeek (api.deepseek.com), through any-llm 1.27.0.[/dim]", highlight=False)
    c.print()
    c.print("any-llm is now your provider for analysis.")
    c.print("Run it with:  [bold]bristlenose run <folder>[/bold]")
    c.print()


# ── 5 ────────────────────────────────────────────────────────────────────
@scene(
    "5 · Scripted setup: --key and the model variable",
    "configure any-llm --key, non-interactive",
    [
        "<code>configure</code> already has <code>--key</code>. The model comes from <code>BRISTLENOSE_ANYLLM_MODEL</code>, as Azure's deployment does. No new flag.",
        "OpenRouter rides on the OpenAI SDK we already ship.",
    ],
)
def s5(c: Console) -> None:
    cmd(c, "export BRISTLENOSE_ANYLLM_MODEL=openrouter:meta-llama/llama-3.3-70b-instruct:free")
    cmd(c, "bristlenose configure any-llm --key sk-or-v1-…")
    c.print()
    c.print("[bold]Model:[/bold] openrouter:meta-llama/llama-3.3-70b-instruct:free  [dim](from BRISTLENOSE_ANYLLM_MODEL)[/dim]", highlight=False)
    c.print("Checking with OpenRouter (~$0.0001, no transcript content)...", end=" ")
    c.print(f"{OK} Valid")
    c.print(f'{OK} Stored in Keychain as "Bristlenose OpenRouter API Key (any-llm)"')
    c.print("[dim]Transcripts will go to OpenRouter (openrouter.ai), which passes them to the[/dim]", highlight=False)
    c.print("[dim]model's host. Check their data policy for the model you picked.[/dim]")
    c.print()
    c.print("any-llm is now your provider for analysis.")
    c.print()


# ── 6 ────────────────────────────────────────────────────────────────────
@scene(
    "6 · configure any-llm — every way it can say no",
    "configure any-llm — refusals",
    [
        "One offline readiness probe answers all of these: format, known provider, inner SDK present, key present (finding 5). No network, nothing stored.",
        "The five built-in providers are refused as inner prefixes and pointed at their own command (finding 15f, proposed).",
        "Implementation rule found while drawing this: Rich's auto-highlighter reads <code>anthropic:claude</code> as an IPv6 address and colours it. Every line that prints a model string turns highlighting off.",
        "A provider outside the default four names the add-on for this channel. The model string is never echoed back in errors that might contain a pasted key (15c).",
    ],
)
def s6(c: Console) -> None:
    cmd(c, "bristlenose configure any-llm")
    c.print("[bold]Model:[/bold] mistral-large-latest", highlight=False)
    c.print(f"{ERR} Write the model as provider:model, e.g. mistral:mistral-large-latest", highlight=False)
    c.print()
    cmd(c, "bristlenose configure any-llm")
    c.print("[bold]Model:[/bold] mistrall:mistral-large-latest", highlight=False)
    c.print(f"{ERR} any-llm doesn't know a provider called \"mistrall\". Did you mean mistral?")
    c.print("  [dim]Providers: https://mozilla-ai.github.io/any-llm/providers/[/dim]")
    c.print()
    cmd(c, "bristlenose configure any-llm")
    c.print("[bold]Model:[/bold] anthropic:claude-sonnet-4-6", highlight=False)
    c.print(f"{ERR} Claude is built in. Use:  [bold]bristlenose configure claude[/bold]")
    c.print()
    cmd(c, "bristlenose configure any-llm")
    c.print("[bold]Model:[/bold] cohere:command-r-plus", highlight=False)
    c.print(f"{ERR} Cohere needs an add-on this install doesn't have.")
    c.print("  Add it:  [bold]pipx inject bristlenose \"any-llm-sdk\\[cohere]\"[/bold]")
    c.print()


# ── 7 ────────────────────────────────────────────────────────────────────
@scene(
    "7 · run — the everyday path",
    "bristlenose run interviews/",
    [
        "Header names any-llm (today an unknown id falls back to \"Claude\"; fixed). New dim line: model, library, destination host.",
        "No \"Estimated LLM cost\" line, and no cost in the summary: we don't price the long tail rather than show Claude's price (finding 6).",
        "Stage lines and summary are today's format; the LLM line names the real model.",
    ],
)
def s7(c: Console) -> None:
    cmd(c, "bristlenose run interviews/")
    c.print(f"\nBristlenose [dim]v{VERSION} · any-llm · {HW}[/dim]\n")
    c.print("[dim]Analysis: mistral:mistral-large-latest via any-llm → Mistral[/dim]", highlight=False)
    c.print("[dim]4 sessions in interviews/[/dim]")
    c.print()
    lines = [
        ("Ingested 4 sessions (4 video)", "0.8s"),
        ("Extracted audio from 4 sessions", "1.3s"),
        ("Transcribed 4 sessions (229 segments)", "2m 41s"),
        ("Identified speakers for 4 sessions", "6.2s"),
        ("Merged transcripts for 4 sessions", "0.1s"),
        ("Segmented 4 transcripts into 35 topics", "11.4s"),
        ("Extracted 48 quotes from 4 sessions", "38.9s"),
        ("Clustered quotes into 4 themes (7 screens)", "9.7s"),
        ("Rendered report", "0.2s"),
    ]
    for text, t in lines:
        c.print(f" {OK} {text.ljust(52)}[dim]{t.rjust(7)}[/dim]")
    c.print()
    c.print("  [dim]4 participants · 7 screens · 4 themes · 48 quotes[/dim]")
    c.print("  [dim]LLM: 44,920 in · 9,112 out (mistral:mistral-large-latest)[/dim]", highlight=False)
    c.print()
    c.print("  [green]Done[/green] in 3m 52s")
    c.print()
    c.print("  Report:  [bold cyan]http://127.0.0.1:8150/report/[/bold cyan]")
    c.print("  [dim]Press Ctrl-C to stop the server[/dim]")
    c.print()


# ── 8 ────────────────────────────────────────────────────────────────────
@scene(
    "8 · run --llm any-llm with no model set",
    "run --llm any-llm — no model",
    [
        "<code>run</code> never prompts (design-cli-provider-selection.md). Exit 2, like the other provider errors.",
        "<code>-l anyllm</code> and <code>--llm any-llm</code> both work; so does the env var, normalised (finding 15a).",
    ],
)
def s8(c: Console) -> None:
    cmd(c, "bristlenose run interviews/ --llm any-llm")
    c.print()
    c.print(f"{ERR} any-llm needs a model, written as provider:model.", highlight=False)
    c.print("  Set it once:  [bold]bristlenose configure any-llm[/bold]")
    c.print("  Or per run:   [bold]BRISTLENOSE_ANYLLM_MODEL=mistral:mistral-large-latest[/bold]", highlight=False)
    c.print()


# ── 9 ────────────────────────────────────────────────────────────────────
@scene(
    "9 · use — switching between stored keys",
    "bristlenose use",
    [
        "<code>use provider:model</code> switches to a model whose key is already stored or exported: no network, nothing asked, like <code>use claude</code>. Keys are stored once per provider, so switching never asks for one again.",
        "A provider with no key yet changes nothing and names the fix. The first two lines are today's <code>_set_current_provider</code> wording.",
    ],
)
def s9(c: Console) -> None:
    cmd(c, "bristlenose use mistral:mistral-large-latest")
    c.print("any-llm is now your provider for analysis (was Claude).")
    c.print("Switch back any time:  [bold]bristlenose use claude[/bold]")
    c.print("Model: mistral:mistral-large-latest (was deepseek:deepseek-flash)", highlight=False)
    c.print()
    cmd(c, "bristlenose use deepseek:deepseek-flash")
    c.print("any-llm is now your provider for analysis.")
    c.print("Model: deepseek:deepseek-flash (was mistral:mistral-large-latest)", highlight=False)
    c.print()
    cmd(c, "bristlenose use openrouter:x-ai/grok-4")
    c.print(f"{ERR} No OpenRouter API key: OPENROUTER_API_KEY isn't set and none is stored.", highlight=False)
    c.print("  Store one:  bristlenose configure any-llm", highlight=False)
    c.print()
    cmd(c, "bristlenose use claude")
    c.print("Claude is now your provider for analysis (was any-llm).")
    c.print("Switch back any time:  [bold]bristlenose use any-llm[/bold]")
    c.print()


# ── 10 ───────────────────────────────────────────────────────────────────
@scene(
    "10 · doctor",
    "bristlenose doctor",
    [
        "Today's rows and row shapes. The API key row names the real provider. Network has no host to probe for Mistral (no API base in 1.27), so the run's preflight covers it.",
        "One new row, <code>any-llm</code>: the version and the providers this install carries. It's the credit as much as the check.",
    ],
)
def s10(c: Console) -> None:
    cmd(c, "bristlenose doctor")
    c.print(f"\nbristlenose {VERSION}\n")
    rows = [
        (OK, "FFmpeg", "8.1.1 (/opt/homebrew/bin/ffmpeg)"),
        (OK, "Transcription", "mlx-whisper 0.4.3 (MLX)"),
        (OK, "Whisper model", "large-v3-turbo cached (1.5 GB)"),
        (OK, "API key", "Mistral (…f2a) (environment)"),
        (OK, "any-llm", "1.27.0 · mistral, groq, openrouter, deepseek"),
        (SKIP, "Network", "checked by the run's preflight for Mistral"),
        (SKIP, "PII redaction", "off (use --redact-pii to enable)"),
        (OK, "Voice pass", "model cached (40 MB)"),
        (OK, "Disk space", "44 GB free"),
        (OK, "Serve mode", "6 deps installed"),
        (OK, "Auth token", "random (generated at serve startup)"),
    ]
    for g, name, val in rows:
        c.print(f" {g} {name.ljust(15)} {escape(val)}")
    c.print("\nAll clear.\n")


# ── 11 ───────────────────────────────────────────────────────────────────
@scene(
    "11 · doctor — when something's off",
    "bristlenose doctor — key missing",
    [
        "No version-window warning (cut in Fable's review): the exact pin and the pipx advice are the fix.",
        "DeepSeek picked, key missing: the variable's name comes from any-llm's own error, never a map we keep.",
        "Fix lines use the existing doctor-fix shape.",
    ],
)
def s11(c: Console) -> None:
    cmd(c, "bristlenose doctor")
    c.print(f"\nbristlenose {VERSION}\n")
    c.print(f" {OK} FFmpeg          8.1.1 (/opt/homebrew/bin/ffmpeg)")
    c.print(f" {ERR} API key         No DeepSeek API key: DEEPSEEK_API_KEY isn't set and none is stored.", highlight=False)
    c.print(f" {SKIP} Network         skipped (no key)")
    c.print()
    c.print("[bold]API key[/bold]")
    c.print("  Store one:  [bold]bristlenose configure any-llm[/bold]")
    c.print()


# ── 12 ───────────────────────────────────────────────────────────────────
@scene(
    "12 · pipeline",
    "bristlenose pipeline (excerpt)",
    [
        "One backend group, \"any-llm\", in every LLM stage, with the model synthesised from settings, as Azure's is. Rated <code>? untested</code>: we don't rate models we haven't measured.",
        "When it can't run, the row says why, in the Azure sibling's shape: not installed / no model set / no key.",
    ],
)
def s12(c: Console) -> None:
    cmd(c, "bristlenose pipeline")
    c.print("QUOTE EXTRACTION, QUOTE CLUSTERING,")
    c.print("THEMATIC GROUPING, DISCUSSION")
    c.print("  Claude")
    c.print(f"    Sonnet 4.6  (default)                    {OK}  [green]●[/green]")
    c.print("  ChatGPT")
    c.print(f"    GPT-5.6 Terra                            {OK}  [green]●[/green]")
    c.print(f"  Azure OpenAI                               {ERR}     no Azure OpenAI key set")
    c.print("  Gemini")
    c.print(f"    3.8 Flash                                {OK}  ?  untested")
    c.print("  Local (Ollama)")
    c.print(f"    llama3.2 3B                              {OK}  {WARN}  small models miss multi-clause quotes")
    c.print("  any-llm")
    c.print(f"    mistral:mistral-large-latest  (current)  {OK}  ?  untested", highlight=False)
    c.print(f"  Apple FM                                   {SKIP}     check in the desktop app")
    c.print()
    c.print("[dim]OS: Darwin arm64 · RAM: 32.0 GB · keys: anthropic, openai, anyllm · ollama: running[/dim]")
    c.print()
    cmd(c, "bristlenose pipeline   # on a machine without the add-on")
    c.print("  ...")
    c.print(f"  any-llm                                    {ERR}     any-llm not installed")
    c.print()


# ── 13 ───────────────────────────────────────────────────────────────────
@scene(
    "13 · run — the provider says no",
    "run — out of credit, bad key, rate limit",
    [
        "Today's failure banners, word for word, naming the account the researcher has (\"Your OpenRouter account…\"), never \"your any-llm account\" (finding 11), with <code>configure any-llm</code> as the key fix.",
        "Classified on the inner provider first, so an empty account isn't read as \"rate limited\" (finding 3). Provider's own words passed through.",
        "Rate limits retry with the provider SDK's own defaults first. OpenRouter's and DeepSeek's 402 reads as out of credit through the new provider-agnostic rule.",
    ],
)
def s13(c: Console) -> None:
    cmd(c, "bristlenose run interviews/")
    c.print(f"\nBristlenose [dim]v{VERSION} · any-llm · {HW}[/dim]\n")
    c.print("[dim]Analysis: openrouter:anthropic/claude-sonnet-4.6 via any-llm → openrouter.ai[/dim]", highlight=False)
    c.print()
    c.print(f" {OK} Ingested 4 sessions (4 video)                            [dim]0.8s[/dim]")
    c.print(f" {OK} Transcribed 4 sessions (229 segments)                 [dim](cached)[/dim]")
    c.print(f" {ERR} Identifying speakers")
    c.print()
    c.print(f"{ERR} Your OpenRouter account ran out of credit.")
    c.print("  then run  [bold]bristlenose run interviews/[/bold]  again.")
    c.print()
    cmd(c, "bristlenose run interviews/")
    c.print("  ...")
    c.print(f"{ERR} Mistral rejected your API key (…x7f).")
    c.print("  Run  [bold]bristlenose configure any-llm[/bold]  to set a new key.")
    c.print()
    cmd(c, "bristlenose run interviews/")
    c.print("  ...")
    c.print(f"{ERR} Rate-limited by DeepSeek.")
    c.print("  Wait a minute and run  [bold]bristlenose run interviews/[/bold]  again.")
    c.print()


# ── 14 ───────────────────────────────────────────────────────────────────
@scene(
    "14 · Help text",
    "run --help / configure --help (excerpts)",
    [
        "Two help strings gain \"any-llm\". No new flags anywhere in v1.",
    ],
)
def s14(c: Console) -> None:
    cmd(c, "bristlenose run --help")
    c.print("│ [bold cyan]--llm[/bold cyan]                 [bold green]-l[/bold green]      [bold yellow]<str>[/bold yellow]   LLM provider: claude, chatgpt, azure, gemini,  │")
    c.print("│                                       local, any-llm.                                │")
    c.print()
    cmd(c, "bristlenose configure --help")
    c.print("│ *    provider      [bold yellow]<str>[/bold yellow]  Provider to configure: claude, chatgpt, gemini,       │")
    c.print("│                           azure, local, any-llm, or miro.                         │")
    c.print()


def render() -> str:
    frames = []
    for title, chrome, fn, notes in SCENES:
        c = Console(record=True, width=92 if title.startswith("14") else 80, color_system="truecolor",
                    force_terminal=True, file=io.StringIO())
        fn(c)
        body = c.export_html(theme=THEME, inline_styles=True, code_format="{code}")
        notes_html = "".join(f"<li>{n}</li>" for n in notes)
        frames.append(
            f'<section class="scene"><h2>{html.escape(title)}</h2>'
            f'<div class="term"><div class="bar"><i></i><i></i><i></i>'
            f"<span>{html.escape(chrome)}</span></div><pre>{body}</pre></div>"
            f'<aside class="note"><b>Commentary</b><ul>{notes_html}</ul></aside></section>'
        )
    return PAGE.replace("{{FRAMES}}", "\n".join(frames))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>any-llm CLI sessions</title>
<style>
:root { color-scheme: light dark;
  --page: light-dark(#f6f5f2, #161616); --ink: light-dark(#1d1d1f, #e8e8e8);
  --muted: light-dark(#6b6b70, #a0a0a5); --rule: light-dark(#d9d6cf, #333);
  --note: light-dark(#efece4, #202020); }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif; }
main { max-width: 980px; margin: 0 auto; padding: 32px 16px 80px; }
h1 { font-size: 26px; margin: 0 0 6px; }
.lede { color: var(--muted); margin: 0 0 18px; max-width: 70ch; }
.key { display: flex; gap: 18px; flex-wrap: wrap; font-size: 13px; color: var(--muted); margin-bottom: 28px; }
.key span::before { content: ""; display: inline-block; width: 12px; height: 12px; margin-right: 6px;
  vertical-align: -1px; border-radius: 3px; }
.key .a::before { background: #1e1e1e; }
.key .c::before { background: repeating-linear-gradient(45deg, var(--note), var(--note) 3px, var(--rule) 3px, var(--rule) 5px); }
.scene { margin: 0 0 40px; }
.scene h2 { font-size: 16px; margin: 0 0 10px; }
.term { border-radius: 10px; overflow: hidden; background: #1e1e1e;
  box-shadow: 0 1px 2px rgba(0,0,0,.2), 0 8px 24px rgba(0,0,0,.18); }
.bar { height: 30px; display: flex; align-items: center; gap: 8px; padding: 0 12px;
  background: #2b2b2b; border-bottom: 1px solid #111; }
.bar i { width: 12px; height: 12px; border-radius: 50%; background: #ff5f57; }
.bar i:nth-child(2) { background: #febc2e; } .bar i:nth-child(3) { background: #28c840; }
.bar span { flex: 1; text-align: center; color: #9a9a9a; font-size: 12px; margin-right: 52px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.term a { color: inherit; }
.term pre { margin: 0; padding: 14px 16px 16px; overflow-x: auto; color: #e5e5e5;
  font: 13px/1.45 ui-monospace, Menlo, "Cascadia Mono", Consolas, monospace; }
.note { margin-top: 10px; padding: 10px 14px; border-left: 3px solid var(--rule);
  background: repeating-linear-gradient(45deg, var(--note), var(--note) 6px, transparent 6px, transparent 9px);
  font-size: 13.5px; }
.note b { font: 11px ui-monospace, Menlo, monospace; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.note ul { margin: 6px 0 0; padding-left: 18px; }
.note code { font-size: 12.5px; }
</style></head><body><main>
<h1>any-llm on the command line</h1>
<p class="lede">Built v1 sessions for <code>docs/design-any-llm.md</code>, after the first review pass.
Every command, the flags it touches, and each response. Glyphs, colours and today's lines are the shipped CLI's;
the any-llm wording is what the built code prints, noted under each frame. Generated by
<code>docs/mockups/any-llm-cli-session.py</code>.</p>
<div class="key"><span class="a">Terminal: what ships</span><span class="c">Commentary: why, not product</span></div>
{{FRAMES}}
</main></body></html>
"""


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
