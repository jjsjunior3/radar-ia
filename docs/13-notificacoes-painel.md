# 13 · Avisos no Android e painel de produção

## Ativar no celular

1. Atualize o Radar IA instalado ou abra sua URL no Chrome atualizado do Android.
2. Entre na sua conta, se necessário.
3. No cartão **Um aviso quando estiver pronto**, toque em **Ativar avisos neste dispositivo**.
4. Permita notificações no diálogo do navegador/Android.
5. Toque em **Enviar aviso de teste** e confira a área de notificações.

A permissão só é solicitada depois de um clique seu. Se estiver bloqueada, libere nas configurações do site e, quando necessário, nas configurações de notificações do Android. Você pode usar **Desativar avisos**; o botão **Sair** também tenta remover a assinatura deste dispositivo. Cada navegador/dispositivo tem uma assinatura própria. O MVP permite até cinco dispositivos da conta responsável.

O teste é solicitado para este dispositivo e deduplicado por minuto. A confirmação na interface significa que a solicitação entrou na fila, não que o Android já exibiu a mensagem. Entrega depende de conexão, permissões, navegador e gerenciamento de bateria. A validação em um Android real exige o teste acima; os testes automatizados não substituem essa confirmação.

## Fluxo de um episódio publicado

O worker usado pelo aplicativo confirma o catálogo privado e o checkpoint antes de enviar o identificador do episódio à fila de notificações. Na entrega, o catálogo é conferido novamente: sem episódio publicado, nenhum aviso é enviado.

Uma tarefa separada na mesma Lambda processa a fila, lê as assinaturas privadas e usa Web Push com VAPID. O payload é criptografado e contém texto genérico. Nenhum áudio, token de acesso ou link S3 assinado vai na notificação. Ao tocar, o usuário abre/foca a biblioteca; a sessão continua necessária para ouvir. O service worker não armazena catálogo ou áudio em cache offline.

O envio automático está ligado ao worker de publicação do app. O caminho legado de publicação pelo terminal/GitHub ainda não emite esse aviso. Na futura produção totalmente automática, mantenha a publicação nesse worker ou integre o mesmo evento após o commit do catálogo.

## Proteções e limites

- Rotas push exigem JWT e a conta responsável configurada no Cognito.
- O endpoint push é validado por provedor/caminho HTTPS, sem credenciais, query ou portas alternativas. O envio não segue redirecionamentos. Os provedores admitidos nesta versão são FCM (Chrome/Android) e Mozilla (Firefox); outros navegadores podem não ser compatíveis.
- A assinatura fica numa tabela DynamoDB privada, com atualização condicional para preservar os demais dispositivos.
- A chave VAPID privada fica no Secrets Manager; a API distribui somente a chave pública. Não rotacione a chave sem planejar uma nova inscrição dos dispositivos.
- Há registro de entrega por episódio/dispositivo no DynamoDB, retido por 90 dias. Uma resposta HTTP 404/410 remove a assinatura expirada. Resposta incerta não é reenviada automaticamente; a notificação do navegador usa uma tag por episódio para reduzir repetição visual. Não há garantia de entrega exatamente uma vez.
- Aviso de teste não gera roteiro, voz ou novo episódio.

## Painel de produção

O painel exibe disparo diário, horário da última execução editorial, resultado, estado da edição e tarefas em andamento. Os horários são apresentados em São Paulo. Uma execução interrompida mostra aviso de revisão; uma geração paga com resultado incerto continua bloqueada para repetição automática.

O backend procura a execução do dia e, se não existir, a mais recente nos sete dias anteriores. Isso é uma consulta limitada a IDs conhecidos na tabela de tarefas, sem varrer dados de outros usuários. A ausência de uma execução antes da primeira rotina AWS é mostrada como **Aguardando primeira execução**, não como prova de falha. Os detalhes da edição continuam separados do resultado da execução: um episódio pode ter sido produzido manualmente.

## Implantação

```bat
.\.venv\Scripts\python.exe examples\configurar_notificacoes.py --plan
```

O comando cria a chave VAPID em memória usando Node, guarda a privada em Secrets Manager e prepara pacotes Linux e um change set. Não executa o plano nem envia avisos. Node deve estar no PATH ou em `NODE_BINARY`. Em ambientes Windows com caminhos longos, `RADAR_BUILD_TEMP` pode apontar para uma pasta temporária curta e gravável. O pacote utiliza uma wheel universal de `http-ece` e bibliotecas nativas Linux para a Lambda Python 3.12.

Revise e execute o plano. Publique a interface com `publicar_interface.py --publish`. Os recursos acrescentados são tabela de assinaturas, fila e mapeamento de notificações, rotas protegidas e permissões específicas. O Scheduler editorial e o login são preservados. Uma implantação sem parâmetros VAPID não habilita o botão de inscrição até configurá-los.

A Lambda aceita uma invocação administrativa `{"push_diagnostic":true}` que valida criptografia/assinatura usando transporte em memória e retorna `sent:false`. Esse teste não contata o serviço de push nem envia mensagens ao usuário.

## Custos e validação

A chave VAPID usa um segundo segredo no Secrets Manager, aproximadamente US$ 0,40/mês além das chamadas. Somados OpenRouter e VAPID, são dois segredos, aproximadamente US$ 0,80/mês. SQS, DynamoDB, Lambda e logs continuam sujeitos ao consumo e às condições da conta. Os valores são estimativas com base na [página oficial de preços](https://aws.amazon.com/secrets-manager/pricing/).

Nesta entrega passaram os testes Python de acesso, validação de endpoint, catálogo publicado, deduplicação e expiração, além dos testes JavaScript do service worker e da sessão. Um Chrome isolado verificou ativar/testar/desativar, permissão somente após clique, painel normal/falha e largura de 390 px, com serviços simulados. Na AWS, o diagnóstico criptográfico da Lambda foi executado sem envio real e as rotas do responsável foram consultadas; outro usuário recebeu 403. O recebimento num Android real depende da confirmação do proprietário.

Referências técnicas: [PushManager.subscribe](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe), [pywebpush](https://github.com/web-push-libs/pywebpush).


## Registro de verificação da entrega

Em 29/10/2026, passaram 237 testes Python (incluindo o teste que executa os três cenários JavaScript do service worker) e os dez testes JavaScript de sessão. A stack concluiu a atualização sem substituir recursos existentes. A Lambda validou VAPID e criptografia com transporte em memória, retornando `sent:false`; a API retornou somente chave pública e recusou outro usuário com 403. As rotas sem login responderam 401. Os arquivos servidos pelo CloudFront foram comparados aos arquivos locais. O painel da API implantada mostrou a edição de hoje em `completed`, com agendamento habilitado e os campos operacionais presentes.

Ainda dependem de confirmação externa: recebimento do aviso no Android do proprietário e a primeira edição nova preparada pelo disparo diário. Os dados de navegador usados nas capturas de UI foram simulados; não comprovam esses dois cenários reais.
