# 17 · Interface por áreas

O aplicativo abre em **Para ouvir**, com episódios não concluídos. Os que têm reprodução iniciada aparecem primeiro, com botão Continuar. Marcar como ouvido remove o item dessa área e preserva seu registro na biblioteca.

**Biblioteca** reúne todo o histórico, com filtros Todos, Não ouvidos, Em andamento e Ouvidos. O filtro selecionado é preservado ao alternar de área durante a mesma abertura do app.

**Análise e aprovação** reúne o estado da edição, o roteiro/fontes, pareceres dos agentes, decisão humana e preferências editoriais. O indicador na navegação avisa quando uma etapa requer atenção. Detalhes técnicos da produção, notificações por dispositivo e programação ficam recolhidos até serem abertos.

O player é compartilhado entre as áreas: mudar a navegação não troca o áudio nem inicia outra reprodução. As áreas privadas são ocultadas no logout. As três áreas não criam novas permissões no backend: autenticação e verificações do responsável continuam valendo.

A interface foi conferida em Chrome com largura de celular e desktop, usando serviços e episódios fictícios: pendentes, ordenação por retomada, filtros, pareceres, indicação de pendência e preservação do player. Essa conferência não comprova uma nova publicação ou reprodução real de áudio na AWS.
