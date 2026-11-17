"""Generative speech with a single recorded quota fallback."""

import audioop
import base64
import io
import json
import wave
from decimal import Decimal
from pathlib import Path

import httpx

from .audio import wav_from_pcm
from .dialogue import digest, read_json, write_json

MODEL = "gemini-3.8-flash-tts"
VOICES = {"leo": "Puck", "carolina": "Kore"}


def gemini_payload(turns, model):
    styles = {
        "leo": "Português brasileiro. Apresentador curioso, tom acolhedor, ritmo moderado. Faça perguntas com interesse e pausas naturais. Pronuncie termos ingleses em inglês.",
        "carolina": "Português brasileiro. Convidada didática, tom tranquilo e espontâneo, ritmo moderado. Responda como numa conversa, com pausas entre ideias. Pronuncie termos ingleses em inglês.",
    }
    payload = {
        "model": model,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": turn["text"],
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "speaker": turn["speaker"],
                                "style": styles[turn["speaker"]],
                            }
                        ],
                    }
                    for turn in turns
                ],
            }
        ],
        "response_format": {"type": "audio"},
        "generation_config": {
            "speech_config": {
                "speakers": [
                    {"speaker": "leo", "voice": "Puck"},
                    {"speaker": "carolina", "voice": "Kore"},
                ]
            }
        },
    }

    speakers = {turn["speaker"] for turn in turns}
    if len(speakers) == 1:
        speaker = next(iter(speakers))
        payload["generation_config"]["speech_config"] = [{"voice": VOICES[speaker]}]
        for part in payload["input"][0]["content"]:
            part["annotations"][0].pop("speaker")
    return payload


def normalized_wav(data, raw_pcm, max_seconds):
    if raw_pcm:
        pcm, rate = data, 24000
    else:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise ValueError("Áudio deve ser mono de 16 bits")
            rate = wav.getframerate()
            pcm = wav.readframes(wav.getnframes())
    if rate not in (16000, 24000) or not pcm or len(pcm) % 2:
        raise ValueError("Formato inesperado")
    if len(pcm) / (rate * 2) > max_seconds:
        raise ValueError("Áudio acima do limite de duração")
    if rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    return wav_from_pcm(pcm, max_seconds=max_seconds)


def synthesize(turns, folder, config, *, persist=None, max_seconds=600):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if not turns or sum(len(t["text"].split()) for t in turns) > 1000:
        raise ValueError("Roteiro vazio ou acima de 1000 palavras")
    if any(t["speaker"] not in VOICES or not t["text"].strip() for t in turns):
        raise ValueError("Locutor ou texto inválido")
    budget = Decimal(str(config.get("fallback_budget_usd", "0.30")))
    if not budget.is_finite() or budget < 0:
        raise ValueError("Orçamento inválido")
    binding = digest(
        json.dumps(
            {
                "turns": turns,
                "model": MODEL,
                "voices": VOICES,
                "max_seconds": max_seconds,
                "budget": str(budget),
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    )
    manifest = folder / "manifest.json"
    if manifest.exists():
        if read_json(manifest)["digest"] != binding:
            raise ValueError("Configuração mudou após início da voz")
    else:
        write_json(manifest, {"digest": binding})

    def save(path, value):
        write_json(path, value)
        if persist:
            persist()

    for provider in ("gemini", "openrouter"):
        marker = folder / (provider + ".json")
        audio_path = folder / (provider + ".wav")
        if marker.exists():
            saved = read_json(marker)
            if saved.get("status") == "complete":
                audio = audio_path.read_bytes()
                if digest(audio) != saved["audio_sha256"]:
                    raise ValueError("Áudio salvo sem integridade")
                return audio, saved
            if provider == "gemini" and saved.get("status") == "quota_rejected":
                continue
            raise ValueError("Tentativa incerta ou rejeitada; inspecione o registro")
        estimated = None
        if provider == "gemini":
            if not config.get("gemini_api_key"):
                raise ValueError("Configure a chave Gemini")
            payload = gemini_payload(turns, MODEL)
            endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"
            headers = {"x-goog-api-key": config["gemini_api_key"]}
        else:
            if not config.get("openrouter_api_key"):
                raise ValueError("Cota gratuita esgotada; configure OpenRouter")
            payload = {
                "model": "google/" + MODEL,
                "response_format": "pcm",
                "input": [
                    {
                        "text": t["text"],
                        "voice": VOICES[t["speaker"]],
                        "instructions": "Português brasileiro, entrevista natural, ritmo moderado, pausas entre ideias. Pronuncie termos ingleses em inglês.",
                    }
                    for t in turns
                ],
            }
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                response = client.get(
                    "https://openrouter.ai/api/v1/models?output_modalities=speech"
                )
            response.raise_for_status()
            pricing = next(
                m["pricing"]
                for m in response.json()["data"]
                if m["id"] == payload["model"]
            )
            rates = [Decimal(pricing["prompt"]), Decimal(pricing["completion"])]
            if any(not r.is_finite() or r < 0 for r in rates):
                raise ValueError("Tarifa inválida")
            estimated = (
                len(json.dumps(payload, ensure_ascii=False).encode()) * rates[0]
                + Decimal(max_seconds * 25) * rates[1]
            )
            if estimated > budget:
                raise ValueError("Estimativa acima do orçamento de voz")
            endpoint = "https://openrouter.ai/api/v1/audio/speech"
            headers = {"Authorization": "Bearer " + config["openrouter_api_key"]}
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "status": "request_started",
                    "provider": provider,
                    "estimated_max_usd": str(estimated)
                    if estimated is not None
                    else None,
                },
                stream,
            )
        if persist:
            persist()
        with httpx.Client(timeout=180, follow_redirects=False) as client:
            response = client.post(endpoint, headers=headers, json=payload)
        if response.status_code != 200:
            status = (
                "quota_rejected"
                if provider == "gemini" and response.status_code == 429
                else "rejected"
            )
            save(
                marker,
                {
                    "status": status,
                    "provider": provider,
                    "http_status": response.status_code,
                },
            )
            if status == "quota_rejected":
                continue
            raise ValueError("Provedor rejeitou a voz; consulte o código HTTP salvo")
        usage, generation_id = None, None
        if provider == "gemini":
            body = response.json()
            if body.get("status") != "completed":
                raise ValueError("Gemini não confirmou conclusão")
            parts = [
                p
                for step in body.get("steps", [])
                if step.get("type") == "model_output"
                for p in step.get("content", [])
                if p.get("type") == "audio"
            ]
            if len(parts) != 1 or parts[0].get("mime_type") != "audio/wav":
                raise ValueError("Resposta não contém WAV único")
            data = base64.b64decode(parts[0]["data"], validate=True)
            usage, generation_id = body.get("usage"), body.get("id")
        else:
            if (
                response.headers.get("content-type", "").split(";")[0].strip()
                != "audio/pcm"
            ):
                raise ValueError("OpenRouter não devolveu PCM")
            data = response.content
            generation_id = response.headers.get("x-generation-id")
        audio, duration = normalized_wav(data, provider == "openrouter", max_seconds)
        temporary = audio_path.with_suffix(".wav.tmp")
        temporary.write_bytes(audio)
        temporary.replace(audio_path)
        saved = {
            "status": "complete",
            "provider": provider,
            "model": MODEL,
            "voices": VOICES,
            "duration_seconds": duration,
            "audio_sha256": digest(audio),
            "usage": usage,
            "generation_id": generation_id,
            "estimated_max_usd": str(estimated) if estimated is not None else None,
        }
        save(marker, saved)
        return audio, saved
    raise ValueError("Voz indisponível")
