"""Piloto de duas vozes: geração local autorizada por --generate, sem publicação."""
import argparse,json,os
from pathlib import Path
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from radar_ia.dialogue import validate_pilot,synthesize_pilot

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'local-output/pilotos/leo-camila-v1')
    args=parser.parse_args();load_dotenv(ROOT/'.env')
    payload=json.loads((ROOT/'examples/piloto_dialogo.json').read_text(encoding='utf-8-sig'));pilot=validate_pilot(payload)
    print('Piloto:',len(pilot.turns),'falas | Leo + Camila | generative')
    print('Palavras:',sum(len(t.text.split()) for t in pilot.turns))
    if not args.generate:
        print('Preparação local. --generate solicita áudio pago no Polly, com cache por fala.');return
    cfg=Config(connect_timeout=10,read_timeout=90,retries={'total_max_attempts':1})
    polly=boto3.Session(region_name=os.getenv('AWS_REGION','us-east-1')).client('polly',config=cfg)
    available=set();token=None
    while True:
        page=polly.describe_voices(Engine='generative',LanguageCode='pt-BR',**({'NextToken':token} if token else {}))
        available.update(v['Id'] for v in page['Voices']);token=page.get('NextToken')
        if not token:break
    if not {'Leo','Camila'}<=available:raise SystemExit('As duas vozes generativas não estão disponíveis nesta região.')
    audio,metadata=synthesize_pilot(polly,payload,args.output_dir)
    print('Áudio:',audio.resolve());print('Duração medida:',round(metadata['duration_seconds'],1),'segundos.')
    print('Somente piloto local; nenhum episódio enviado ou publicado.')


if __name__=='__main__':main()
