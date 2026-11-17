"""Generate a local interview using Gemini, with a quota-only OpenRouter fallback."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from radar_ia.dialogue import validate_pilot
from radar_ia.generative_tts import synthesize

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument(
        "--script", type=Path, default=ROOT / "examples/piloto_recuperacao.json"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "local-output/pilotos/gemini-fallback-v1",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    pilot = validate_pilot(json.loads(args.script.read_text(encoding="utf-8-sig")))
    config = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "fallback_budget_usd": os.getenv("TTS_FALLBACK_BUDGET_USD", "0.30"),
    }
    print(
        "Gemini:",
        bool(config["gemini_api_key"]),
        "| OpenRouter:",
        bool(config["openrouter_api_key"]),
    )
    print("Limite prévio por estimativa (USD):", config["fallback_budget_usd"])
    if not args.generate:
        print("Preparação local. --generate solicita áudio.")
        return
    audio, receipt = synthesize(
        [turn.model_dump() for turn in pilot.turns],
        args.output_dir,
        config,
        max_seconds=120,
    )
    target = args.output_dir / "piloto.wav"
    target.write_bytes(audio)
    print("Áudio:", target.resolve())
    print(
        "Provedor:",
        receipt["provider"],
        "| Duração:",
        round(receipt["duration_seconds"], 1),
    )


if __name__ == "__main__":
    main()
