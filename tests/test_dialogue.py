import io,math,json,copy,wave
from unittest.mock import Mock
import pytest
from radar_ia.dialogue import synthesize_pilot,normalize_pcm,validate_pilot,turn_ssml,Turn
from array import array


def sample():
    return {'is_demo':True,'turns':[{'speaker':'leo','text':'Este é um piloto com vozes sintéticas.'},{'speaker':'camila','text':'Vamos conversar sobre um exemplo.'}]}


def pcm():return array('h',(int(2500*math.sin(i/10)) for i in range(1600))).tobytes()


def test_cast_order_pause_duration_and_cached_generation(tmp_path):
    polly=Mock();polly.synthesize_speech.side_effect=lambda **kw:{'AudioStream':io.BytesIO(pcm()),'RequestCharacters':20}
    audio,metadata=synthesize_pilot(polly,sample(),tmp_path)
    assert [call.kwargs['VoiceId'] for call in polly.synthesize_speech.call_args_list]==['Leo','Camila']
    assert metadata['duration_seconds']==pytest.approx(.58)
    with wave.open(str(audio)) as wav:assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
    synthesize_pilot(polly,sample(),tmp_path);assert polly.synthesize_speech.call_count==2
    changed=sample();changed['turns'][0]['text']='Mudou depois da geração.'
    with pytest.raises(ValueError,match='mudou'):synthesize_pilot(polly,changed,tmp_path)
    assert polly.synthesize_speech.call_count==2


def test_unknown_paid_result_blocks_repeat(tmp_path):
    polly=Mock();polly.synthesize_speech.side_effect=TimeoutError()
    with pytest.raises(TimeoutError):synthesize_pilot(polly,sample(),tmp_path)
    with pytest.raises(ValueError,match='não repetir'):synthesize_pilot(polly,sample(),tmp_path)
    polly.synthesize_speech.assert_called_once()


def test_pcm_integrity_and_silence_guard():
    normalized,gain=normalize_pcm(array('h',[32767,-32768]*10).tobytes())
    assert max(abs(v) for v in array('h',normalized))<=30000
    with pytest.raises(ValueError):normalize_pcm(bytes(3200))
    with pytest.raises(ValueError):normalize_pcm(b'x')


def test_voice_allowlist_and_both_speakers_required():
    payload=sample();payload['turns'][1]['speaker']='unknown'
    with pytest.raises(ValueError):validate_pilot(payload)
    payload=sample();payload['turns'][1]['speaker']='leo'
    with pytest.raises(ValueError,match='duas vozes'):validate_pilot(payload)


def test_english_markup_without_accumulated_final_pause():
    ssml=turn_ssml(Turn(speaker='camila',text='Human in the loop é revisão humana.',english_terms=['human in the loop']))
    assert '<lang xml:lang="en-US">Human in the loop</lang>' in ssml
    assert not ssml.endswith('<break time="950ms"/></speak>')


def test_invalid_ssml_budget_is_blocked_before_any_paid_request(tmp_path):
    payload=sample();payload['turns'][0]['text']='a. '*210
    polly=Mock()
    with pytest.raises(ValueError,match='SSML'):synthesize_pilot(polly,payload,tmp_path)
    polly.synthesize_speech.assert_not_called()
