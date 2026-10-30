# Comunicação do projeto e modelos de arquitetura

Três modelos para apresentar o Radar IA no LinkedIn e no portfólio. São diagramas da implementação atual, com arquivos editáveis, sem identificadores de conta, bucket real, e-mail, credenciais ou URLs temporárias.

## Arquivos

Todas as imagens têm **1600 × 2000 pixels**, proporção 4:5. PNG para publicar; SVG para editar texto, cores e composição.

| Modelo | Público e mensagem | PNG | SVG editável |
|---|---|---|---|
| 01 · Arquitetura | Visão técnica: produção, aplicativo, serviços AWS e acesso | [Imagem](assets/linkedin/01-arquitetura.png) | [Editar](assets/linkedin/01-arquitetura.svg) |
| 02 · Fluxo editorial | Visão de produto: da notícia ao play, com seleção e avaliação por agentes | [Imagem](assets/linkedin/02-fluxo-editorial.png) | [Editar](assets/linkedin/02-fluxo-editorial.svg) |
| 03 · Módulos e IA | Responsabilidades de Python, LLM, TTS, publicação e player | [Imagem](assets/linkedin/03-modulos-e-ia.png) | [Editar](assets/linkedin/03-modulos-e-ia.svg) |

**Sugestão editorial:** o modelo 02 apresenta o problema e a experiência com mais facilidade para um público amplo. O modelo 01 ajuda a explicar decisões de engenharia; o 03 detalha as responsabilidades dos componentes. Eles podem ser usados separadamente ou como sequência, ajustando a linguagem da publicação ao objetivo.

## O que cada imagem representa

### Modelo 01 · Arquitetura

- Produção: EventBridge Scheduler, Python/RSS, agentes OpenRouter/Gemini, avaliador, Polly e S3; GitHub Actions para CI/operação manual.
- Aplicativo: navegador/Android, CloudFront, S3 da interface, Cognito, API Gateway, Lambda e DynamoDB.
- Infraestrutura: CloudFormation, IAM/OIDC, CloudWatch, origem S3 via OAC e links temporários de áudio.
- As setas são uma visão lógica de responsabilidades e acesso. A autenticação real envolve redirecionamentos entre navegador e Cognito; o navegador apresenta o access token à API. Cognito não chama a API pelo usuário.
- O avaliador pode devolver análise ao roteirista; o ciclo tem uma correção e encaminha a decisão ao responsável após duas reprovações.

### Modelo 02 · Fluxo editorial

Mostra sete etapas: coleta, relevância, roteiro, avaliação, síntese, validação do áudio e publicação privada com aviso. O modo automático exige aprovação do avaliador vinculada ao roteiro e verificação de duração antes da publicação.

### Modelo 03 · Módulos e IA

Apresenta os papéis funcionais e os módulos: coleta determinística, relevância/roteiro/avaliação com chamadas LLM separadas, produção Polly/S3 e player privado.

**Os agentes são coordenados explicitamente em Python.** Não são processos autônomos sem limites. A primeira versão permite até dois roteiros e bloqueia resultados pagos incertos; veja [o guia dos agentes](16-agentes-editoriais.md).

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

- Observar uma edição diária completa dos agentes na AWS antes de descrevê-la como validada sem intervenção.
- Explicar que a revisão automática compara o roteiro aos resumos, sem checagem factual externa.
- Atualizar a condição de open source quando o repositório estiver acessível ao público.
- Usar dados de demonstração se for incluir capturas do aplicativo.

A postagem no LinkedIn é uma ação separada; estes arquivos são material preparado para sua revisão e publicação.
