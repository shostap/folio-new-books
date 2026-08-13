"""Tests for src/subjects.py — subject-heading classification."""

from src.subjects import (
    classify_subject,
    parse_groups_config,
    ungrouped_label,
    lcc_class_from_call_number,
    lcc_class_from_subjects,
    normalize_subjects,
    _flatten_subjects,
)


_GROUPS = {
    "Engineering": ["computer", "programming", "physics"],
    "Humanities":  ["literature", "philosophy", "history"],
    "Sciences":    ["biology", "chemistry"],
}


# ── classify_subject ──────────────────────────────────────────────────


class TestClassifySubject:
    def test_simple_keyword_match(self):
        subjects = ["Computer programming"]
        assert classify_subject(subjects, _GROUPS) == "Engineering"

    def test_matches_subdivision_text(self):
        # FOLIO often returns subjects like "X -- Y -- Z"; punctuation collapsed
        subjects = ["History -- 20th century"]
        assert classify_subject(subjects, _GROUPS) == "Humanities"

    def test_first_matching_group_wins(self):
        # "computer history" — Engineering comes first in dict order
        subjects = ["Computer history"]
        assert classify_subject(subjects, _GROUPS) == "Engineering"

    def test_no_match_returns_none(self):
        subjects = ["Cooking, French"]
        assert classify_subject(subjects, _GROUPS) is None

    def test_empty_subjects_returns_none(self):
        assert classify_subject([], _GROUPS) is None

    def test_empty_groups_returns_none(self):
        assert classify_subject(["Computer programming"], {}) is None

    def test_case_insensitive(self):
        subjects = ["COMPUTER SCIENCE"]
        assert classify_subject(subjects, _GROUPS) == "Engineering"

    def test_dict_shaped_subjects(self):
        # mod-search returns subjects as [{"value": "..."}]
        subjects = [{"value": "Biology textbook"}]
        assert classify_subject(subjects, _GROUPS) == "Sciences"

    def test_mixed_string_and_dict_subjects(self):
        subjects = ["History", {"value": "Philosophy"}]
        assert classify_subject(subjects, _GROUPS) == "Humanities"


# ── parse_groups_config ───────────────────────────────────────────────


class TestParseGroupsConfig:
    def test_splits_keywords(self):
        raw = {"Engineering": "computer, programming, math"}
        result = parse_groups_config(raw)
        assert result == {"Engineering": ["computer", "programming", "math"]}

    def test_strips_whitespace(self):
        raw = {"Sciences": "  biology ,  chemistry  "}
        result = parse_groups_config(raw)
        assert result == {"Sciences": ["biology", "chemistry"]}

    def test_lowercases_keywords(self):
        raw = {"Test": "Foo, BAR"}
        result = parse_groups_config(raw)
        assert result == {"Test": ["foo", "bar"]}

    def test_drops_empty_keywords(self):
        raw = {"Test": "foo, , bar,"}
        result = parse_groups_config(raw)
        assert result == {"Test": ["foo", "bar"]}

    def test_drops_groups_with_no_keywords(self):
        raw = {"Empty": "", "Has-Keywords": "foo"}
        result = parse_groups_config(raw)
        assert "Empty" not in result
        assert result["Has-Keywords"] == ["foo"]


# ── Helpers ───────────────────────────────────────────────────────────


def test_ungrouped_label():
    assert ungrouped_label() == "Other"


def test_flatten_subjects_strips_punctuation():
    blob = _flatten_subjects(["Computer programming -- Study and teaching"])
    assert "computer programming" in blob
    assert "--" not in blob  # collapsed to whitespace


# ── lcc_class_from_call_number ───────────────────────────────────────


class TestLccClass:
    def test_two_letter_subclass_wins_over_one_letter(self):
        # PN51 should resolve to PN (Literature/Drama/Journalism), not just P
        assert lcc_class_from_call_number("PN51 .T7 2022") == \
            "Literature (General); Drama; Journalism"

    def test_qa_is_mathematics(self):
        # Was lumped under "Science" before — now finer
        assert lcc_class_from_call_number("QA76.5 .S5 2024") == "Mathematics; Computer Science"

    def test_ps_is_american_literature(self):
        assert lcc_class_from_call_number("PS3558.E63 D8") == "American Literature"

    def test_p_alone_falls_back_to_language_and_literature(self):
        # "P51" — only one alpha char before digits, so falls back to P
        assert lcc_class_from_call_number("P51 .X1") == "Language and Literature"

    def test_unknown_two_letter_falls_back_to_one_letter(self):
        # QX is not in the map, but Q is
        assert lcc_class_from_call_number("QX1 .X") == "Science"

    def test_lowercase_input_works(self):
        assert lcc_class_from_call_number("ta330 .B57") == "Civil Engineering"

    def test_strips_leading_whitespace(self):
        assert lcc_class_from_call_number("  HF5429 .S5") == "Commerce"

    def test_empty_string_returns_none(self):
        assert lcc_class_from_call_number("") is None

    def test_dewey_decimal_returns_none(self):
        assert lcc_class_from_call_number("641.5 SMI") is None

    def test_unknown_letter_returns_none(self):
        # X and Y are unassigned in LCC
        assert lcc_class_from_call_number("X999 .X") is None

    def test_online_placeholder_rejected(self):
        # "Online" is the ebook placeholder, not an LCC call number
        assert lcc_class_from_call_number("Online") is None

    def test_internet_placeholder_rejected(self):
        assert lcc_class_from_call_number("Internet") is None

    def test_letters_without_digits_rejected(self):
        # Even valid letters need a following digit to count as LCC
        assert lcc_class_from_call_number("ELECTRONIC BOOK") is None

    def test_on_order_placeholder_rejected(self):
        assert lcc_class_from_call_number("[On order]") is None


# ── lcc_class_from_subjects ──────────────────────────────────────────


class TestLccClassFromSubjects:
    def test_user_ebook_classifies_via_subjects(self):
        """The exact example reported by the user."""
        subjects = [
            "Women and socialism--Communist countries",
            "Women--Employment--Communist countries",
            "Women's rights--Communist countries",
            "Motherhood--Communist countries",
            "SOCIAL SCIENCE--Women's Studies",
            "POLITICAL SCIENCE--Political Ideologies--Communism & Socialism",
            "Electronic books",
        ]
        # "women" → HQ → "Family; Marriage; Sex" (which covers Women's Studies)
        assert lcc_class_from_subjects(subjects) == "Family; Marriage; Sex"

    def test_bisac_main_heading_match(self):
        # BISAC categories use " / " as a separator; the leading part wins
        subjects = ["POLITICAL SCIENCE / Political Ideologies / Communism & Socialism"]
        assert lcc_class_from_subjects(subjects) == "Political Science"

    def test_lcsh_main_heading_match(self):
        subjects = ["Computer programming -- Study and teaching"]
        assert lcc_class_from_subjects(subjects) == "Mathematics; Computer Science"

    def test_first_subject_wins(self):
        subjects = [
            "Astronomy -- Popular works",  # → QB → Astronomy
            "Chemistry",                    # → QD → Chemistry
        ]
        assert lcc_class_from_subjects(subjects) == "Astronomy"

    def test_format_markers_skipped(self):
        # "Electronic books" alone is just a format tag; should return None
        # not "Library Science" (Z, from "books")
        subjects = ["Electronic books"]
        assert lcc_class_from_subjects(subjects) is None

    def test_format_marker_in_list_is_passed_over(self):
        subjects = ["Electronic books", "Biology -- Textbooks"]
        # Should skip "Electronic books" and match "Biology" instead
        assert lcc_class_from_subjects(subjects) == "Natural History; Biology"

    def test_empty_subjects_returns_none(self):
        assert lcc_class_from_subjects([]) is None
        assert lcc_class_from_subjects(None) is None

    def test_dict_shaped_subject(self):
        # mod-search sometimes returns [{"value": "..."}]
        subjects = [{"value": "Astronomy"}]
        assert lcc_class_from_subjects(subjects) == "Astronomy"

    def test_no_matching_keyword_returns_none(self):
        # Subjects with no recognizable LCC-mappable keywords
        subjects = ["Foobar", "Nonsense topic", "Whatchamacallit"]
        assert lcc_class_from_subjects(subjects) is None


# ── normalize_subjects ───────────────────────────────────────────────


class TestNormalizeSubjects:
    def test_string_array(self):
        assert normalize_subjects(["A", "B"]) == ["A", "B"]

    def test_dict_array(self):
        assert normalize_subjects([{"value": "A"}, {"value": "B"}]) == ["A", "B"]

    def test_mixed_shapes(self):
        assert normalize_subjects(["A", {"value": "B"}]) == ["A", "B"]

    def test_empty_input(self):
        assert normalize_subjects([]) == []
        assert normalize_subjects(None) == []

    def test_drops_empty_strings(self):
        assert normalize_subjects(["", "A", {"value": ""}]) == ["A"]
