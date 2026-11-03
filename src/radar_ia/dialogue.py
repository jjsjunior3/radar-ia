"""Piloto local de diálogo; não altera roteiro, catálogo ou publicação de produção."""
import hashlib
import json
import math
import sys
from array import array
from contextlib import closing
from pathlib import Path
from typing import Literal
from pydantic import Field
from .script import StrictModel
from .audio import wav_from_pcm
from .speech_markup import bilingual_ssml,PARAGRAPH_PAUSE_MS

VOICES={'leo':'Leo','camila':'Camila','carolina':'Carolina'}
RENDERER='dialogue-pilot-v1'
GAP_MS=380


class Turn(StrictModel):
    speaker:Literal['leo','camila','carolina']
    text:str=Field(min_length=1,max_length=1600)
    english_terms:list[str]=Field(default_factory=list,max_length=4)


class Pilot(StrictModel):
    is_demo:Literal[True]
    turns:list[Turn]=Field(min_length=2,max_length=12)


def validate_pilot(payload):
    pilot=Pilot.model_validate(payload)
    speakers={turn.speaker for turn in pilot.turns}
    if len(speakers)!=2 or 'leo' not in speakers:raise ValueError('Piloto exige as duas vozes: Leo e uma convidada')
    if sum(len(turn.text.split()) for turn in pilot.turns)>220:raise ValueError('Encurte o piloto antes de gerar')
    for turn in pilot.turns:
        if not turn.text.strip() or any(not term.strip() or term.casefold() not in turn.text.casefold() for term in turn.english_terms):raise ValueError('Texto ou termo inglês inválido')
        if len(turn_ssml(turn))>6000:raise ValueError('SSML acima do limite; encurte a fala antes de gerar')
    return pilot


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)


def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(data):return hashlib.sha256(data).hexdigest()


def turn_ssml(turn):
    text=bilingual_ssml(turn.text,turn.english_terms)
    ending=f'<break time="{PARAGRAPH_PAUSE_MS}ms"/></speak>'
    # A pausa entre locutores é montada no PCM, sem acumular a pausa final do parágrafo.
    if text.endswith(ending):text=text[:-len(ending)]+'</speak>'
    if turn.speaker=='carolina':text=text.replace('<break time="450ms"/>',' ')
    return text


def normalize_pcm(pcm):
    if not pcm or len(pcm)%2:raise ValueError('PCM inválido')
    samples=array('h');samples.frombytes(pcm)
    if sys.byteorder!='little':samples.byteswap()
    peak=max(abs(value) for value in samples)
    rms=math.sqrt(sum(value*value for value in samples)/len(samples))
    if not peak or rms<1:raise ValueError('Trecho sem sinal audível; revisar antes de repetir')
    gain=min(1.5,max(.6,3500/rms),30000/peak)
    normalized=array('h',(round(value*gain) for value in samples))
    if sys.byteorder!='little':normalized.byteswap()
    return normalized.tobytes(),round(gain,4)


def synthesize_pilot(polly,payload,folder):
    pilot=validate_pilot(payload);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    config={'script':pilot.model_dump(),'voices':{turn.speaker:VOICES[turn.speaker] for turn in pilot.turns},'engine':'generative','renderer':RENDERER,'gap_ms':GAP_MS}
    fingerprint=digest(json.dumps(config,sort_keys=True,ensure_ascii=False).encode())
    manifest=folder/'manifest.json';audio=folder/'piloto.wav';metadata=folder/'metadata.json'
    if manifest.exists():
        if read_json(manifest)['digest']!=fingerprint:raise ValueError('Roteiro/configuração mudou; use uma nova pasta de revisão')
    else:write_json(manifest,{'digest':fingerprint,'config':config})
    if audio.exists():
        saved=read_json(metadata)
        if digest(audio.read_bytes())!=saved['audio_sha256']:raise ValueError('Áudio alterado')
        return audio,saved
    montage=bytearray();results=[]
    for index,turn in enumerate(pilot.turns):
        ssml=turn_ssml(turn);voice=VOICES[turn.speaker]
        turn_hash=digest(json.dumps({'text':ssml,'voice':voice,'renderer':RENDERER},sort_keys=True).encode())
        marker=folder/'turns'/f'{index:02}.json';pcm_file=marker.with_suffix('.pcm')
        previous=read_json(marker) if marker.exists() else None
        if previous and previous.get('digest')!=turn_hash:raise ValueError('Trecho mudou; não reaproveitar tentativa')
        if pcm_file.exists():
            raw=pcm_file.read_bytes()
            if not previous or digest(raw)!=previous.get('sha256'):raise ValueError('Trecho sem integridade válida')
        else:
            if previous:raise ValueError('Chamada iniciada sem resposta salva; não repetir cobrança automaticamente')
            write_json(marker,{'digest':turn_hash,'status':'request_started','voice':voice})
            response=polly.synthesize_speech(Text=ssml,TextType='ssml',VoiceId=voice,Engine='generative',LanguageCode='pt-BR',OutputFormat='pcm',SampleRate='16000')
            with closing(response['AudioStream']) as stream:raw=stream.read()
            if not raw or len(raw)%2:raise ValueError('PCM retornado inválido')
            temporary=pcm_file.with_suffix('.pcm.tmp');temporary.write_bytes(raw);temporary.replace(pcm_file)
            write_json(marker,{'digest':turn_hash,'status':'complete','sha256':digest(raw),'voice':voice,'request_characters':response.get('RequestCharacters')})
        normalized,gain=normalize_pcm(raw)
        if index:montage.extend(bytes(16000*2*GAP_MS//1000))
        montage.extend(normalized);results.append({'speaker':turn.speaker,'voice':voice,'gain':gain,'seconds':len(raw)/32000})
    wav,seconds=wav_from_pcm(bytes(montage),max_seconds=120)
    saved={'renderer':RENDERER,'duration_seconds':seconds,'duration_verified':True,'audio_sha256':digest(wav),'turns':results,'publication':'local_only','is_demo':True}
    write_json(metadata,saved);temporary=audio.with_suffix('.wav.tmp');temporary.write_bytes(wav);temporary.replace(audio)
    return audio,saved
