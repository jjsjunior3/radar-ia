import io
import wave
from types import SimpleNamespace
import pytest
from radar_ia.audio import chunks, wav_from_pcm, make_audio


def test_chunks_preserve_words():
    text = "alpha beta gamma delta"
    parts = chunks(text, 10)
    assert " ".join(parts) == text
    assert all(len(part) <= 10 for part in parts)


def test_empty_text_rejected():
    with pytest.raises(ValueError): chunks("  ")


def test_actual_wav_duration():
    data, duration = wav_from_pcm(b"\0\0" * 16000)
    assert duration == 1
    with wave.open(io.BytesIO(data)) as wav:
        assert wav.getnframes() == 16000
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1


def test_over_limit_is_rejected_not_truncated():
    with pytest.raises(ValueError, match="excede"):
        wav_from_pcm(b"\0\0" * 16001, max_seconds=1)


def test_multiple_polly_chunks_and_stream_closed():
    calls, streams = [], []
    def synthesize(**kwargs):
        calls.append(kwargs)
        stream = io.BytesIO(b"\0\0" * 16000)
        streams.append(stream)
        return {"AudioStream": stream}
    _, meta = make_audio(SimpleNamespace(synthesize_speech=synthesize), "palavra " * 500)
    assert len(calls) == 2
    assert meta["duration_seconds"] == 2
    assert all(stream.closed for stream in streams)
    import xml.etree.ElementTree as ET
    assert all(len("".join(ET.fromstring(call["Text"]).itertext())) <= 2500 for call in calls)
    assert all(len(call["Text"]) <= 6000 for call in calls)


def test_default_audio_matches_selected_engine_and_language_markup():
    calls=[]
    def synthesize(**kwargs):
        calls.append(kwargs)
        return {'AudioStream': io.BytesIO(b'\0\0' * 1600)}
    _,meta=make_audio(SimpleNamespace(synthesize_speech=synthesize),'Training loop é ciclo de treinamento.',english_terms=['training loop'])
    assert calls[0]['Engine']=='generative'
    assert calls[0]['TextType']=='ssml'
    assert '<lang xml:lang="en-US">Training loop</lang>' in calls[0]['Text']
    assert meta['duration_verified'] is True
