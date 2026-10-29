import calendar
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


def clean(text):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", text))).strip()


def canonical(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError("URL deve ser HTTPS pública sem credenciais")
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit(("https", p.hostname.lower(), p.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


@dataclass(frozen=True)
class News:
    title: str
    url: str
    published: str
    summary: str
    source: str

    def data(self):
        return asdict(self)


class Fetcher:
    """Allowlist exata, inclusive em cada redirecionamento; limite de bytes."""
    def __init__(self, domains):
        self.domains = set(domains)
        self.client = httpx.Client(timeout=20, headers={"User-Agent": "RadarIA/0.1"})

    def get(self, url):
        for _ in range(6):
            # Valida sem reescrever o endereço de transporte: a barra pode
            # ser necessária ao servidor. Normalização é só para comparação.
            canonical(url)
            if urlsplit(url).hostname.lower() not in self.domains:
                raise ValueError("Domínio fora da allowlist")
            with self.client.stream("GET", url) as r:
                if r.is_redirect:
                    url = str(r.url.join(r.headers["location"]))
                    continue
                r.raise_for_status()
                if not any(t in r.headers.get("content-type", "").lower() for t in ("xml", "rss", "atom", "html")):
                    raise ValueError("Tipo de conteúdo inesperado")
                body = bytearray()
                for chunk in r.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise ValueError("Resposta acima de 2 MB")
                return bytes(body), canonical(str(r.url))
        raise ValueError("Redirecionamentos excessivos")

    def close(self):
        self.client.close()


def collect(feeds, fetch, now, hours, keywords):
    import feedparser  # Apenas coleta RSS; worker de voz não precisa deste pacote.
    candidates, errors = [], []
    for feed in feeds:
        try:
            raw, _ = fetch(feed)
            parsed = feedparser.parse(raw)
            for e in parsed.entries[:100]:
                try:
                    # updated não comprova publicação: publicação ausente é rejeitada.
                    stamp = e.get("published_parsed")
                    if not stamp:
                        continue
                    date = datetime.fromtimestamp(calendar.timegm(stamp), timezone.utc)
                    if not now - timedelta(hours=hours) <= date <= now:
                        continue
                    title, summary = clean(e.get("title", "")), clean(e.get("summary", ""))[:2400]
                    if not title or not summary or not any(k.casefold() in (title + " " + summary).casefold() for k in keywords):
                        continue
                    candidates.append(News(title, canonical(e.link), date.isoformat(), summary, feed))
                except (ValueError, AttributeError, OverflowError):
                    continue
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"Falha no feed {feed}: {type(exc).__name__}")
    return candidates, errors


def title_key(title):
    return re.sub(r"[^\w]+", " ", title.casefold()).strip()


def duplicate(a, b):
    return a["url"] == b["url"] or SequenceMatcher(None, title_key(a["title"]), title_key(b["title"])).ratio() >= .86


def curate(candidates, history, fetch):
    selected = []
    for item in sorted(candidates, key=lambda n: n.published, reverse=True):
        if any(duplicate(item.data(), other) for other in history + [n.data() for n in selected]):
            continue
        try:
            _, final = fetch(item.url)
        except (httpx.HTTPError, ValueError):
            continue
        item = News(item.title, final, item.published, item.summary, item.source)
        if any(duplicate(item.data(), other) for other in history + [n.data() for n in selected]):
            continue
        selected.append(item)
        if len(selected) == 5:
            return selected
    raise ValueError(f"Somente {len(selected)} notícias válidas inéditas; são necessárias exatamente 5")
