from agent.chat_sanitize import ThinkingStreamFilter, strip_thinking_content


def test_strip_complete_redacted_thinking_block():
    raw = "<think>内部分析</think>\n\n你好，我是助手。"
    assert strip_thinking_content(raw) == "你好，我是助手。"


def test_strip_think_tag_variants():
    raw = (
        "\u003cthink\u003e\u63a8\u7406\u4e2d\u003c/think\u003e\n"
        "\u003cthinking\u003e\u5185\u90e8\u003c/thinking\u003e\u6b63\u6587"
    )
    assert strip_thinking_content(raw) == "正文"


def test_strip_unclosed_thinking_tag():
    raw = "<think>还在想…"
    assert strip_thinking_content(raw) == ""


def test_stream_filter_emits_only_visible_delta():
    filt = ThinkingStreamFilter()
    assert filt.feed("<redacted_th") == ""
    assert filt.feed("inking>secret") == ""
    assert filt.feed("</think>") == ""
    assert filt.feed("可见") == "可见"
    assert filt.visible_text() == "可见"
