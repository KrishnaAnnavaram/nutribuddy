import pytest

from nutribuddy.render import to_html
from nutribuddy.safety import InputError, clean_input, in_scope, red_flags
from nutribuddy.sessions import SessionNotFound, SessionStore


@pytest.mark.parametrize("text", ["Can I eat 2 eggs a day?", "Is it OK to have coffee, tea and milk?",
                                  "What's a good snack for diabetes?"])
def test_normal_questions_with_digits_commas_apostrophes_are_accepted(text):
    assert clean_input(text, 600) == text


def test_clean_input_removes_control_characters_and_checks_length():
    assert clean_input("fish\x00 and\x1b rice\n", 100) == "fish and rice"
    with pytest.raises(InputError):
        clean_input("   ", 100)
    with pytest.raises(InputError):
        clean_input("a" * 101, 100)
    with pytest.raises(InputError):
        clean_input("1234 !!", 100)


@pytest.mark.parametrize("text, flag", [
    ("I have chest pain", "chest pain"),
    ("sudden shortness of breath", "breathing difficulty"),
    ("I fainted twice", "fainting"),
    ("my blood sugar is 450", "very high blood sugar"),
    ("blood glucose of 45 this morning", "very low blood sugar"),
])
def test_red_flags(text, flag):
    assert flag in red_flags(text)


def test_no_red_flag_for_normal_text():
    assert red_flags("Can I eat 2 eggs a day? My blood sugar is 120.") == []


def test_scope_check():
    assert in_scope("Can I eat rice?")
    assert not in_scope("Who won the football match?")


def test_html_output_is_escaped():
    out = to_html("<script>alert(1)</script>\n<strong>bold</strong> & more")
    assert "<script" not in out and "<strong>" not in out
    assert "&lt;script&gt;" in out and out.count("<br>") == 1


def test_session_store_is_server_side_and_bounded(tmp_path):
    store = SessionStore(tmp_path / "s.sqlite", max_turns_stored=4)
    sid = store.create("heart")
    assert len(sid) >= 20 and store.condition(sid) == "heart"
    for i in range(10):
        store.append(sid, "user", f"q{i}")
    assert store.history(sid, 100) == [("user", "q6"), ("user", "q7"), ("user", "q8"), ("user", "q9")]
    assert store.history(sid, 2) == [("user", "q8"), ("user", "q9")]
    assert store.history(sid, 0) == []
    with pytest.raises(SessionNotFound):
        store.append("missing", "user", "x")
    other = store.create()
    assert other != sid and store.history(other, 5) == []
