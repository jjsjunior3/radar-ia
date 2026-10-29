# Dados e privacidade

Esta descrição corresponde ao MVP privado. Quem implantar outra instância deve revisar sua configuração e informar seus próprios usuários.

O aplicativo usa Cognito para autenticação. O backend guarda catálogo e arquivos de episódios no S3 privado, posição de escuta e marcação de ouvidos no DynamoDB, e checkpoints/tarefas para acompanhar produção e evitar repetições. O navegador pode guardar um refresh token por até 30 dias; não guarda a senha. O serviço de login da AWS recebe a senha diretamente.

Ao ativar avisos, o navegador fornece um endpoint de push e material de criptografia da assinatura. Esses dados ficam em uma tabela privada, vinculados ao usuário autenticado. O servidor recebe a assinatura, não o conteúdo de outros aplicativos ou notificações do telefone. Desativar os avisos remove a assinatura desse dispositivo; sair também tenta desativá-la. Se não houver conexão, uma assinatura antiga pode permanecer no servidor até ser removida ao receber resposta de expiração do provedor.

Os avisos usam mensagem genérica e payload criptografado pelo protocolo Web Push. A notificação pode aparecer na tela bloqueada conforme as preferências do Android. Ao tocar, o usuário abre a biblioteca; áudio e dados continuam exigindo sessão válida. Os serviços de push do navegador, a AWS e o OpenRouter processam os dados necessários às respectivas funções. A LLM recebe a pauta e os resumos selecionados, não a senha ou o histórico de escuta.

O MVP não carrega analytics ou scripts de publicidade. Logs técnicos são retidos por 14 dias; tarefas editoriais e de áudio têm TTL de 30 dias, e registros de deduplicação de avisos têm TTL de 90 dias. A remoção por TTL é eventual. Arquivos e catálogo S3 não possuem exclusão automática nesta versão. O administrador da instância pode remover manualmente dados e assinaturas pelos serviços AWS.

A licença MIT cobre o código do projeto. Ela não concede acesso à biblioteca privada nem direitos sobre textos, áudios, marcas ou notícias de terceiros.
