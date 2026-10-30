# 20 · Diferenciais recomendados para a próxima versão

Minha recomendação para fortalecer o portfólio é demonstrar qualidade e confiabilidade com evidências. Acrescentar agentes sem medir seu efeito aumentaria complexidade e custos sem mostrar benefício.

| Prioridade | Entrega proposta | Evidência que produziria |
|---|---|---|
| 1 | Conjunto pequeno de casos editoriais revisados por humano, incluindo anúncios exagerados, datas ruins, números inventados e traduções de marcas | Comparação de prompts/modelos em fidelidade, clareza e taxa de encaminhamento humano |
| 2 | Métricas por agente: tempo, tokens, falhas, número de revisões e custo estimado com tabela de preços versionada | Saber onde o fluxo falha ou fica caro; distinguir estimativa de cobrança real |
| 3 | Comparação com e sem memória editorial usando os mesmos casos | Verificar se as preferências realmente ajudam, em vez de inferir melhoria a partir da aprovação |

A Anthropic descreve o padrão de avaliação/otimização como adequado quando há critérios claros e refinamento mensurável, mantendo a arquitetura simples: [Building effective agents](https://www.anthropic.com/research/building-effective-agents).

A AWS documenta observabilidade de agentes com rastreamento de operações e convenções OpenTelemetry: [AI observability](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/observability-ai.html). O Radar IA não implantou OpenSearch ou OpenTelemetry nesta versão; CloudWatch e checkpoints atuais são uma base para a evolução, não equivalem a esse conjunto completo de métricas.

Esses são próximos passos propostos. Os testes atuais verificam contratos e controles do software; a comparação textual do painel mostra mudanças, mas não mede a qualidade semântica de uma edição. Não há resultado de benchmark de melhoria editorial publicado nesta versão.
