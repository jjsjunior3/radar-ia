# Segurança

## Relatar um problema

Não abra uma issue pública com chaves, endpoints de push, tokens JWT, senhas, URLs assinadas ou dados da biblioteca. Quando a opção de relato privado de vulnerabilidade estiver habilitada no GitHub, use-a. Se não estiver disponível, solicite um canal privado ao mantenedor pelo perfil GitHub, sem divulgar os detalhes sensíveis publicamente.

O projeto é um MVP de portfólio, sem prazo contratual de resposta. Use a versão atual da branch principal e consulte os avisos das dependências antes de implantar uma instância própria.

## Modelo de acesso

O shell web é público; catálogo, progresso, revisão e configuração push exigem access token validado no API Gateway. Ações editoriais e push estão limitadas ao responsável configurado por `sub` do Cognito. Buckets de dados permanecem privados. A API emite URLs de áudio com validade curta e não recebe senha do usuário.

Tokens de acesso ficam em memória; o refresh token pode permanecer no armazenamento deste navegador por até 30 dias. Sair remove a sessão local, tenta revogá-la e desativa a assinatura push deste dispositivo. Um access token já copiado pode permanecer utilizável até expirar no authorizer JWT. Detalhes em `docs/06-app-hospedado.md`.

Credenciais AWS locais usam sessão temporária. GitHub usa OIDC; Lambdas usam papéis IAM. As chaves OpenRouter e VAPID ficam no Secrets Manager. A chave VAPID pública pode ser distribuída ao navegador; a privada não deve sair do serviço de envio. Não registre respostas completas de provedores em logs públicos.

## Antes de abrir ou distribuir o código

```bat
.\.venv\Scripts\python.exe tools\auditar_repositorio.py --history
```

A ferramenta procura candidatos por padrões e relata arquivo/linha sem imprimir valores. Verifique também imagens, PDFs e arquivos grandes manualmente: uma auditoria por padrões não garante ausência de segredos. Se uma credencial real tiver sido versionada, revogue ou troque a credencial antes de considerar remoção do histórico. Não reescreva histórico compartilhado sem combinar com os responsáveis.

Relatórios e arquivos de revisão ficam em `local-output/`, ignorado pelo Git. Nunca transforme esse diretório em artefato público de CI. As flags de produção podem iniciar chamadas pagas; o projeto mantém checkpoints para bloquear repetição automática quando o resultado é incerto.
