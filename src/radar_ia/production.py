"""Produção local acompanhada: checkpoints e revisão antes de voz/publicação.

O callback persist salva checkpoints antes de iniciar chamadas pagas.
"""
import hashlib
import json
import io
import wave
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .audio import wav_from_pcm
from .brief import build_brief
from .collection import collect_sources
from .news import canonical, duplicate, Fetcher
from .review import render_report
from .script import validate_script, spoken_text, render_script, assemble_script
from .speech_markup import speech_chunks,bilingual_ssml,RENDERER_VERSION
from .weekly import plan,merge_queue
from .windows import collection_start


def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def read_json(path,default=None):
    return json.loads(Path(path).read_text(encoding='utf-8-sig')) if Path(path).exists() else default


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


class Production:
    def __init__(self,output,now=None,*,day=None,persist=None):
        self.now=now or datetime.now(timezone.utc)
        if self.now.tzinfo is None:raise ValueError('Horário com fuso obrigatório')
        self.day=day or self.now.astimezone(ZoneInfo('America/Sao_Paulo')).date().isoformat()
        self.output=Path(output)
        self.folder=self.output/'production'/self.day
        self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'checkpoint.json'
        self.state=read_json(self.path,{'date':self.day,'stage':'new'})
        self.global_path=self.output/'production'/'editorial-state.json'
        self.persist=persist or (lambda: None)

    def save_json(self,path,data):
        write_json(path,data)
        self.persist()

    def stage(self,name,**values):
        self.state.update(stage=name,updated_at=datetime.now(timezone.utc).isoformat(),**values)
        self.save_json(self.path,self.state)

    def prepare(self,sources,catalog,collector=collect_sources):
        if self.now.astimezone(ZoneInfo('America/Sao_Paulo')).weekday()>4:
            raise ValueError('Sem edição regular no fim de semana')
        if self.day!=self.now.astimezone(ZoneInfo('America/Sao_Paulo')).date().isoformat():
            raise ValueError('Coleta permitida apenas para a edição de hoje')
        existing=next((e for e in catalog['episodes'] if e['date']==self.day),None)
        if existing and self.state['stage'] not in ('publish_in_progress','completed'):
            self.stage('completed',episode_id=existing['id'],existing_catalog_entry=True)
            return self.state
        if self.state['stage']!='new':return self.state
        shared=read_json(self.global_path,{'queue':[],'last_covered_at':None})
        since,reason=collection_start(self.now,shared['last_covered_at'])
        report=collector(sources,self.now,since)
        queue=merge_queue(shared['queue'],report['candidates'])
        used={canonical(url):e['id'] for e in catalog['episodes'] for url in e.get('news_urls',[])}
        for item in queue:
            if canonical(item['url']) in used:
                item['used_in']=list(set(item.get('used_in',[])+[used[canonical(item['url'])]]))
        previously_used=[item for item in queue if item.get('used_in')]
        for item in queue:
            if not item.get('used_in'):
                match=next((old for old in previously_used if duplicate(item,old)),None)
                if match:item['used_in']=list(match['used_in'])
        agenda=plan(queue,self.now);agenda['planned_for']=self.now.isoformat()
        brief=build_brief(agenda)
        brief['collection_cutoff']=report['collected_at']
        write_json(self.folder/'coleta.json',report)
        write_json(self.folder/'fila-editorial.json',queue)
        write_json(self.folder/'plano-editorial.json',agenda)
        write_json(self.folder/'briefing.json',brief)
        (self.folder/'pauta.md').write_text(render_report(agenda,self.now.isoformat()),encoding='utf-8')
        self.stage('prepared' if brief['news'] else 'no_content',window_reason=reason)
        return self.state

    def draft(self,generate):
        if (self.folder/'roteiro.json').exists():
            brief,script,text=self.script_bundle()
            if self.state['stage'] in ('prepared','draft_in_progress','draft_failed'):
                (self.folder/'narracao.txt').write_text(text,encoding='utf-8')
                (self.folder/'revisao.md').write_text(render_script(script,brief),encoding='utf-8')
                self.stage('awaiting_script_review')
            return script.model_dump()
        if self.state['stage'] not in ('prepared','draft_in_progress','draft_failed'):
            raise ValueError('Prepare uma pauta com conteúdo antes do roteiro')
        brief=read_json(self.folder/'briefing.json')
        raw_path=self.folder/'resposta-original.json'
        if raw_path.exists():
            raw=read_json(raw_path)
            if not raw.get('choices') or raw['choices'][0].get('finish_reason')!='stop':
                raise ValueError('Resposta salva incompleta; revisar antes de autorizar outra chamada paga')
            if raw['choices'][0]['message'].get('refusal'):
                raise ValueError('Resposta recusada pelo provedor')
            script,changes=assemble_script(json.loads(raw['choices'][0]['message']['content']),brief)
            metadata={'status':'recuperado_localmente','local_changes':changes}
        else:
            if self.state['stage']!='prepared':
                raise ValueError('Tentativa anterior sem resposta salva: resultado incerto. Não repetir a chamada paga automaticamente.')
            self.stage('draft_in_progress')
            try:script,metadata=generate(brief,lambda raw:self.save_json(raw_path,raw))
            except Exception:
                self.stage('draft_failed');raise
        write_json(self.folder/'roteiro.json',script.model_dump())
        write_json(self.folder/'metadados-llm.json',metadata)
        (self.folder/'narracao.txt').write_text(spoken_text(script),encoding='utf-8')
        (self.folder/'revisao.md').write_text(render_script(script,brief),encoding='utf-8')
        self.stage('awaiting_script_review')
        return script.model_dump()

    def replan(self):
        """Reaplica regras à coleta salva antes de qualquer geração de roteiro."""
        if self.state['stage'] not in ('prepared','no_content') or (self.folder/'roteiro.json').exists():
            raise ValueError('Replanejar somente antes de iniciar o roteiro')
        report=read_json(self.folder/'coleta.json')
        collected=datetime.fromisoformat(report['collected_at'])
        if collected.tzinfo is None or not 0 <= (self.now-collected).total_seconds() <= 86400:
            raise ValueError('Coleta antiga; não replanejar para contornar o limite de 24 horas')
        agenda=plan(read_json(self.folder/'fila-editorial.json'),self.now)
        agenda['planned_for']=report['collected_at']
        brief=build_brief(agenda)
        brief['collection_cutoff']=report['collected_at']
        write_json(self.folder/'briefing-antes-replanejamento.json',read_json(self.folder/'briefing.json'))
        write_json(self.folder/'plano-editorial.json',agenda)
        write_json(self.folder/'briefing.json',brief)
        (self.folder/'pauta.md').write_text(render_report(agenda,self.now.isoformat()),encoding='utf-8')
        self.stage('prepared' if brief['news'] else 'no_content')

    def script_bundle(self):
        brief=read_json(self.folder/'briefing.json')
        script=validate_script(read_json(self.folder/'roteiro.json'),brief)
        return brief,script,spoken_text(script)

    def approve_script(self):
        if self.state['stage'] not in ('awaiting_script_review','script_approved'):
            raise ValueError('Gere e revise o roteiro antes da aprovação')
        brief,script,text=self.script_bundle()
        (self.folder/'narracao.txt').write_text(text,encoding='utf-8')
        digest=fingerprint({'brief':brief,'script':script.model_dump()})
        write_json(self.folder/'aprovacao-roteiro.json',{'digest':digest,'approved_at':datetime.now(timezone.utc).isoformat()})
        self.stage('script_approved')

    def approved_bundle(self):
        brief,script,text=self.script_bundle()
        approval=read_json(self.folder/'aprovacao-roteiro.json',{})
        if approval.get('digest')!=fingerprint({'brief':brief,'script':script.model_dump()}):
            raise ValueError('Roteiro/briefing sem aprovação válida ou alterados após revisão')
        return brief,script,text

    def revalidate(self,sources,fetcher_factory=Fetcher):
        brief=read_json(self.folder/'briefing.json')
        planned=datetime.fromisoformat(brief['planned_for'])
        if planned.tzinfo is None or not 0 <= (self.now-planned).total_seconds() <= 86400:
            raise ValueError('Pauta deve ter até 24 horas; revisar a edição antes de continuar')
        for news in brief['news']:
            published=datetime.fromisoformat(news['published'])
            if published.tzinfo is None or not 0 <= (self.now-published).total_seconds() <= 8*86400:
                raise ValueError('Data da notícia inválida ou fora da janela editorial')
            source=next((s for s in sources if s['name']==news['source']),None)
            if source is None:raise ValueError('Fonte não configurada')
            fetcher=fetcher_factory(source['domains'])
            try:
                _,final=fetcher.get(news['url'])
                if canonical(final)!=canonical(news['url']):raise ValueError('URL mudou: revisar notícia novamente')
            finally:fetcher.close()

    def synthesize(self,polly,voice='Camila',engine='generative'):
        brief,script,text=self.approved_bundle()
        if (self.folder/'episode.wav').exists():
            metadata=self.validate_audio(text)
            if metadata['voice']!=voice or metadata['engine']!=engine:
                raise ValueError('Áudio salvo usa outra voz ou engine')
            if self.state['stage'] in ('audio_in_progress','audio_failed'):
                self.stage('awaiting_audio_review')
            return metadata
        if self.state['stage'] not in ('script_approved','audio_in_progress','audio_failed'):
            raise ValueError('Aprove o roteiro antes da voz')
        terms=[t.term_en for t in script.glossary]
        requests=[bilingual_ssml(part,terms) for part in speech_chunks(text)]
        if any(len(r)>6000 for r in requests):raise ValueError('SSML acima do limite')
        chunks_dir=self.folder/'audio-chunks';chunks_dir.mkdir(exist_ok=True)
        pcm=bytearray();self.stage('audio_in_progress')
        for index,ssml in enumerate(requests):
            digest=fingerprint({'ssml':ssml,'voice':voice,'engine':engine})
            meta_path=chunks_dir/f'{index}.json';pcm_path=chunks_dir/f'{index}.pcm'
            previous=read_json(meta_path,{})
            if previous and previous.get('digest')!=digest:raise ValueError('Texto/voz alterado após início da síntese; usar nova revisão sem reaproveitar trechos')
            if pcm_path.exists():
                data=pcm_path.read_bytes()
                if not data or len(data)%2 or previous.get('sha256')!=hashlib.sha256(data).hexdigest():
                    raise ValueError('Trecho salvo sem integridade válida; revisar sem nova cobrança')
            else:
                if previous:raise ValueError('Trecho com chamada iniciada e sem resposta salva; não repetir cobrança automaticamente')
                self.save_json(meta_path,{'digest':digest,'status':'request_started'})
                try:
                    response=polly.synthesize_speech(Text=ssml,TextType='ssml',OutputFormat='pcm',SampleRate='16000',VoiceId=voice,Engine=engine,LanguageCode='pt-BR')
                    with closing(response['AudioStream']) as stream:data=stream.read()
                    if not data or len(data)%2:raise ValueError('Trecho PCM inválido')
                    temporary=pcm_path.with_suffix('.pcm.tmp')
                    temporary.write_bytes(data)
                    temporary.replace(pcm_path)
                    self.save_json(meta_path,{'digest':digest,'status':'complete','sha256':hashlib.sha256(data).hexdigest()})
                except Exception:self.stage('audio_failed');raise
            pcm.extend(data)
        audio,duration=wav_from_pcm(bytes(pcm))
        metadata={'duration_seconds':duration,'voice':voice,'engine':engine,'renderer':RENDERER_VERSION,'duration_verified':True,'script_sha256':hashlib.sha256(text.encode()).hexdigest(),'audio_sha256':hashlib.sha256(audio).hexdigest()}
        # Metadados primeiro; áudio é o marcador de cache concluído.
        write_json(self.folder/'metadados-audio.json',metadata)
        temporary=self.folder/'episode.wav.tmp'
        temporary.write_bytes(audio)
        temporary.replace(self.folder/'episode.wav')
        self.stage('awaiting_audio_review')
        return metadata

    def validate_audio(self,text):
        data=(self.folder/'episode.wav').read_bytes()
        metadata=read_json(self.folder/'metadados-audio.json',{})
        if metadata.get('script_sha256')!=hashlib.sha256(text.encode()).hexdigest() or metadata.get('audio_sha256')!=hashlib.sha256(data).hexdigest():
            raise ValueError('Áudio alterado ou corresponde a outro roteiro')
        with wave.open(io.BytesIO(data)) as wav:
            duration=wav.getnframes()/wav.getframerate()
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())!=(1,2,16000) or not 0<duration<=600:
                raise ValueError('Formato ou duração inválidos')
        return metadata

    def approve_audio(self):
        _,_,text=self.approved_bundle()
        self.validate_audio(text)
        if self.state['stage'] not in ('awaiting_audio_review','audio_approved'):
            raise ValueError('Gere e ouça o áudio antes de aprovar')
        data=(self.folder/'episode.wav').read_bytes()
        write_json(self.folder/'aprovacao-audio.json',{'sha256':hashlib.sha256(data).hexdigest(),'approved_at':datetime.now(timezone.utc).isoformat()})
        self.stage('audio_approved')

    def publish(self,upload):
        brief,script,text=self.approved_bundle()
        self.validate_audio(text)
        audio=(self.folder/'episode.wav').read_bytes()
        approval=read_json(self.folder/'aprovacao-audio.json',{})
        if approval.get('sha256')!=hashlib.sha256(audio).hexdigest():raise ValueError('Áudio sem aprovação válida')
        if self.state['stage'] not in ('audio_approved','publish_in_progress','completed'):raise ValueError('Aprove a escuta antes da publicação')
        self.stage('publish_in_progress')
        episode=upload(audio,script.model_dump(),text,brief,self.day)
        # Só após o catálogo confirmar o episódio, atualizar cobertura e uso editorial.
        shared=read_json(self.global_path,{'queue':[],'last_covered_at':None})
        queue=merge_queue(shared['queue'],read_json(self.folder/'fila-editorial.json',[]))
        used={canonical(n['url']) for n in brief['news']}
        for item in queue:
            if canonical(item['url']) in used:item['used_in']=list(set(item.get('used_in',[])+[episode['id']]))
        cutoff=brief['collection_cutoff']
        if shared['last_covered_at'] and datetime.fromisoformat(shared['last_covered_at'])>datetime.fromisoformat(cutoff):cutoff=shared['last_covered_at']
        write_json(self.global_path,{'queue':queue,'last_covered_at':cutoff})
        write_json(self.folder/'recibo.json',episode)
        self.stage('completed',episode_id=episode['id'])
        return episode
