"""Áudio PCM/WAV com duração medida e divisão sem cortar palavras."""
import io
import wave
from contextlib import closing


def chunks(text: str, limit: int = 2500) -> list[str]:
    words = text.split()
    if not words:
        raise ValueError("Narração vazia")
    result, current = [], ""
    for word in words:
        if len(word) > limit:
            raise ValueError("Palavra excede tamanho permitido por trecho")
        candidate = f"{current} {word}" if current else word
        if len(candidate) > limit:
            result.append(current)
            current = word
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def wav_from_pcm(pcm: bytes, max_seconds: int = 600) -> tuple[bytes, float]:
    if not pcm or len(pcm) % 2:
        raise ValueError("PCM vazio ou desalinhado para amostras de 16 bits")
    seconds = len(pcm) / (16000 * 2)
    if seconds > max_seconds:
        raise ValueError(f"Áudio tem {seconds:.1f}s; excede {max_seconds}s. Encurtar roteiro; não publicar.")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm)
    return output.getvalue(), seconds


def make_audio(polly, text: str, voice: str = "Camila", engine: str = "generative", *, english_terms: list[str] | None = None, use_ssml: bool = True) -> tuple[bytes, dict]:
    from .speech_markup import speech_chunks, bilingual_ssml, RENDERER_VERSION
    parts = speech_chunks(text) if use_ssml else chunks(text)
    requests = [bilingual_ssml(part, english_terms or []) for part in parts] if use_ssml else parts
    if any(len(part) > 6000 for part in requests):
        raise ValueError("SSML excede limite total por requisição; reduzir trechos antes de gerar")
    pcm = bytearray()
    for part in requests:
        response = polly.synthesize_speech(Text=part, TextType="ssml" if use_ssml else "text", OutputFormat="pcm",
                    SampleRate="16000", VoiceId=voice, Engine=engine, LanguageCode="pt-BR")
        with closing(response["AudioStream"]) as stream:
            data = stream.read()
        if not data or len(data) % 2:
            raise ValueError("Polly retornou trecho PCM vazio ou inválido")
        pcm.extend(data)
    wav, seconds = wav_from_pcm(bytes(pcm))
    return wav, {"duration_seconds": seconds, "duration_verified": True, "chunks": len(parts),
                 "submitted_characters": sum(map(len, parts)), "voice": voice, "engine": engine,
                 "text_type": "ssml" if use_ssml else "text", "english_terms": english_terms or [],
                 "renderer": RENDERER_VERSION if use_ssml else "plain-text",
                 "status": "aguarda_escuta", "language": "pt-BR", "format": "wav", "sample_rate": 16000}
