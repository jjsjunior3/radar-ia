"""Snapshot privado por edição; gravação condicional impede sobrescrita concorrente."""
import io
import json
import zipfile
import hashlib
from contextlib import closing
from pathlib import Path, PurePosixPath

from botocore.exceptions import ClientError

MAX_BYTES = 50 * 1024 * 1024


class ProductionStore:
    def __init__(self, client, bucket, prefix, output, day):
        self.client, self.bucket = client, bucket
        self.base = prefix.strip('/') + '/production'
        self.root = Path(output) / 'production'
        self.folder = self.root / day
        self.key = f'{self.base}/editions/{day}.zip'
        self.global_key = f'{self.base}/editorial-state.json'
        self.etag = self.global_etag = None

    def get(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('NoSuchKey', '404'):
                return None, None
            raise
        with closing(response['Body']) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Estado remoto acima do limite de 50 MiB')
        return data, response['ETag']

    def load(self):
        raw, self.etag = self.get(self.key)
        # Nunca misturar uma revisão local modificada com a versão remota.
        if raw is not None:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.infolist()
                if len(members) > 1000 or sum(i.file_size for i in members) > MAX_BYTES:
                    raise ValueError('Snapshot remoto excede limites')
                for member in members:
                    path = PurePosixPath(member.filename)
                    if member.is_dir() or path.is_absolute() or '..' in path.parts or '\\' in member.filename or ':' in member.filename:
                        raise ValueError('Caminho inválido no snapshot remoto')
                if self.folder.exists() and any(self.folder.iterdir()):
                    raise ValueError('Use pasta de saída vazia para restaurar o estado remoto')
                for member in members:
                    target = self.folder.joinpath(*PurePosixPath(member.filename).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
        shared, self.global_etag = self.get(self.global_key)
        self.root.mkdir(parents=True, exist_ok=True)
        if shared is not None:
            json.loads(shared)
            (self.root / 'editorial-state.json').write_bytes(shared)

    def put(self, key, data, etag, content_type):
        if len(data) > MAX_BYTES:
            raise ValueError('Snapshot acima do limite de 50 MiB')
        condition = {'IfMatch': etag} if etag else {'IfNoneMatch': '*'}
        return self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
            ContentType=content_type, ServerSideEncryption='AES256', **condition)['ETag']

    def save(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            total = 0
            for path in sorted(self.folder.rglob('*')):
                if path.is_symlink():
                    raise ValueError('Links simbólicos não são permitidos no estado')
                if path.is_file() and not path.name.endswith('.tmp'):
                    total += path.stat().st_size
                    if total > MAX_BYTES:
                        raise ValueError('Estado local acima do limite de 50 MiB')
                    archive.write(path, path.relative_to(self.folder).as_posix())
        self.etag = self.put(self.key, stream.getvalue(), self.etag, 'application/zip')

    def save_editorial(self):
        path = self.root / 'editorial-state.json'
        if path.exists():
            self.global_etag = self.put(self.global_key, path.read_bytes(), self.global_etag, 'application/json')

    def archive_audio_revision(self):
        raw,etag=self.get(self.key)
        if raw is None or etag!=self.etag:
            raise ValueError('Edição remota mudou; não iniciar nova versão de áudio')
        digest=hashlib.sha256(raw).hexdigest()
        key=f'{self.base}/audio-archives/{self.folder.name}/{digest}.zip'
        previous,_=self.get(key)
        if previous is None:self.put(key,raw,None,'application/zip')
        elif previous!=raw:raise ValueError('Backup de áudio divergente; interrompido')
        return {'key':key,'sha256':digest}
