"""Polly opcional: sem --generate apenas verifica o texto local."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from radar_ia.audio import make_audio
from radar_ia.speech_markup import speech_chunks


def main():
    parser = argparse.ArgumentParser(description="Áudio local com Polly; sem upload ou publicação")
    parser.add_argument("--script", required=True, type=Path, help="Arquivo narracao.txt revisado")
    parser.add_argument("--generate", action="store_true", help="Chamar Polly; pode gerar custo")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    text = args.script.read_text(encoding="utf-8-sig")
    parts = speech_chunks(text)
    structured_path = args.script.parent / "roteiro.json"
    if not structured_path.exists():
        raise SystemExit("Mantenha roteiro.json junto de narracao.txt para carregar o glossário de inglês.")
    structured = json.loads(structured_path.read_text(encoding="utf-8"))
    english_terms = [term["term_en"] for term in structured.get("glossary", [])]
    region = os.getenv("AWS_REGION", "").strip()
    voice, engine = os.getenv("POLLY_VOICE", "Camila"), os.getenv("POLLY_ENGINE", "generative")
    print("Palavras:", len(text.split()), "| Trechos:", len(parts))
    print("Região:", region or "não configurada", "| Voz:", voice, "| Engine:", engine)
    print("SSML: pausas por parágrafo; termos ingleses:", ", ".join(english_terms) or "nenhum")
    if not args.generate:
        print("Verificação local concluída; nenhuma consulta à AWS. Pronúncia e duração ainda não verificadas.")
        return
    if not region:
        raise SystemExit("Configure AWS_REGION antes de gerar áudio.")
    try:
        session = boto3.Session(region_name=region)
        # Uma tentativa por trecho: retries podem repetir cobrança após falha incerta.
        polly = session.client("polly", config=Config(retries={"total_max_attempts": 1}, connect_timeout=10, read_timeout=60))
        audio, metadata = make_audio(polly, text, voice, engine, english_terms=english_terms)
    except (BotoCoreError, ClientError) as exc:
        code = exc.response["Error"]["Code"] if isinstance(exc, ClientError) else type(exc).__name__
        raise SystemExit(f"AWS não concluiu o áudio ({code}). Verifique credenciais, permissões e combinação voz/engine/região; não repetir automaticamente.") from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    target = args.script.parent / "audio" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target.mkdir(parents=True, exist_ok=False)
    metadata["script_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (target / "episode.wav").write_bytes(audio)
    (target / "metadados.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Áudio local salvo em:", target.resolve())
    print("Duração medida:", round(metadata["duration_seconds"], 1), "segundos. Nenhum upload ou publicação.")


if __name__ == "__main__":
    main()
