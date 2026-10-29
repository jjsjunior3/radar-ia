from radar_ia.editorial import classify, choose


def test_human_agents_do_not_count_as_ai_agents():
    assert classify('Bluesky blocks links to leaked DHS employee data','Identifies ICE agents working for Homeland Security').category=='revisao'
    assert classify('Software for travel agents','AI agents automate booking').category=='tecnico'


def test_funding_titles_remain_market_even_with_agents():
    assert classify('Wabi, the AI agent, now valued at $1.25B after latest round','').category=='mercado'
    assert classify('Agent identity startup Mintive lands Cowboy Ventures','enterprise agents').category=='mercado'


def test_promotion_not_promoted_by_ai_mention():
    assert classify("AWS named a Leader in Magic Quadrant", "AI agents").priority == "baixa"


def test_market_not_promoted_by_ai_mention():
    assert classify("Big tech hiring AI engineers", "LLM agents").category == "mercado"


def test_word_boundaries_avoid_ai_substrings():
    assert classify("Retail results", "A fair bargain").category == "revisao"


def test_portuguese_accents():
    assert classify("Demissões em empresa", "").category == "mercado"


def test_technical():
    assert classify("Prompt caching for agents", "").priority == "alta"


def test_weak_day_adds_market_but_not_promotion():
    items = [{"title": t} for t in ["LLM agents", "Tech hiring", "Tech layoffs", "Tech expansion", "Company awards"]]
    result = choose(items)
    assert len(result) == 3
    assert [i["editorial"]["category"] for i in result] == ["tecnico", "mercado", "mercado"]


def test_strong_day_omits_market():
    items = [{"title": t} for t in ["LLM tools", "RAG retrieval", "SDK update", "Tech hiring"]]
    assert len(choose(items)) == 3


def test_empty_day_stays_empty():
    assert choose([]) == []


def test_generic_sdk_is_medium():
    assert classify("Fleet-wide computer vision with SageMaker SDK v3", "Reference architecture").priority == "media"


def test_api_alone_is_medium_but_llm_api_is_high():
    assert classify("New API for developers", "").priority == "media"
    assert classify("New API for LLM agents", "").priority == "alta"


def test_generic_security_is_medium():
    assert classify("Security update", "Network protection").priority == "media"
    assert classify("Prompt injection protection", "").priority == "alta"


def test_market_report_is_complementary_not_technical():
    result = classify("New jobs report tracks technology hiring", "AI skills demand")
    assert result.category == "mercado"
    assert result.priority == "complementar"


import pytest


@pytest.mark.parametrize("title", [
    "Guidewire buys Hyperexponential for $1.7B in cash",
    "VCs will make billions on Anthropic’s IPO",
    "Re:Build raises $2.1B",
    "Meta AI director Rohit Patel leaves to take on Microsoft Office",
    "Voters in Texas hate data centers",
])
def test_business_headline_overrides_technical_summary(title):
    assert classify(title, "LLM agents and SDK tools").category == "mercado"


def test_technical_headline_not_market_from_summary_mention():
    assert classify("RAG retrieval evaluation", "Our investment in tools").category == "tecnico"
