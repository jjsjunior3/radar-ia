# OpenRouter — configuração do primeiro roteiro

O novo comando examples/gerar_roteiro.py usa OpenRouter por padrão, preservando a integração OpenAI como alternativa. A biblioteca Python openai é o cliente compatível; neste modo a cobrança e a autenticação são do OpenRouter, não da OpenAI.

## Configurar

Edite .env na raiz do Radar IA:

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=COLE_A_CHAVE_LOCALMENTE
OPENROUTER_MODEL=google/gemini-2.5-flash
```

Use uma chave de API de inferência do OpenRouter, não uma chave administrativa. Não cole no chat nem em capturas de tela. .env está no .gitignore. Uma chave dedicada ao projeto com limite pequeno de gastos ajuda a acompanhar os testes. Não usar saldo como estimativa de consumo futuro.

Modelo inicial: google/gemini-2.5-flash, configurável. A página consultada informa US$0,30 por milhão de tokens de entrada e US$2,50 por milhão de saída; verificar preços antes de ampliar o uso. O suporte ao esquema depende do endpoint. A requisição usa provider.require_parameters=true e valida a resposta localmente. Se nenhum endpoint aceitar os parâmetros, falhar em vez de remover o esquema silenciosamente.

## Verificar sem gastar

```bat
.\.venv\Scripts\python.exe examples\gerar_roteiro.py
```

Só informa modelo/provedor e presença da chave; não imprime seu valor nem acessa rede.

## Gerar um roteiro real

Conferir plano e briefing recentes. Se necessário, executar planejar_semana.py e preparar_roteiro.py novamente, sem recoletar se a coleta ainda for apropriada. Em seguida:

```bat
.\.venv\Scripts\python.exe examples\gerar_roteiro.py --generate
```

O comando revalida links e faz uma chamada paga de chat completions, com JSON Schema e no máximo 6000 tokens de saída. Não há novas tentativas automáticas no cliente. Limite de tokens não equivale a teto financeiro; tentativas rejeitadas pela validação local também podem ter sido cobradas. Métricas retornadas, inclusive custo quando fornecido, ficam em metadados.json de gerações válidas.

Ainda não foi validado ao vivo com uma chave. Testes usam respostas simuladas. O comando não chama Polly/S3 e não publica nada. Revisar tradução, fatos, números, glossário e naturalidade antes da voz. Pronúncia e duração real são verificadas na etapa de áudio.

## Fontes oficiais

- https://openrouter.ai/docs/quickstart
- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/google/gemini-2.5-flash

O fluxo legado radar-ia/cli.py ainda não usa esta configuração; usar os comandos de examples durante esta fase acompanhada.

## Correção: glossário fora da narração

Após primeiro retorno real, validação encontrou termo ausente na fala referenciada. A resposta anterior não foi persistida; não se pode concluir se foi omissão ou variação de grafia, nem recuperá-la dos arquivos locais.

Nova montagem determinística: se termo ou explicação do glossário não constar na fala relacionada, acrescentar ambos ao fim da primeira notícia referenciada. Somente texto já fornecido pelo modelo é reutilizado. IDs, campos, URLs e limites continuam validados; alterações ficam em local_changes dos metadados. Isso não comprova a correção da explicação e pode requerer edição para naturalidade. Não substitui avaliação factual ou de tradução.

Toda nova resposta recebida é salva em resposta-original.json antes da validação. Briefing da tentativa é preservado previamente; erros de validação ficam em arquivo e a tentativa não vira roteiro aprovado. Para reprocessar offline: python examples/reprocessar_roteiro.py CAMINHO_DA_PASTA_DA_TENTATIVA. Esse exemplo suporta respostas Chat Completions concluídas e gera subpasta reprocessado; não chama modelo ou nuvem. Ajustes locais não geram nova cobrança; requisição original pode ter sido cobrada.
