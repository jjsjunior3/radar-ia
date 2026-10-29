# Aplicativo privado hospedado — preparação para Android

## Arquitetura escolhida

- CloudFront: interface HTTPS em endereço próprio da distribuição, sem exigir domínio comprado.
- S3 separado: arquivos públicos da interface (HTML, CSS, JS, ícone). Bucket privado acessível pelo CloudFront via OAC.
- Cognito: tela de login com cadastro público desativado. Fluxo authorization code + PKCE, sem client secret no navegador.
- API Gateway: valida assinatura, emissor, audiência, validade e escopo openid do access token antes de chamar o Lambda. Lambda rejeita ID tokens.
- Lambda Python: consulta catálogo, emite link temporário para episódio e grava progresso. O papel não pode gerar voz nem escrever no catálogo/áudios publicados; a revisão de roteiro permite escrever somente nos checkpoints de produção, com autorização do responsável.
- DynamoDB: progresso por identificador sub do Cognito e episódio; usuário não escolhe user_id no corpo da requisição.
- S3 de áudio existente: continua privado, sem conceder leitura pública ao CloudFront da interface.

A página de entrada e o código da interface são públicos. Biblioteca, catálogo, progresso e links de áudio exigem login. Isso é privacidade de dados, não ocultação de HTML/JS; compatível com código open source. Um link assinado pode ser usado por quem o possuir enquanto válido; sair do app não revoga instantaneamente um link já emitido.

## Estado desta entrega

Infraestrutura implantada. O proprietário confirmou login, reprodução, progresso e uso no computador e Android, incluindo instalação do aplicativo no celular. As seções de recuperação abaixo registram o histórico de implantação. A execução manual de preparação pelo GitHub Actions também foi validada; a primeira produção agendada de uma edição nova ainda precisa ser acompanhada (ver guia 07).

Template editável: infra/private-app.json. Pacote Lambda contém apenas __init__.py e hosted_api.py; usa boto3 fornecido pelo runtime Python3.12 da AWS. Não empacota .env, e-mail, chaves, SQLite ou episódios. Fixação/empacotamento do SDK é melhoria de reprodutibilidade para produção.

## Implantar

O perfil radar-ia precisa de permissão para provisionar CloudFormation, IAM roles, Lambda, API Gateway, CloudFront, S3, Cognito, DynamoDB e logs. Essas permissões são de provisionamento e não são dadas ao Lambda. Erro AccessDenied deve ser analisado; não adicionar AdministratorAccess automaticamente.

```bat
.\.venv\Scripts\python.exe examples\deploy_private_app.py
```

O comando acima só prepara o pacote. Para criar recursos (com custos AWS):

```bat
.\.venv\Scripts\python.exe examples\deploy_private_app.py --deploy
```

Ele envia o pacote a um prefixo de deployments do bucket de áudio existente, valida o template na AWS, cria/atualiza a stack radar-ia-private-app, espera conclusão e envia somente arquivos web permitidos ao bucket da interface. CloudFront pode demorar vários minutos. Uma atualização sem mudanças de template ainda envia a interface e invalida o cache. Credenciais temporárias precisam continuar válidas durante a operação.

Outputs ficam em local-output/deploy/outputs.json. config.json hospedado contém apenas endpoint, domínio de login e client ID (identificadores públicos), nunca segredos. CloudFormation não cria o usuário automaticamente.

## Primeiro acesso: senha definida pelo proprietário

APP_LOGIN_EMAIL no .env já contém o e-mail informado pelo usuário. Executar pessoalmente:

```bat
.\.venv\Scripts\python.exe examples\configurar_login_app.py
```

A senha é solicitada por getpass, não é exibida nem passada em argumentos, e é enviada diretamente ao Cognito. O assistente não deve executar esse comando interativo nem receber a senha no chat. Sem envio de convite por e-mail (MessageAction SUPPRESS). Usuário criado como acesso administrativo, cadastro público bloqueado. Não marcamos o e-mail como verificado sem um fluxo de verificação; recuperação por e-mail requer etapa adicional. Perda da senha, neste estágio, é resolvida pelo proprietário via comando administrativo. Reexecutar para usuário existente pede ALTERAR antes de trocar senha.

Abrir WebUrl no Android e fazer login. A senha do app é independente de IAM/root. Não usar a senha root no aplicativo.

## Progresso e sessão

SQLite permanece no protótipo local. DynamoDB guarda progresso por usuário/dispositivo compartilhado na versão hospedada; não há migração automática do progresso local. Atualizações concorrentes usam versão condicional; conflito devolve 409 e pede atualização, sem sobrescrever silenciosamente o outro dispositivo.

Access token fica em memória. sessionStorage mantém somente state/verifier PKCE até a troca por token. Recarregar exige novo fluxo de login; a sessão do Cognito pode facilitar a entrada. Refresh tokens não são persistidos nem usados nesta versão. Logout limpa token local e sessão hospedada; avaliar revogação adicional e recuperação de conta antes de abrir acesso a outras pessoas. MFA TOTP configurável, opcional; não alegar que está ativo sem configurar.

## Custos e operação

Recursos de cobrança por uso: Lambda, HTTP API, DynamoDB, Cognito, S3 e tráfego CloudFront. DynamoDB também tem recuperação pontual habilitada, com cobrança de backup conforme armazenamento. Logs têm retenção de 14 dias. Não há garantia de custo zero ou de enquadramento em free tier.

Stack tem proteção contra exclusão. Tabela, user pool e bucket web têm retenção; mesmo ao remover a stack, esses recursos podem permanecer e continuar gerando custo. Revisar e remover explicitamente quando não forem mais necessários. Bucket de áudio preexistente não é gerenciado pela stack. Não há limpeza automática de uploads de pacotes antigos.

## Instalação e verificação Android

Manifest e ícone preparados. Instalação/atalho pela opção do Chrome precisa ser conferida no aparelho. Sem offline ou service worker nesta etapa: não armazenar respostas privadas ou URLs assinadas em cache. Testar áudio com tela bloqueada, interrupção, troca de rede, expiração de link, filtros e retomada entre computador e celular.

Checklist antes de considerar hospedagem concluída:
1. Sem login, API retorna 401; interface não exibe catálogo.
2. Login do usuário cadastrado; cadastro público indisponível.
3. Áudio toca via link temporário; URL direta do S3 não autoriza acesso público.
4. Progresso de um usuário não aparece para outro.
5. Pausar no computador e continuar no Android após atualizar biblioteca.
6. Logout, expiração da sessão e link expirado produzem orientação clara.

## Fontes oficiais

- https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html
- https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html

## Recuperação da primeira implantação

Diagnóstico real: ApiFunction falhou porque ReservedConcurrentExecutions=5 reduziria a concorrência não reservada da conta abaixo do mínimo de 10. Distribution foi cancelada como consequência; não era falha de CloudFront.

Correção: remover reserva fixa do Lambda, mantendo throttling HTTP API em cinco requisições por segundo e burst dez. Throttling não é teto financeiro nem limite exato de execução concorrente. Não solicitar aumento de quota para este MVP.

A stack terminou em ROLLBACK_COMPLETE. Nesse estado, não aceita update comum. O novo parâmetro --deploy --recover-failed registra inventário, verifica que os recursos estão DELETE_COMPLETE/DELETE_SKIPPED, desativa a proteção contra exclusão somente nessa stack falhada, remove a stack e aguarda exclusão antes de criar novamente. Stacks saudáveis nunca são apagadas por esse parâmetro. A nova criação reativa proteção contra exclusão.

Três recursos retidos foram observados: ProgressTable, UserPool e WebBucket. Não são apagados automaticamente; manter inventário para revisão/limpeza posterior. O bucket de áudio privado preexistente não faz parte da stack e permanece intacto. Se houver falhas repetidas, revisar recursos retidos para não acumular infraestrutura desnecessária.

Comando de recuperação acompanhado:

```bat
.\.venv\Scripts\python.exe examples\deploy_private_app.py --deploy --recover-failed
```

Validação após correção: 138 testes locais e validate-template da AWS passaram. validate-template não garante sucesso de provisionamento ou quotas; aguardar resultado real. O script agora imprime CREATE_FAILED/UPDATE_FAILED ao ocorrer erro de espera em vez de mostrar apenas traceback de WaiterError.


## Política de senha atualizada

A pedido do proprietário: mínimo de oito caracteres, com maiúscula, minúscula, número e símbolo. Template e comando de configuração usam a mesma regra. Reduzir o mínimo não altera senhas existentes.

Atualização remota confirmada: stack UPDATE_COMPLETE e describe_user_pool retornou MinimumLength=8, mantendo requisitos de maiúscula/minúscula/número/símbolo. Aplicado por change set derivado do template remoto, revisado como uma única modificação de Policies no UserPool, sem substituição. O comando de senha agora consulta a política real antes de pedir a senha, evitando divergência local/remota. Usuário previamente criado sem senha permanente é reaproveitado; usuário CONFIRMED exige confirmação de troca. Nenhuma senha foi recebida ou definida pelo assistente.

## Recuperação de retorno OAuth inválido/expirado

Primeiro teste de login não exibiu episódio. Diagnóstico: catálogo S3 contém uma entrada; nenhum evento Lambda no período consultado; tela mostrou Retorno de login inválido ou expirado. Não era biblioteca vazia confirmada. Sem consultar tokens ou senha do usuário.

Correção publicada somente nos arquivos web: preparar botão Entrar antes de validar callback, mostrar estado desconectado e mensagem global em caso de falha, manter biblioteca escondida até autenticação válida. Validação state/PKCE e limite de dez minutos permanecem. Timestamps inválidos ou futuros são rejeitados. Modo hospedado deixa de exibir rodapé de prévia local após carregar configuração.

Verificação: 138 testes Python + três testes JavaScript do fluxo expirado/state incorreto/timestamp futuro passaram. auth.js atualizado confirmado via HTTPS; invalidação CloudFront solicitada. Login autenticado e reprodução após correção ainda dependem do teste do proprietário, sem compartilhar credenciais.

Atualizações futuras de interface usam examples/publicar_interface.py --publish, sem reaplicar infraestrutura ou políticas IAM/Cognito. Recomeçar login pelo endereço raiz do aplicativo; não reutilizar um link Cognito antigo com state/code_challenge vencidos.
