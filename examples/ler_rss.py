"""Exploração de um RSS: execute a partir da raiz do projeto."""
import calendar
import json
import os
from dotenv import load_dotenv
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html import unescape

import feedparser
import httpx

from radar_ia.news import Fetcher, canonical, duplicate
from radar_ia.editorial import classify
from radar_ia.windows import collection_start
from radar_ia.news import clean


def clean_summary(text: str) -> str:
    """Decodifica entidades HTML e normaliza espaços; não remove tags."""
    return " ".join(unescape(text).split())


from radar_ia.collection import check_date, check_candidate


def main() -> None:
    load_dotenv()
    now = datetime.now(timezone.utc)
    folder = Path(os.getenv("OUTPUT_DIR", "local-output"))
    state_path = folder / "edicoes.json"
    state = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.exists() else {}
    since, window_reason = collection_start(
        now, state.get("last_completed_at"),
        int(os.getenv("INITIAL_LOOKBACK_DAYS", "7")),
        int(os.getenv("MAX_RECOVERY_DAYS", "7")),
    )
    hours = (now - since).total_seconds() / 3600
    sources_path = Path(os.getenv("RSS_SOURCES_FILE", "config/sources.json"))
    sources = json.loads(sources_path.read_text(encoding="utf-8-sig"))
    accepted, rejected, source_results = [], [], []
    counts, validation_counts = Counter(), Counter()
    print("Consulta:", now.astimezone(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"))
    print("Início da janela:", since.isoformat(), "—", window_reason)
    for source in sources:
        print("\nFonte:", source["name"])
        fetcher = Fetcher(source["domains"])
        result = {"name": source["name"], "url": source["url"], "entries": 0, "accepted": 0, "status": "ok"}
        source_results.append(result)
        try:
            try:
                body, _ = fetcher.get(source["url"])
            except (httpx.HTTPError, ValueError) as exc:
                result.update(status="erro", error=str(exc))
                print("Falha na fonte:", type(exc).__name__, str(exc))
                continue
            feed = feedparser.parse(body)
            result["entries"] = len(feed.entries)
            if feed.bozo:
                result["warning"] = "Irregularidade na leitura do XML"
            if not feed.entries:
                result["status"] = "sem entradas"
            # Limite explícito: RSS não garante arquivo completo do período.
            for news in feed.entries[:100]:
                status, published = check_date(news, now, hours)
                counts[status] += 1
                if status != "dentro da janela":
                    rejected.append({"title": news.get("title", ""), "source": source["url"], "reason": status})
                    continue
                validation, item = check_candidate(news, accepted, fetcher.get)
                validation_counts[validation] += 1
                print(f"  [{validation}] {news.get('title', 'Sem título')}")
                if item is None:
                    rejected.append({"title": news.get("title", ""), "source": source["url"], "reason": validation})
                    continue
                item.update(published=published.isoformat(), source=source["url"], source_name=source["name"], summary=clean(news.get("summary", "")))
                accepted.append(item)
                result["accepted"] += 1
                verdict = classify(item["title"], item["summary"])
                print(f"    Editorial: {verdict.category} / {verdict.priority}")
        finally:
            fetcher.close()
    report = {
        "schema_version": 2, "collected_at": now.isoformat(), "window_start": since.isoformat(),
        "window_reason": window_reason, "sources": source_results,
        "date_counts": dict(counts), "validation_counts": dict(validation_counts),
        "candidates": accepted, "rejected": rejected,
        "limitations": ["Triagem por palavras-chave", "Sem tradução ou roteiro", "Datas declaradas no RSS", "Feed pode omitir parte do período; no máximo 100 entradas por fonte", "Coleta não marca edição concluída"],
    }
    folder.mkdir(parents=True, exist_ok=True)
    report_path = folder / "coleta.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nResumo por fonte:")
    for result in source_results:
        print(f"  {result['name']}: {result['status']}; {result['entries']} entradas, {result['accepted']} candidatas aceitas")
    print("Candidatas totais:", len(accepted))
    print("Relatório salvo em:", report_path.resolve())
    print("A seleção temática é feita separadamente por examples/planejar_semana.py.")
    if not any(result["status"] == "ok" for result in source_results):
        raise SystemExit("Nenhuma fonte trouxe entradas utilizáveis; consulte o relatório de falhas.")


if __name__ == "__main__":
    main()
