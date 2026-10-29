"""Reprocessa resposta salva sem consultar APIs ou gerar cobrança."""
import argparse
import json
from pathlib import Path
from radar_ia.script import assemble_script, spoken_text, render_script


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path, help="Pasta da tentativa em local-output/roteiros")
    args = parser.parse_args()
    folder = args.attempt
    raw = json.loads((folder / "resposta-original.json").read_text(encoding="utf-8"))
    brief = json.loads((folder / "briefing.json").read_text(encoding="utf-8"))
    if "choices" not in raw or not raw["choices"] or raw["choices"][0].get("finish_reason") != "stop":
        raise SystemExit("Este reprocessador exige uma resposta Chat Completions concluída.")
    payload = json.loads(raw["choices"][0]["message"]["content"])
    script, changes = assemble_script(payload, brief)
    target = folder / "reprocessado"
    target.mkdir(exist_ok=True)
    (target / "roteiro.json").write_text(json.dumps(script.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "narracao.txt").write_text(spoken_text(script), encoding="utf-8")
    (target / "revisao.md").write_text(render_script(script, brief), encoding="utf-8")
    (target / "ajustes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Reprocessado sem rede em:", target.resolve())


if __name__ == "__main__":
    main()
