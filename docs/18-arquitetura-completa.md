# 18 · Organograma completo: agentes, serviços e aprendizado

O diagrama descreve a implementação, incluindo caminhos de reprovação, decisão humana e memória editorial. Os agentes LLM têm papéis separados e são coordenados por Python; não executam livremente código ou alterações de infraestrutura.

```mermaid
flowchart TB
    subgraph CONTROLE[Infraestrutura e operação]
        GH[GitHub Actions: testes e operação manual] --> OIDC[IAM / OIDC: credenciais temporárias]
        CFN[CloudFormation: template e helpers] --> AWS[Recursos AWS do projeto]
        SM[Secrets Manager: OpenRouter e VAPID]
        CW[CloudWatch: logs de execução]
    end
    subgraph EDITORIAL[Lambda editorial: Python]
        SCH[EventBridge Scheduler: seg–sex, 8h30 / São Paulo] --> CLAIM[DynamoDB Jobs: uma execução por data]
        CLAIM --> RESTORE[S3 privado: restaurar checkpoint / consultar catálogo]
        RESTORE --> COL[1. Coletor: RSS / httpx / feedparser]
        RSS[Fontes RSS configuradas] --> COL
        COL --> RULES[Datas / HTTPS / domínios / deduplicação / grade semanal]
        RULES --> REL[2. Agente de relevância: nota 0–5 e motivo por ID]
        REL -->|Notas >= 3| WR[3. Roteirista: PT-BR / inglês explicado / JSON]
        REL -->|Nenhuma elegível| EMPTY[Sem conteúdo: encerrar sem Polly]
        WR --> VALID[Pydantic / IDs / glossário / limite de texto]
        VALID -->|Válido| REV[4. Avaliador: comparar roteiro às evidências]
        VALID -->|Resposta inválida conhecida: uma correção| WR
        VALID -->|Resultado incerto ou erro persistente| BLOCK[Interromper e preservar tentativa]
        REV -->|Primeira reprovação + análise| WR
        REV -->|Segunda reprovação| HOLD[Aguardando decisão humana]
        REV -->|Aprovado / nota >= 4 / sem bloqueantes| BIND[Aprovação vinculada ao hash do roteiro]
        SM --> REL
        SM --> WR
        SM --> REV
        REL <--> OPEN[OpenRouter / modelo configurado]
        WR <--> OPEN
        REV <--> OPEN
    end
    subgraph APRENDIZADO[Memória editorial privada]
        HOLD --> REVIEWNOTICE[SQS avisos: solicitação de revisão]
        HUMAN[Responsável: texto + pareceres + versões + diferenças] -->|Aprovar / registrar preferência| HAPP[API: aprovação humana / hash / autor / horário]
        HAPP --> MEMORY[S3: observação e trecho do roteiro aceito]
        MEMORY --> LIMIT[Até 5 aprovações humanas dos 14 dias anteriores]
        LIMIT -. contexto, sem alterar instruções de sistema .-> REL
        LIMIT -. contexto, sem alterar instruções de sistema .-> WR
        LIMIT -. contexto, sem alterar instruções de sistema .-> REV
        HAPP --> BIND
    end
    subgraph PRODUCAO[Produção e publicação]
        BIND --> MODE[Modo automático habilitado]
        MODE --> AQ[SQS áudio: tarefa por hash / voz / versão]
        AQ --> WORK[5. Lambda worker: validar aprovação e fontes]
        WORK --> POLLY[Amazon Polly: Leo generativa / SSML]
        POLLY --> WAV[Integridade / roteiro correspondente / WAV até 600 s]
        WAV -->|Inválido| BLOCK
        WAV -->|Válido| CAT[S3 privado: áudio + catálogo / escrita condicional]
        CAT --> STATE[S3: cobertura e estado editorial após catálogo]
        STATE --> NQ[SQS avisos: episódio publicado]
        REVIEWNOTICE --> NOTIFIER[Lambda worker: conferir se revisão ainda está pendente]
        NQ --> NOTIFIER
        NOTIFIER --> LEDGER[DynamoDB Jobs: deduplicar por aviso e dispositivo]
        LEDGER --> PUSH[Web Push / VAPID: payload genérico]
        SM --> PUSH
    end
    subgraph APP[Aplicativo e consumo privado]
        PHONE[Android / navegador / PWA] --> CF[CloudFront / HTTPS / origem privada OAC]
        CF --> WEB[S3 da interface: HTML / CSS / JS]
        PHONE <--> COG[Cognito: Authorization Code / PKCE / sessão persistente]
        PHONE -->|Access token| GW[API Gateway: validação JWT]
        GW --> API[Lambda API: biblioteca / aprovação / refinamento / links temporários]
        API --> PROG[DynamoDB Progress: posição / ouvido por usuário]
        API --> SUBS[DynamoDB Push: assinaturas privadas]
        SUBS --> NOTIFIER
        API -->|Leitura do catálogo e link assinado| CAT
        PHONE -->|Reprodução por link temporário| CAT
        API --> HUMAN
        PUSH -->|Pronto: Para ouvir / revisão: Análise e aprovação| PHONE
    end
    COL -. checkpoints .-> SNAP[S3: respostas / roteiros / pareceres / recibos]
    REV -. checkpoints .-> SNAP
    WORK -. checkpoints .-> SNAP
    BLOCK --> JOBFAIL[DynamoDB: failed / needs_review]
    CLAIM -. falhas não tratadas .-> DLQE[SQS: fila de falhas editorial]
    AQ -. entrega/processamento não tratado .-> DLQA[SQS: dead letter do worker]
    WORK -. logs .-> CW
    REV -. logs .-> CW
    API -. logs .-> CW
```

## Como cada agente trabalha

| Papel | Recebe | Decide ou produz | Limite |
|---|---|---|---|
| Coletor | RSS, domínios permitidos e janela editorial | Evidências e candidatas deduplicadas | Não usa LLM; não lê a internet sem restrição |
| Relevância | Até 7 candidatas pré-selecionadas + preferências humanas | Nota e justificativa; mantém notas a partir de 3 | Não pode inventar IDs ou incluir fontes externas |
| Roteirista | Evidências selecionadas, memória e parecer anterior | Roteiro, títulos/resumos PT-BR e inglês contextualizado | Até duas versões; máximo inicial de mil palavras |
| Avaliador | Roteiro, evidências e memória | Aprovação ou correções por notícia; nota 0–5 | Aprova com nota >= 4 e sem bloqueantes; não é checagem factual externa |
| Produtor | Aprovação ligada ao conteúdo e tarefa idempotente | Áudio Polly, verificação, publicação e aviso | Sem resposta paga salva, não repete automaticamente; áudio até dez minutos |
| Responsável humano | Segundo roteiro reprovado, pareceres e mudanças | Aprovação final e preferências futuras | A decisão não remove verificações técnicas nem modifica o roteiro silenciosamente |

## Como ele “aprende”

1. Uma aprovação humana pelo app registra observação opcional, trecho aceito, hash, autor e horário.
2. Um registro pequeno e privado é salvo no S3 por data; repetição da mesma aprovação não duplica o evento.
3. Na próxima edição, o sistema carrega até cinco aprovações dos 14 dias anteriores, pertencentes ao responsável configurado.
4. Relevância, roteirista e avaliador recebem esse contexto como preferências editoriais. Fontes e instruções de sistema continuam prevalecendo.
5. O painel mostra o contexto efetivamente usado naquela edição, as versões preservadas e uma comparação textual.

Esse mecanismo é memória contextual. Não altera pesos do modelo, não faz fine-tuning, não reescreve código e não comprova que toda edição ficou melhor. Aprovações automáticas não alimentam a memória. A janela de consulta não apaga os registros S3; o administrador pode remover preferências no armazenamento privado.

## Catálogo de serviços

| Serviço | Função |
|---|---|
| EventBridge Scheduler | Iniciar rotina em fuso São Paulo, sem computador ligado |
| Lambda editorial | Coordenar coleta e agentes, guardar checkpoints e enfileirar produção/revisão |
| OpenRouter / Gemini configurado | Chamadas LLM separadas para relevância, roteiro e avaliação |
| SQS áudio / avisos / filas de falha | Desacoplar trabalho e encaminhar falhas não tratadas |
| Lambda worker | Gerar áudio, publicar e entregar avisos com deduplicação |
| Amazon Polly | Síntese Leo generativa com SSML |
| S3 de áudio | Catálogo, episódios, checkpoints, memória e artefatos de implantação privados |
| DynamoDB Jobs | Reivindicação de tarefas, status e ledger de avisos |
| CloudFront + S3 web + OAC | Entregar a interface por HTTPS com origem privada |
| Cognito | Login sem cadastro público; OAuth/PKCE |
| API Gateway + Lambda API | Validar acesso e operar biblioteca, progresso, revisão e links assinados |
| DynamoDB Progress / Push | Posição de escuta e assinaturas por responsável/dispositivo |
| Secrets Manager | Segredos OpenRouter e VAPID fora do repositório |
| IAM / OIDC | Permissões por função e acesso temporário do GitHub |
| CloudWatch | Logs de execução, sem registrar chaves ou payloads privados de push |
| CloudFormation | Recursos declarados em arquivo versionado |
| GitHub Actions | Testes e operação manual; seu cron de produção fica bloqueado quando o Scheduler AWS está ativo |

Os logs não constituem, por si só, um painel de métricas de qualidade/custo. Avaliação mensurável de roteiros e observabilidade mais completa são evoluções propostas.
