"""Private episode notes, read from the published script and sources."""

import json
from urllib.parse import urlsplit

MAX_BYTES = 1_000_000


def safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
        ):
            return value
    except ValueError:
        pass
    return None


def build_notes(episode, script, sources):
    if not isinstance(script, dict) or not isinstance(sources, list):
        raise TypeError("Detalhes do episódio incompatíveis")
    stories = script.get("stories", [])
    if not isinstance(stories, list):
        raise TypeError("Pautas incompatíveis")
    by_id = {item.get("id"): item for item in sources if isinstance(item, dict)}
    topics = []
    for story in stories:
        source = by_id.get(story["news_id"], {})
        narration = story["narration_pt"]
        turns = [{"speaker": "Narração", "text": narration}]
        question, _, answer = narration.partition("\n")
        if (
            episode.get("format") == "interview"
            and question.rstrip().endswith("?")
            and answer.strip()
        ):
            turns = [
                {"speaker": "Apresentador", "text": question},
                {"speaker": "Convidada", "text": answer.strip()},
            ]
        topics.append(
            {
                "id": story["news_id"],
                "title": story["title_pt"],
                "summary": story["summary_pt"],
                "turns": turns,
                "source": {
                    "name": source.get("source", ""),
                    "title": source.get("title", story["title_pt"]),
                    "published": source.get("published"),
                    "url": safe_url(source.get("url")),
                },
            }
        )
    return {
        "episode_id": episode["id"],
        "title": episode["title"],
        "intro": script.get("intro_pt", ""),
        "topics": topics,
        "outro": script.get("outro_pt", ""),
        "glossary": [
            {
                "term": term["term_en"],
                "explanation": term["explanation_pt"],
                "news_ids": term.get("news_ids", []),
            }
            for term in script.get("glossary", [])
        ],
    }


def read_notes(s3, bucket, prefix, episode):
    base = f"{prefix.strip('/')}/episodes/{episode['id']}/"

    def asset(field, name):
        if episode.get(field) != base + name:
            raise ValueError("Arquivo fora da pasta do episódio")
        response = s3.get_object(Bucket=bucket, Key=base + name)
        with response["Body"] as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Arquivo do episódio acima do limite")
        return json.loads(raw)

    return build_notes(
        episode,
        asset("script_key", "roteiro.json"),
        asset("sources_key", "fontes.json"),
    )
