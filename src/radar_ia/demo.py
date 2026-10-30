"""Dados fictícios para demonstrar a interface sem AWS, LLM ou áudio real."""
from datetime import date,timedelta


def episodes():
    return [dict(id='demo-1',date='2026-10-30',title='Exemplo: novidades em ferramentas de IA',duration_seconds=300,demo=True,demo_progress={'position':0,'heard':False}),
            dict(id='demo-2',date='2026-10-29',title='Exemplo: engenharia de IA na prática',duration_seconds=370,demo=True,demo_progress={'position':120,'heard':False}),
            dict(id='demo-3',date='2026-10-28',title='Exemplo: mercado de tecnologia',duration_seconds=240,demo=True,demo_progress={'position':240,'heard':True})]


def edition(day,approved=False,feedback=''):
    previous=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
    v1='Exemplo fictício de roteiro: a ferramenta é a melhor solução para todas as equipes.'
    v2='Exemplo fictício revisado: segundo a fonte de demonstração, a ferramenta foi testada em um cenário específico. Isso não comprova resultado para todas as equipes.'
    findings=[{'news_id':1,'severity':'blocking','issue':'Generalização sem evidência.','correction':'Atribuir a afirmação à fonte e limitar ao cenário descrito.'}]
    return {'demo':True,'date':day,'stage':'completed' if approved else 'awaiting_human_review','theme':'Demonstração editorial',
        'narration':v2,'sources':[{'title':'Notícia fictícia para demonstração','source':'Fonte de exemplo','url':'https://example.org','published':day}],
        'digest':'a'*64,'human_escalated':True,'automatic_publication':True,'schedule_enabled':False,'jobs':[],
        'can_approve_script':not approved,'can_generate_audio':False,'can_approve_audio':False,'can_publish':False,
        'editorial_reviews':[{'approved':False,'quality':2,'findings':findings},{'approved':False,'quality':3,'findings':findings}],
        'refinement':{'versions':[{'version':1,'narration':v1},{'version':2,'narration':v2}],
            'changes':'--- Versão 1\n+++ Versão 2\n-'+v1+'\n+'+v2,
            'examples':[{'date':previous,'theme':'Exemplo fictício','feedback':feedback or 'Prefiro atribuições claras e explicações curtas.','accepted_excerpt':'Trecho fictício aprovado.'}]}}
