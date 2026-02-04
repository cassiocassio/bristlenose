# Tag Taxonomy Redesign — Draft

## Old system (14 categories)

**Intent (7):** narration, confusion, judgment, frustration, delight, suggestion, task_management
**Emotion (7):** neutral, frustrated, delighted, confused, amused, sarcastic, critical

Problems:
- Overlap: confusion/confused, frustration/frustrated, delight/delighted
- "narration" and "task_management" aren't emotions — they're utterance types
- "judgment" is ambiguous (positive or negative?)
- Too many badges per quote

## New system (7 categories)

Based on academic research (see `docs/academic-sources.html`):

| Tag | Valence | Description |
|-----|---------|-------------|
| **frustration** | negative | Difficulty, annoyance, friction, things not working |
| **confusion** | negative | Not understanding, uncertainty, cognitive struggle |
| **doubt** | negative | Scepticism, worry, distrust, unease, anxiety |
| **surprise** | neutral | Expectation mismatch — interface behaved differently than anticipated (flag for investigation) |
| **satisfaction** | positive | Met expectations, task success, things working as expected |
| **delight** | positive | Exceeded expectations, pleasure, positive surprise |
| **confidence** | positive | Trust, feeling in control, credibility signals |

Plus **intensity (1-3)**: low, moderate, strong

## Key changes

1. **Single field** — `sentiment` replaces both `intent` and `emotion`
2. **One tag per quote** — force a single dominant sentiment (simpler, cleaner)
3. **No "neutral" default** — if no sentiment detected, leave field empty/null. Purely descriptive narration quotes are still extracted but not tagged
4. **Intensity kept but hidden** — stored in the model for future use, but not shown as a badge in the UI
5. **Removed:** narration, task_management, judgment, sarcastic, amused, critical

## Prompt section (for QUOTE_EXTRACTION_PROMPT)

```
For each quote, classify the participant's sentiment:

- **sentiment**: the single dominant feeling expressed — one of:
  - `frustration` — difficulty, annoyance, friction ("This is so slow", "Why won't it work?")
  - `confusion` — not understanding, uncertainty ("I don't get what this means", "Where am I supposed to click?")
  - `doubt` — scepticism, worry, distrust ("I'm not sure I'd trust this", "This seems sketchy")
  - `surprise` — expectation mismatch, the interface behaved differently than anticipated ("Oh, that's not what I expected", "Wait, that button does *that*?"). Flags quotes for researcher investigation
  - `satisfaction` — met expectations, task success ("Good, that worked", "Okay, found it")
  - `delight` — exceeded expectations, pleasure, positive surprise ("Oh I love this!", "That's really nice")
  - `confidence` — trust, feeling in control ("I know exactly what to do here", "This feels solid")

  Leave empty if the quote is purely descriptive with no emotional content (e.g., "I'm clicking on beds").

- **intensity**: how strong the sentiment is — `1` (mild), `2` (moderate), `3` (strong)
```

## Model changes

### models.py

Replace `QuoteIntent` and `EmotionalTone` enums with:

```python
class Sentiment(str, Enum):
    FRUSTRATION = "frustration"
    CONFUSION = "confusion"
    DOUBT = "doubt"
    SURPRISE = "surprise"
    SATISFACTION = "satisfaction"
    DELIGHT = "delight"
    CONFIDENCE = "confidence"
```

Update `ExtractedQuote`:
```python
class ExtractedQuote(BaseModel):
    # ... existing fields ...
    sentiment: Sentiment | None = None  # Single dominant sentiment, or None if purely descriptive
    intensity: int = 1  # 1=mild, 2=moderate, 3=strong — kept for future use, not displayed
    # Remove: intent, emotion
```

### structured.py

Update `ExtractedQuoteItem`:
```python
sentiment: str | None = Field(
    default=None,
    description=(
        "Single dominant sentiment: frustration, confusion, doubt, surprise, "
        "satisfaction, delight, confidence. Leave empty/null if purely descriptive."
    ),
)
intensity: int = Field(
    default=1,
    description="Sentiment intensity: 1 (mild), 2 (moderate), 3 (strong)",
    ge=1,
    le=3,
)
```

### render_html.py

Update `_quote_badges()`:
```python
def _quote_badges(quote: ExtractedQuote) -> str:
    """Build HTML badge span for the quote's sentiment (if any)."""
    if quote.sentiment is None:
        return ""
    css_class = f"badge badge-ai badge-{quote.sentiment.value}"
    return f'<span class="{css_class}" data-badge-type="ai">{quote.sentiment.value}</span>'
    # Note: intensity is stored but not displayed as a badge
```

Update `_build_sentiment_html()`:
- Negative: frustration, confusion, doubt
- Positive: satisfaction, delight, confidence
- Neutral (don't count in histogram): surprise

## CSS additions needed

### Design system abstraction for sentiment colours

Create a semantic layer in `tokens.css` that maps sentiments to colours. This makes it easy to:
1. Tweak the palette in one place
2. Eventually let users assign colours to custom tags

```css
/* tokens.css — Sentiment colour palette (easily tweakable) */

/* Negative sentiments */
--bn-sentiment-frustration: var(--bn-colour-red-600);
--bn-sentiment-frustration-bg: var(--bn-colour-red-50);
--bn-sentiment-confusion: var(--bn-colour-orange-600);
--bn-sentiment-confusion-bg: var(--bn-colour-orange-50);
--bn-sentiment-doubt: var(--bn-colour-purple-600);
--bn-sentiment-doubt-bg: var(--bn-colour-purple-50);

/* Neutral (investigation flag) */
--bn-sentiment-surprise: var(--bn-colour-amber-600);
--bn-sentiment-surprise-bg: var(--bn-colour-amber-50);

/* Positive sentiments */
--bn-sentiment-satisfaction: var(--bn-colour-green-600);
--bn-sentiment-satisfaction-bg: var(--bn-colour-green-50);
--bn-sentiment-delight: var(--bn-colour-emerald-600);
--bn-sentiment-delight-bg: var(--bn-colour-emerald-50);
--bn-sentiment-confidence: var(--bn-colour-blue-600);
--bn-sentiment-confidence-bg: var(--bn-colour-blue-50);
```

### Badge classes (badge.css)

```css
.badge-frustration { background: var(--bn-sentiment-frustration-bg); color: var(--bn-sentiment-frustration); }
.badge-confusion { background: var(--bn-sentiment-confusion-bg); color: var(--bn-sentiment-confusion); }
.badge-doubt { background: var(--bn-sentiment-doubt-bg); color: var(--bn-sentiment-doubt); }
.badge-surprise { background: var(--bn-sentiment-surprise-bg); color: var(--bn-sentiment-surprise); }
.badge-satisfaction { background: var(--bn-sentiment-satisfaction-bg); color: var(--bn-sentiment-satisfaction); }
.badge-delight { background: var(--bn-sentiment-delight-bg); color: var(--bn-sentiment-delight); }
.badge-confidence { background: var(--bn-sentiment-confidence-bg); color: var(--bn-sentiment-confidence); }
```

### Future: User-defined tag colours

For custom user tags, we'll need:
1. A way to store colour assignments (localStorage or people.yaml)
2. CSS custom properties injected at runtime, e.g.:
   ```css
   .badge-user[data-tag="my-tag"] {
     background: var(--bn-user-tag-my-tag-bg, var(--bn-colour-user-tag-bg));
     color: var(--bn-user-tag-my-tag, var(--bn-colour-user-tag-text));
   }
   ```
3. A colour picker UI in the report

This is out of scope for the taxonomy redesign but the `--bn-sentiment-*` abstraction layer sets up the pattern.
