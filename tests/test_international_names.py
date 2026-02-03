"""Adversarial test suite for international name handling.

Reverse-engineered from "Falsehoods Programmers Believe About Names"
(Patrick McKenzie, 2010) and the Shine Solutions examples (2018), plus
the W3C "Personal names around the world" article.

Tests every code path that touches participant names:
  - _COLON_SPEAKER_PATTERN  (speaker extraction from VTT/SRT cue text)
  - _VTT_SPEAKER_PATTERN    (voice tag extraction in VTT)
  - _GENERIC_LABEL_RE       (is this a real name or a placeholder?)
  - suggest_short_names()   (first-token heuristic for short names)
  - extract_names_from_labels()
"""

from __future__ import annotations

import pytest

from bristlenose.models import (
    FullTranscript,
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.people import (
    _GENERIC_LABEL_RE,
    extract_names_from_labels,
    suggest_short_names,
)
from bristlenose.stages.parse_subtitles import (
    _VTT_SPEAKER_PATTERN,
    _extract_speaker,
)

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _people_with_names(name_map: dict[str, str]) -> PeopleFile:
    """Build a PeopleFile with full_name set, short_name empty."""
    from datetime import datetime, timezone

    participants: dict[str, PersonEntry] = {}
    for pid, full_name in name_map.items():
        participants[pid] = PersonEntry(
            computed=PersonComputed(
                participant_id=pid,
                session_id="s1",
                session_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                duration_seconds=60.0,
                words_spoken=100,
                pct_words=50.0,
                pct_time_speaking=50.0,
                source_file="test.vtt",
            ),
            editable=PersonEditable(full_name=full_name),
        )
    return PeopleFile(participants=participants)


def _transcript_with_labels(pid: str, labels: list[str]) -> FullTranscript:
    """Build a FullTranscript where each label appears once as PARTICIPANT."""
    from datetime import datetime, timezone

    segs = []
    for i, label in enumerate(labels):
        segs.append(
            TranscriptSegment(
                start_time=float(i),
                end_time=float(i + 1),
                text="some text",
                speaker_label=label,
                speaker_role=SpeakerRole.PARTICIPANT,
                source="vtt",
            )
        )
    return FullTranscript(
        session_id=f"s-{pid}",
        participant_id=pid,
        segments=segs,
        source_file="test.vtt",
        session_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        duration_seconds=float(len(labels)),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Colon speaker pattern — "Speaker Name: text" extraction
#
# The regex must accept real names from real platforms.  Zoom uses this
# format with the participant's Zoom display name, which can be anything
# the user typed.
# ═══════════════════════════════════════════════════════════════════════════


class TestColonSpeakerPattern:
    """Names that appear as 'Name: spoken text' in VTT/SRT cue text."""

    # -- Should match (real names from real platforms) -----------------------

    def test_simple_western(self) -> None:
        assert _extract_speaker("Sarah Jones: Hello everyone") == "Sarah Jones"

    def test_east_asian_romanised(self) -> None:
        """Chinese name in Western order (common on Zoom)."""
        assert _extract_speaker("Wei Zhang: Thank you") == "Wei Zhang"

    def test_japanese_romanised(self) -> None:
        """Japanese name in Western order."""
        assert _extract_speaker("Yuki Tanaka: Good morning") == "Yuki Tanaka"

    def test_korean_romanised(self) -> None:
        assert _extract_speaker("Ji-hyun Park: I agree") == "Ji-hyun Park"

    def test_hyphenated_given_name(self) -> None:
        """French-style compound given name."""
        assert _extract_speaker("Jean-Pierre Dupont: Bonjour") == "Jean-Pierre Dupont"

    def test_apostrophe_in_surname(self) -> None:
        """Irish surname."""
        assert _extract_speaker("Siobhan O'Brien: Right") == "Siobhan O'Brien"

    def test_period_in_name(self) -> None:
        """Academic title or initial."""
        assert _extract_speaker("Dr. Melissa Ko: Let me explain") == "Dr. Melissa Ko"

    def test_single_initial_middle(self) -> None:
        """Harry S Truman style."""
        assert _extract_speaker("Harry S. Truman: We shall") == "Harry S. Truman"

    def test_mononym(self) -> None:
        """Indonesian/Burmese single name — e.g. Suharto, Madonna."""
        assert _extract_speaker("Suharto: Welcome") == "Suharto"

    def test_all_caps(self) -> None:
        """Some Zoom users type their name in all caps."""
        assert _extract_speaker("KSHITIJ MAHESHWARY: Thank you") == "KSHITIJ MAHESHWARY"

    def test_initials_with_spaces(self) -> None:
        """Indian-style initials."""
        assert _extract_speaker("R P SINGH: Yes") == "R P SINGH"

    # -- Comma in Zoom display names (known failure — see real Zoom data) ---

    @pytest.mark.xfail(reason="Comma not in _COLON_SPEAKER_PATTERN char class")
    def test_zoom_affiliation_comma(self) -> None:
        """Zoom displays affiliation after comma: 'Sanjay Gupta, WUD'."""
        assert _extract_speaker("Sanjay Gupta, WUD: Good afternoon") == "Sanjay Gupta, WUD"

    @pytest.mark.xfail(reason="Comma not in _COLON_SPEAKER_PATTERN char class")
    def test_zoom_affiliation_no_space(self) -> None:
        """No space after comma."""
        assert _extract_speaker("Rajat Verma,WUD: Hello") == "Rajat Verma,WUD"

    # -- Name particles and prefixes ----------------------------------------

    def test_dutch_van_der(self) -> None:
        assert _extract_speaker("Pieter van der Meer: Hello") == "Pieter van der Meer"

    def test_arabic_al_prefix(self) -> None:
        assert _extract_speaker("Taj al-Din: Peace be upon you") == "Taj al-Din"

    def test_spanish_de_la(self) -> None:
        assert _extract_speaker("Maria de la Cruz: Hola") == "Maria de la Cruz"

    @pytest.mark.xfail(reason="ü is not in [A-Za-z] range")
    def test_german_von(self) -> None:
        assert _extract_speaker("Klaus von Bülow: Guten Tag") == "Klaus von Bülow"

    @pytest.mark.xfail(reason="ü is not in [A-Za-z] range")
    def test_umlaut_in_name(self) -> None:
        """German umlaut — outside ASCII A-Za-z."""
        assert _extract_speaker("Jürgen Müller: Hallo") == "Jürgen Müller"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_french_accented(self) -> None:
        """French accented characters."""
        assert _extract_speaker("René Détienne: Bonjour") == "René Détienne"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_spanish_accented(self) -> None:
        """Spanish tilde."""
        assert _extract_speaker("José Muñoz: Buenos días") == "José Muñoz"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_portuguese_cedilla(self) -> None:
        assert _extract_speaker("João Gonçalves: Olá") == "João Gonçalves"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_turkish_dotless_i(self) -> None:
        """Turkish İ/ı distinction."""
        assert _extract_speaker("Işık Barış: Merhaba") == "Işık Barış"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_polish_diacritics(self) -> None:
        assert _extract_speaker("Łukasz Wójcik: Dzień dobry") == "Łukasz Wójcik"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_czech_hacek(self) -> None:
        assert _extract_speaker("Jiří Dvořák: Dobrý den") == "Jiří Dvořák"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_icelandic_eth_thorn(self) -> None:
        """Icelandic ð and þ."""
        assert _extract_speaker("Guðrún Þórdís: Halló") == "Guðrún Þórdís"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_vietnamese_diacritics(self) -> None:
        """Vietnamese uses extensive diacritics."""
        assert _extract_speaker("Nguyễn Thị Minh: Xin chào") == "Nguyễn Thị Minh"

    @pytest.mark.xfail(reason="accented chars not in [A-Za-z] range")
    def test_scandinavian_ae_oe(self) -> None:
        """Norwegian/Danish Æ Ø Å."""
        assert _extract_speaker("Bjørn Ødegård: Hei") == "Bjørn Ødegård"

    # -- Non-Latin scripts (Zoom allows display names in any script) --------

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_chinese_characters(self) -> None:
        """Chinese name in native script."""
        assert _extract_speaker("张伟: 你好") == "张伟"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_japanese_kanji(self) -> None:
        assert _extract_speaker("田中裕子: おはようございます") == "田中裕子"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_korean_hangul(self) -> None:
        assert _extract_speaker("박지현: 동의합니다") == "박지현"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_arabic_script(self) -> None:
        """Arabic name in native script (RTL)."""
        assert _extract_speaker("محمد أحمد: مرحبا") == "محمد أحمد"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_hebrew_script(self) -> None:
        assert _extract_speaker("שרה כהן: שלום") == "שרה כהן"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_cyrillic_russian(self) -> None:
        """Russian name in Cyrillic."""
        assert _extract_speaker("Борис Ельцин: Здравствуйте") == "Борис Ельцин"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_devanagari_hindi(self) -> None:
        assert _extract_speaker("पुष्पेन्द्र सिंह: नमस्ते") == "पुष्पेन्द्र सिंह"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_thai_script(self) -> None:
        assert _extract_speaker("สมชาย: สวัสดีครับ") == "สมชาย"

    @pytest.mark.xfail(reason="regex only allows A-Za-z")
    def test_georgian_script(self) -> None:
        assert _extract_speaker("ნინო: გამარჯობა") == "ნინო"

    # -- Should NOT match (false positive risks) ----------------------------

    def test_url_in_text(self) -> None:
        """'https' is 5 alpha chars followed by colon — matches the speaker
        pattern as a false positive.  This is a known limitation of the
        colon-based heuristic.  In practice, VTT cue text rarely starts
        with a bare URL scheme."""
        # Documenting current behaviour, not asserting it's ideal
        result = _extract_speaker("https: this is a link")
        assert result == "https"  # false positive — accepted tradeoff

    def test_timestamp_colon(self) -> None:
        """'00:01:23' should not match."""
        assert _extract_speaker("00:01:23 some text") is None

    def test_colon_in_quote(self) -> None:
        """A colon mid-sentence isn't a speaker prefix."""
        # The regex requires the speaker name to start at ^, so this is OK
        # only if the text doesn't start with a name-like string.
        result = _extract_speaker("I said: let me think about that")
        # "I said" could match — 6 chars, all alpha + space
        # This is a known false-positive risk
        assert result in (None, "I said")  # document the ambiguity

    def test_number_prefix(self) -> None:
        """Name starting with digit should not match."""
        assert _extract_speaker("2pac: All eyes on me") is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. VTT voice span pattern — <v Speaker Name>text</v>
#
# Teams uses this for speaker identification.  The name can be anything
# from a GUID to a real name to "LastName, FirstName" format.
# ═══════════════════════════════════════════════════════════════════════════


class TestVttVoiceSpanPattern:
    """Names inside <v ...> voice tags in WebVTT."""

    def _match(self, raw: str) -> str | None:
        m = _VTT_SPEAKER_PATTERN.search(raw)
        return m.group(1).strip() if m else None

    # -- Western names ------------------------------------------------------

    def test_simple_name(self) -> None:
        assert self._match("<v Sarah Jones>Hello</v>") == "Sarah Jones"

    def test_name_no_closing_tag(self) -> None:
        """Teams sometimes omits closing </v>."""
        assert self._match("<v Sarah Jones>Hello everyone") == "Sarah Jones"

    # -- Teams GUID format --------------------------------------------------

    def test_azure_ad_guid(self) -> None:
        """Real Teams VTT: speaker is an Azure AD GUID."""
        raw = "<v 68f0e9b4-d6de-4cad-9c2a-9b587e97837f@72f988bf-86f1-41af-91ab-2d7cd011db47>Hello</v>"
        result = self._match(raw)
        assert result is not None
        assert "68f0e9b4" in result

    # -- LastName, FirstName (Teams corporate directory) --------------------

    def test_lastname_firstname(self) -> None:
        """Teams can show 'Sohoni, Sohum' format from AD."""
        assert self._match("<v Sohoni, Sohum>Good afternoon</v>") == "Sohoni, Sohum"

    # -- Non-ASCII names in voice tags (Teams shows display name) -----------

    def test_accented_in_voice_tag(self) -> None:
        assert self._match("<v José García>Hola</v>") == "José García"

    def test_chinese_in_voice_tag(self) -> None:
        assert self._match("<v 张伟>你好</v>") == "张伟"

    def test_arabic_in_voice_tag(self) -> None:
        assert self._match("<v محمد أحمد>مرحبا</v>") == "محمد أحمد"

    def test_cyrillic_in_voice_tag(self) -> None:
        assert self._match("<v Наина Ельцина>Здравствуйте</v>") == "Наина Ельцина"

    def test_korean_in_voice_tag(self) -> None:
        assert self._match("<v 박지현>안녕하세요</v>") == "박지현"

    def test_devanagari_in_voice_tag(self) -> None:
        assert self._match("<v पुष्पेन्द्र सिंह>नमस्ते</v>") == "पुष्पेन्द्र सिंह"

    # -- Edge cases ---------------------------------------------------------

    def test_name_with_parentheses(self) -> None:
        """Zoom/Teams display name with pronouns."""
        assert self._match("<v Sarah Jones (she/her)>Hi</v>") == "Sarah Jones (she/her)"

    def test_name_with_emoji(self) -> None:
        """Some people put emoji in their Zoom display name."""
        assert self._match("<v 🌟 Sarah>Hi</v>") == "🌟 Sarah"

    def test_name_with_pipe(self) -> None:
        """Corporate format: 'Name | Department'."""
        assert self._match("<v Sarah Jones | Engineering>Hello</v>") == "Sarah Jones | Engineering"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Generic label filter — should NOT be treated as real names
# ═══════════════════════════════════════════════════════════════════════════


class TestGenericLabelFilter:
    """The _GENERIC_LABEL_RE should match placeholders, not real names."""

    # -- Should be recognised as generic ------------------------------------

    def test_speaker_a(self) -> None:
        assert _GENERIC_LABEL_RE.match("Speaker A")

    def test_speaker_1(self) -> None:
        assert _GENERIC_LABEL_RE.match("Speaker 1")

    def test_speaker_underscore(self) -> None:
        assert _GENERIC_LABEL_RE.match("SPEAKER_00")

    def test_unknown(self) -> None:
        assert _GENERIC_LABEL_RE.match("Unknown")

    def test_narrator(self) -> None:
        assert _GENERIC_LABEL_RE.match("Narrator")

    # -- Should NOT be flagged as generic (real names) ----------------------

    def test_real_western_name(self) -> None:
        assert not _GENERIC_LABEL_RE.match("Sarah Jones")

    def test_mononym_suharto(self) -> None:
        assert not _GENERIC_LABEL_RE.match("Suharto")

    def test_mononym_madonna(self) -> None:
        assert not _GENERIC_LABEL_RE.match("Madonna")

    def test_chinese_romanised(self) -> None:
        assert not _GENERIC_LABEL_RE.match("Wei Zhang")

    def test_arabic_romanised(self) -> None:
        assert not _GENERIC_LABEL_RE.match("Taj al-Din")

    def test_chinese_characters(self) -> None:
        assert not _GENERIC_LABEL_RE.match("张伟")

    def test_arabic_script(self) -> None:
        assert not _GENERIC_LABEL_RE.match("محمد أحمد")

    def test_cyrillic(self) -> None:
        assert not _GENERIC_LABEL_RE.match("Борис Ельцин")

    def test_guid(self) -> None:
        """Azure AD GUID should NOT be generic (it's not a placeholder pattern)."""
        assert not _GENERIC_LABEL_RE.match(
            "68f0e9b4-d6de-4cad-9c2a-9b587e97837f@72f988bf-86f1-41af-91ab-2d7cd011db47"
        )

    # -- Tricky names that could false-positive -----------------------------

    def test_name_speaker(self) -> None:
        """The surname 'Speaker' exists (rare but real).
        'Speaker' alone does NOT match the generic regex (it requires
        'speaker' + a trailing alphanumeric like 'Speaker A' or 'speaker1').
        This means bare 'Speaker' would be treated as a real name — but in
        practice it only appears in Whisper output as 'SPEAKER_00' which
        does match."""
        assert not _GENERIC_LABEL_RE.match("Speaker")  # bare 'Speaker' escapes
        assert not _GENERIC_LABEL_RE.match("John Speaker")

    def test_name_unknown_surname(self) -> None:
        """Someone named 'Unknown' — edge case."""
        assert _GENERIC_LABEL_RE.match("Unknown")  # can't distinguish


# ═══════════════════════════════════════════════════════════════════════════
# 4. Short name suggestion — "first token" heuristic
#
# Assumes Western given-name-first ordering.  Breaks spectacularly for
# names where the family name comes first, names with particles, and
# mononyms.
# ═══════════════════════════════════════════════════════════════════════════


class TestSuggestShortNames:
    """suggest_short_names() takes first whitespace-delimited token."""

    # -- Western names (the happy path) -------------------------------------

    def test_western_two_part(self) -> None:
        people = _people_with_names({"p1": "Sarah Jones"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Sarah"

    def test_western_three_part(self) -> None:
        people = _people_with_names({"p1": "Sarah Jane Jones"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Sarah"

    def test_disambiguation(self) -> None:
        people = _people_with_names({"p1": "Sarah Jones", "p2": "Sarah Kim"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Sarah J."
        assert people.participants["p2"].editable.short_name == "Sarah K."

    # -- Mononyms -----------------------------------------------------------

    def test_mononym(self) -> None:
        """Single name — short name IS the full name."""
        people = _people_with_names({"p1": "Suharto"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Suharto"

    # -- East Asian names (family name first) -------------------------------
    #
    # In Chinese/Japanese/Korean convention, the family name comes first.
    # "张伟" = Zhang (family) Wei (given).  Our heuristic takes "Zhang" as
    # the short name — which is the FAMILY name, not the given name.
    # In Chinese culture, using someone's family name alone is not how you'd
    # address them informally.  But we accept this limitation.

    def test_chinese_romanised_family_first(self) -> None:
        """Zhang Wei → short name 'Zhang' (family name, not given)."""
        people = _people_with_names({"p1": "Zhang Wei"})
        suggest_short_names(people)
        # This is "wrong" culturally but structurally consistent
        assert people.participants["p1"].editable.short_name == "Zhang"

    def test_japanese_romanised(self) -> None:
        """Tanaka Yuki → short name 'Tanaka' (family name)."""
        people = _people_with_names({"p1": "Tanaka Yuki"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Tanaka"

    def test_korean_romanised(self) -> None:
        """Park Ji-hyun → 'Park' (family name)."""
        people = _people_with_names({"p1": "Park Ji-hyun"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Park"

    def test_chinese_western_order(self) -> None:
        """Wei Zhang (westernised) → 'Wei' (given name). Correct."""
        people = _people_with_names({"p1": "Wei Zhang"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Wei"

    # -- Name particles (the heuristic grabs the particle, not the name) ----

    def test_dutch_van_der(self) -> None:
        """'Pieter van der Meer' → short name 'Pieter'. OK."""
        people = _people_with_names({"p1": "Pieter van der Meer"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Pieter"

    def test_arabic_romanised(self) -> None:
        """'Taj al-Din' → 'Taj'. Acceptable."""
        people = _people_with_names({"p1": "Taj al-Din"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Taj"

    def test_spanish_de_la(self) -> None:
        """'Maria de la Cruz' → 'Maria'. OK."""
        people = _people_with_names({"p1": "Maria de la Cruz"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Maria"

    # -- Disambiguation with non-Western names ------------------------------

    def test_disambiguate_chinese_family_names(self) -> None:
        """Two Zhangs: 'Zhang Wei' and 'Zhang Fang'."""
        people = _people_with_names({"p1": "Zhang Wei", "p2": "Zhang Fang"})
        suggest_short_names(people)
        # Disambiguates with last-name initial — but "Wei" and "Fang" are
        # given names, not family names.  The result is correct structurally
        # but the semantics are inverted.
        assert people.participants["p1"].editable.short_name == "Zhang W."
        assert people.participants["p2"].editable.short_name == "Zhang F."

    # -- Russian patronymic names -------------------------------------------

    def test_russian_three_part(self) -> None:
        """Boris Nikolayevich Yeltsin → 'Boris'. OK for informal."""
        people = _people_with_names({"p1": "Boris Nikolayevich Yeltsin"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Boris"

    def test_russian_female_patronymic(self) -> None:
        """Naina Iosifovna Yeltsina → 'Naina'."""
        people = _people_with_names({"p1": "Naina Iosifovna Yeltsina"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Naina"

    # -- Icelandic patronymic -----------------------------------------------

    def test_icelandic_patronymic(self) -> None:
        """Ólafur Grímsson — 'Grímsson' is NOT a family name, it's
        a patronymic.  Both parts are 'given' in a sense.  Taking
        the first token is actually correct for Icelandic (people
        are addressed by given name)."""
        people = _people_with_names({"p1": "Ólafur Grímsson"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Ólafur"

    # -- Spanish compound surnames ------------------------------------------

    def test_spanish_two_surnames(self) -> None:
        """'María García López' — short name 'María'. Correct."""
        people = _people_with_names({"p1": "María García López"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "María"

    def test_spanish_disambiguation_wrong_initial(self) -> None:
        """Two Marías: 'María García' and 'María López'.
        Disambiguation gives 'María G.' and 'María L.' — uses the
        father's family name initial, which is the correct one for
        Spanish names."""
        people = _people_with_names({"p1": "María García", "p2": "María López"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "María G."
        assert people.participants["p2"].editable.short_name == "María L."

    # -- Titles and honorifics as part of the name --------------------------

    def test_title_as_first_token(self) -> None:
        """'Dr. Sarah Jones' → short name 'Dr.' — the title, not the name.
        This is the 'first token' heuristic failing."""
        people = _people_with_names({"p1": "Dr. Sarah Jones"})
        suggest_short_names(people)
        # Structural behaviour: first token is "Dr."
        assert people.participants["p1"].editable.short_name == "Dr."

    # -- Names with non-Latin scripts ---------------------------------------

    def test_chinese_characters_no_spaces(self) -> None:
        """Chinese names have no spaces: '张伟' is two characters, one token.
        Short name = full name (mononym-like)."""
        people = _people_with_names({"p1": "张伟"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "张伟"

    def test_japanese_kanji_no_spaces(self) -> None:
        """Japanese: '田中裕子' = Tanaka Yuko, but no space."""
        people = _people_with_names({"p1": "田中裕子"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "田中裕子"

    def test_arabic_script(self) -> None:
        """Arabic: 'محمد أحمد' — space-separated, first token is 'محمد'."""
        people = _people_with_names({"p1": "محمد أحمد"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "محمد"

    def test_cyrillic(self) -> None:
        """Russian in Cyrillic: 'Борис Ельцин' → 'Борис'."""
        people = _people_with_names({"p1": "Борис Ельцин"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Борис"

    # -- Very long names ----------------------------------------------------

    def test_picasso_full_name(self) -> None:
        """Picasso's full baptismal name."""
        full = (
            "Pablo Diego José Francisco de Paula Juan Nepomuceno "
            "María de los Remedios Cipriano de la Santísima Trinidad "
            "Ruiz y Picasso"
        )
        people = _people_with_names({"p1": full})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Pablo"

    # -- Very short names ---------------------------------------------------

    def test_single_character_name(self) -> None:
        """Some names are a single character — e.g. Chinese single-char name."""
        people = _people_with_names({"p1": "X"})
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "X"


# ═══════════════════════════════════════════════════════════════════════════
# 5. extract_names_from_labels — end-to-end from transcript to name
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractNamesFromLabels:
    """Names extracted from speaker_label metadata on transcript segments."""

    def test_real_name_extracted(self) -> None:
        t = _transcript_with_labels("p1", ["Luigi Iannone"] * 5)
        names = extract_names_from_labels([t])
        assert names == {"p1": "Luigi Iannone"}

    def test_generic_label_filtered(self) -> None:
        t = _transcript_with_labels("p1", ["Speaker 1"] * 5)
        names = extract_names_from_labels([t])
        assert "p1" not in names

    def test_numeric_label_filtered(self) -> None:
        t = _transcript_with_labels("p1", ["1234"] * 5)
        names = extract_names_from_labels([t])
        assert "p1" not in names

    def test_guid_not_filtered(self) -> None:
        """Azure AD GUIDs are not caught by generic filter — they become names.
        This is a known limitation."""
        guid = "68f0e9b4-d6de-4cad-9c2a-9b587e97837f@72f988bf-86f1-41af-91ab-2d7cd011db47"
        t = _transcript_with_labels("p1", [guid] * 5)
        names = extract_names_from_labels([t])
        assert names["p1"] == guid  # unfortunate but true

    def test_chinese_characters_extracted(self) -> None:
        t = _transcript_with_labels("p1", ["张伟"] * 5)
        names = extract_names_from_labels([t])
        assert names == {"p1": "张伟"}

    def test_arabic_script_extracted(self) -> None:
        t = _transcript_with_labels("p1", ["محمد أحمد"] * 5)
        names = extract_names_from_labels([t])
        assert names == {"p1": "محمد أحمد"}

    def test_most_frequent_label_wins(self) -> None:
        """When a speaker has multiple labels, the most frequent wins."""
        labels = ["Dr. Melissa Ko"] * 3 + ["Melissa Ko"] * 7
        t = _transcript_with_labels("p1", labels)
        names = extract_names_from_labels([t])
        assert names["p1"] == "Melissa Ko"

    def test_mixed_real_and_generic(self) -> None:
        """Most frequent is real, some generic mixed in."""
        labels = ["Nancy"] * 8 + ["Unknown"] * 2
        t = _transcript_with_labels("p1", labels)
        names = extract_names_from_labels([t])
        assert names["p1"] == "Nancy"
