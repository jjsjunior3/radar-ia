# Contribuir com o Radar IA

O Radar IA é um projeto de portfólio em Python, com aplicativo privado e código sob licença MIT. O repositório é público e aceita contribuições reproduzíveis. O acesso à instância do autor não faz parte da contribuição; use seu próprio ambiente para integrações AWS.

## Começar sem credenciais ou serviços pagos

Requisitos: Python 3.12 e Node.js 22 para os testes JavaScript.

Windows:

```bat
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/web/auth.test.cjs tests/web/push.test.cjs
.\.venv\Scripts\python.exe -m radar_ia.local_app --demo
```

Linux/macOS: use `python3.12` para criar a venv e `.venv/bin/python` nos comandos seguintes. A demonstração abre em `http://127.0.0.1:8765`. Não precisa de `.env`, OpenRouter ou AWS. Os testes de aplicação usam serviços simulados. Os testes de push do service worker são executados também pelo pytest quando Node está disponível.

`--preview` consulta RSS reais, mas não gera texto pago ou voz. Comandos com `--execute`, `--generate`, `--upload`, `--apply`, `--deploy` ou `--plan` devem ser lidos antes de usar: alguns criam recursos, armazenam credenciais em serviços AWS ou geram custos. Testes de integração ao vivo exigem uma conta sua.

## Propor uma mudança

1. Abra uma issue descrevendo o problema e o resultado esperado, sem dados pessoais ou segredos.
2. Crie uma branch e mantenha a mudança focada. Preserve checkpoints e aprovações vinculadas ao conteúdo.
3. Acrescente testes quando a mudança afetar comportamento, segurança ou recuperação. Evite testes que apenas copiem a implementação.
4. Execute os testes e atualize a documentação quando mudar operação, configuração ou custos.
5. Abra um PR explicando problema, comportamento resultante e validação. Separe o que foi simulado do que foi confirmado num dispositivo real.

Não inclua `.env`, dumps de produção, áudio de terceiros, URLs assinadas, endpoints de push, arquivos de usuários ou chaves. Os diagramas têm SVGs editáveis em `docs/assets/linkedin/`; o logo tem origem em `infra/cognito/logo.svg`.

## Decisões do produto

- Biblioteca privada, login Cognito e progresso por usuário.
- Edições de até dez minutos, sem obrigação de preencher uma quantidade fixa de notícias.
- Português brasileiro com inglês técnico explicado; voz sintética identificada.
- Revisão humana durante os ajustes finos; automação completa e notificações somente após publicação são objetivos de evolução.
- Código, dados e episódios têm permissões e ciclos de publicação distintos.

Trate colaboradores com respeito, descreva fatos e evite dados pessoais em exemplos e discussões.
