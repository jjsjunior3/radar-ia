"""Comandos acompanhados, usados no terminal e no GitHub Actions."""
import argparse
import os
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from .catalog import read_catalog, upload_episode, verify_private
from .llm_config import settings_from_env
from .production import Production, read_json
from .production_store import ProductionStore
from .script import generate_script

STEPS = ('status', 'prepare', 'draft', 'approve-script', 'audio', 'approve-audio', 'publish')


def parser():
    result = argparse.ArgumentParser(description='Radar IA: produção acompanhada, com estado privado no S3')
    result.add_argument('step', choices=STEPS)
    result.add_argument('--date', type=date.fromisoformat, help='Edição existente; coleta somente para hoje')
    result.add_argument('--execute', action='store_true', help='Autoriza chamada paga em draft/audio ou publicação em publish')
    result.add_argument('--reviewed', action='store_true', help='Confirma revisão humana em approve-script/approve-audio')
    result.add_argument('--local', action='store_true', help='Estado local; não combinar com Actions para a mesma edição')
    return result


def execute(args, output, now=None):
    now = now or datetime.now(timezone.utc)
    day = (args.date or now.astimezone(ZoneInfo('America/Sao_Paulo')).date()).isoformat()
    if args.step in ('draft', 'audio', 'publish') and not args.execute:
        print('Nenhuma chamada executada. Adicione --execute para esta etapa.')
        return
    if args.step in ('approve-script', 'approve-audio') and not args.reviewed:
        raise ValueError('Revise o arquivo correspondente e informe --reviewed')
    bucket = os.environ.get('S3_BUCKET', '').strip()
    if not bucket:
        raise ValueError('Configure S3_BUCKET')
    prefix = os.environ.get('S3_PREFIX', 'radar-ia').strip('/')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    session = boto3.Session(region_name=region)
    config = Config(signature_version='s3v4', retries={'total_max_attempts': 1}, connect_timeout=10, read_timeout=90)
    s3 = session.client('s3', config=config)
    verify_private(s3, bucket)
    store = None
    if not args.local:
        store = ProductionStore(s3, bucket, prefix, output, day)
        store.load()
    run = Production(output, now, day=day, persist=store.save if store else None)
    sources = read_json(Path(os.getenv('RSS_SOURCES_FILE', 'config/sources.json')))
    if args.step == 'prepare':
        catalog, _ = read_catalog(s3, bucket, f'{prefix}/catalog.json')
        run.prepare(sources, catalog)
    elif args.step == 'draft':
        if run.state['stage'] in ('completed','no_content'):
            print('Edição já publicada ou sem conteúdo; nenhuma geração solicitada.')
            return
        run.revalidate(sources)
        settings = settings_from_env(os.environ)
        if settings.provider != 'openrouter':
            raise ValueError('Este fluxo de recuperação requer LLM_PROVIDER=openrouter')
        if not settings.api_key or not settings.model:
            raise ValueError('Configure a chave e o modelo do OpenRouter')
        with OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=90, max_retries=0) as client:
            run.draft(lambda brief, save: generate_script(client, settings.model, brief,
                provider=settings.provider, on_response=save))
    elif args.step == 'approve-script':
        run.approve_script()
    elif args.step == 'audio':
        run.revalidate(sources)
        run.synthesize(session.client('polly', config=config),
            voice=os.getenv('POLLY_VOICE', 'Camila'), engine=os.getenv('POLLY_ENGINE', 'generative'))
    elif args.step == 'approve-audio':
        run.approve_audio()
    elif args.step == 'publish':
        # Após falha no commit editorial, reconciliar um episódio já publicado mesmo com pauta antiga.
        if run.state['stage'] not in ('publish_in_progress', 'completed'):
            run.revalidate(sources)
        def upload(audio, script, narration, brief, edition):
            episode, _ = upload_episode(s3, bucket, prefix, audio=audio, script=script,
                narration=narration, brief=brief, date=edition, title=f"Radar IA — {brief['theme']}")
            return episode
        run.publish(upload)
        if store:
            store.save_editorial()
    print('Edição:', day, '| Etapa:', run.state['stage'])
    # Arquivos privados para revisão; jamais incluir .env nem credenciais.
    print('Pasta de revisão:', run.folder.resolve())
    if store:
        print('Estado salvo no S3 privado. Para baixar, use o comando status.')
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write(f"## Radar IA\n\nEdição: {day}\n\nEtapa: `{run.state['stage']}`\n\nArquivos de revisão no S3 privado; consulte docs/07-producao-acompanhada.md.\n")


def main(argv=None):
    load_dotenv()
    args = parser().parse_args(argv)
    try:
        if args.local:
            execute(args, Path(os.getenv('OUTPUT_DIR', 'local-output')))
        else:
            # Sempre restaurar em pasta nova; não reutilizar arquivos locais divergentes.
            with TemporaryDirectory(prefix='radar-production-') as temporary:
                output = Path(temporary)
                execute(args, output)
                if args.step == 'status':
                    import shutil
                    day = (args.date or datetime.now(ZoneInfo('America/Sao_Paulo')).date()).isoformat()
                    source = output/'production'/day
                    if source.exists():
                        target = Path(os.getenv('OUTPUT_DIR','local-output'))/'revisoes-remotas'/day/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                        shutil.copytree(source, target)
                        print('Cópia local para revisão:', target.resolve())
    except (ValueError, OSError, BotoCoreError, ClientError, OpenAIError, httpx.HTTPError) as exc:
        # Não imprimir respostas do provedor, tokens, URLs assinadas ou configuração de credenciais.
        if isinstance(exc, ValueError):
            raise SystemExit(str(exc)) from None
        raise SystemExit(f'Etapa interrompida ({type(exc).__name__}). Estado privado preservado; consulte status antes de repetir.') from None


if __name__ == '__main__':
    main()
