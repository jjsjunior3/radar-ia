"""Compara vozes em amostra curta; não gera um episódio completo."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing
import os
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from radar_ia.speech_markup import bilingual_ssml

TEXT = """Você está ouvindo uma amostra do Radar IA. Vamos testar uma conversa em português, com termos técnicos em inglês.

Training loop significa ciclo de treinamento. Fine-tuning significa ajuste fino de um modelo. Primeiro ouvimos o termo em inglês; depois, sua explicação em português.

O objetivo é acompanhar as notícias com clareza, sem pressa e com uma voz consistente. Esta amostra não é uma notícia real."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true', help='Gerar três amostras pagas no Polly')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    variants = [('A-neural-simples', 'neural', 'text', TEXT),
                ('B-neural-ingles', 'neural', 'ssml', bilingual_ssml(TEXT, ['training loop', 'fine-tuning'])),
                ('C-generativa-ingles', 'generative', 'ssml', bilingual_ssml(TEXT, ['training loop', 'fine-tuning']))]
    if not args.generate:
        print('Três amostras preparadas; nenhuma chamada AWS realizada.')
        return
    folder = Path(os.getenv('OUTPUT_DIR','local-output')) / 'amostras-voz' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'texto.txt').write_text(TEXT, encoding='utf-8')
    polly=boto3.Session().client('polly', region_name=os.getenv('AWS_REGION','us-east-1'), config=Config(retries={'total_max_attempts':1},read_timeout=90,connect_timeout=10))
    results=[]
    for name,engine,kind,text in variants:
        (folder/(name+'.txt')).write_text(text,encoding='utf-8')
        try:
            print('Solicitando:', name, flush=True)
            response=polly.synthesize_speech(Text=text,TextType=kind,VoiceId='Camila',Engine=engine,LanguageCode='pt-BR',OutputFormat='mp3',SampleRate='24000')
            with closing(response['AudioStream']) as stream:
                data=stream.read()
            if not data: raise ValueError('Áudio vazio')
            (folder/(name+'.mp3')).write_bytes(data)
            results.append(dict(name=name,engine=engine,status='gerada',request_characters=response.get('RequestCharacters')))
            print('Gerada:',name)
        except (BotoCoreError,ClientError,ValueError) as exc:
            code=exc.response['Error']['Code'] if isinstance(exc,ClientError) else type(exc).__name__
            results.append(dict(name=name,engine=engine,status='falhou',error=code))
            print('Falhou:',name,code)
        (folder/'resultados.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Pasta:',folder.resolve())


if __name__=='__main__':
    main()
