"""Enable Gemini TTS and quota fallback in the private AWS worker."""

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

import boto3
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("Use --apply para configurar o segredo e atualizar o worker na AWS.")
        return
    env = dotenv_values(ROOT / ".env")
    secret = {
        "gemini_api_key": env.get("GEMINI_API_KEY", ""),
        "openrouter_api_key": env.get("OPENROUTER_API_KEY", ""),
        "fallback_budget_usd": env.get("TTS_FALLBACK_BUDGET_USD") or "0.30",
    }
    if not secret["gemini_api_key"] or not secret["openrouter_api_key"]:
        raise SystemExit("Configure as duas chaves no .env")
    raw = subprocess.check_output(
        [
            "aws",
            "configure",
            "export-credentials",
            "--profile",
            "radar-ia",
            "--format",
            "process",
        ]
    )
    credentials = json.loads(raw)
    session = boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name="us-east-1",
    )
    cf, s3, secrets = (
        session.client(name) for name in ("cloudformation", "s3", "secretsmanager")
    )
    stack_name = "radar-ia-private-app"
    current = cf.describe_stacks(StackName=stack_name)["Stacks"][0]
    if current["StackStatus"] != "UPDATE_COMPLETE":
        raise SystemExit("Aguarde a stack ficar disponível")
    parameters = {p["ParameterKey"]: p["ParameterValue"] for p in current["Parameters"]}
    template = json.dumps(
        json.loads((ROOT / "infra/private-app.json").read_text(encoding="utf-8")),
        separators=(",", ":"),
    )
    cf.validate_template(TemplateBody=template)
    payload = json.dumps(secret, sort_keys=True)
    token = hashlib.sha256(payload.encode()).hexdigest()
    try:
        arn = secrets.create_secret(
            Name="radar-ia/voice-gemini", SecretString=payload, ClientRequestToken=token
        )["ARN"]
    except secrets.exceptions.ResourceExistsException:
        arn = secrets.put_secret_value(
            SecretId="radar-ia/voice-gemini",
            SecretString=payload,
            ClientRequestToken=token,
        )["ARN"]
    source = s3.get_object(
        Bucket=parameters["AudioBucket"], Key=parameters["WorkerCodeKey"]
    )["Body"].read()
    output = io.BytesIO()
    added = {"radar_ia/generative_tts.py", "radar_ia/dialogue.py"}
    with (
        zipfile.ZipFile(io.BytesIO(source)) as old,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as new,
    ):
        for item in old.infolist():
            local = ROOT / "src" / item.filename
            body = (
                local.read_bytes()
                if item.filename.startswith("radar_ia/") and local.is_file()
                else old.read(item.filename)
            )
            new.writestr(item, body)
            added.discard(item.filename)
        for name in sorted(added):
            new.write(ROOT / "src" / name, name)
    archive = output.getvalue()
    with zipfile.ZipFile(io.BytesIO(archive)) as check:
        if check.testzip() is not None:
            raise ValueError("Pacote inválido")
    key = (
        "radar-ia/deployments/"
        + hashlib.sha256(archive).hexdigest()[:24]
        + "/worker.zip"
    )
    s3.put_object(
        Bucket=parameters["AudioBucket"],
        Key=key,
        Body=archive,
        ServerSideEncryption="AES256",
        ContentType="application/zip",
    )
    updates = {"WorkerCodeKey": key, "TtsSecretArn": arn}
    values = [
        {"ParameterKey": k, "UsePreviousValue": True}
        for k in parameters
        if k not in updates
    ]
    values.extend({"ParameterKey": k, "ParameterValue": v} for k, v in updates.items())
    cf.update_stack(
        StackName=stack_name,
        TemplateBody=template,
        Parameters=values,
        Capabilities=["CAPABILITY_IAM"],
    )
    print("Atualização iniciada. Chaves salvas no Secrets Manager.", flush=True)


if __name__ == "__main__":
    main()
