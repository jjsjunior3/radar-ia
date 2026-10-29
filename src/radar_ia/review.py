"""Relatório legível de revisão; títulos originais são preservados."""
from collections import Counter

SECTIONS = (("main", "Candidatas do tema"), ("waiting", "Aguardando outro tema"),
            ("review", "Revisão editorial"), ("excluded", "Fora da seleção"), ("recap", "Possíveis retomadas"))


def render_report(result: dict, planned_for: str) -> str:
    lines = ["# Radar IA — revisão editorial", "", f"Data: {planned_for}",
             f"Tema: {result['theme']}", "", "Simulação; nenhum episódio foi publicado.",
             "Títulos originais preservados. Tradução e roteiro ainda não gerados.", "",
             "## Diversidade das candidatas do tema", ""]
    sources = Counter(i.get("source_name", i.get("source", "Não informada")) for i in result["main"])
    lines.extend(f"- {name}: {count}" for name, count in sources.items())
    if len(sources) == 1:
        lines.extend(["", "Revisar diversidade: todas as candidatas do tema são da mesma fonte."])
    if not sources:
        lines.append("Nenhuma candidata do tema. Considerar edição curta ou revisão de alternativas.")
    for field, label in SECTIONS:
        lines.extend(["", f"## {label} ({len(result[field])})", ""])
        for item in result[field]:
            lines.extend([f"### {item['title']}", "", f"Fonte: {item.get('source_name', item.get('source', 'Não informada'))}",
                          f"Publicação: {item.get('published', 'Não informada')}",
                          f"URL: {item['url']}", "", f"Motivo: {item['reason']}", ""])
    lines.extend(["", "## Limites desta revisão", "",
                  "- Links precisam ser revalidados antes da produção.",
                  "- Regras lexicais não verificam fatos nem garantem adequação ao tema.",
                  "- Quantidade de candidatas não é quantidade final de notícias narradas.",
                  "- O limite de 10 minutos precisa ser medido no áudio final."])
    return "\n".join(lines) + "\n"
