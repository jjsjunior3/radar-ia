"""Resume a failed relevance selection once, preserving its received response."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import boto3
from openai import OpenAI
from radar_ia.agents import EditorialAgents, BudgetClient, content, RelevanceDecision
from radar_ia.production import Production, read_json, fingerprint
from radar_ia.production_store import ProductionStore
from radar_ia.jobs import JobStore, JobQueue, editorial_job_id
from radar_ia.push import review_notice

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dispatch-approved", action="store_true")
    args = parser.parse_args()
    credentials = json.loads(subprocess.check_output(
        ["aws", "configure", "export-credentials", "--profile", "radar-ia", "--format", "process"]))
    session = boto3.Session(aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"], region_name="us-east-1")
    env = session.client("lambda").get_function_configuration(
        FunctionName="radar-ia-private-app-editorial")["Environment"]["Variables"]
    s3 = session.client("s3")
    jobs = JobStore(session.resource("dynamodb").Table(env["JOBS_TABLE"]))
    parent_id = editorial_job_id(args.date)
    parent = jobs.get(parent_id)
    if not parent or parent["status"] != "failed" or parent.get("error_code") != "ValueError":
        raise ValueError("Recovery requires a failed editorial ValueError")
    output = Path("local-output/recovery") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    store = ProductionStore(s3, env["S3_BUCKET"], env.get("S3_PREFIX", "radar-ia"), output, args.date)
    store.load()
    now = datetime.now(timezone.utc)
    run = Production(output, now, day=args.date, persist=store.save)
    if args.dispatch_approved:
        brief, script, _ = run.approved_bundle()
        if run.state["stage"] != "script_approved":
            raise ValueError("Dispatch requires an approved script")
        summary = {"date": args.date, "planned_for": brief["planned_for"],
            "digest": fingerprint({"brief": brief, "script": script.model_dump()}),
            "audio_revision": run.state.get("audio_revision", "initial"), "can_generate_audio": True}
        JobQueue(jobs, session.client("sqs"), env["AUDIO_QUEUE_URL"]).start(summary, "audio",
            {"digest": summary["digest"], "confirmed": True}, env["REVIEWER_SUB"], automatic=True)
        identifier = hashlib.sha256(("relevance-recovery-v1:" + args.date).encode()).hexdigest()
        jobs.update(identifier, "succeeded", edition_stage="script_approved")
        jobs.update(parent_id, "succeeded", edition_stage="script_approved",
            recovery_job_id=identifier, previous_error_code=parent["error_code"])
        print("Approved script queued for audio", flush=True)
        return
    if run.state["stage"] != "prepared":
        raise ValueError("Recovery requires a prepared checkpoint")
    original = read_json(run.folder / "agents/original-brief.json")
    raw = read_json(run.folder / "agents/relevance/response.json")
    decision = RelevanceDecision.model_validate(content(raw))
    expected = {n["id"] for n in original["news"]}
    received = [n.news_id for n in decision.candidates]
    if len(received) != len(set(received)) or not set(received) < expected:
        raise ValueError("Recovery requires a received response with missing IDs only")
    root = Path(__file__).resolve().parents[1]
    run.revalidate(read_json(root / "config/sources.json"))
    print("Saved response verified; missing IDs:", sorted(expected - set(received)), flush=True)
    if not args.resume:
        print("Use --resume for the paid repair and subsequent editorial steps")
        return
    identifier = hashlib.sha256(("relevance-recovery-v1:" + args.date).encode()).hexdigest()
    jobs.create({"job_id": identifier, "action": "editorial_recovery", "date": args.date,
        "status": "queued", "parent_job_id": parent_id, "checkpoint_etag": store.etag,
        "created_at": now.isoformat(), "updated_at": now.isoformat(), "can_retry": False})
    if not jobs.claim(identifier):
        raise ValueError("Recovery already started; inspect its preserved result")
    sqs = session.client("sqs")
    try:
        secret = session.client("secretsmanager").get_secret_value(
            SecretId=env["OPENROUTER_SECRET_ARN"])["SecretString"]
        with OpenAI(api_key=secret, base_url="https://openrouter.ai/api/v1", timeout=90, max_retries=0) as client:
            agents = EditorialAgents(run, BudgetClient(client), env.get("OPENROUTER_MODEL", "google/gemini-2.5-flash"))
            if agents.select():
                run.draft(agents.generate)
        if run.state["stage"] == "awaiting_script_review" and env.get("AUTOMATIC_PUBLICATION") == "true":
            run.approve_script(mode="automatic")
            brief, script, _ = run.approved_bundle()
            summary = {"date": args.date, "planned_for": brief["planned_for"], "digest": fingerprint({"brief": brief, "script": script.model_dump()}),
                "audio_revision": run.state.get("audio_revision", "initial"), "can_generate_audio": True}
            JobQueue(jobs, sqs, env["AUDIO_QUEUE_URL"]).start(summary, "audio",
                {"digest": summary["digest"], "confirmed": True}, env["REVIEWER_SUB"], automatic=True)
        if run.state["stage"] == "awaiting_human_review":
            brief, script, _ = run.script_bundle()
            review_notice(sqs, env["NOTIFICATION_QUEUE_URL"], args.date,
                fingerprint({"brief": brief, "script": script.model_dump()}))
        jobs.update(identifier, "succeeded", edition_stage=run.state["stage"])
        jobs.update(parent_id, "succeeded", edition_stage=run.state["stage"],
            recovery_job_id=identifier, previous_error_code=parent["error_code"])
        print("Recovery stage:", run.state["stage"], flush=True)
    except Exception as exc:
        jobs.update(identifier, "failed", error_code=type(exc).__name__, can_retry=False)
        print("Recovery preserved; error type:", type(exc).__name__, flush=True)
        raise SystemExit(1)

if __name__ == "__main__":
    main()

