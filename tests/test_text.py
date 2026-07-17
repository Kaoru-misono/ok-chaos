from src.chaos.text import normalize_text, text_matches


def test_normalize_text_handles_full_width_and_whitespace() -> None:
    assert normalize_text(" 前 往 卡厄思核心　１ ") == "前往卡厄思核心1"


def test_text_matches_supports_exact_and_contains() -> None:
    assert text_matches("点击确认继续", "确认")
    assert not text_matches("点击确认继续", "确认", exact=True)
    assert text_matches(" 确 认 ", "确认", exact=True)
