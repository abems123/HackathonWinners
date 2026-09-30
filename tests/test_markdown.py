from core.templatetags.bron_tags import render_markdown


def test_uploaded_markup_cannot_execute_script():
    result = str(
        render_markdown(
            '<script>alert(1)</script><img src=x onerror=alert(2)><a href="javascript:alert(3)" onclick="x()">Click</a>'
        )
    )
    assert "<script" not in result
    assert "<img" not in result
    assert "javascript:" not in result
    assert "onclick" not in result


def test_source_tables_and_emphasis_are_readable():
    result = str(
        render_markdown(
            "**5th working day**\n\n| Month | Due |\n| --- | --- |\n| September | 7 October |"
        )
    )
    assert "<strong>5th working day</strong>" in result
    assert "<table>" in result and "<td>7 October</td>" in result
