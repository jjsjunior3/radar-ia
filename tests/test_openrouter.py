import json
from types import SimpleNamespace
import pytest
from radar_ia.llm_config import settings_from_env
from radar_ia.script import generate_script


def test_openrouter_settings_and_secret_repr():
    config = settings_from_env({"OPENROUTER_API_KEY": "secret-test"})
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert "secret-test" not in repr(config)
    assert config.model == "google/gemini-2.5-flash"


def test_unsupported_provider():
    with pytest.raises(ValueError): settings_from_env({"LLM_PROVIDER": "other"})


def test_openrouter_contract_and_usage():
    payload = {"intro_pt": "Olá.", "stories": [{"news_id": 1, "title_pt": "Teste", "summary_pt": "Resumo", "narration_pt": "Texto de teste."}], "glossary": [], "outro_pt": "Até logo."}
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="fake", model="test", usage=SimpleNamespace(model_dump=lambda: {"cost": .001}), choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(payload), refusal=None))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    brief = {"news": [{"id": 1, "summary_original": "Evidence"}]}
    script, metadata = generate_script(client, "test/model", brief, provider="openrouter")
    assert captured["extra_body"]["provider"]["require_parameters"] is True
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert metadata["usage"]["cost"] == .001
    assert script.stories[0].news_id == 1


@pytest.mark.parametrize("reason", ["length", "content_filter", "error"])
def test_openrouter_truncation_rejected(reason):
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason=reason, message=SimpleNamespace(refusal=None))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    with pytest.raises(ValueError, match="incompleta"):
        generate_script(client, "test/model", {"news": [{"id": 1, "summary_original": "Evidence"}]}, provider="openrouter")
