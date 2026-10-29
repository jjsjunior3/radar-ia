"""Prévia HTTP exclusivamente local. Não é servidor de produção ou login remoto."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from .catalog import read_catalog
from .progress import ProgressStore


class Library:
    def __init__(self, output, demo=False):
        self.output=Path(output)
        self.demo=demo
        self.progress=ProgressStore(self.output/'app'/'progress.sqlite3')
        self.cached=None
        self.cached_at=0
        if not demo:
            self.bucket=os.getenv('S3_BUCKET','').strip()
            if not self.bucket: raise ValueError('Configure S3_BUCKET')
            self.prefix=os.getenv('S3_PREFIX','radar-ia').strip('/')
            self.s3=boto3.Session().client('s3',region_name=os.getenv('AWS_REGION','us-east-1'),config=Config(signature_version='s3v4',retries={'total_max_attempts':1},connect_timeout=10,read_timeout=20))

    def episodes(self):
        if self.demo:
            return [dict(id='demo-1',date='2026-10-28',title='Caixa de ferramentas',theme='Guias, agentes e infraestrutura',duration_seconds=217.6,visibility='local-demo',description='Demonstração da biblioteca. O player será conectado ao episódio privado no modo S3.')]
        if self.cached is None or time.monotonic()-self.cached_at>30:
            catalog,_=read_catalog(self.s3,self.bucket,f'{self.prefix}/catalog.json')
            self.cached=catalog['episodes']
            self.cached_at=time.monotonic()
        return self.cached

    def episode(self,episode_id):
        return next((e for e in self.episodes() if e['id']==episode_id),None)

    def listing(self):
        progress=self.progress.all()
        return {'mode':'demo' if self.demo else 's3','episodes':[dict(e,progress=progress.get(e['id'],dict(position=0,heard=False))) for e in self.episodes()]}

    def audio_url(self,episode):
        if self.demo: raise ValueError('Player de demonstração: execute em modo S3 para ouvir o episódio privado.')
        key=episode['audio_key']
        if not key.startswith(f'{self.prefix}/episodes/'): raise ValueError('Chave de áudio fora do catálogo permitido')
        return self.s3.generate_presigned_url('get_object',Params={'Bucket':self.bucket,'Key':key},ExpiresIn=300)


def handler_for(library,port):
    web=Path(__file__).parent/'web'
    allowed_hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Não registrar URLs temporárias ou corpos de requisição.
        def reply(self,status,payload,mime='application/json; charset=utf-8'):
            body=json.dumps(payload,ensure_ascii=False).encode() if 'application/json' in mime else payload
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' https://*.amazonaws.com; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)
        def authorized_host(self):
            if self.headers.get('Host') not in allowed_hosts:
                self.reply(403,{'error':'Esta prévia aceita apenas acesso local.'})
                return False
            return True
        def do_GET(self):
            if not self.authorized_host(): return
            path=urlparse(self.path).path
            try:
                if path=='/api/episodes':
                    return self.reply(200,library.listing())
                if path.startswith('/api/audio/'):
                    episode=library.episode(unquote(path[len('/api/audio/'):]))
                    if not episode: return self.reply(404,{'error':'Episódio não encontrado'})
                    return self.reply(200,{'url':library.audio_url(episode),'expires_in':300})
                assets={'/':('index.html','text/html; charset=utf-8'),'/auth.js':('auth.js','text/javascript; charset=utf-8'),'/manifest.webmanifest':('manifest.webmanifest','application/manifest+json'),'/icon.svg':('icon.svg','image/svg+xml'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
                if path not in assets: return self.reply(404,{'error':'Página não encontrada'})
                name,mime=assets[path]
                return self.reply(200,(web/name).read_bytes(),mime)
            except ValueError as exc:
                return self.reply(400,{'error':str(exc)})
            except Exception:
                return self.reply(503,{'error':'Não foi possível consultar o S3. Confira login AWS, conexão e permissões.'})
        def do_POST(self):
            if not self.authorized_host(): return
            if self.headers.get('X-Radar-Client')!='web' or self.headers.get('Origin') not in {f'http://{host}' for host in allowed_hosts}:
                return self.reply(403,{'error':'Origem não autorizada'})
            if urlparse(self.path).path!='/api/progress': return self.reply(404,{'error':'Rota não encontrada'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096: raise ValueError('Requisição inválida')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict) or set(data)-{'episode_id','position','heard'}: raise ValueError('Campos inválidos')
                episode=library.episode(data.get('episode_id'))
                if not episode: return self.reply(404,{'error':'Episódio não encontrado'})
                result=library.progress.save(episode['id'],episode['duration_seconds'],position=data.get('position'),heard=data.get('heard'))
                return self.reply(200,result)
            except (ValueError,TypeError): return self.reply(400,{'error':'Progresso inválido'})
            except Exception: return self.reply(503,{'error':'Não foi possível salvar o progresso'})
    return Handler


def main():
    parser=argparse.ArgumentParser(description='Biblioteca local do Radar IA; não expor na rede')
    parser.add_argument('--demo',action='store_true',help='Sem AWS; dados demonstrativos')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[2]/'.env')
    library=Library(os.getenv('OUTPUT_DIR','local-output'),args.demo)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(library,args.port))
    print(f'Radar IA local: http://127.0.0.1:{args.port}',flush=True)
    print('Modo: demonstração sem AWS' if args.demo else 'Modo: catálogo privado S3',flush=True)
    print('Somente neste computador. Ctrl+C encerra.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=='__main__': main()
