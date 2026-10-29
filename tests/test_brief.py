from radar_ia.brief import build_brief


def story(i, source="A", summary="Resumo factual"):
    return dict(title=f"Notícia {i}", url=f"https://example.org/{i}", source_name=source, summary=summary, published="2026-10-28T12:00:00+00:00", reason="Tema compatível")


def test_empty_brief_stays_empty():
    result = build_brief(dict(theme="Mercado", main=[]))
    assert result["news"] == []
    assert result["status"] == "sem_conteudo"


def test_traceable_ids_and_source_alternation():
    result = build_brief(dict(theme="Ferramentas", main=[story(1), story(2), story(3, "B")]))
    assert [n["source"] for n in result["news"]] == ["A", "B", "A"]
    assert [n["id"] for n in result["news"]] == [1, 2, 3]


def test_missing_evidence_is_not_sent():
    result = build_brief(dict(theme="Ferramentas", main=[story(1, summary="")]))
    assert not result["news"]
    assert any("Resumo ausente" in w for w in result["warnings"])


def test_cap_is_maximum_not_required_count():
    result = build_brief(dict(theme="Ferramentas", main=[story(i) for i in range(10)]))
    assert len(result["news"]) == 7
    assert result["max_audio_seconds"] == 600


def test_tracking_urls_do_not_duplicate_brief():
    first = story(1)
    second = dict(first, url=first["url"] + "?utm_source=rss")
    assert len(build_brief(dict(theme="Teste", main=[first, second]))["news"]) == 1
