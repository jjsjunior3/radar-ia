"""Revisão de roteiro sobre checkpoint privado; somente stdlib e cliente S3."""
import hashlib
import difflib
import io
import json
import re
import zipfile
import wave
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from botocore.exceptions import ClientError

MAX_BYTES = 50 * 1024 * 1024


class ReviewConflict(Exception):
    pass


def digest_script(brief, script):
    return hashlib.sha256(json.dumps({'brief':brief,'script':script},ensure_ascii=False,sort_keys=True).encode()).hexdigest()


class ReviewStore:
    def __init__(self, s3, bucket, prefix):
        self.s3, self.bucket, self.prefix = s3, bucket, prefix.strip('/')

    def key(self, edition):
        if not isinstance(edition,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',edition) or date.fromisoformat(edition).isoformat()!=edition:
            raise ValueError('Data inválida')
        return f'{self.prefix}/production/editions/{edition}.zip'

    def load(self, edition):
        key=self.key(edition)
        listing=self.s3.list_objects_v2(Bucket=self.bucket,Prefix=key,MaxKeys=1)
        if not any(item['Key']==key for item in listing.get('Contents',[])):
            return None,None
        response=self.s3.get_object(Bucket=self.bucket,Key=key)
        with response['Body'] as body:raw=body.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Checkpoint excede limite')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=archive.infolist()
            if len(members)>1000 or sum(item.file_size for item in members)>MAX_BYTES:
                raise ValueError('Checkpoint excede limite')
            names=[item.filename for item in members]
            if len(set(names))!=len(names) or any(name.startswith('/') or '..' in name.split('/') or '\\' in name or ':' in name for name in names):
                raise ValueError('Checkpoint inválido')
            checkpoint=json.loads(archive.read('checkpoint.json'))
            if checkpoint.get('date')!=edition:raise ValueError('Data divergente')
        return raw,response['ETag']

    def summary(self, edition, raw=None):
        if raw is None:raw,_=self.load(edition)
        if raw is None:
            return {'date':edition,'stage':'new','can_approve_script':False,'narration':'','sources':[]}
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            checkpoint=json.loads(archive.read('checkpoint.json'))
            result={'date':edition,'stage':checkpoint['stage'],'updated_at':checkpoint.get('updated_at'),
                'can_approve_script':False,'narration':'','sources':[]}
            if 'briefing.json' in archive.namelist():
                brief=json.loads(archive.read('briefing.json'))
                result['theme']=brief.get('theme','')
                result['planned_for']=brief.get('planned_for')
                for news in brief.get('news',[]):
                    url=news.get('url','');parsed=urlsplit(url)
                    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
                        raise ValueError('Fonte inválida')
                    result['sources'].append({'title':news['title_original'],'source':news['source'],'url':url,'published':news.get('published')})
            if 'roteiro.json' in archive.namelist():
                script=json.loads(archive.read('roteiro.json'))
                if not isinstance(script,dict) or set(script)!={'intro_pt','stories','glossary','outro_pt'}:
                    raise ValueError('Roteiro inválido')
                if [s['news_id'] for s in script['stories']]!=[n['id'] for n in brief['news']]:
                    raise ValueError('Referências divergentes')
                narration=archive.read('narracao.txt').decode('utf-8-sig').replace('\r\n','\n')
                if not narration.strip() or len(narration)>20000:raise ValueError('Narração inválida')
                result.update(narration=narration,digest=digest_script(brief,script),
                    can_approve_script=checkpoint['stage'] in ('awaiting_script_review','awaiting_human_review'))
            versions=[]
            for number in (1,2):
                name=f'agents/writer-{number}/response.json'
                if name not in archive.namelist():continue
                try:
                    raw_version=json.loads(archive.read(name))
                    draft=json.loads(raw_version['choices'][0]['message']['content'])
                    parts=[draft['intro_pt'],*(story['narration_pt'] for story in draft['stories']),draft['outro_pt']]
                    if not all(isinstance(part,str) for part in parts):raise ValueError('Texto inválido')
                    versions.append({'version':number,'narration':'\n\n'.join(parts)[:12000]})
                except (ValueError,KeyError,TypeError,IndexError):
                    versions.append({'version':number,'narration':'Resposta não estruturada; consulte o parecer de validação.'})
            changes=''
            if len(versions)==2:
                changes='\n'.join(difflib.unified_diff(versions[0]['narration'].splitlines(),versions[1]['narration'].splitlines(),fromfile='Versão 1',tofile='Versão 2',lineterm=''))[:16000]
            memory=brief.get('editorial_memory',[]) if 'briefing.json' in archive.namelist() else []
            result['refinement']={'versions':versions,'changes':changes,'examples':[
                {key:str(item.get(key,''))[:2000] for key in ('date','theme','feedback','accepted_excerpt')}
                for item in memory[:5] if isinstance(item,dict)]}
            result['human_escalated']='agents/escalation.json' in archive.namelist()
            result['editorial_reviews']=[json.loads(archive.read(name)) for name in sorted(archive.namelist()) if re.fullmatch(r'agents/review-[12]\.json',name)]
            if 'aprovacao-roteiro.json' in archive.namelist():
                human=json.loads(archive.read('aprovacao-roteiro.json'))
                result['human_feedback']=human.get('feedback','')
                result['human_approved_by']=human.get('approved_by','')
                result['human_approved_at']=human.get('approved_at','')
            names=archive.namelist()
            approved='aprovacao-roteiro.json' in names and json.loads(archive.read('aprovacao-roteiro.json')).get('digest')==result.get('digest')
            result['can_generate_audio']=bool(approved and checkpoint['stage']=='script_approved')
            result['audio_revision']=str(checkpoint.get('audio_revision','initial'))
            result['can_approve_audio']=False;result['can_publish']=False
            if 'metadados-audio.json' in names and 'episode.wav' in names:
                metadata=json.loads(archive.read('metadados-audio.json'))
                digest=metadata.get('audio_sha256','')
                if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Hash de áudio inválido')
                result.update(audio_digest=digest,voice=metadata.get('voice'),duration_seconds=metadata.get('duration_seconds'))
                result['can_approve_audio']=bool(approved and checkpoint['stage']=='awaiting_audio_review')
                audio_approved='aprovacao-audio.json' in names and json.loads(archive.read('aprovacao-audio.json')).get('sha256')==digest
                result['can_publish']=bool(approved and audio_approved and checkpoint['stage']=='audio_approved')
            return result

    def approve_script(self, edition, data, user_id):
        if not isinstance(data,dict) or not {'digest','confirmed'}<=set(data) or set(data)-{'digest','confirmed','feedback'} or data['confirmed'] is not True or not isinstance(data['digest'],str) or not re.fullmatch('[a-f0-9]{64}',data['digest']):
            raise ValueError('Aprovação inválida')
        if not isinstance(data.get('feedback',''),str) or len(data.get('feedback',''))>2000:raise ValueError('Observação editorial inválida')
        raw,etag=self.load(edition)
        if raw is None:raise ReviewConflict()
        summary=self.summary(edition,raw)
        if data['digest']!=summary.get('digest'):raise ReviewConflict()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if summary['stage'] not in ('awaiting_script_review','awaiting_human_review'):
                if 'aprovacao-roteiro.json' in archive.namelist() and json.loads(archive.read('aprovacao-roteiro.json')).get('digest')==data['digest']:
                    return summary
                raise ReviewConflict()
            if 'episode.wav' in archive.namelist() or any(name.startswith('audio-chunks/') for name in archive.namelist()):
                raise ReviewConflict()
            now=datetime.now(timezone.utc).isoformat()
            checkpoint=json.loads(archive.read('checkpoint.json'))
            checkpoint.update(stage='script_approved',updated_at=now)
            replacements={'checkpoint.json':checkpoint,'aprovacao-roteiro.json':{
                'digest':data['digest'],'approved_at':now,'approved_by':user_id,'channel':'web','mode':'human',
                'editorial_override':summary.get('human_escalated',False),'feedback':data.get('feedback','').strip()}}
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as target:
                for name in archive.namelist():
                    if name not in replacements:target.writestr(name,archive.read(name))
                for name,value in replacements.items():
                    target.writestr(name,json.dumps(value,ensure_ascii=False,indent=2).encode())
        try:
            self.s3.put_object(Bucket=self.bucket,Key=self.key(edition),Body=output.getvalue(),
                ContentType='application/zip',ServerSideEncryption='AES256',IfMatch=etag)
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('PreconditionFailed','412','ConditionalRequestConflict'):
                raise ReviewConflict() from None
            raise
        return self.summary(edition,output.getvalue())

    def approve_audio(self, edition, data, user_id):
        if not isinstance(data,dict) or set(data)!={'digest','confirmed'} or data['confirmed'] is not True:
            raise ValueError('Confirmação inválida')
        raw,etag=self.load(edition)
        if raw is None:raise ReviewConflict()
        summary=self.summary(edition,raw)
        if not summary.get('audio_digest') or data['digest']!=summary['audio_digest']:raise ReviewConflict()
        if summary.get('can_publish'):return summary
        if not summary.get('can_approve_audio'):raise ReviewConflict()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            audio=archive.read('episode.wav');metadata=json.loads(archive.read('metadados-audio.json'))
            if hashlib.sha256(audio).hexdigest()!=data['digest'] or metadata['script_sha256']!=hashlib.sha256(summary['narration'].encode()).hexdigest():
                raise ReviewConflict()
            with wave.open(io.BytesIO(audio)) as wav:
                if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())!=(1,2,16000) or not 0<wav.getnframes()/16000<=600:
                    raise ValueError('Áudio inválido')
            now=datetime.now(timezone.utc).isoformat()
            checkpoint=json.loads(archive.read('checkpoint.json'));checkpoint.update(stage='audio_approved',updated_at=now)
            replacements={'checkpoint.json':checkpoint,'aprovacao-audio.json':{'sha256':data['digest'],'approved_at':now,'approved_by':user_id,'channel':'web'}}
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as target:
                for name in archive.namelist():
                    if name not in replacements:target.writestr(name,archive.read(name))
                for name,value in replacements.items():target.writestr(name,json.dumps(value,ensure_ascii=False).encode())
        try:self.s3.put_object(Bucket=self.bucket,Key=self.key(edition),Body=output.getvalue(),ContentType='application/zip',ServerSideEncryption='AES256',IfMatch=etag)
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('PreconditionFailed','412','ConditionalRequestConflict'):raise ReviewConflict() from None
            raise
        return self.summary(edition,output.getvalue())
