# S3 privado e catálogo de episódios

## Decisões

- Bucket exclusivo na região us-east-1, nome gerado registrado em S3_BUCKET no .env.
- Todos os bloqueios de acesso público ativados; ObjectOwnership BucketOwnerEnforced (sem ACLs).
- Criptografia SSE-S3 AES256; política nega transporte HTTP. Não configurar hospedagem pública.
- Um diretório imutável por versão de episódio, identificado por data e hash do áudio/roteiro.
- Catálogo contém referências internas, nunca URLs temporárias. URLs assinadas são geradas sob demanda.
- Atualizar catálogo por IfMatch/IfNoneMatch para não sobrescrever alteração concorrente. Arquivos precedem o catálogo; falha pode deixar objetos órfãos, mas não entrada apontando para arquivos ainda não enviados.
- Repetir mesmo envio não duplica o episódio; versão de áudio/roteiro diferente gera outra entrada. Seleção de versão final/substituição é evolução futura.
- Progresso de escuta é dado por usuário e não será salvo neste catálogo compartilhado.

## Comandos

```bat
.\.venv\Scripts\python.exe examples\configurar_s3.py --create
.\.venv\Scripts\python.exe examples\configurar_s3.py --check
.\.venv\Scripts\python.exe examples\enviar_episodio.py --audio-dir local-output/roteiros/20261028T145020657999Z/revisao-local/audio/20261028T175448972644Z --date 2026-10-28 --upload
```

Depois do envio, s3-receipt.json fica na pasta do áudio. Para gerar link privado temporário:

```bat
.\.venv\Scripts\python.exe examples\link_episodio.py --receipt local-output/roteiros/20261028T145020657999Z/revisao-local/audio/20261028T175448972644Z/s3-receipt.json
```

O link fica em link-temporario.txt, fora do Git. Não incluí-lo em README, catálogo ou posts. Quem tiver o link pode usar o acesso enquanto válido. Duração solicitada: cinco minutos, limitada também à validade da credencial temporária. Renovar sob demanda no futuro app.

A criação não modifica buckets preexistentes. Se ocorrer falha parcial após criar o bucket, --check permite conferir, mas reparo de configuração deve ser analisado explicitamente; não apagar/recriar automaticamente. Erro de rede não confirma se a criação aconteceu.

## Permissões

config/iam-runtime-policy.json contém sugestão de permissões de execução, restrita ao bucket escolhido/prefixo. SignInLocalDevelopmentAccess é adicional para login local. Provisionar bucket requer permissões administrativas de S3 que não estão na política de execução. Nenhuma política foi anexada automaticamente; usuário IAM atual pode ter acesso mais amplo. Separar função de provisionamento da função de execução antes de automatizar.

## Custos e limites

Custos de armazenamento em GB/mês, PUT/GET e transferência de saída; conferir preços da região em https://aws.amazon.com/s3/pricing/ . Um WAV de 217,6 segundos tem cerca de 7 MB; MP3 de distribuição reduzirá armazenamento e tráfego no futuro. Não há expiração automática de episódios nesta versão. Não habilitamos versionamento do bucket nesta etapa; alterações concorrentes são protegidas por condição e versões de episódios usam nomes diferentes.

Upload privado não integra ainda histórico local used_in nem marco da última edição concluída. Integrar esses estados de forma recuperável antes do agendamento; não marcar manualmente uma edição como concluída só porque arquivos existem. Este catálogo é a base do app, não o pipeline diário final.

Fontes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html ; https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html ; https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html .
