"""Marcação SSML conservadora para testes de português com termos ingleses."""
import re
from html import escape


def bilingual_ssml(text: str, terms: list[str]) -> str:
    terms = sorted({term.strip() for term in terms if term.strip()}, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(term) for term in terms) + r")(?!\w)", re.I) if terms else None
    paragraphs = []
    for paragraph in text.split("\n\n"):
        if not paragraph.strip():
            continue
        pieces, position = [], 0
        if pattern:
            for match in pattern.finditer(paragraph):
                pieces.append(escape(paragraph[position:match.start()]))
                pieces.append('<lang xml:lang="en-US">' + escape(match.group()) + '</lang>')
                position = match.end()
        pieces.append(escape(paragraph[position:]))
        paragraphs.append('<p>' + ''.join(pieces) + '</p>')
    return '<speak>' + ''.join(paragraphs) + '</speak>'


def speech_chunks(text: str, limit: int = 2500) -> list[str]:
    """Preserva parágrafos e prefere cortes entre frases, não no meio delas."""
    units = []
    for paragraph in text.split('\n\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= limit:
            units.append(paragraph)
            continue
        for sentence in re.split(r'(?<=[.!?])\s+', paragraph):
            if len(sentence) <= limit:
                units.append(sentence)
            else:
                from .audio import chunks
                units.extend(chunks(sentence, limit))
    if not units:
        raise ValueError('Narração vazia')
    result, current = [], ''
    for unit in units:
        candidate = current + '\n\n' + unit if current else unit
        if len(candidate) > limit:
            result.append(current)
            current = unit
        else:
            current = candidate
    if current:
        result.append(current)
    return result
