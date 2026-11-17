"""Prepare or render a local Gemini TTS interview with a preserved request."""
import argparse
import base64
import io
import json
import os
import wave
from pathlib import Path

import httpx
from dotenv import load_dotenv

from radar_ia.dialogue import digest, read_json, validate_pilot, write_json

ROOT = Path(__file__).resolve().parents[1]


def request_payload(pilot, model):
    styles = {
        "leo": "Português brasileiro. Apresentador curioso, tom acolhedor, ritmo moderado. Faça perguntas com interesse e pausas naturais. Pronuncie termos ingleses em inglês.",
        "carolina": "Português brasileiro. Convidada didática, tom tranquilo e espontâneo, ritmo moderado. Responda como numa conversa, com pausas entre ideias. Pronuncie termos ingleses em inglês.",
    }
    return {
        "model": model,
        "input": [{"type": "user_input", "content": [
            {"type": "text", "text": turn.text, "annotations": [{
                "type": "speech_metadata", "speaker": turn.speaker,
                "style": styles[turn.speaker],
            }]} for turn in pilot.turns
        ]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": {"speakers": [
            {"speaker": "leo", "voice": "Puck"},
            {"speaker": "carolina", "voice": "Kore"},
        ]}},
    }


def render(payload, folder, key):
    folder.mkdir(parents=True, exist_ok=True)
    binding = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())
    marker, response_file = folder / "request.json", folder / "response.json"
    if marker.exists():
        if read_json(marker)["digest"] != binding:
            raise ValueError("Roteiro ou modelo alterado. Use outra pasta de revisão.")
        if not response_file.exists():
            raise ValueError("Chamada iniciada sem resposta salva. Verifique antes de repetir a cobrança.")
    else:
        with marker.open("x", encoding="utf-8") as stream:
            json.dump({"digest": binding, "model": payload["model"]}, stream)
        with httpx.Client(timeout=120, follow_redirects=False) as client:
            response = client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": key}, json=payload,
            )
        # Preserve the response before interpreting it. Never save request headers.
        write_json(response_file, {"status": response.status_code, "body": response.json()})
    saved = read_json(response_file)
    if saved["status"] != 200:
        raise ValueError(f"Gemini retornou HTTP {saved['status']}. Inspecione a resposta local preservada.")
    body = saved["body"]
    if body.get("status") != "completed":
        raise ValueError("Gemini não confirmou conclusão. Verifique a resposta preservada.")
    parts = [
        part
        for step in body.get("steps", [])
        if step.get("type") == "model_output"
        for part in step.get("content", [])
        if part.get("type") == "audio"
    ]
    if len(parts) != 1 or parts[0].get("mime_type") != "audio/wav":
        raise ValueError("Resposta deve conter um único áudio WAV. Verifique a resposta salva.")
    audio = base64.b64decode(parts[0]["data"], validate=True)
    with wave.open(io.BytesIO(audio), "rb") as wav:
        seconds = wav.getnframes() / wav.getframerate()
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or not 0 < seconds <= 120:
            raise ValueError("Formato ou duração do piloto fora do esperado.")
    metadata = {"provider": "gemini", "model": payload["model"], "duration_seconds": seconds,
        "audio_sha256": digest(audio), "script_digest": binding, "usage": body.get("usage"),
        "publication": "local_only"}
    write_json(folder / "metadata.json", metadata)
    target = folder / "piloto.wav"
    temporary = folder / "piloto.wav.tmp"
    temporary.write_bytes(audio)
    temporary.replace(target)
    return target, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--script", type=Path, default=ROOT / "examples/piloto_recuperacao.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "local-output/pilotos/gemini-recuperacao-v1")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    pilot = validate_pilot(json.loads(args.script.read_text(encoding="utf-8-sig")))
    if {turn.speaker for turn in pilot.turns} != {"leo", "carolina"}:
        raise ValueError("Esta comparação exige Leo e Carolina.")
    model = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    payload = request_payload(pilot, model)
    key = os.getenv("GEMINI_API_KEY", "")
    print(f"Modelo: {model} | Falas: {len(pilot.turns)} | Credencial: {'presente' if key else 'ausente'}")
    if not args.generate:
        print("Preparação local concluída. --generate solicita áudio ao Gemini.")
        return
    if not key:
        raise SystemExit("Configure GEMINI_API_KEY no .env antes de gerar.")
    target, metadata = render(payload, args.output_dir, key)
    print(f"Áudio: {target.resolve()} | Duração: {metadata['duration_seconds']:.1f} s")


if __name__ == "__main__":
    main()
