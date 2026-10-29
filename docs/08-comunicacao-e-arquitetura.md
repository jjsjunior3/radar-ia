# Comunicação do projeto e modelos de arquitetura

Três modelos para apresentar o Radar IA no LinkedIn e no portfólio. São diagramas da implementação atual, com arquivos editáveis, sem identificadores de conta, bucket real, e-mail, credenciais ou URLs temporárias.

## Arquivos

Todas as imagens têm **1600 × 2000 pixels**, proporção 4:5. PNG para publicar; SVG para editar texto, cores e composição.

| Modelo | Público e mensagem | PNG | SVG editável |
|---|---|---|---|
| 01 · Arquitetura | Visão técnica: produção, aplicativo, serviços AWS e acesso | [Imagem](assets/linkedin/01-arquitetura.png) | [Editar](assets/linkedin/01-arquitetura.svg) |
| 02 · Fluxo editorial | Visão de produto: da notícia ao play, com as duas revisões humanas | [Imagem](assets/linkedin/02-fluxo-editorial.png) | [Editar](assets/linkedin/02-fluxo-editorial.svg) |
| 03 · Módulos e IA | Responsabilidades de Python, LLM, TTS, publicação e player | [Imagem](assets/linkedin/03-modulos-e-ia.png) | [Editar](assets/linkedin/03-modulos-e-ia.svg) |

**Sugestão editorial:** o modelo 02 apresenta o problema e a experiência com mais facilidade para um público amplo. O modelo 01 ajuda a explicar decisões de engenharia; o 03 detalha as responsabilidades dos componentes. Eles podem ser usados separadamente ou como sequência, ajustando a linguagem da publicação ao objetivo.

## O que cada imagem representa

### Modelo 01 · Arquitetura

- Produção: GitHub Actions, Python, RSS, OpenRouter/Gemini, revisão humana, Polly e S3.
- Aplicativo: navegador/Android, CloudFront, S3 da interface, Cognito, API Gateway, Lambda e DynamoDB.
- Infraestrutura: CloudFormation, IAM/OIDC, CloudWatch, origem S3 via OAC e links temporários de áudio.
- As setas são uma visão lógica de responsabilidades e acesso. A autenticação real envolve redirecionamentos entre navegador e Cognito; o navegador apresenta o access token à API. Cognito não chama a API pelo usuário.
- O cartão de revisão reúne as duas decisões humanas; o fluxo cronológico completo aparece no modelo 02.

### Modelo 02 · Fluxo editorial

Mostra sete etapas: coleta, curadoria, roteiro, revisão do texto, síntese, escuta e publicação privada. As etapas humanas têm cor própria. A rotina agendada para na geração do roteiro; gerar áudio e publicar exigem revisão e ação explícita.

### Modelo 03 · Módulos e IA

Apresenta os papéis funcionais e os módulos que os implementam. Coletor, curadoria e publicador são código Python. Roteirista usa LLM via OpenRouter. Narrador usa o serviço TTS Amazon Polly. Player usa o aplicativo e os serviços AWS.

**Não há sistema multiagente autônomo implementado no MVP.** Os papéis visuais descrevem componentes orquestrados explicitamente. Uma futura arquitetura com agentes deve ser apresentada como evolução, com autonomia, ferramentas e limites efetivamente implementados.

## Como falar de open source

O código está sob licença MIT, mas o repositório continua privado durante a revisão. As imagens usam **“Open source em preparação”** e **“abertura pública planejada”**. Isso preserva a intenção do projeto e descreve corretamente o acesso atual.

Depois da abertura pública, atualizar essas frases no gerador/SVG, acrescentar o endereço acessível do repositório e exportar novamente as imagens. A publicação do código é independente da privacidade dos episódios e do aplicativo. Não incluir dados de conta ou conteúdo pessoal no material público.

## Como editar e regenerar

Os SVGs são arquivos de texto e podem ser abertos em editores vetoriais como Inkscape. O gerador em Python também permite manter as três imagens consistentes:

```bat
.\.venv\Scripts\python.exe tools\gerar_diagramas.py
```

O comando recria os SVGs, usando somente a biblioteca padrão. Ele não faz chamadas de IA, não usa credenciais e não altera a aplicação. Ao mudar o gerador, exporte novamente os PNGs; o gerador não atualiza os PNGs sozinho.

Os PNGs desta entrega foram renderizados diretamente dos SVGs com Sharp. Não usam imagens produzidas por IA nem têm texto incorporado de forma não editável no arquivo-fonte. Para exportar manualmente, abra o SVG no editor vetorial e exporte a página inteira para PNG em 1600 × 2000.

A identidade usa fontes sans-serif, contraste alto, margens constantes e a assinatura **“Feito por jrsantosdev”**. Os cartões nomeiam os serviços em texto; não usam logotipos oficiais de terceiros nem sugerem parceria com AWS, Google ou OpenRouter.

## Conferência antes do post

- Confirmar o resultado da primeira edição nova pelo GitHub Actions antes de descrevê-la como validada.
- Manter a revisão humana explícita ao explicar o grau de automação.
- Atualizar a condição de open source quando o repositório estiver acessível ao público.
- Usar dados de demonstração se for incluir capturas do aplicativo.

A postagem no LinkedIn é uma ação separada; estes arquivos são material preparado para sua revisão e publicação.
