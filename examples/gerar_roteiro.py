"""Geração real opcional. Sem --generate, apenas verifica a preparação local."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, APIStatusError, APIConnectionError
import httpx
from radar_ia.auth import check_openrouter_auth
from radar_ia.script import validate_brief, generate_script, spoken_text, render_script
from radar_ia.news import Fetcher, canonical
from radar_ia.llm_config import settings_from_env


def main():
    parser = argparse.ArgumentParser(description="Roteiro Radar IA; chamada paga somente com --generate")
    parser.add_argument("--check-auth", action="store_true", help="Verificar chave OpenRouter sem gerar tokens")
    parser.add_argument("--generate", action="store_true", help="Chamar a API configurada; pode gerar custo")
    args = parser.parse_args()
    env_path = Path(__file__).resolve().parents[1] / ".env"
    terminal_key_present = bool(os.environ.get("OPENROUTER_API_KEY"))
    load_dotenv(env_path)
    if terminal_key_present:
        print("Configuração: variáveis já definidas no terminal têm precedência sobre o .env.")
    folder = Path(os.getenv("OUTPUT_DIR", "local-output"))
    source = folder / "briefing-roteiro.json"
    if not source.exists():
        raise SystemExit("Execute primeiro examples/preparar_roteiro.py")
    brief = json.loads(source.read_text(encoding="utf-8"))
    ids = validate_brief(brief)
    print("Notícias no briefing:", len(ids))
    settings = settings_from_env(os.environ)
    model, key = settings.model, settings.api_key
    print("Provedor:", settings.provider)
    print("Modelo configurado:", model or "não configurado")
    print("Credencial:", "presente (valor oculto)" if key else "não configurada")
    if args.check_auth:
        if settings.provider != "openrouter":
            raise SystemExit("--check-auth está disponível para OpenRouter neste exemplo.")
        try:
            check_openrouter_auth(key)
        except (ValueError, httpx.HTTPError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Falha de conexão ao verificar autenticação."
            raise SystemExit(message) from None
        print("Autenticação aceita pelo OpenRouter. Nenhuma geração de tokens solicitada.")
        if not args.generate:
            return
    if not args.generate:
        print("Preparação local verificada. Nenhuma chamada externa. --generate inicia a geração paga.")
        return
    if not model or not key:
        raise SystemExit("Configure o modelo e a chave do provedor escolhido no .env; não envie a chave no chat.")
    now = datetime.now(timezone.utc)
    try:
        planned = datetime.fromisoformat(brief["planned_for"])
        if planned.tzinfo is None or not 0 <= (now - planned).total_seconds() <= 86400:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise SystemExit("Briefing sem planejamento recente. Refaça planejamento e preparação antes de gerar.")
    sources = json.loads(Path(os.getenv("RSS_SOURCES_FILE", "config/sources.json")).read_text(encoding="utf-8-sig"))
    allowed = {s["url"]: s["domains"] for s in sources}
    # Rechecar cada página sob a política da fonte que a coletou.
    for news in brief["news"]:
        source_url = next((s["url"] for s in sources if s["name"] == news.get("source")), None)
        if source_url not in allowed:
            raise SystemExit("Fonte do briefing não encontrada na configuração; recoletar.")
        fetcher = Fetcher(allowed[source_url])
        try:
            _, final = fetcher.get(news["url"])
            if canonical(final) != canonical(news["url"]):
                raise SystemExit("URL mudou desde a coleta; recoletar antes da geração.")
        finally:
            fetcher.close()
    client_options = {"api_key": key, "timeout": 90, "max_retries": 0}
    if settings.base_url:
        client_options["base_url"] = settings.base_url
    target = folder / "roteiros" / now.strftime("%Y%m%dT%H%M%S%fZ")
    target.mkdir(parents=True, exist_ok=False)
    (target / "briefing.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    def preserve_response(response):
        (target / "resposta-original.json").write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with OpenAI(**client_options) as client:
            script, metadata = generate_script(client, model, brief, provider=settings.provider, on_response=preserve_response)
    except AuthenticationError:
        raise SystemExit("Autenticação recusada (401). Verifique a chave de API do provedor. Para OpenRouter, use --check-auth antes de tentar gerar novamente.") from None
    except APIStatusError as exc:
        raise SystemExit(f"Provedor retornou HTTP {exc.status_code}. Geração interrompida; não houve nova tentativa automática.") from None
    except APIConnectionError:
        raise SystemExit("Falha de conexão com o provedor; não repetir automaticamente porque o resultado da requisição é incerto.") from None
    except ValueError as exc:
        (target / "erro-validacao.txt").write_text(str(exc), encoding="utf-8")
        raise SystemExit(f"Resposta não aprovada: {exc}. Tentativa preservada em {target.resolve()}; revisar sem gerar novamente.") from None
    # Resposta original já salva antes da validação.
    files = {"roteiro.json": script.model_dump(), "metadados.json": metadata, "briefing.json": brief}
    for name, value in files.items():
        (target / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "narracao.txt").write_text(spoken_text(script), encoding="utf-8")
    (target / "revisao.md").write_text(render_script(script, brief), encoding="utf-8")
    print("Roteiro salvo para revisão em:", target.resolve())
    print("Nenhum áudio gerado ou episódio publicado. Duração real ainda não medida.")


if __name__ == "__main__":
    main()
