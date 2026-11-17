from bibaifilter.core.parsing import parse_decision, parse_score


def test_structured_and_bare_values():
    assert parse_score('{"score": 5}').score == 5
    assert parse_score('```json\n{"score": 6}\n```').status == "ok"
    assert parse_score("7").status == "ok"
    assert parse_score(" 3. ").score == 3
    assert parse_score("**4**").score == 4


def test_no_silent_default():
    for text in ("", None, "   "):
        p = parse_score(text)
        assert p.status == "empty" and p.score is None
    p = parse_score("I cannot rate this.")
    assert p.status == "unparsable" and p.score is None


def test_truncation_is_never_trusted():
    p = parse_score("5", finish_reason="length")
    assert p.status == "truncated" and p.score is None


def test_out_of_range_is_not_clamped():
    assert parse_score("9").status == "out_of_range"
    assert parse_score('{"score": 0}').status == "out_of_range"
    assert parse_score("4.5").status == "out_of_range"


def test_ambiguous_text_is_not_resolved_by_first_number():
    p = parse_score("On a scale from 1 to 7 I give it 5")
    assert p.status == "ambiguous" and p.score is None
    p = parse_score("Score: 5")
    assert p.status == "extracted" and p.score == 5


def test_phrases_are_not_mapped():
    assert parse_score("very relevant").status == "unparsable"


def test_refusal():
    assert parse_score(None, finish_reason="content_filter").status == "refused"


def test_decisions():
    assert parse_decision('{"decision": "include", "reason": "RCT in schools"}').decision == "include"
    assert parse_decision("Exclude.").decision == "exclude"
    assert parse_decision("I would include or exclude").status == "ambiguous"
    assert parse_decision("").status == "empty"
