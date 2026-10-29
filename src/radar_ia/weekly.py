"""Grade semanal e planejamento preliminar; não publica episódios."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .editorial import classify, matches, normalize
from .news import canonical

GRADE = {
    0: "Panorama da semana",
    1: "Carreira e mercado",
    2: "Caixa de ferramentas",
    3: "Engenharia de IA",
    4: "Fechamento da semana",
}
TOOLS = ("sdk", "api", "library", "biblioteca", "framework", "tool", "tools", "ferramentas")


def tool_signals(title: str, summary: str) -> list[str]:
    """Exige termo no título ou expressão específica no resumo.

    Uma menção incidental a tools em um resumo não define o tema.
    """
    title_text = normalize(title)
    hits = [term for term in TOOLS if matches(title_text, (term,))]
    specific = ("sdk", "api", "library", "biblioteca", "framework", "developer tool", "developer tools")
    summary_text = normalize(summary)
    hits.extend(term for term in specific if term not in hits and matches(summary_text, (term,)))
    return hits


def merge_queue(previous: list[dict], incoming: list[dict]) -> list[dict]:
    """Mesma URL mantém estado editorial, mas atualiza metadados da coleta."""
    merged = {canonical(item["url"]): dict(item) for item in previous}
    for item in incoming:
        key = canonical(item["url"])
        used = merged.get(key, {}).get("used_in", [])
        merged[key] = dict(item, used_in=used)
    return list(merged.values())


def plan(items: list[dict], now: datetime, max_age_days: int = 7) -> dict:
    if now.tzinfo is None:
        raise ValueError("Use uma data com fuso horário")
    day = now.astimezone(ZoneInfo("America/Sao_Paulo")).weekday()
    result = {"theme": GRADE.get(day, "Sem edição regular"), "main": [],
              "waiting": [], "review": [], "excluded": [], "recap": [], "max_audio_seconds": 600}
    for item in items:
        try:
            date = datetime.fromisoformat(item["published"])
            if date.tzinfo is None:
                raise ValueError("Data sem fuso")
        except (KeyError, ValueError, TypeError):
            result["excluded"].append(dict(item, reason="Publicação ausente ou inválida; recoletar"))
            continue
        age = now - date
        if age < timedelta(0) or age > timedelta(days=max_age_days):
            result["excluded"].append(dict(item, reason="Data futura ou mais antiga que a retenção editorial"))
            continue
        verdict = classify(item["title"], item.get("summary", ""))
        if item.get("used_in"):
            target = "recap" if day == 4 else "excluded"
            result[target].append(dict(item, reason="Já usada; só retomar com enquadramento explícito e revisão"))
            continue
        if verdict.category in ("institucional", "revisao"):
            result["review"].append(dict(item, reason=verdict.reason))
            continue
        signals = tool_signals(item["title"], item.get("summary", ""))
        fits = (day in (0, 4) or
                day == 1 and verdict.category == "mercado" or
                day == 2 and verdict.category == "tecnico" and bool(signals) or
                day == 3 and verdict.category == "tecnico" and verdict.priority == "alta")
        target = "main" if fits else "waiting"
        if not fits:
            reason = f"Categoria {verdict.category}, prioridade {verdict.priority}: sem sinal suficiente para {GRADE.get(day, 'fim de semana')}."
        elif day == 2:
            reason = "Ferramentas: termos encontrados — " + ", ".join(signals) + ". " + verdict.reason
        elif day == 1:
            reason = "Tema de carreira/mercado. " + verdict.reason
        elif day == 3:
            reason = "Engenharia de IA: prioridade alta. " + verdict.reason
        else:
            reason = "Panorama/fechamento: candidata ainda não usada. " + verdict.reason
        result[target].append(dict(item, reason=reason))
    return result
