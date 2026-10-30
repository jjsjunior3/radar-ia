"""Gera três artes SVG editáveis, sem dependências ou chamadas externas.

Execute da raiz: python tools/gerar_diagramas.py
Os PNGs de divulgação são exportados a partir desses mesmos SVGs.
"""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'docs' / 'assets' / 'linkedin'
W, H = 1600, 2000


class Art:
    def __init__(self, background, ink, muted, accent):
        self.ink, self.muted, self.accent = ink, muted, accent
        self.parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">
<title>Radar IA — arquitetura e fluxo do MVP privado</title>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{accent}"/></marker></defs>
<rect width="1600" height="2000" fill="{background}"/>
<g font-family="Segoe UI, Arial, sans-serif">''']

    def rect(self, x, y, w, h, fill, stroke='none', radius=24):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    def text(self, x, y, value, size=28, fill=None, weight=400, spacing=0):
        fill = fill or self.ink
        self.parts.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}">{escape(value)}</text>')

    def lines(self, x, y, values, size=25, fill=None, gap=36):
        for i, value in enumerate(values):
            self.text(x, y+i*gap, value, size, fill)

    def path(self, d, arrow=True, color=None, dashed=False):
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color or self.accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"'
                          + (' marker-end="url(#arrow)"' if arrow else '')
                          + (' stroke-dasharray="8 10"' if dashed else '') + '/>')

    def pill(self, x, y, w, value, fill, color, size=22):
        self.rect(x, y, w, 44, fill, radius=22)
        self.text(x+18, y+30, value, size, color, 600)

    def card(self, x, y, w, title, body, fill, stroke, tag=None, h=166, title_size=31):
        self.rect(x,y,w,h,fill,stroke)
        if tag:
            self.text(x+24,y+32,tag,19,self.accent,700,1)
            title_y=y+77
        else:title_y=y+46
        self.text(x+24,title_y,title,title_size,weight=650)
        self.lines(x+24,title_y+40,body,24,self.muted,gap=32)

    def footer(self, variant):
        self.path('M 80 1880 H 1520',False,self.muted)
        self.text(80,1932,'Feito por jrsantosdev',28,weight=650)
        self.text(80,1970,'MVP privado • código sob licença MIT • abertura pública planejada',23,self.muted)
        self.text(1375,1932,variant,24,self.muted)

    def save(self, filename):
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/filename).write_text('\n'.join(self.parts)+ '\n</g></svg>\n',encoding='utf-8')


def architecture():
    a=Art('#091322','#F3F7FC','#B0C0D2','#52DAC4')
    a.rect(80,70,76,8,a.accent,radius=4)
    a.text(80,132,'RADAR IA  /  ARQUITETURA',24,a.accent,700,3)
    a.text(80,238,'Da notícia ao seu celular.',76,weight=700)
    a.text(80,302,'Python, LLM e AWS em uma experiência de áudio privada.',31,a.muted)
    a.pill(80,342,300,'ATÉ 10 MINUTOS', '#153430',a.accent)
    a.pill(400,342,476,'PT-BR + INGLÊS TÉCNICO','#14243A','#CBDCF3')

    a.rect(80,430,1440,560,'#101F32','#24374D',32)
    a.text(112,478,'01  PRODUÇÃO COM AGENTES',27,a.accent,700)
    a.text(112,517,'EventBridge Scheduler • seg–sex, 8h30 • America/Sao_Paulo',25,a.muted)
    cards=[(112,552,400,'Fontes RSS',['httpx + feedparser','Publicação declarada no feed']),
           (600,552,400,'Python: curadoria',['Datas, HTTPS e deduplicação','Grade semanal + pauta variável']),
           (1088,552,400,'OpenRouter + Gemini',['Agentes: relevância + roteiro','JSON validado com Pydantic']),
           (1088,762,400,'Avaliador editorial',['Aprova ou devolve análise','Até duas revisões de roteiro']),
           (600,762,400,'Amazon Polly',['Leo • engine generative','SSML + duração medida']),
           (112,762,400,'Amazon S3 privado',['Áudio, fontes e catálogo','Checkpoints para retomada'])]
    for x,y,w,title,body in cards:a.card(x,y,w,title,body,'#172A40','#30465E',h=148,title_size=29)
    a.path('M 523 625 H 584');a.path('M 1011 625 H 1072')
    a.path('M 1288 708 V 746');a.path('M 1076 836 H 1016');a.path('M 588 836 H 528')
    a.text(112,960,'IAM por função • segredos LLM/VAPID • CI e operação manual no GitHub Actions.',24,a.muted)

    a.rect(80,1030,1440,652,'#101F32','#24374D',32)
    a.text(112,1080,'02  APLICATIVO E ACESSO',27,a.accent,700)
    a.card(112,1128,400,'Celular / navegador',['Player web instalável','Ouvidos, pendentes e retomada'],'#172A40','#30465E',h=150)
    a.card(600,1128,400,'Amazon CloudFront',['Entrega HTTPS da interface','Origem S3 via OAC'],'#172A40','#30465E',h=150)
    a.card(1088,1128,400,'S3 da interface',['HTML + CSS + JavaScript','Bucket privado; interface pública'],'#172A40','#30465E',h=150,title_size=30)
    a.path('M 523 1202 H 584');a.path('M 1011 1202 H 1072')
    a.path('M 252 1290 V 1354')
    a.text(275,1326,'Login + PKCE',23,a.muted)
    a.path('M 450 1290 V 1338 H 616 V 1354')
    a.text(650,1334,'Access token do app',22,a.muted)
    row=[(112,'Cognito',['Login privado','Sem cadastro público']),
         (480,'API Gateway',['Validação JWT','Escopo openid']),
         (848,'Lambda',['API em Python','Links temporários']),
         (1216,'DynamoDB',['Posição de escuta','Usuário + episódio'])]
    for x,title,body in row:a.card(x,1370,272,title,body,'#172A40','#30465E',h=160,title_size=29)
    for x in (764,1132):a.path(f'M {x} 1450 H {x+68}')
    a.text(112,1582,'Acesso ao áudio: app → API → link assinado → S3 de áudio privado.',27,a.ink)
    a.text(112,1625,'CloudFormation provisiona a infraestrutura • CloudWatch recebe os logs.',24,a.muted)
    a.text(112,1660,'Após publicar: SQS + Lambda → Web Push; assinaturas privadas no DynamoDB.',22,a.muted)

    a.rect(80,1722,1440,112,'#153430')
    a.text(112,1765,'OPEN SOURCE EM PREPARAÇÃO',27,a.accent,700,1)
    a.text(112,1805,'Licença MIT. Código e dados privados têm ciclos de publicação separados.',26,'#C7E6DF')
    a.footer('01 / 03');a.save('01-arquitetura.svg')


def journey():
    a=Art('#F3F5F0','#102B2B','#526561','#117E74')
    a.text(80,115,'RADAR IA  /  DO RSS AO PLAY',24,a.accent,700,3)
    a.text(80,217,'Notícia boa merece',78,weight=750)
    a.text(80,306,'uma escuta melhor.',78,weight=750)
    a.text(80,367,'Agentes especializados, revisão editorial e áudio privado.',31,a.muted)
    rows=[('01','COLETA','Encontrar e validar','RSS, datas de publicação e URLs HTTPS.','httpx • feedparser',False),
          ('02','AGENTE DE RELEVÂNCIA','Selecionar o que importa','Nota e justificativa sobre a pré-seleção por tema.','OpenRouter • JSON validado',True),
          ('03','AGENTE ROTEIRISTA','Explicar em português','Inglês técnico contextualizado e saída validada.','OpenRouter • Gemini • Pydantic',False),
          ('04','AGENTE AVALIADOR','Aprovar ou pedir correções','Devolve análise ao roteirista; até duas revisões.','Parecer + hash do roteiro',True),
          ('05','VOZ SINTÉTICA','Transformar texto em áudio','Pausas e inglês via SSML; WAV de até 600 segundos.','Amazon Polly • Leo generativa',False),
          ('06','VERIFICAÇÃO DO ÁUDIO','Validar antes de publicar','Integridade, vínculo com roteiro e até 10 minutos.','Código Python • WAV',False),
          ('07','PUBLICAÇÃO PRIVADA','Dar play, pausar e retomar','Catálogo privado, progresso e aviso por dispositivo.','AWS • Android • Web Push',False)]
    a.path('M 143 490 V 1638',False,'#AFC9C0')
    for i,(number,label,title,body,tech,human) in enumerate(rows):
        y=440+i*172
        a.rect(101,y+45,84,84,a.accent if not human else '#A65E2B',radius=42)
        a.text(116,y+100,number,39,'#FFFFFF',700)
        a.rect(224,y,1296,155,'#FFFFFF' if not human else '#FBEEE3','#D9E1D9' if not human else '#E3B78F')
        a.text(250,y+31,label,19,a.accent if not human else '#8D491D',700,1.5)
        a.text(250,y+75,title,35,weight=700)
        a.text(250,y+119,body,25,a.muted)
        # A tecnologia é um complemento à hierarquia editorial.
        a.text(950,y+33,tech,21,a.muted,500)
    a.rect(80,1680,1440,145,'#DDEDE6')
    a.text(112,1725,'AGENDADO: SEG–SEX, 8H30 • AMERICA/SAO_PAULO',26,a.accent,700)
    a.text(112,1765,'Coleta → agentes → Polly → catálogo privado → aviso.',28,weight=600)
    a.text(112,1803,'Open source em preparação • licença MIT • sem preenchimento artificial.',24,a.muted)
    a.footer('02 / 03');a.save('02-fluxo-editorial.svg')


def modules():
    a=Art('#161428','#F6F3FF','#BFB8D4','#BBA3FF')
    a.rect(80,72,76,8,a.accent,radius=4)
    a.text(80,137,'RADAR IA  /  MÓDULOS E RESPONSABILIDADES',23,a.accent,700,2)
    a.text(80,245,'Agentes com limites claros.',79,weight=700)
    a.text(80,309,'Automação modular + geração com LLM + serviços AWS.',31,a.muted)
    a.rect(80,364,1440,118,'#26213E','#53446E')
    a.text(112,413,'ORQUESTRAÇÃO EM PYTHON',26,a.accent,700)
    a.text(112,454,'production.py + Lambda + EventBridge Scheduler • checkpoints S3 • IAM por função',27)
    cards=[
        (80,550,'01  Coletor RSS','CÓDIGO PYTHON',['collection.py • httpx • feedparser','Datas, URLs e domínios permitidos','Resumos e referências preservados']),
        (840,550,'02  Relevância','AGENTE LLM',['RelevanceAgent • OpenRouter','Nota de 0 a 5 + justificativa por ID','Seleciona candidatas com nota mínima 3']),
        (840,950,'03  Roteirista','GERAÇÃO COM LLM',['script.py • OpenRouter • Gemini','JSON estruturado + validação Pydantic','Português e glossário técnico em inglês']),
        (80,950,'04  Avaliador','AGENTE LLM',['ScriptReviewerAgent • OpenRouter','Fidelidade às evidências e clareza','Aprovação vinculada ao hash do roteiro']),
        (80,1350,'05  Produtor','POLLY + PUBLICAÇÃO DETERMINÍSTICA',['Leo • SSML • WAV de até 10 minutos','S3 privado + catálogo idempotente','Só publica após aprovação editorial']),
        (840,1350,'06  Player privado','APLICATIVO WEB',['CloudFront • Cognito • API Gateway','Lambda • S3 • DynamoDB • Web Push','Ouvidos, pendentes e posição de escuta'])]
    for x,y,title,tag,body in cards:
        a.card(x,y,680,title,body,'#26213E','#51446B',tag=tag,h=280,title_size=37)
    a.path('M 776 690 H 824')
    a.path('M 1180 846 V 934')
    a.path('M 824 1090 H 776')
    a.path('M 420 1246 V 1334')
    a.path('M 776 1490 H 824')
    a.text(80,881,'Coleta determinística; relevância, roteiro e avaliação usam LLM.',27,a.muted)
    a.text(560,1280,'Reprovação → roteirista • até duas revisões.',27,a.muted)
    a.rect(80,1690,1440,136,'#30264B')
    a.text(112,1736,'OPEN SOURCE EM PREPARAÇÃO • MIT',27,a.accent,700)
    a.text(112,1778,'Hoje: aplicativo privado. Evolução: feed RSS público e abertura do código.',26)
    a.footer('03 / 03');a.save('03-modulos-e-ia.svg')


if __name__ == '__main__':
    architecture();journey();modules()
    print(f'Três SVGs editáveis gerados em: {OUT}')
