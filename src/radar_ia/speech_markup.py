"""Marcação SSML conservadora para testes de português com termos ingleses."""
import re
from html import escape

RENDERER_VERSION = 'bilingual-pauses-v2'
SENTENCE_PAUSE_MS = 450
PARAGRAPH_PAUSE_MS = 950
ABBREVIATIONS = ('sr.', 'sra.', 'dr.', 'dra.', 'prof.', 'profa.', 'etc.', 'vs.', 'e.g.', 'i.e.', 'u.s.', 'u.k.', 'ex.', 'art.', 'fig.')


def sentences(paragraph: str) -> list[str]:
    """Separa frases sem tratar decimal ou abreviação conhecida como fim."""
    result, start = [], 0
    for boundary in re.finditer(r'(?<=[.!?])\s+', paragraph):
        prefix = paragraph[start:boundary.start()]
        if prefix.split() and prefix.split()[-1].casefold() in ABBREVIATIONS:
            continue
        result.append(prefix)
        start = boundary.end()
    if paragraph[start:].strip():result.append(paragraph[start:])
    return result


def bilingual_ssml(text: str, terms: list[str]) -> str:
    terms = sorted({term.strip() for term in terms if term.strip()}, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(term) for term in terms) + r")(?!\w)", re.I) if terms else None
    paragraphs = []
    for paragraph in text.split("\n\n"):
        if not paragraph.strip():
            continue
        rendered = []
        for sentence in sentences(paragraph.strip()):
            pieces, position = [], 0
            if pattern:
                for match in pattern.finditer(sentence):
                    pieces.append(escape(sentence[position:match.start()]))
                    pieces.append('<lang xml:lang="en-US">' + escape(match.group()) + '</lang>')
                    position = match.end()
            pieces.append(escape(sentence[position:]))
            rendered.append('<s>' + ''.join(pieces) + '</s>')
        paragraphs.append('<p>' + f'<break time="{SENTENCE_PAUSE_MS}ms"/>'.join(rendered) + '</p>' + f'<break time="{PARAGRAPH_PAUSE_MS}ms"/>')
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
