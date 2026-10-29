"""Triagem editorial inicial, baseada em título/resumo, sem chamadas de LLM."""
from dataclasses import dataclass
import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def matches(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(r"(?<!\w)" + re.escape(normalize(term)) + r"(?!\w)", text) for term in terms)


@dataclass(frozen=True)
class Editorial:
    category: str
    priority: str
    reason: str


TECH = ("agent", "agents", "agentic", "agente", "agentes", "llm", "llms", "rag", "retrieval", "prompt caching", "evaluation", "avaliacao", "tool calling", "llm security", "seguranca de llm", "prompt injection")
APPLIED = ("developer", "developers", "sdk", "api", "security", "seguranca", "sagemaker", "infrastructure", "infraestrutura", "latency", "latencia", "fine-tuned", "fine-tuning", "machine learning", "computer vision", "cost", "custos")
MARKET = ("layoffs", "layoff", "demissoes", "demite", "demitindo", "hiring", "contratacoes", "contratando", "vagas", "workforce", "expansion", "expansao", "data center", "data centers", "datacenter", "datacenters", "skills demand", "competencias mais exigidas", "job cuts", "job market", "jobs report", "recruiting", "recrutamento", "investimento", "investment", "investments")
BUSINESS = ("ipo", "acquires", "acquisition", "aquisicao", "adquire", "compra empresa", "raises", "captacao", "funding round", "rodada de investimento", "valued at", "valuation", "latest round")
BUSINESS_PATTERNS = (r"\bbuys\s+.+\s+for\s+\$", r"\b(?:director|ceo|cto|executive)\b.+\b(?:leaves|joins|steps down)\b", r"\bstartup\b.+\blands\b")
PROMO = ("magic quadrant", "named a leader", "award", "awards", "premio", "premiacao")


def classify(title: str, summary: str) -> Editorial:
    """A ordem evita promover marketing ou mercado por menções incidentais a IA."""
    text = normalize(title + " " + summary)
    if matches(normalize(title), PROMO):
        return Editorial("institucional", "baixa", "Título centrado em prêmio ou reconhecimento; não priorizar sem novidade técnica comprovada.")
    headline = normalize(title)
    if matches(headline, MARKET + BUSINESS) or any(re.search(pattern, headline) for pattern in BUSINESS_PATTERNS):
        return Editorial("mercado", "complementar", "Título sinaliza trabalho, expansão, investimento, aquisição ou liderança; verificar contexto, região e período. Evento isolado não comprova tendência.")
    if matches(text, ("ice agents", "federal agents", "immigration agents", "agentes de imigracao", "real estate agents", "travel agents")) and not matches(text, ("ai agent", "ai agents", "artificial intelligence", "agentic", "llm", "machine learning")):
        return Editorial("revisao", "indefinida", "Agentes humanos ou profissionais não comprovam relação com agentes de IA.")
    if matches(text, TECH):
        return Editorial("tecnico", "alta", "Menciona agentes, LLMs, recuperação, avaliação ou segurança específica de LLMs.")
    if matches(text, APPLIED):
        return Editorial("tecnico", "media", "Menciona ferramentas gerais, segurança, aplicações, infraestrutura, desempenho ou custos; não basta para prioridade alta.")
    return Editorial("revisao", "indefinida", "Sem sinal suficiente nas regras; requer revisão, não descarte automático.")


def choose(items: list[dict], weak_day_threshold: int = 3, max_market: int = 2) -> list[dict]:
    """Recebe apenas candidatas já validadas. Não obriga quantidade mínima.

    Dia fraco: menos de três candidatas técnicas de prioridade alta/média.
    A duração final será controlada na etapa de roteiro/áudio, não aqui.
    """
    ranked = []
    for item in items:
        verdict = classify(item["title"], item.get("summary", ""))
        ranked.append(dict(item, editorial=verdict.__dict__))
    technical = [i for i in ranked if i["editorial"]["category"] == "tecnico"]
    technical.sort(key=lambda i: {"alta": 0, "media": 1}[i["editorial"]["priority"]])
    market = [i for i in ranked if i["editorial"]["category"] == "mercado"]
    return technical + (market[:max_market] if len(technical) < weak_day_threshold else [])
