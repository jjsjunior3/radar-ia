"""Testes locais da janela de publicação do exemplo, sem internet."""
import runpy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

check_date = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "ler_rss.py"))["check_date"]
NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("age,expected", [
    (timedelta(0), "dentro da janela"),
    (timedelta(hours=24), "dentro da janela"),
    (timedelta(hours=48), "dentro da janela"),
    (timedelta(hours=48, seconds=1), "mais antiga que a janela"),
    (timedelta(seconds=-1), "data futura"),
])
def test_date_boundaries(age, expected):
    entry = {"published_parsed": (NOW - age).utctimetuple()}
    assert check_date(entry, NOW)[0] == expected


def test_updated_does_not_replace_publication():
    entry = {"updated_parsed": NOW.utctimetuple()}
    assert check_date(entry, NOW) == ("sem data de publicação válida", None)


def test_invalid_date():
    assert check_date({"published_parsed": "inválida"}, NOW)[0] == "sem data de publicação válida"

module = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "ler_rss.py"))
check_candidate = module["check_candidate"]


def test_tracking_duplicate_skips_request():
    def forbidden(url):
        raise AssertionError("Não deveria acessar a rede")
    news = {"title": "Outro título", "link": "https://aws.amazon.com/post?utm_source=rss"}
    accepted = [{"title": "Título anterior", "url": "https://aws.amazon.com/post"}]
    assert "duplicada" in check_candidate(news, accepted, forbidden)[0]


def test_final_redirect_duplicate():
    news = {"title": "Novidade de infraestrutura", "link": "https://aws.amazon.com/new"}
    accepted = [{"title": "Artigo anterior", "url": "https://aws.amazon.com/final"}]
    fetch = lambda url: (b"<html></html>", "https://aws.amazon.com/final")
    assert check_candidate(news, accepted, fetch)[0] == "duplicada após redirecionamento"


def test_http_url_rejected():
    news = {"title": "Notícia", "link": "http://aws.amazon.com/post"}
    assert "rejeitada" in check_candidate(news, [], lambda url: None)[0]


def test_valid_candidate():
    news = {"title": "Novidade", "link": "https://aws.amazon.com/post"}
    result, item = check_candidate(news, [], lambda url: (b"html", url))
    assert result == "candidata válida"
    assert item["url"] == news["link"]


def test_fetcher_blocks_redirect_outside_allowlist():
    import httpx
    from radar_ia.news import Fetcher
    fetcher = Fetcher(["aws.amazon.com"])
    fetcher.client.close()
    def handler(request):
        assert request.url.host == "aws.amazon.com"
        return httpx.Response(302, headers={"location": "https://example.org/private"})
    fetcher.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError, match="allowlist"):
            fetcher.get("https://aws.amazon.com/post")
    finally:
        fetcher.close()


def test_fetcher_http_failure_reported():
    import httpx
    def fetch(url):
        request = httpx.Request("GET", url)
        httpx.Response(404, request=request).raise_for_status()
    news = {"title": "Novidade", "link": "https://aws.amazon.com/missing"}
    assert check_candidate(news, [], fetch)[0] == "página retornou HTTP 404"


def test_fetcher_preserves_trailing_slash_redirect():
    import httpx
    from radar_ia.news import Fetcher
    fetcher = Fetcher(["aws.amazon.com"])
    fetcher.client.close()
    visited = []
    def handler(request):
        visited.append(request.url.path)
        if request.url.path == "/post":
            return httpx.Response(301, headers={"location": "/post/"})
        assert request.url.path == "/post/"
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>ok</html>")
    fetcher.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        body, final = fetcher.get("https://aws.amazon.com/post")
        assert body == b"<html>ok</html>"
        assert visited == ["/post", "/post/"]
        assert final == "https://aws.amazon.com/post"
    finally:
        fetcher.close()
