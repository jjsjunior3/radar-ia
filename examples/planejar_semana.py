"""Planeja a partir da coleta local; não acessa rede, LLM ou AWS."""
import json
import argparse
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from pathlib import Path

from radar_ia.weekly import merge_queue, plan
from radar_ia.review import render_report
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description="Simulação editorial local, sem serviços pagos")
    parser.add_argument("--date", help="Simular YYYY-MM-DD às 08h30 de São Paulo; não publica")
    args = parser.parse_args()
    load_dotenv()
    if args.date:
        try:
            now = datetime.strptime(args.date, "%Y-%m-%d").replace(hour=8, minute=30, tzinfo=ZoneInfo("America/Sao_Paulo"))
        except ValueError:
            parser.error("Use --date YYYY-MM-DD")
    else:
        now = datetime.now(timezone.utc)
    folder = Path(os.getenv("OUTPUT_DIR", "local-output"))
    source = folder / "coleta.json"
    if not source.exists():
        raise SystemExit("Execute primeiro examples/ler_rss.py")
    report = json.loads(source.read_text(encoding="utf-8"))
    queue_path = folder / "fila-editorial.json"
    previous = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else []
    queue = merge_queue(previous, report["candidates"])
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    result = plan(queue, now)
    result["planned_for"] = now.isoformat()
    output = folder / "plano-editorial.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path = folder / "revisao-editorial.md"
    review_path.write_text(render_report(result, now.isoformat()), encoding="utf-8")
    print("Tema da simulação:", result["theme"])
    for field, label in [("main", "Candidatas do tema"), ("waiting", "Aguardando outro tema"),
                         ("review", "Revisão editorial"), ("excluded", "Fora da seleção"), ("recap", "Possíveis retomadas")]:
        print(f"\n{label}: {len(result[field])}")
        for item in result[field]:
            print(" -", item["title"])
            print("   Fonte:", item.get("source_name", item.get("source", "não registrada")))
            print("   Motivo:", item["reason"])
    print("\nPlano salvo em:", output.resolve())
    print("Revisão legível:", review_path.resolve())
    print("Simulação: nenhuma notícia foi marcada como publicada. Links precisam ser revalidados antes do episódio.")


if __name__ == "__main__":
    main()
