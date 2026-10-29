# Produção acompanhada e GitHub Actions

## O que foi implementado

O comando `radar-ia production` conecta coleta, grade semanal, roteiro OpenRouter, revisão humana, Polly Camila generativa e publicação no catálogo privado existente. O comando sem argumentos agora mostra ajuda: o fluxo antigo de cinco notícias não é mais executado por padrão.

A rotina usa quantidade variável de notícias e mede o WAV final, com limite de 600 segundos. Uma edição sem conteúdo suficiente termina sem inventar notícias, gerar voz ou avançar a cobertura editorial.

Os arquivos de cada edição ficam em `radar-ia/production/editions/AAAA-MM-DD.zip` no mesmo bucket privado. O ZIP contém somente os arquivos de produção; não contém `.env`, credenciais AWS nem chave do OpenRouter. O estado editorial compartilhado fica em `radar-ia/production/editorial-state.json`.

## Por que guardar checkpoints

O computador do GitHub Actions é temporário. Sem estado remoto, uma tentativa nova perderia o que já foi gerado. Antes da chamada à LLM ou de cada trecho Polly, o programa salva o início da tentativa no S3. Depois salva a resposta e os resultados.

Se houver resposta salva da LLM, o programa consegue reprocessá-la sem solicitar outra geração. Se houver trecho de áudio completo e íntegro, ele é reaproveitado. Uma chamada iniciada sem resposta persistida é tratada como resultado incerto: não repetir automaticamente. Isso reduz cobranças repetidas, mas não garante cobrança única pelo provedor.

As gravações do estado e catálogo usam condições de versão (ETag). Uma execução que leu uma versão antiga não pode sobrescrever a versão nova. O workflow também usa uma fila de concorrência única e não cancela a produção em andamento.

## 1. Preparar a identidade AWS do GitHub

No CMD, na raiz do projeto, com o GitHub CLI autenticado e a sessão AWS válida:

```bat
.\.venv\Scripts\python.exe examples\configurar_github_aws.py
```

Esse comando consulta os dados do repositório e da conta AWS e grava os documentos IAM em `local-output/github-aws/`. Ainda não altera permissões. Confira `trust.json` e `permissions.json`.

A confiança permite somente o repositório informado e a branch `main`. Para repositórios criados depois de 15/07/2026, usa IDs numéricos do proprietário e repositório, conforme o formato atual padrão do GitHub. Organizações que customizaram o subject OIDC precisam revisar esse formato antes de criar a função.

Para criar o provedor OIDC, quando necessário, e a função `radar-ia-github-production`:

```bat
.\.venv\Scripts\python.exe examples\configurar_github_aws.py --create
```

O provedor existente é reaproveitado. O script não modifica provedores compartilhados nem amplia uma função existente divergente. A função recebe leitura/verificação do bucket, leitura/gravação no catálogo, episódios e estado de produção, e síntese Polly em us-east-1. Não recebe acesso administrativo a IAM, Cognito, Lambda, CloudFront ou progresso de escuta.

Se a sessão AWS expirou, execute `aws login --profile radar-ia` antes de tentar novamente. Não use credenciais root nem publique arquivos da pasta `.aws`.

## 2. Configurar variáveis e segredo no GitHub

```bat
.\.venv\Scripts\python.exe examples\configurar_github_repo.py --apply
```

O script lê os identificadores salvos no passo anterior e cadastra as variáveis `AWS_ROLE_ARN`, `S3_BUCKET` e `RADAR_SCHEDULE_ENABLED=false`. Lê a chave do OpenRouter do ambiente/.env e envia ao GitHub por entrada padrão, sem imprimir o valor nem colocá-lo nos argumentos do processo.

A chave fica em `Secrets`, com o nome `OPENROUTER_API_KEY`. Não é enviada ao Git e não deve ser colada no chat. Nenhuma chave permanente AWS é cadastrada: o GitHub usa OIDC e recebe uma sessão temporária.

## 3. Enviar o código e fazer a primeira execução manual

Depois de enviar o commit para `main`:

```bat
gh workflow run production.yml --ref main -f step=prepare
gh run list --workflow production.yml --limit 5
```

A etapa `prepare` consulta o catálogo, coleta e valida as candidatas e prepara a pauta. Não chama a LLM nem Polly. Se já existe episódio publicado para hoje, registra essa situação sem gerar outro.

No GitHub, abra Actions > Produção acompanhada do Radar IA para acompanhar o resultado. A execução do Actions ainda precisa ser validada na sua conta; testes locais não demonstram que a confiança OIDC e as permissões reais estão corretas.

## 4. Produzir uma edição com revisão humana

Os comandos abaixo usam hoje em São Paulo. Para retomar outra edição, acrescente `--date AAAA-MM-DD` nos comandos Python ou `-f date=AAAA-MM-DD` no `gh workflow run`. A coleta só prepara a edição de hoje; geração e publicação novas exigem pauta de até 24 horas.

| Etapa | Comando local usando estado privado remoto | Efeito |
|---|---|---|
| Preparar | `radar-ia production prepare` | Coleta e prepara pauta, sem LLM/Polly |
| Consultar/baixar | `radar-ia production status` | Copia arquivos privados para revisão local |
| Gerar roteiro | `radar-ia production draft --execute` | Chama OpenRouter quando ainda necessário; pode gerar custo |
| Aprovar roteiro | `radar-ia production approve-script --reviewed` | Confirma que você revisou o texto |
| Gerar voz | `radar-ia production audio --execute` | Usa Polly e mede o WAV; pode gerar custo |
| Aprovar voz | `radar-ia production approve-audio --reviewed` | Confirma que você ouviu e aprovou o WAV |
| Publicar | `radar-ia production publish --execute` | Envia episódio ao catálogo privado do aplicativo |

No seu ambiente Windows, use `.\.venv\Scripts\radar-ia.exe` no lugar de `radar-ia`. A alternativa equivalente é `.\.venv\Scripts\python.exe -m radar_ia.production_cli`.

Também é possível escolher a etapa em Run workflow, no GitHub. Escolher `draft`, `audio` ou `publish` autoriza o efeito indicado; escolher uma aprovação confirma a sua revisão humana. O workflow não aprova etapas sozinho.

Para revisar uma pauta ou roteiro produzido no GitHub:

```bat
.\.venv\Scripts\radar-ia.exe production status
```

O programa mostra uma pasta dentro de `local-output/revisoes-remotas/`. Abra `pauta.md`, `revisao.md`, `narracao.txt` ou `episode.wav`, conforme a etapa. Nenhum link público ou URL assinada é gravado no log do Actions. Não usamos artefatos públicos nem commits para os episódios.

A cópia baixada é somente para consulta. Alterações nela não são importadas automaticamente para o estado remoto; se precisar corrigir um roteiro, interrompa as aprovações e revise a edição antes de continuar. Uma futura interface de edição/rejeição ainda será implementada.

## 5. Habilitar a rotina, depois do teste manual

```bat
gh variable set RADAR_SCHEDULE_ENABLED --body true --repo jjsjunior3/radar-ia
```

O workflow tem cron `30 8 * * 1-5` e `timezone: America/Sao_Paulo`. Às 8h30, de segunda a sexta, inicia preparação e geração do roteiro. Ele para aguardando sua revisão: áudio e publicação continuam manuais nesta primeira versão acompanhada. Portanto, 8h30 é o horário de início da produção, não garantia de episódio disponível para ouvir nesse minuto.

O GitHub pode atrasar ou deixar de iniciar eventos agendados em períodos de sobrecarga. O agendamento não equivale a uma garantia de horário. A variável começa em `false` e permanece assim até você validar a execução manual.

Para suspender novas produções agendadas:

```bat
gh variable set RADAR_SCHEDULE_ENABLED --body false --repo jjsjunior3/radar-ia
```

Isso não cancela uma execução já iniciada.

## Recuperação e limites

### Primeira execução: OIDC aceito e AccessDenied no S3

A política inclui `s3:ListBucket` no bucket do projeto. Essa permissão permite distinguir arquivo ausente (404) de acesso negado (403) durante a primeira consulta ao estado. Ela não concede leitura do conteúdo de outros objetos, escrita em outros buckets ou acesso público. A política de objetos continua restrita aos caminhos do Radar IA.

Se a função foi criada com a primeira versão da política, aplique a migração:

```bat
.\.venv\Scripts\python.exe examples\configurar_github_aws.py --update
```

O comando aceita somente a política anterior exata, salva uma cópia local e adiciona essa permissão no bucket do projeto. Não altera a confiança OIDC, não recria recursos e rejeita outras divergências. Não é necessário cadastrar novamente variáveis ou segredos.

Depois de enviar o código corrigido com `git push`, inicie uma nova execução usando `gh workflow run production.yml --ref main -f step=prepare`. O erro agora informa operação e código AWS, sem imprimir a resposta completa. O AccessDenied original não informava a operação; por isso a nova execução ainda precisa confirmar a resolução.

Referência: [GetObject e diferença entre 403 e 404 no S3](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html).

### Outros casos

- Após uma falha, consulte `status`. Não remova marcadores de tentativa incerta sem examinar o que aconteceu e o custo registrado pelo provedor.
- Falha ao publicar não avança cobertura/uso editorial. O catálogo S3 é a confirmação de que o episódio existe.
- Se o catálogo foi confirmado, mas houve falha ao salvar o histórico editorial compartilhado, reexecute `publish --execute` para reconciliar; o upload identifica o mesmo episódio e não gera áudio nem roteiro novamente.
- Não misture o modo `--local` com o estado remoto da mesma edição. O modo local exige apenas um escritor.
- Cada snapshot tem limite de 50 MiB, suficiente para WAV/PCM mono de até 10 minutos nesta configuração. Snapshots são enviados em checkpoints; há operações S3 adicionais, armazenamento de rascunhos e possível transferência cobrada ao baixar para o computador. A retenção automática desses rascunhos é uma evolução futura.
- Somente resumo RSS, data declarada e acesso à URL são verificados. Isso não substitui checagem factual independente.
- O código foi validado localmente com serviços simulados. O primeiro teste real do workflow, a criação da função IAM e a ativação do cron são passos operacionais separados.

## Referências oficiais

- [OIDC GitHub com AWS e formato de subject](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [Agendamento, timezone e possíveis atrasos](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
