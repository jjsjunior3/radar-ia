import io
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from radar_ia.episode_notes import build_notes, read_notes
from radar_ia.hosted_api import handle
from test_hosted_api import event

EP = {"id": "2026-11-16-test", "title": "Edição", "format": "interview",
      "script_key": "radar/episodes/2026-11-16-test/roteiro.json",
      "sources_key": "radar/episodes/2026-11-16-test/fontes.json"}
SCRIPT = {"intro_pt": "Abertura.", "stories": [
    {"news_id": 1, "title_pt": "Pauta", "summary_pt": "Resumo.",
     "narration_pt": "Como funciona?\nCom exemplos."}],
    "outro_pt": "Encerramento.", "glossary": [
        {"term_en": "checkpoint", "explanation_pt": "Registro persistido.", "news_ids": [1]}]}
SOURCES = [{"id": 1, "source": "Fonte", "url": "https://example.org/news", "title": "Original"}]


def test_published_interview_notes_and_legacy_narration():
    details = build_notes(EP, SCRIPT, SOURCES)
    assert [t["speaker"] for t in details["topics"][0]["turns"]] == ["Apresentador", "Convidada"]
    assert details["glossary"][0]["term"] == "checkpoint"
    legacy = dict(EP)
    legacy.pop("format")
    assert build_notes(legacy, SCRIPT, SOURCES)["topics"][0]["turns"][0]["text"] == SCRIPT["stories"][0]["narration_pt"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:secret@example.org", "http://example.org"])
def test_unsafe_source_urls_are_not_linked(url):
    result = build_notes(EP, SCRIPT, [{**SOURCES[0], "url": url}])
    assert result["topics"][0]["source"]["url"] is None


def test_asset_keys_are_bound_to_episode():
    client = Mock()
    with pytest.raises(ValueError, match="pasta"):
        read_notes(client, "bucket", "radar", dict(EP, script_key="radar/other/secret.json"))
    client.get_object.assert_not_called()


def test_loads_only_published_assets():
    client = Mock()
    client.get_object.side_effect = [
        {"Body": io.BytesIO(json.dumps(value).encode())} for value in (SCRIPT, SOURCES)]
    result = read_notes(client, "bucket", "radar", EP)
    assert result["episode_id"] == EP["id"]
    assert len(client.get_object.call_args_list) == 2


def test_notes_route_requires_login_and_existing_catalog_entry():
    backend = SimpleNamespace(episodes=Mock(return_value=[EP]), notes=Mock(return_value={"episode_id": EP["id"]}))
    req = event("GET /api/episodes/{episode_id}")
    req["pathParameters"] = {"episode_id": EP["id"]}
    assert handle({}, backend)["statusCode"] == 401
    backend.episodes.assert_not_called()
    assert handle(req, backend)["statusCode"] == 200
    req["pathParameters"]["episode_id"] = "unpublished"
    assert handle(req, backend)["statusCode"] == 404
    backend.notes.assert_called_once()
