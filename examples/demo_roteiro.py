"""Demo fictícia local, sem rede, credenciais ou custo."""
import json
from pathlib import Path
from radar_ia.script import validate_script, spoken_text, render_script


def main():
    brief = {"theme": "Demonstração fictícia", "news": [{"id": 1,
        "title_original": "Fictional tool adds caching", "summary_original": "A fictional tool stores results for reuse.",
        "source": "Fixture local fictícia", "url": "https://example.org/fictional", "published": "2026-10-28T12:00:00+00:00"}]}
    payload = {"intro_pt": "Esta é uma demonstração fictícia para testar o formato, não uma notícia real.",
        "stories": [{"news_id": 1, "title_pt": "Ferramenta fictícia reutiliza resultados",
        "summary_pt": "Neste exemplo fictício, a ferramenta armazena resultados para reutilização.",
        "narration_pt": "No exemplo fictício, a ferramenta usa caching, armazenamento de resultados para reutilização. Esse é o significado de caching neste contexto."}],
        "glossary": [{"term_en": "caching", "explanation_pt": "armazenamento de resultados para reutilização", "news_ids": [1]}],
        "outro_pt": "Fim da demonstração fictícia."}
    script = validate_script(payload, brief)
    folder = Path("local-output/demo-roteiro")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "roteiro.json").write_text(json.dumps(script.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "narracao.txt").write_text(spoken_text(script), encoding="utf-8")
    (folder / "revisao.md").write_text(render_script(script, brief), encoding="utf-8")
    print("Demo fictícia validada e salva em:", folder.resolve())
    print("Nenhuma LLM ou serviço de voz foi chamado.")


if __name__ == "__main__":
    main()
