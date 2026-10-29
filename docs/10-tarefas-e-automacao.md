# 10 · Geração em segundo plano e caminho para automação

## Objetivo do produto

O destino do Radar IA é produzir e publicar episódios automaticamente e notificar o proprietário quando estiverem prontos. As aprovações humanas são temporárias, durante os ajustes de conteúdo e voz. O modo acompanhado continua disponível para diagnóstico e mudanças editoriais.

A automação completa ainda não está habilitada. Hoje o agendamento prepara o roteiro; a geração de voz e a publicação exigem confirmação. A notificação de episódio pronto será uma etapa própria, disparada somente após confirmar a entrada no catálogo privado. O canal de notificação ainda será definido; não há envio implementado neste incremento.

## Fluxo pelo aplicativo

1. Leia o roteiro e confira as fontes; aprove a versão exata.
2. Autorize a geração com Leo generative. A Polly é cobrada nesta etapa.
3. A API cria uma tarefa no DynamoDB e envia seu identificador à fila SQS.
4. Uma Lambda separada restaura o checkpoint privado e reutiliza o mesmo código Python da produção local.
5. O worker verifica datas e URLs e salva o estado antes de cada chamada à Polly.
6. Ouça a prévia privada; aprove o áudio e solicite publicação.
7. Outra tarefa atualiza o catálogo; o episódio passa a aparecer na biblioteca. Atualize a biblioteca se necessário.

Você pode fechar o app durante o processamento. Ao voltar, o painel recupera o estado; enquanto aberto, consulta tarefas a cada cinco segundos. A prévia usa URL temporária de cinco minutos; carregue novamente caso expire. A escuta da prévia não altera o progresso da biblioteca.

## Decisões técnicas

- **SQS:** separa requisições curtas da geração demorada. A entrega pode ocorrer mais de uma vez; uma atualização condicional no DynamoDB permite reivindicar a tarefa uma única vez.
- **DynamoDB:** identificador determinístico vinculado à edição, roteiro, revisão, voz e renderizador. Dois cliques recuperam a mesma tarefa. Retenção por TTL de 30 dias, com remoção eventual.
- **Lambda worker:** Python 3.12 Linux x86_64, 512 MiB, até 15 minutos. Fila com visibilidade de 90 minutos e máximo de duas execuções concorrentes. Fila de mensagens não processadas após três entregas com falha de infraestrutura.
- **Checkpoint S3:** gravação condicional por ETag impede sobrescrever uma edição modificada em paralelo. Se uma chamada paga ficar sem resposta salva, a tarefa requer análise; não há repetição automática dessa chamada.
- **Permissões:** a API não chama Polly nem grava episódios publicados. O worker recebe apenas os acessos necessários ao bucket do projeto, tarefas, fila, logs e síntese de voz.
- **Pacotes separados:** a API contém somente módulos leves; o worker inclui dependências Linux, sem copiar bibliotecas nativas da venv Windows. Nenhuma chave OpenRouter é necessária no worker de áudio/publicação.

Uma tarefa em execução há mais de vinte minutos aparece como resultado incerto. Retomadas seguras usam os trechos já salvos. Erros editoriais e resultados incertos não exibem botão de repetição; revisar o checkpoint antes de qualquer nova chamada paga. Uma falha ao enviar a mensagem pode ser recuperada reenviando a mesma tarefa, sem criar novo identificador.

## Próximos incrementos aprovados

1. Validar o fluxo completo no celular com uma edição nova e medir custo/qualidade.
2. Melhorar confiabilidade do agendamento, diagnóstico e retenção de falhas.
3. Identidade visual do login: logo e cores aplicados ao Cognito clássico; ver [guia 11](11-identidade-login.md).
4. Implementar modo automático com limites de custo/duração, critérios editoriais e tratamento de falhas. Ativá-lo após concluir os ajustes finos.
5. Notificar somente quando um episódio estiver pronto e confirmado no catálogo; evitar notificações duplicadas para a mesma edição.
6. Auditar o repositório para abertura pública e finalizar materiais do portfólio/LinkedIn.

Código aberto e acesso público aos episódios são decisões distintas: o código pode ser público enquanto a biblioteca permanece privada.

## Referências técnicas

- [Empacotamento Python na Lambda](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html).
- [Lambda com SQS e processamento idempotente](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html).


## Validação do incremento (29/10/2026)

- 211 testes Python e três testes JavaScript passaram localmente; o workflow de testes do commit de implementação também passou.
- Teste integrado com serviços simulados percorreu aprovação do texto, síntese, checkpoint, aprovação do WAV e publicação real pelo módulo de catálogo; uma entrega duplicada não chamou Polly novamente.
- Navegador isolado verificou as quatro confirmações, prévia, payloads e layout de 390 pixels. As chamadas desse teste foram simuladas.
- CloudFormation concluiu a atualização sem substituir recursos existentes. O worker Linux foi invocado na AWS, e uma tarefa de diagnóstico percorreu SQS, reivindicação condicional e atualização DynamoDB. A tarefa foi rejeitada antes da síntese e removida após o teste.
- A API implantada respondeu ao responsável, recusou outro usuário com 403 e recusou acesso sem login com 401. Arquivos do CloudFront foram comparados aos arquivos locais.
- Nenhum episódio novo foi gerado para testar a implantação. A primeira geração e publicação de uma edição nova pelo aplicativo ainda requer validação no uso acompanhado.
