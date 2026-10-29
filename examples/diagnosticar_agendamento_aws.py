"""Consulta Scheduler, tarefa editorial e checkpoint privado sem gerar conteudo."""
import json
from datetime import datetime,timezone,timedelta,time
from pathlib import Path
from zoneinfo import ZoneInfo
import boto3
from dotenv import load_dotenv
from botocore.config import Config
from radar_ia.jobs import editorial_job_id,public_job
from radar_ia.review_api import ReviewStore

ROOT=Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT/'.env')
    outputs=json.loads((ROOT/'local-output/deploy/outputs.json').read_text(encoding='utf-8'))
    if not outputs.get('EditorialSchedule'):raise SystemExit('Agendamento AWS ainda nao instalado; atualizar outputs da stack.')
    session=boto3.Session(region_name='us-east-1');config=Config(connect_timeout=10,read_timeout=60,retries={'total_max_attempts':1})
    cf=session.client('cloudformation',config=config).describe_stacks(StackName='radar-ia-private-app')['Stacks'][0]
    parameters={item['ParameterKey']:item['ParameterValue'] for item in cf['Parameters']}
    schedule=session.client('scheduler',config=config).get_schedule(Name=outputs['EditorialSchedule'])
    now=datetime.now(timezone.utc);local=now.astimezone(ZoneInfo('America/Sao_Paulo'));day=local.date().isoformat()
    item=session.resource('dynamodb',config=config).Table(outputs['JobsTable']).get_item(Key={'job_id':editorial_job_id(day)},ConsistentRead=True).get('Item')
    edition=ReviewStore(session.client('s3',config=config),parameters['AudioBucket'],parameters['AudioPrefix']).summary(day)
    report={'provider':'aws_eventbridge_scheduler','checked_at':local.isoformat(),'date':day,
        'schedule_state':schedule['State'],'expression':schedule['ScheduleExpression'],'timezone':schedule['ScheduleExpressionTimezone'],
        'flexible_time_window':schedule['FlexibleTimeWindow']['Mode'],'job':public_job(item),
        'scheduled_at':item.get('scheduled_at') if item else None,'started_at':item.get('started_at') if item else None,
        'delay_seconds':int(item['delay_seconds']) if item and 'delay_seconds' in item else None,'edition_stage':edition['stage']}
    if schedule['State']!='ENABLED':message='Disparo diario AWS esta desativado.'
    elif item:message='Tarefa editorial encontrada; conferir status e etapa abaixo.'
    elif local.weekday()>4:message='Sem edicao regular prevista para o fim de semana.'
    elif (local.hour,local.minute)<(8,30):message='Aguardando 8h30 de Sao Paulo; nenhuma tarefa prevista ainda.'
    elif schedule['CreationDate']>datetime.combine(local.date(),time(8,30),local.tzinfo):message='Agendamento instalado apos o horario de hoje; aguardar o proximo dia util.'
    else:message='Nenhuma tarefa editorial de hoje registrada. Conferir Lambda, Scheduler e fila de falhas.'
    next_day=local.date()
    if (local.hour,local.minute)>=(8,30):next_day+=timedelta(days=1)
    while next_day.weekday()>4:next_day+=timedelta(days=1)
    report['next_expected']=datetime.combine(next_day,time(8,30),local.tzinfo).isoformat()
    report['message']=message
    target=ROOT/'local-output/diagnostico-agendamento-aws.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));print('Resumo:',message)


if __name__=='__main__':main()
