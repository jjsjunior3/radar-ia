import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from openai import OpenAI

from .news import Fetcher, collect, curate
from .services import Store, generate, synthesize


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Configure {name}")
    return value


def csv(name):
    return [v.strip() for v in required(name).split(",") if v.strip()]


def run(preview=False):
    load_dotenv()
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    hours, retention = int(os.getenv("LOOKBACK_HOURS", "72")), int(os.getenv("HISTORY_DAYS", "30"))
    if not 1 <= hours <= 168 or not 7 <= retention <= 365:
        raise ValueError("LOOKBACK_HOURS: 1..168; HISTORY_DAYS: 7..365")
    output = Path(os.getenv("OUTPUT_DIR", "local-output")) / day
    output.mkdir(parents=True, exist_ok=True)
    store = None
    if not preview:
        session = boto3.Session(region_name=required("AWS_REGION"))
        cfg = Config(retries={"mode": "standard", "max_attempts": 5}, connect_timeout=10, read_timeout=60)
        store = Store(session.client("s3", config=cfg), required("S3_BUCKET"), os.getenv("S3_PREFIX", "radar-ia"))
        manifest = store.read(f"episodes/{day}/manifest.json")
        if manifest:
            # Recupera histórico se a execução anterior falhou depois do commit do episódio.
            history = store.read("history.json", [])
            existing = {n["url"] for n in history}
            history.extend(n for n in manifest["news"] if n["url"] not in existing)
            store.json("history.json", history)
            print(f"Edição {day} já concluída; histórico reconciliado.")
            return
        history = store.read("history.json", [])
    else:
        history = []
    cutoff = now - timedelta(days=retention)
    history = [n for n in history if datetime.fromisoformat(n["published"]) >= cutoff]
    fetcher = Fetcher(csv("ALLOWED_DOMAINS"))
    try:
        candidates, errors = collect(csv("RSS_URLS"), fetcher.get, now, hours, csv("KEYWORDS"))
        for error in errors:
            print(error)
        selected = curate(candidates, history, fetcher.get)
    finally:
        fetcher.close()
    news = [n.data() for n in selected]
    (output / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    if preview:
        print(f"Prévia: cinco notícias salvas em {output}; histórico remoto não consultado.")
        return
    model = required("OPENAI_MODEL")
    with OpenAI(api_key=required("OPENAI_API_KEY"), timeout=90, max_retries=2) as client:
        script = generate(client, model, selected)
    (output / "script.txt").write_text(script, encoding="utf-8")
    audio = synthesize(session.client("polly", config=cfg), script,
                       os.getenv("POLLY_VOICE", "Camila"), os.getenv("POLLY_ENGINE", "neural"))
    (output / "episode.wav").write_bytes(audio)
    base = f"episodes/{day}"
    store.put(f"{base}/episode.wav", audio, "audio/wav")
    store.put(f"{base}/script.txt", script.encode(), "text/plain; charset=utf-8")
    manifest = {"date": day, "created_at": now.isoformat(), "model": model, "news": news,
                "audio_key": store.key(f"{base}/episode.wav"), "script_characters": len(script),
                "date_validation": "Data declarada no RSS; não verificação editorial independente"}
    # Manifesto por último: marca de conclusão. Falhas anteriores podem ser reexecutadas.
    store.json(f"{base}/manifest.json", manifest)
    store.json("history.json", history + news)
    print(f"Edição privada {day} concluída; {len(audio)} bytes de áudio.")


def main():
    parser = argparse.ArgumentParser(description="Radar IA privado")
    parser.add_argument("--preview", action="store_true", help="Coleta sem LLM/AWS; ignora histórico remoto")
    args = parser.parse_args()
    run(args.preview)


if __name__ == "__main__":
    main()
