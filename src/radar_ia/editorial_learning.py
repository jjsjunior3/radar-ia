"""Memória editorial privada: aprovações humanas, sem alterar código ou validações."""
import json
from datetime import date,timedelta
from botocore.exceptions import ClientError


def record_feedback(s3,bucket,prefix,summary,user_id):
    if summary.get('human_approved_by')!=user_id or not summary.get('digest'):return
    item={'date':summary['date'],'digest':summary['digest'],'approved_by':user_id,
          'approved_at':summary.get('human_approved_at'),'theme':summary.get('theme',''),
          'feedback':summary.get('human_feedback','')[:2000],'accepted_excerpt':summary.get('narration','')[:1000]}
    key=f"{prefix}/production/feedback/{summary['date']}.json"
    try:s3.put_object(Bucket=bucket,Key=key,Body=json.dumps(item,ensure_ascii=False).encode(),ContentType='application/json',ServerSideEncryption='AES256',IfNoneMatch='*')
    except ClientError as exc:
        if exc.response['Error']['Code'] not in ('PreconditionFailed','412'):raise


def load_feedback(s3,bucket,prefix,day,owner):
    result=[]
    for offset in range(1,15):
        previous=(date.fromisoformat(day)-timedelta(days=offset)).isoformat()
        try:response=s3.get_object(Bucket=bucket,Key=f'{prefix}/production/feedback/{previous}.json')
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('NoSuchKey','404'):continue
            raise
        with response['Body'] as body:raw=body.read(12001)
        if len(raw)>12000:raise ValueError('Memória editorial acima do limite')
        item=json.loads(raw)
        if item.get('approved_by')!=owner or item.get('date')!=previous:raise ValueError('Origem da memória editorial inválida')
        if not all(isinstance(item.get(key,''),str) for key in ('feedback','accepted_excerpt','theme')):raise ValueError('Memória editorial inválida')
        result.append({key:item.get(key,'') for key in ('date','theme','feedback','accepted_excerpt')})
        if len(result)==5:break
    return result
