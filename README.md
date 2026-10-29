# Radar IA

Boletim de IA em português brasileiro, com inglês técnico contextualizado e episódios de até 10 minutos. Feito por **jrsantosdev**.

Projeto em desenvolvimento acompanhado, com áudio e catálogo privados no S3. Código preparado para open source; credenciais e dados locais não devem ser publicados.

## Estado atual

- Coleta RSS de cinco fontes, validação de data/URL e deduplicação inicial.
- Grade editorial de segunda a sexta e fila local.
- Roteiro estruturado via OpenRouter, validação e revisão editorial.
- Amazon Polly: Camila generativa com SSML; medição de duração WAV.
- S3 privado com catálogo e proteção contra atualização concorrente.
- Biblioteca local com filtros/player e progresso SQLite.
- Hospedagem HTTPS com Cognito, Lambda/API Gateway e DynamoDB preparada; implantação/testes reais pendentes.

O comando legado radar-ia ainda não reúne o fluxo novo; usar os exemplos documentados. Agendamento GitHub Actions, recuperação editorial integrada, feed público e aplicativo Android validado seguem pendentes. Não usar este repositório como pipeline completo de produção.

## Desenvolvimento

```bat
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
```

Copiar .env.example para .env, preencher apenas localmente. Não sobrescrever um .env existente com credenciais.

## Biblioteca local

```bat
.\.venv\Scripts\python.exe -m radar_ia.local_app
```

Abrir http://127.0.0.1:8765. Restrita ao computador; sem login de produção. --demo não acessa AWS.

## Documentação

- docs/01-produto.md — decisões editoriais e escopo.
- docs/02-openrouter.md — modelo, configuração e validação do roteiro.
- docs/03-primeiro-audio.md — voz e geração de áudio.
- docs/04-s3-privado.md — armazenamento e catálogo.
- docs/05-biblioteca-local.md — player e progresso local.
- docs/06-app-hospedado.md — arquitetura, implantação e limites da versão remota.

Não publicar local-output/, .env, URLs temporárias, banco local ou arquivos .aws. Os arquivos web não contêm credenciais; a versão hospedada protege os dados por autenticação.

## Licença e código aberto

Código sob licença MIT. O repositório começa privado durante a revisão; sua abertura pública é uma etapa separada. Dados de conta, episódios, credenciais e progresso não fazem parte da licença nem devem ser publicados. A política IAM em config/iam-runtime-policy.example.json é um modelo; a versão gerada com bucket real fica ignorada pelo Git.

## Validação automática

.github/workflows/tests.yml executa testes Python e JavaScript sem credenciais de AWS ou OpenRouter. Esse workflow não gera episódios nem chama serviços pagos. A produção agendada é outro fluxo, ainda em integração, e usará função AWS própria via OIDC em vez de chaves de acesso permanentes.
