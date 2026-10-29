"""Prepara briefing local; nenhuma chamada de IA, voz ou nuvem."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from radar_ia.brief import build_brief


def main():
    load_dotenv()
    folder = Path(os.getenv("OUTPUT_DIR", "local-output"))
    source = folder / "plano-editorial.json"
    if not source.exists():
        raise SystemExit("Execute primeiro examples/planejar_semana.py")
    plan = json.loads(source.read_text(encoding="utf-8"))
    brief = build_brief(plan)
    target = folder / "briefing-roteiro.json"
    target.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Tema:", brief["theme"])
    print("Notícias no briefing:", len(brief["news"]))
    print("Estado:", brief["status"])
    for warning in brief["warnings"]:
        print("Revisão:", warning)
    print("Arquivo:", target.resolve())
    print("Nenhuma chamada à LLM realizada. Este arquivo ainda não é o roteiro.")


if __name__ == "__main__":
    main()
