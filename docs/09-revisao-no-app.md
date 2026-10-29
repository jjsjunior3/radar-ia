# Revisão de roteiro pelo aplicativo

> Este guia registra a primeira etapa da interface. A geração em segundo plano, prévia, aprovação de áudio e publicação estão descritas no [guia 10](10-tarefas-e-automacao.md). A revisão humana é provisória durante os ajustes finos; o objetivo final é publicação automática com notificação.

## O que esta etapa entrega

Depois do login, a conta responsável vê o painel **Edição de hoje**, calculado no fuso America/Sao_Paulo. Ele mostra o tema, estado atual, texto da narração e links das fontes. A biblioteca e o player existentes continuam disponíveis.

Quando o estado é `awaiting_script_review`, o painel permite marcar **Li o roteiro e conferi as fontes desta versão** e selecionar **Aprovar roteiro**. O resultado é `script_approved` no mesmo checkpoint S3 utilizado pelo fluxo de produção. Não é uma aprovação simulada nem uma segunda base de dados.

**Aprovar o texto não chama LLM, não gera voz e não publica o episódio.** A geração de áudio exige outra confirmação explícita no modo acompanhado. Veja o guia 10 para executá-la pelo app. Edição/rejeição do roteiro ainda é uma evolução posterior.

Se a edição já foi publicada, o painel informa **Publicado** e mantém o texto/fontes para consulta, sem oferecer uma aprovação desnecessária. Se não há edição salva para hoje, informa que ela ainda não foi preparada.

## Proteções da aprovação

- API Gateway continua exigindo access token válido e escopo openid.
- Lambda aceita revisão somente quando o `sub` autenticado corresponde ao `REVIEWER_SUB` configurado. Outros ouvintes não recebem roteiro ou acesso às ações de revisão.
- A confirmação é explícita e vinculada a um digest do briefing e roteiro exibidos.
- O servidor recarrega a edição antes de aprovar. Conteúdo diferente retorna 409 e exige revisão da versão atual.
- A gravação usa IfMatch/ETag: uma atualização concorrente não pode ser sobrescrita.
- Repetir uma aprovação da mesma versão não reinicia o fluxo nem reescreve o checkpoint.
- Uma aprovação de texto só pode iniciar no estado de revisão, antes de haver áudio gerado.
- A API não aceita voz, publicação, identificador de usuário ou novo texto no corpo dessa ação.

## Infraestrutura

Rotas novas:

- `GET /api/production/{date}`: estado, texto e fontes da edição, apenas para o responsável.
- `POST /api/production/{date}/approve-script`: confirma a versão exibida, apenas para o responsável.

O corpo da aprovação contém somente `digest` e `confirmed: true`. Responses privados usam `Cache-Control: no-store`.

O pacote da Lambda inclui `hosted_api.py` e `review_api.py`, além do marcador de pacote. Usa biblioteca padrão e SDK AWS do runtime; não inclui .env, chaves de provedores ou dependências do gerador de roteiro.

O papel da API recebe leitura e escrita restritas a `production/editions/*`, além de listagem limitada a esse prefixo para identificar uma edição ausente sem confundi-la com acesso negado. Continua sem permissão Polly e sem escrita em `episodes/*` ou `catalog.json`.

O checkpoint ZIP é a fonte de verdade, com limites de 50 MiB e mil membros. Para consultar uma edição já com áudio, a API lê o ZIP, mas descompacta somente os arquivos de texto necessários. Isso é um compromisso do MVP: um índice de leitura separado pode reduzir transferência e latência quando o volume crescer. A aprovação ocorre antes da voz e regrava um checkpoint pequeno; os áudios publicados permanecem fora dessa ação.

## Configuração do responsável

O template tem o parâmetro `ReviewerSub`, vazio por padrão. Sem esse parâmetro, as rotas recusam revisão e o painel fica oculto. Não é suficiente informar um e-mail no navegador.

Em uma stack existente, o comando de implantação procura o usuário indicado por `APP_LOGIN_EMAIL` e resolve seu atributo `sub` no Cognito. Como alternativa administrativa, pode usar `APP_REVIEWER_SUB`. Nenhum desses valores é incluído no config.json público.

Em uma implantação nova, crie primeiro o usuário com o comando administrativo de login e depois atualize a stack para configurar o responsável. Isso não abre cadastro público.

## Implantação revisável

```bat
.\.venv\Scripts\python.exe examples\deploy_private_app.py --plan
```

O comando empacota/envia o código e cria um change set para uma stack existente, sem executá-lo. O resumo fica em `local-output/deploy/latest-change-set.json`. O modo de planejamento não recupera nem recria uma stack falhada.

Nesta entrega, o plano foi revisado e aplicado com mudanças na função da API, seu papel, integração e duas rotas; nenhuma substituição de recurso. Depois os arquivos estáticos foram publicados com `publicar_interface.py --publish`.

## Validação desta entrega

- 200 testes Python e 3 testes JavaScript passaram durante a implementação.
- Testes da API verificam responsável versus outro usuário, confirmação explícita, digest desatualizado, concorrência, idempotência e compatibilidade da aprovação web com o worker de produção.
- Um navegador isolado, com respostas simuladas, verificou seleção da confirmação, POST correto, pós-aprovação, renderização segura de texto e layout a 390 pixels sem rolagem horizontal. Capturas de prévia estão em `local-output/ui-review-preview/`.
- Na Lambda implantada, um evento de teste com o identificador do responsável retornou a edição concluída de 29/10, com roteiro e sete fontes. Outro identificador recebeu 403. Esses eventos administrativos não substituem o teste do login real no navegador.
- Como o roteiro de hoje já está aprovado/publicado, o botão de aprovação não aparece para essa edição. A primeira aprovação humana real pelo app será feita quando uma nova edição chegar ao estado de revisão.

## Próximo passo de uso

Recarregue o app e entre na conta se solicitado. Hoje o painel deve informar **Publicado**. Na próxima edição em revisão, leia o texto, confira as fontes, marque a confirmação e aprove pelo celular. Depois prossiga para a geração/escuta do áudio pelo fluxo acompanhado.
