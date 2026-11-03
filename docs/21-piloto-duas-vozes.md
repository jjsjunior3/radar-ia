# 21 · Piloto de podcast com duas vozes

A amostra usa Leo e Camila, ambos com engine generative em us-east-1. O texto é demonstrativo, escrito para o piloto, sem notícias reais e sem chamada de LLM. A abertura informa que são vozes sintéticas.

## Executar

```bat
.\.venv\Scripts\python.exe examples\piloto_duas_vozes.py
```

Esse comando apenas valida o roteiro. Para gerar a amostra paga no Polly:

```bat
aws login --profile radar-ia
.\.venv\Scripts\python.exe examples\piloto_duas_vozes.py --generate
```

O roteiro editável fica em `examples/piloto_dialogo.json`. A saída padrão é `local-output/pilotos/leo-camila-v1/piloto.wav`, junto de manifesto, metadados e trechos PCM. Esses arquivos locais não devem ser publicados no Git.

Cada fala tem locutor explícito. O helper verifica a disponibilidade das duas vozes na região antes de sintetizar. Os trechos usam PCM mono de 16 kHz, ajuste moderado de volume sem adicionar clipping, pausas de 380 ms entre falas e marcação de inglês via SSML. O WAV final tem duração medida e limite de 120 segundos nesta amostra.

## Reutilização e custo

Há cache por fala e manifesto vinculado ao texto, às vozes e à versão do renderizador. Executar novamente com o mesmo conteúdo reutiliza os resultados. Marcador de chamada iniciada sem resposta íntegra bloqueia repetição automática. Alterar o roteiro ou o elenco exige uma pasta de revisão diferente, indicada por `--output-dir`; isso pode gerar novas cobranças. Não exclua marcadores para forçar repetição de chamadas incertas.

## Resultado de 02/11/2026

Foram geradas sete falas alternadas com duração final medida de **85,9 segundos**. O arquivo e a reutilização real do cache foram conferidos sem nova chamada paga. Os testes simulados cobrem elenco, ordem, pausas, integridade, volume, inglês e bloqueio de resultado pago incerto. A avaliação subjetiva de naturalidade e química entre as vozes depende da escuta do proprietário.

O piloto permanece local. A rotina diária continua com um narrador Leo; não houve upload, publicação ou alteração dos episódios existentes.

## Próximas etapas após a escuta

1. Ajustar a voz complementar, as pausas e o tamanho das falas conforme o feedback.
2. Criar um roteiro de diálogo versionado, vinculando cada fala e termo inglês às notícias/fontes da pauta.
3. Adaptar roteirista e avaliador para conversa natural, perguntas sem premissas inventadas e consistência de cada locutor.
4. Tornar validações de apresentação específicas do locutor: a regra de Leo não pode bloquear Camila quando ela for a locutora.
5. Vincular aprovações, hashes e tarefas ao roteiro, ao elenco e à versão do renderizador; preservar compatibilidade com episódios antigos.
6. Integrar síntese, montagem e conferência de até dez minutos no worker antes de ativar publicação automática nesse formato.

O objetivo é um diálogo com perguntas úteis e respostas apoiadas nas fontes, preservando o aprendizado de inglês. A simples alternância de vozes não comprova que uma conversa ficou natural.
