import base64
import io
import json
import wave
from unittest.mock import Mock

import httpx
import pytest
from radar_ia.generative_tts import synthesize

TURNS = [{"speaker": "leo", "text": "Como testar?"}, {"speaker": "carolina", "text": "Com exemplos."}]
CONFIG = {"gemini_api_key": "secret-google", "openrouter_api_key": "secret-router", "fallback_budget_usd": "0.30"}


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(bytes(48000))
    return output.getvalue()


def test_direct_success_is_cached_and_keeps_keys_private(tmp_path, monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"status": "completed", "steps": [{"type": "model_output",
            "content": [{"type": "audio", "mime_type": "audio/wav", "data": base64.b64encode(wav_bytes()).decode()}]}]})
    transport(monkeypatch, handle)
    audio, meta = synthesize(TURNS, tmp_path, CONFIG)
    assert meta["provider"] == "gemini"
    synthesize(TURNS, tmp_path, CONFIG)
    assert len(calls) == 1
    with wave.open(io.BytesIO(audio)) as wav:
        assert wav.getframerate() == 16000
    assert "secret-" not in "".join(p.read_text() for p in tmp_path.glob("*.json"))
    with pytest.raises(ValueError, match="Configuração"):
        synthesize(TURNS[::-1], tmp_path, CONFIG)


def test_quota_fallback_is_bounded_and_cached(tmp_path, monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        if "googleapis" in str(request.url):
            return httpx.Response(429)
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "google/gemini-3.8-flash-tts",
                "pricing": {"prompt": "0.0000005", "completion": "0.000009"}}]})
        payload = json.loads(request.content)
        assert payload["input"][1]["voice"] == "Kore"
        return httpx.Response(200, content=bytes(48000), headers={"content-type": "audio/pcm", "x-generation-id": "test"})
    transport(monkeypatch, handle)
    _, meta = synthesize(TURNS, tmp_path, CONFIG)
    assert meta["provider"] == "openrouter"
    assert meta["generation_id"] == "test"
    synthesize(TURNS, tmp_path, CONFIG)
    assert len(calls) == 3


@pytest.mark.parametrize("failure", ["timeout", "500", "401", "malformed"])
def test_unknown_or_nonquota_outcome_never_falls_back(tmp_path, monkeypatch, failure):
    calls = []
    def handle(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private details", request=request)
        if failure == "malformed":
            return httpx.Response(200, json={"status": "completed"})
        return httpx.Response(int(failure))
    transport(monkeypatch, handle)
    for _ in range(2):
        with pytest.raises((ValueError, httpx.ReadTimeout)):
            synthesize(TURNS, tmp_path, CONFIG)
    assert len(calls) == 1


def test_price_above_budget_blocks_paid_post(tmp_path, monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        if request.method == "POST":
            assert "googleapis" in str(request.url)
            return httpx.Response(429)
        return httpx.Response(200, json={"data": [{"id": "google/gemini-3.8-flash-tts",
            "pricing": {"prompt": "1", "completion": "1"}}]})
    transport(monkeypatch, handle)
    with pytest.raises(ValueError, match="orçamento"):
        synthesize(TURNS, tmp_path, CONFIG)
    assert len(calls) == 2


def test_bulletin_uses_single_speaker_schema():
    from radar_ia.generative_tts import gemini_payload, MODEL
    payload = gemini_payload([TURNS[0]], MODEL)
    assert payload["generation_config"]["speech_config"] == [{"voice": "Puck"}]
    assert "speaker" not in payload["input"][0]["content"][0]["annotations"][0]
