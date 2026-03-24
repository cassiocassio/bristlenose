# German locale review — questions for a native speaker

Bristlenose is a local-first user-research analysis tool (macOS desktop app + web). We've machine-translated the UI into German and need a native speaker — ideally someone who does qualitative research — to sanity-check the terminology.

You don't need to review every string. The standard UI chrome (Save = Sichern, Cancel = Abbrechen, etc.) comes straight from Apple's official German macOS glossary — those are fine. What we need your eye on is the **research domain vocabulary** and a few specific choices.

## The terms we're most unsure about

### 1. Kodes or Codes?

We used **"Kodes"** (with K) throughout — ATLAS.ti germanises it this way. MAXQDA keeps "Codes". In your experience, which do German researchers actually say? Would "Kodes" feel natural in a tool UI, or would you expect "Codes"?

Current usage: menu items like "Kode erstellen", "Kode umbenennen", "Kodes zusammenführen".

### 2. Codebuch — does it land?

We used **"Codebuch"** for "Codebook" (MAXQDA's term). Alternatives from academic literature: "Kategoriensystem" (Mayring), "Codierleitfaden" (coding guide). Does "Codebuch" feel right in a tool UI, or would something else be more natural?

### 3. Sentiment labels

These are badges on participant quotes showing emotional tone. We chose:

| English | German | Why | Alternatives we rejected |
|---------|--------|-----|-------------------------|
| Frustration | Frustration | Same word | — |
| Confusion | Verwirrung | | Irritation (too strong) |
| Doubt | Zweifel | | Unsicherheit (= uncertainty, broader) |
| Surprise | Überraschung | | Erstaunen (more literary) |
| Satisfaction | Zufriedenheit | | Befriedigung (sexual connotation risk) |
| **Delight** | **Begeisterung** | Enthusiasm, excitement | Entzücken (too literary/precious), Freude (too generic) |
| **Confidence** | **Zuversicht** | Forward-looking assurance | Vertrauen (= trust, different concept), Selbstvertrauen (too long for a badge) |

**Delight** and **Confidence** are the two we're least sure about. In English UX research, "delight" is the positive surprise — the moment a user says "oh, that's nice!" Does "Begeisterung" capture that, or is it too strong (closer to "enthusiasm")?

For "Confidence" — we mean the feeling of being in control, knowing what to do next. "Zuversicht" has an optimistic/hopeful tone. Is that right, or would something else fit better?

### 4. Gender-inclusive forms

We used the **Genderdoppelpunkt** (colon):

- Forscher:in (Researcher)
- Teilnehmer:in (Participant)
- Beobachter:in (Observer)

Is this what your institution or community uses? The main alternatives:
- **Genderstern**: Forscher\*in — older convention, still common
- **Partizip**: Forschende / Teilnehmende / Beobachtende — avoids the binary marker entirely, increasingly popular in academic German
- **Slash**: Forscher/in — more traditional

No strong opinion from our side — we want whatever feels most natural to German-speaking researchers right now.

### 5. Sessions → Interviews

We translated "Sessions" as **"Interviews"** because that's what German researchers call them (not "Sitzungen", which sounds clinical). But Bristlenose can also ingest focus groups, usability tests, and diary studies — not just interviews. Does "Interviews" still work as the tab label for a mixed set of research sessions, or would you expect something broader?

### 6. Anything that sounds off

Here are a few more strings where we made judgment calls. Do any of these read strangely?

| Key | German | English original |
|-----|--------|-----------------|
| Star (a quote) | Markieren | Star |
| Starred Quotes Only | Nur markierte Zitate | Starred Quotes Only |
| Re-analyse | Erneut analysieren | Re-analyse |
| Built with Bristlenose | Erstellt mit Bristlenose | Built with Bristlenose |
| Give feedback | Feedback geben | Give feedback |
| Report an issue | Problem melden | Report an issue |
| Toggle Sidebar | Seitenleiste ein-/ausblenden | Toggle Sidebar |
| Check System Health | Systemzustand prüfen | Check System Health |
| Picture in Picture | Bild-in-Bild | Picture in Picture |

## What you don't need to review

- Standard Apple macOS terms (Sichern, Abbrechen, Widerrufen, etc.) — verified against Apple's glossary
- Keyboard shortcuts and symbols (⌘, ⇧, etc.) — kept as-is
- Technical terms that stay English by convention (LLM, CSV, Framework, Tag, PII)
- The product name "Bristlenose" — never translated

## How to send feedback

Just annotate this document or reply with your thoughts — even a quick "Kodes feels weird, use Codes" is helpful. No need to be thorough about every string; we mainly want the six items above.
