"""Envia episódio revisado ao catálogo privado; sem --upload só verifica arquivos."""
import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from radar_ia.catalog import upload_episode
from radar_ia.script import validate_script, spoken_text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--audio-dir',required=True,type=Path)
    parser.add_argument('--date',required=True,type=date.fromisoformat)
    parser.add_argument('--title',default='Radar IA — Caixa de ferramentas')
    parser.add_argument('--upload',action='store_true')
    args=parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    audio_dir=args.audio_dir
    revision=audio_dir.parent.parent
    brief_path=revision/'briefing.json'
    if not brief_path.exists(): brief_path=revision.parent/'briefing.json'
    brief=json.loads(brief_path.read_text(encoding='utf-8'))
    payload=json.loads((revision/'roteiro.json').read_text(encoding='utf-8'))
    script=validate_script(payload,brief)
    narration=(revision/'narracao.txt').read_text(encoding='utf-8')
    if narration!=spoken_text(script): raise SystemExit('Narração e roteiro divergentes; revisar antes do upload.')
    metadata=json.loads((audio_dir/'metadados.json').read_text(encoding='utf-8'))
    if metadata.get('script_sha256')!=hashlib.sha256(narration.encode()).hexdigest():
        raise SystemExit('Áudio corresponde a outro texto; não enviar.')
    audio=(audio_dir/'episode.wav').read_bytes()
    print('Título:',args.title,'| Data:',args.date)
    print('Áudio e texto consistentes; bytes:',len(audio))
    if not args.upload:
        print('Sem alterações na AWS. --upload envia os arquivos e registra no catálogo privado.')
        return
    bucket=os.getenv('S3_BUCKET','').strip()
    if not bucket: raise SystemExit('Configure S3_BUCKET no .env')
    client=boto3.Session().client('s3',region_name=os.getenv('AWS_REGION','us-east-1'),config=Config(signature_version='s3v4',retries={'total_max_attempts':1},connect_timeout=10,read_timeout=60))
    try:
        episode,created=upload_episode(client,bucket,os.getenv('S3_PREFIX','radar-ia'),audio=audio,script=script.model_dump(),narration=narration,brief=brief,date=args.date.isoformat(),title=args.title)
    except ClientError as exc:
        code=exc.response['Error']['Code']
        if code in ('PreconditionFailed','412','ConditionalRequestConflict'):
            raise SystemExit('Catálogo mudou durante o envio. Nada foi sobrescrito no catálogo; reexecute para reconciliar.') from None
        raise SystemExit(f'S3 retornou {code}. Verifique permissões/configuração; não considere o episódio concluído.') from None
    (audio_dir/'s3-receipt.json').write_text(json.dumps({'bucket':bucket,'episode':episode},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Episódio registrado no catálogo privado.' if created else 'Episódio já registrado; não duplicado.')
    print('ID:',episode['id'])
    print('Nenhum acesso público habilitado; nenhum progresso de escuta alterado.')


if __name__=='__main__': main()
