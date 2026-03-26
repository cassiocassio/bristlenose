# PII Redaction Audit

This folder contains the results of running a deliberately adversarial test
transcript through Bristlenose's PII redaction (Microsoft Presidio, spaCy
`en_core_web_lg`, score threshold 0.7, default entity types).

The purpose is transparency: researchers and their organisations can see
exactly what gets caught and what slips through before relying on automated
PII redaction.

## Files

| File | What it is |
|------|-----------|
| [Original transcript](../../tests/fixtures/pii_horror_transcript.txt) | A fictional interview with PII planted across 8 adversarial categories |
| [Expected results](../../tests/fixtures/pii_horror_expected.yaml) | What we predict Presidio will catch/miss, with legal category annotations |
| [Redacted transcript](redacted-transcript.md) | The transcript after Presidio processing — compare with the original |
| [PII summary](pii-summary.txt) | The audit log showing every detected entity, its type, score, and timecode |

## What Presidio caught (45 entities)

- **Person names** — full names in clear context (Sarah Thornton, Rebecca Cheung, Dave Robson, Ahmed Rasheed, etc.)
- **Email addresses** — all 4 standard-format emails detected (score 1.0)
- **Phone number** — +44 international format detected
- **NHS number** — 943 476 5919 detected (score 1.0)
- **IBAN** — GB29 NWBK 6016 1331 9268 19 detected (score 1.0)
- **IP address** — 192.168.1.42 detected (score 0.95)
- **Some hard names caught** — Presidio surprised us by catching Bazza, Deano, Grace, Fatimah bint Khalid, Karen O'Brien-Kingsley, Kapoor, Jonh (misspelled), and Rachael

## What Presidio missed

### Names and identifiers
- **Will, Hope** — common English words used as names, not detected
- **Xiaoming** — Chinese single name, not detected
- **"our Trace"** — colloquial diminutive, not detected
- **@sarahthornton92, @sarah.t.a11y** — social media handles
- **sthornton, bwilloughby** — usernames
- **sarah_thornton_feedback.docx** — name in filename
- **linkedin.com/in/sarah-thornton-92** — name in URL

### Financial and identity numbers
- **4532 0123 4567 8901** — credit card with spaces (Presidio expects contiguous digits)
- **AB 12 34 56 C** — UK National Insurance number (no recogniser)
- **KV68 NPR** — UK vehicle registration (no recogniser)
- **60-16-13 / 31926819** — bank sort code and account number (no recogniser)
- **EMP-4582** — employee badge number (detected as PERSON, not as an ID)

### Addresses and locations
- **14 Rosemary Lane, Fetcham, GU2 4AB** — full postal address (ADDRESS not in default entities)
- **Clocktower Coworking on Brimley Street** — workplace
- **"the blue door, corner of Elm Road"** — described location

### GDPR special category data (Article 9) — none detected
- "since my ADHD diagnosis" — health
- "on sertraline for anxiety" — medication
- "Irish Travellers" — ethnic origin
- "card-carrying Labour member" — political opinion
- "we keep halal at home", "converted to Islam" — religion
- "our Unison rep" — trade union
- "my wife, well partner" — sexual orientation (implied)
- "panic attacks" — mental health

### Indirect identification — none detected
- "born on the 14th of March 1987" — date of birth
- "I'm 38" — age
- "the only accessibility tester" — unique role
- "St Wilfred's Primary in Ashtead" — child's school
- "Riverside Surgery in Ashtead" — GP surgery
- "38-year-old female accessibility tester at Hartwell in Fetcham who has ADHD" — mosaic

### False positives (over-redaction)
- **Fetcham** detected as PERSON (it's a place name, not a person)
- **St Wilfred's** detected as PERSON
- **Rosemary Lane** detected as PERSON
- **EMP-4582** detected as PERSON

## Bottom line

Presidio is good at structured PII (emails, phones, IBANs, standard-format names). It is poor at conversational PII (dictated details, nicknames, indirect identifiers) and has zero capability for GDPR special category data. **Human review is required before sharing transcripts externally.**

---

*This transcript is entirely fictional. All people, organisations, and details are invented. See the [fiction disclaimer](../../tests/fixtures/pii_horror_transcript.txt) at the top of the test file.*
