"""Coleta compartilhada pelo exemplo e pelo fluxo diário."""
import calendar
from datetime import datetime, timedelta, timezone
from collections import Counter
import httpx
from .news import Fetcher, canonical, duplicate, clean


def clean_summary(text):
    return clean(text)


def check_date(entry: dict, now: datetime, hours: int = 48) -> tuple[str, datetime | None]:
    """Valida publicação; atualização não substitui data ausente."""
    stamp = entry.get("published_parsed")
    if not stamp:
        return "sem data de publicação válida", None
    try:
        published = datetime.fromtimestamp(calendar.timegm(stamp), timezone.utc)
    except (ValueError, OverflowError, TypeError, OSError):
        return "sem data de publicação válida", None
    if published > now:
        return "data futura", published
    if now - published > timedelta(hours=hours):
        return "mais antiga que a janela", published
    return "dentro da janela", published


def check_candidate(news: dict, accepted: list[dict], fetch) -> tuple[str, dict | None]:
    """Normaliza, verifica a página e compara com candidatas desta execução."""
    title = clean_summary(news.get("title", ""))
    if not title:
        return "título ausente", None
    try:
        item = {"title": title, "url": canonical(news.get("link", ""))}
        if any(duplicate(item, other) for other in accepted):
            return "duplicada por URL ou título semelhante", None
        _, item["url"] = fetch(item["url"])
        if any(duplicate(item, other) for other in accepted):
            return "duplicada após redirecionamento", None
    except httpx.HTTPStatusError as exc:
        return f"página retornou HTTP {exc.response.status_code}", None
    except httpx.HTTPError:
        return "falha de conexão com a página", None
    except ValueError as exc:
        return f"URL ou página rejeitada: {exc}", None
    return "candidata válida", item



def collect_sources(sources, now, since, fetcher_factory=Fetcher):
    import feedparser  # Carregar somente durante coleta RSS.
    accepted,rejected,results=[],[],[]
    hours=(now-since).total_seconds()/3600
    if hours<=0:raise ValueError('Janela de coleta inválida')
    for source in sources:
        fetcher=fetcher_factory(source['domains'])
        result={'name':source['name'],'url':source['url'],'status':'ok','accepted':0,'entries':0}
        results.append(result)
        try:
            try:raw,_=fetcher.get(source['url'])
            except (httpx.HTTPError,ValueError) as exc:
                result.update(status='erro',error=type(exc).__name__)
                continue
            feed=feedparser.parse(raw)
            result['entries']=len(feed.entries)
            if not feed.entries:result['status']='sem entradas'
            if feed.bozo:result['warning']='XML com irregularidade'
            for entry in feed.entries[:100]:
                status,published=check_date(entry,now,hours)
                if status!='dentro da janela':
                    rejected.append({'title':entry.get('title',''),'source':source['url'],'reason':status})
                    continue
                status,item=check_candidate(entry,accepted,fetcher.get)
                if item is None:
                    rejected.append({'title':entry.get('title',''),'source':source['url'],'reason':status})
                    continue
                item.update(summary=clean(entry.get('summary','')),published=published.isoformat(),source=source['url'],source_name=source['name'])
                accepted.append(item);result['accepted']+=1
        finally:fetcher.close()
    if not any(r['status']=='ok' for r in results):raise ValueError('Todas as fontes falharam ou não trouxeram entradas; não avançar a edição.')
    return {'schema_version':2,'collected_at':now.isoformat(),'window_start':since.isoformat(),'sources':results,'candidates':accepted,'rejected':rejected}
