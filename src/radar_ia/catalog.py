"""Catálogo privado no S3, com atualização condicional para evitar perda de dados."""
import hashlib
import io
import json
import wave
from contextlib import closing
from botocore.exceptions import ClientError

BLOCK = {"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True}


def verify_private(client, bucket):
    block = client.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    if any(block.get(key) is not True for key in BLOCK):
        raise ValueError("Bucket deve manter os quatro bloqueios de acesso público ativados")
    rules = client.get_bucket_ownership_controls(Bucket=bucket)["OwnershipControls"]["Rules"]
    if not any(r.get("ObjectOwnership") == "BucketOwnerEnforced" for r in rules):
        raise ValueError("Bucket deve desabilitar ACLs com BucketOwnerEnforced")
    client.get_bucket_encryption(Bucket=bucket)


def read_catalog(client, bucket, key):
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return {"schema_version": 1, "episodes": []}, None
        raise
    with closing(response["Body"]) as stream:
        data = json.loads(stream.read())
    if data.get("schema_version") != 1 or not isinstance(data.get("episodes"), list):
        raise ValueError("Catálogo remoto incompatível; não sobrescrever")
    return data, response["ETag"]


def upload_episode(client, bucket, prefix, *, audio, script, narration, brief, date, title):
    verify_private(client, bucket)
    with wave.open(io.BytesIO(audio)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    if not 0 < duration <= 600:
        raise ValueError("Duração do WAV fora do limite de 10 minutos")
    encoded_script = json.dumps(script, ensure_ascii=False, sort_keys=True).encode()
    digest = hashlib.sha256(audio + encoded_script + narration.encode()).hexdigest()
    episode_id = f"{date}-{digest[:16]}"
    base = f"{prefix.strip('/')}/episodes/{episode_id}"
    catalog_key = f"{prefix.strip('/')}/catalog.json"
    catalog, etag = read_catalog(client, bucket, catalog_key)
    existing = next((e for e in catalog["episodes"] if e["id"] == episode_id), None)
    if existing:
        return existing, False
    assets = {"episode.wav": (audio, "audio/wav"), "roteiro.json": (encoded_script, "application/json"),
              "narracao.txt": (narration.encode(), "text/plain; charset=utf-8"),
              "fontes.json": (json.dumps(brief["news"], ensure_ascii=False).encode(), "application/json")}
    for name, (body, mime) in assets.items():
        client.put_object(Bucket=bucket, Key=f"{base}/{name}", Body=body, ContentType=mime,
                          ServerSideEncryption="AES256")
    episode = {"id": episode_id, "date": date, "title": title, "theme": brief["theme"],
               "duration_seconds": duration, "audio_key": f"{base}/episode.wav",
               "script_key": f"{base}/roteiro.json", "sources_key": f"{base}/fontes.json",
               "sha256": digest, "visibility": "private", "news_urls": [n["url"] for n in brief["news"]]}
    client.put_object(Bucket=bucket, Key=f"{base}/manifest.json", Body=json.dumps(episode, ensure_ascii=False).encode(),
                      ContentType="application/json", ServerSideEncryption="AES256")
    updated = dict(catalog, episodes=sorted(catalog["episodes"] + [episode], key=lambda e: e["date"], reverse=True))
    condition = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
    # Catálogo é o commit: só aponta para arquivos já enviados.
    client.put_object(Bucket=bucket, Key=catalog_key, Body=json.dumps(updated, ensure_ascii=False, indent=2).encode(),
                      ContentType="application/json", ServerSideEncryption="AES256", **condition)
    return episode, True
