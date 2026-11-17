import base64
import importlib.util
import io
import wave
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("gemini_pilot", Path(__file__).resolve().parents[1] / "examples/comparar_gemini_tts.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_gemini_saved_response_is_reused_without_second_request(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(bytes(48000))
    response = Mock(status_code=200)
    response.json.return_value = {"status": "completed", "steps": [{"type": "model_output", "content": [{
        "type": "audio", "mime_type": "audio/wav",
        "data": base64.b64encode(buffer.getvalue()).decode()}]}]}
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    monkeypatch.setattr(pilot.httpx, "Client", Mock(return_value=client))
    payload = {"model": "test", "input": []}
    path, meta = pilot.render(payload, tmp_path, "private-key")
    assert meta["duration_seconds"] == 1
    pilot.render(payload, tmp_path, "private-key")
    client.post.assert_called_once()
    assert "private-key" not in (tmp_path / "request.json").read_text()
    with pytest.raises(ValueError, match="alterado"):
        pilot.render({"model": "other"}, tmp_path, "private-key")


def test_gemini_uncertain_call_is_blocked(tmp_path, monkeypatch):
    payload = {"model": "test"}
    pilot.write_json(tmp_path / "request.json", {
        "digest": pilot.digest(__import__("json").dumps(payload, sort_keys=True, ensure_ascii=False).encode())})
    create = Mock()
    monkeypatch.setattr(pilot.httpx, "Client", create)
    with pytest.raises(ValueError, match="sem resposta"):
        pilot.render(payload, tmp_path, "private-key")
    create.assert_not_called()
