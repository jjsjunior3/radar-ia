from radar_ia.review import render_report


def test_review_displays_single_source_warning_and_no_publication():
    result = dict(theme="Ferramentas", main=[dict(title="SDK novo", url="https://example.org/post", source_name="Fonte A", reason="sdk")], waiting=[], review=[], excluded=[], recap=[])
    text = render_report(result, "2026-10-28")
    assert "mesma fonte" in text
    assert "nenhum episódio foi publicado" in text
    assert "SDK novo" in text


def test_review_empty_day_does_not_invent_content():
    result = dict(theme="Ferramentas", main=[], waiting=[], review=[], excluded=[], recap=[])
    assert "Nenhuma candidata" in render_report(result, "2026-10-28")
