# 12 · Agendamento editorial na AWS

## Decisão e evidência

Em 29/10/2026, o GitHub registrou o evento agendado às 14h30 de São Paulo, cerca de seis horas depois das 8h30 configuradas. Branch, workflow e variável estavam corretos. O registro confirma o atraso, mas não determina a causa. O GitHub documenta que eventos agendados podem atrasar ou ser descartados em períodos de carga.

A produção diária passa para **EventBridge Scheduler → Lambda editorial**, com `cron(30 8 ? * MON-FRI *)`, fuso `America/Sao_Paulo` e janela flexível desativada. Scheduler trabalha com precisão de um minuto; 8h30 é o início previsto, não uma promessa de que o áudio estará pronto nesse instante. O computador e o celular podem estar desligados. Login no app serve para consultar, revisar e ouvir; não dispara a rotina diária.

O GitHub continua executando testes e permite etapas manuais. A variável `RADAR_SCHEDULE_ENABLED=false` bloqueia seu job de produção agendada. O bloco cron permanece como opção de retorno, sem depender de outra credencial permanente para a AWS. Não habilite os dois mecanismos ao mesmo tempo.

## O que roda automaticamente nesta fase

1. O Scheduler invoca a Lambda com o horário previsto da edição.
2. A Lambda valida dia útil, fuso/horário e atraso máximo de uma hora. Eventos antigos não criam edições de outro dia.
3. Uma tarefa determinística por data é criada e reivindicada condicionalmente no DynamoDB. Entregas duplicadas não iniciam outra geração.
4. O código `Production` restaura o checkpoint do S3 e consulta o catálogo. Uma edição já existente é preservada.
5. Coleta RSS, curadoria semanal e validação de URLs/datas usam os mesmos módulos do terminal.
6. A Lambda lê a chave OpenRouter no Secrets Manager e gera o roteiro com `max_retries=0`. O checkpoint registra a tentativa antes da chamada paga e salva a resposta antes da validação.
7. A edição fica em `awaiting_script_review` no aplicativo. Um dia sem conteúdo elegível termina em `no_content` e não chama a LLM.

**Voz e publicação ainda exigem revisão.** As aprovações são provisórias durante os ajustes finos. Publicação totalmente automática e notificação no Android continuam no roteiro de evolução.

## Separação de permissões

A Lambda editorial tem leitura do catálogo, leitura/escrita de checkpoints, tarefas DynamoDB e acesso ao segredo específico do OpenRouter. Não recebe permissão Polly nem escrita em catálogo/episódios. A Lambda de áudio/publicação e a API continuam com seus papéis próprios.

A chave não é incluída no ZIP, template ou variáveis de ambiente da Lambda. Apenas o ARN do segredo identifica onde buscá-la. O script verifica a autenticação do OpenRouter sem gerar tokens antes de criar o segredo. Se o segredo já existir, não substitui seu conteúdo implicitamente. Uma eventual troca da chave exige atualizar o segredo de forma administrativa e também o segredo GitHub usado na operação manual.

## Falhas e retomadas

- Lambda editorial: Python 3.12 Linux x86_64, 512 MiB, até 15 minutos; coleta com limite de tempo para reservar espaço à geração.
- Scheduler pode tentar novamente a entrega à API Lambda duas vezes, dentro de uma hora. Isso não autoriza repetir a geração.
- A execução assíncrona da Lambda não faz nova tentativa automática após erro de processamento. Falhas vão para a fila privada `EditorialFailureQueue`, retida por 14 dias.
- A tarefa DynamoDB registra início, atraso, resultado e código de erro, sem mensagens do provedor ou credenciais. Logs ficam no CloudWatch por 14 dias.
- Uma chamada paga sem resposta persistida exige análise. Repetir o mesmo evento não ultrapassa a reivindicação diária.
- Na recuperação manual, consulte `production status` e o checkpoint antes de executar `prepare` ou `draft --execute`. Uma resposta salva pode ser reprocessada sem nova chamada; resultado incerto continua bloqueado pelo código de produção.

A fila e os logs permitem diagnóstico; ainda não enviam alerta ou notificação ao proprietário. O pipeline manual do GitHub não participa do bloqueio diário DynamoDB: durante uma execução AWS, aguarde a conclusão antes de operar a mesma edição manualmente. O ETag protege gravações concorrentes no S3, mas não substitui essa disciplina operacional entre ferramentas distintas.

## Implantação reproduzível

Com `.env`, sessão AWS e dependências do projeto configurados:

```bat
.\.venv\Scripts\python.exe examples\configurar_agendamento_aws.py --plan
```

O comando valida a chave existente, cria o segredo se ausente, monta um pacote Linux e cria um change set com o agendamento **desativado**. Não executa a atualização nem chama a geração. O plano fica em `local-output/deploy/editorial-change-set.json`.

Revise o plano e execute o change set com AWS CLI/CloudFormation. Atualize `local-output/deploy/outputs.json` a partir dos outputs da stack. Faça um teste administrativo da Lambda com `{"diagnostic":true}`: ele verifica pacote, bucket, existência do segredo e leitura da tabela, sem ler o valor do segredo nem chamar LLM/Polly.

Após a validação:

```bat
.\.venv\Scripts\python.exe examples\configurar_agendamento_aws.py --activate-plan
```

Revise e execute esse segundo change set. Somente então bloqueie o cron GitHub com `gh variable set RADAR_SCHEDULE_ENABLED --body false --repo SEU_USUARIO/radar-ia`. Não reative o GitHub enquanto o Scheduler AWS estiver habilitado. Em uma stack atualizada, o script geral de deploy preserva os parâmetros editoriais existentes; uma implantação nova começa sem essa rotina opcional até configurá-la.

## Diagnóstico diário

```bat
.\.venv\Scripts\python.exe examples\diagnosticar_agendamento_aws.py
```

O relatório mostra provedor, configuração de horário, estado do Scheduler, tarefa editorial do dia, atraso registrado, etapa no S3 e próximo horário previsto. Ele não gera conteúdo ou exibe chaves. `diagnosticar_agendamento.py` continua sendo o diagnóstico específico do GitHub, não do novo disparo AWS.

## Custos adicionais

O Secrets Manager custa aproximadamente **US$ 0,40 por segredo/mês**, além das requisições. O Scheduler oferece 14 milhões de invocações gratuitas por mês, compartilhadas conforme os termos da AWS; cerca de 22 disparos mensais são uma fração dessa faixa. Isso não torna o projeto inteiro gratuito: Lambda, S3, DynamoDB, SQS, logs, OpenRouter e Polly têm cobrança conforme consumo e condições da conta. Não há nova cobrança fixa de servidor dedicado.

Referências oficiais: [limitações do cron GitHub](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows), [horários e fusos do Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html), [preço do Scheduler](https://aws.amazon.com/eventbridge/pricing/), [preço do Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/).
## Validação em 29/10/2026

- 221 testes Python passaram localmente; o workflow GitHub do commit de implementação passou, incluindo os testes JavaScript existentes.
- CloudFormation instalou os sete recursos editoriais sem substituir recursos existentes; o Scheduler começou desativado. A ativação posterior modificou somente o estado do agendamento.
- Uma invocação administrativa `diagnostic` verificou o pacote Linux e acessos de leitura da Lambda. Um agendamento pontual de teste, criado com o mesmo papel e destino da rotina diária, chegou à Lambda e produziu o marcador `editorial_diagnostic_ok` no CloudWatch. Ele foi configurado para exclusão automática após a execução. Nenhuma geração OpenRouter ou Polly foi solicitada.
- O Scheduler diário foi consultado em estado `ENABLED`, com cron de segunda a sexta, fuso São Paulo e janela flexível `OFF`. O GitHub foi consultado com `RADAR_SCHEDULE_ENABLED=false`.
- O diagnóstico AWS confirmou a edição de hoje em `completed` e o próximo disparo previsto para **30/10/2026 às 8h30 de São Paulo**. Como a instalação ocorreu à noite, nenhum disparo diário era esperado retroativamente para hoje.
- **Ainda pendente:** validar uma edição nova completa preparada pela rotina diária. O teste pontual comprova entrega e acesso básico, não comprova a coleta de amanhã, qualidade do roteiro ou pontualidade futura.
