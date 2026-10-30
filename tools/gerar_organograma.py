"""Mapa completo em SVG editável; não usa IA, credenciais ou serviços externos."""
from html import escape
from pathlib import Path
import textwrap

OUT=Path(__file__).resolve().parents[1]/'docs/assets'
W,H=2200,2800
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"><title>Radar IA: agentes, serviços e aprendizado</title><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0 0L10 5L0 10" fill="#57dbc0"/></marker></defs><rect width="2200" height="2800" fill="#091322"/><g font-family="Segoe UI,Arial,sans-serif">']

def text(x,y,value,size=27,color='#F3F7FC',weight=400):parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}">{escape(value)}</text>')
def box(x,y,w,h,title,lines,color='#172A40',title_size=31):
 parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{color}" stroke="#38516A" stroke-width="2"/>')
 text(x+26,y+48,title,title_size,weight=700)
 row=0
 for line in lines:
  for wrapped in textwrap.wrap(line,width=int((w-52)/13)):
   text(x+26,y+94+row*34,wrapped,25,'#B8C9DB');row+=1

def arrow(path):parts.append(f'<path d="{path}" fill="none" stroke="#57dbc0" stroke-width="4" marker-end="url(#arrow)"/>')

text(80,100,'RADAR IA / ARQUITETURA COMPLETA',29,'#57dbc0',700)
text(80,195,'Agentes, serviços e aprendizado.',76,weight=700)
text(80,248,'Da notícia ao áudio privado, com decisões rastreáveis e refinamento editorial.',30,'#B8C9DB')
for x,title,lines in [(80,'GitHub Actions + IAM/OIDC',['Testes e operação manual','Sessões AWS temporárias']), (600,'CloudFormation + S3',['Infraestrutura em arquivo','Artefatos privados de deploy']), (1120,'Secrets Manager',['Credenciais OpenRouter','Chave privada VAPID']), (1640,'CloudWatch',['Logs por Lambda','Sem chaves nos registros'])]:box(x,300,480,185,title,lines,title_size=27)
text(80,550,'PRODUÇÃO / EVENTBRIDGE SCHEDULER → LAMBDA EDITORIAL',30,'#57dbc0',700)
text(80,594,'Seg–sex, 8h30 São Paulo • DynamoDB Jobs evita execução duplicada por data.',26,'#B8C9DB')
box(80,650,600,230,'01 / Coletor determinístico',['RSS • httpx • feedparser','Datas, HTTPS, domínios e deduplicação','Grade semanal e até 7 candidatas'])
box(800,650,600,230,'02 / Agente de relevância',['OpenRouter • modelo configurado','Nota de 0 a 5 + motivo por notícia','Seleciona notas a partir de 3'])
box(1520,650,600,230,'03 / Agente roteirista',['OpenRouter • JSON + Pydantic','PT-BR e inglês contextualizado','Recebe análise para uma correção'])
arrow('M 690 765 H 786');arrow('M 1410 765 H 1506');arrow('M 1820 890 V 1006')
text(1350,956,'Roteiro + evidências originais',25,'#57dbc0')
box(1520,1020,600,250,'04 / Agente avaliador',['Fidelidade, atribuições e clareza','Aprova com nota ≥ 4, sem bloqueantes','1ª reprovação: análise ao roteirista','2ª reprovação: decisão humana'])
box(800,1020,600,250,'05 / Decisão humana',['Roteiro + dois pareceres + diferenças','Aprovação ligada ao hash e ao autor','Preferências não alteram o texto atual','Após aprovar: retoma automaticamente'],'#30264B')
box(80,1020,600,250,'06 / Memória editorial privada',['S3: observação + trecho aceito','Até 5 aprovações humanas em 14 dias','Contexto para relevância/roteiro/avaliação','Não treina o modelo nem muda código'],'#30264B')
arrow('M 1510 1140 H 1414');arrow('M 790 1140 H 694')
arrow('M 1820 1278 V 1390 H 380 V 1486')
arrow('M 1100 1278 V 1425 H 380 V 1486')
text(80,1340,'Aprovação do avaliador OU decisão humana',28,'#57dbc0',600)
text(650,1458,'MEMÓRIA → próxima edição; fontes e validações continuam obrigatórias.',25,'#C9B7F8')
box(80,1500,600,260,'07 / SQS + DynamoDB Jobs',['Fila de áudio e tarefa por hash','Voz/versão vinculadas ao conteúdo','Estados e cobranças incertas preservados','Checkpoint: S3 privado'])
box(800,1500,600,260,'08 / Lambda worker + Polly',['Valida aprovação e revalida fontes','Leo generativa • SSML bilíngue','WAV íntegro e duração de até 600 s','Sem aprovação: não chama Polly'])
box(1520,1500,600,260,'09 / S3 + avisos Web Push',['Catálogo confirma antes do aviso','SQS avisos → worker → VAPID','DynamoDB deduplica por dispositivo','Revisão pendente também gera aviso'])
arrow('M 690 1630 H 786');arrow('M 1410 1630 H 1506')
text(80,1845,'APLICATIVO / ANDROID, NAVEGADOR E DADOS PRIVADOS',30,'#57dbc0',700)
for x,title,lines in [(80,'Android / navegador',['PWA: Para ouvir / Biblioteca','Análise e aprovação']), (600,'CloudFront + S3 web',['Interface HTTPS','Origem privada por OAC']), (1120,'Cognito / PKCE',['Login por convite','Sessão persistente']), (1640,'API Gateway + Lambda',['JWT / autorização do responsável','Progresso, revisão e links'])]:box(x,1890,480,215,title,lines,title_size=27)
box(80,2170,600,240,'DynamoDB / dados do app',['Progress: posição e ouvido por usuário','Push: assinaturas por dispositivo','Jobs: tarefas e ledger de avisos'])
box(800,2170,600,240,'S3 / acesso ao episódio',['Áudios e catálogo privados','API emite URL temporária','Originais, versões e pareceres privados'])
box(1520,2170,600,240,'Falhas e intervenção',['Jobs: failed ou needs_review','SQS: filas de falha / dead letter','Resultados pagos incertos não repetem'])
text(80,2490,'COMO APRENDE: aprovação humana → memória S3 → contexto dos três agentes LLM.',29,'#C9B7F8',600)
text(80,2540,'O painel mostra referências usadas e mudanças entre versões. Comparação de texto não comprova melhoria.',26,'#B8C9DB')
text(80,2590,'Avaliação usa resumos RSS; não equivale a checagem factual externa. Uma edição automática real ainda será observada.',25,'#B8C9DB')
parts.append('<path d="M80 2650H2120" stroke="#38516A" stroke-width="2"/>')
text(80,2710,'Feito por jrsantosdev',32,weight=700)
text(80,2758,'Código sob licença MIT • aplicativo, episódios e memória continuam privados.',25,'#B8C9DB')
parts.append('</g></svg>');OUT.mkdir(exist_ok=True);(OUT/'arquitetura-completa.svg').write_text('\n'.join(parts),encoding='utf-8')
print('SVG editável:',OUT/'arquitetura-completa.svg')
