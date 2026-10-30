# 15 · Publicação automática e operação do MVP

O modo automático mantém o app, os áudios e os dados privados. Abrir o código no GitHub não habilita cadastro público nem publica o bucket.

## Fluxo diário

1. EventBridge Scheduler inicia a Lambda editorial às 8h30, de segunda a sexta, em America/Sao_Paulo. Feriados também estão incluídos.
2. Python coleta, verifica datas/URLs e deduplica as notícias. Sem conteúdo elegível, encerra sem inventar um episódio.
3. Os agentes de relevância, roteiro e avaliação fazem a seleção e o ciclo de correção descrito no [guia dos agentes](16-agentes-editoriais.md). OpenRouter retorna o roteiro estruturado. O aplicativo valida esquema, IDs, glossário e limite de texto. Se os IDs forem os mesmos em outra ordem, restaura a ordem da pauta e registra a alteração.
4. Somente após aprovação do avaliador vinculada ao hash do conteúdo, a autorização do roteiro é registrada com `mode=automatic`. A tarefa de áudio é vinculada ao hash do roteiro e enviada ao SQS.
5. O worker verifica novamente as fontes e gera voz Leo generativa no Polly. Trechos concluídos são preservados; chamadas de resultado incerto não são repetidas automaticamente.
6. O WAV precisa ter integridade válida, corresponder ao roteiro e durar até 600 segundos. A autorização automática do áudio também fica registrada como tal.
7. O worker publica no catálogo privado e só depois solicita o aviso Web Push. O celular pode estar com o app fechado; a entrega depende das permissões e conectividade do dispositivo.

A checagem automática valida estrutura, referências, URLs e integridade. Ela não comprova que todo fato narrado está correto nem avalia subjetivamente a qualidade da voz. As fontes ficam disponíveis para consulta no app.

## Ativar

Configure primeiro o app, as notificações e o agendamento conforme os guias anteriores. Use uma sessão AWS temporária:

```bat
aws login --profile radar-ia
.\.venv\Scripts\python.exe examples\configurar_automacao.py --plan --enable
```

O helper empacota API e Lambdas Linux, envia artefatos privados e prepara um change set. Revise `local-output/deploy/automatic-change-set.json` antes de executar o comando exibido. A execução do change set ativa `AutomaticPublicationEnabled=true` e permite à Lambda editorial enviar tarefas somente para a fila de áudio do projeto. Ela continua sem permissão Polly ou escrita no catálogo.

Uma instalação nova começa com esse parâmetro em `false`. Os valores secretos continuam no Secrets Manager; o parâmetro não contém credenciais. O helper geral de deploy preserva o modo existente.

## Pausar e recuperar

Para voltar ao fluxo acompanhado, prepare e execute um plano com `--plan --disable`. Isso bloqueia novas publicações automáticas; tarefas já em execução podem concluir. Para pausar todo o disparo diário, desative o Scheduler também. Não exclua tarefas ou checkpoints para forçar uma nova cobrança.

O modo automático não faz repetição ilimitada nem possui um teto financeiro em dólares. As barreiras são uma tarefa editorial por data, hashes de conteúdo, ausência de repetição paga quando o resultado é incerto, até sete notícias, até mil palavras e áudio de até dez minutos. Custos continuam dependendo de caracteres/tokens, armazenamento e utilização. Configure alertas de orçamento na sua conta.

Falhas param o fluxo e aparecem no painel. O aviso ao usuário é de episódio publicado; não há aviso push de falha implementado. Consulte o diagnóstico diário e a fila de falhas quando não houver edição:

```bat
.\.venv\Scripts\python.exe examples\diagnosticar_agendamento_aws.py
```

Uma edição parcialmente concluída pode ser retomada por um operador usando os resultados salvos. A publicação automática não foi liberada para contornar bloqueios de validação ou dados pagos incertos.

## Evidências e limites da primeira versão

O fluxo acompanhado foi usado em produção, incluindo publicação e notificação recebida em Android real. Testes de integração exercitam os módulos reais de produção e armazenamento com serviços externos simulados: autorização automática, síntese, publicação, aviso após catálogo, desativação e entrega duplicada. Eles não geram cobranças nem substituem uma edição diária real sem intervenção.

O disparo de 30/10/2026 chegou às 8h30 com três segundos de atraso e exigiu recuperação da ordem dos IDs. A primeira edição sem intervenção após ativar esse modo ainda precisa ser observada. Isso deve constar como limite conhecido da versão inicial.
