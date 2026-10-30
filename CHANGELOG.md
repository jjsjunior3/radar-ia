# Histórico de mudanças

## 0.1.0 · 30/10/2026

Primeira versão do MVP Radar IA, com código preparado para distribuição sob licença MIT.

- Coleta RSS, validação de datas/URLs, domínios permitidos, deduplicação e pauta semanal variável.
- Agentes separados de relevância, roteiro e avaliação via OpenRouter; feedback ao roteirista e uma correção antes da revisão humana na segunda reprovação.
- Aprovação editorial vinculada ao conteúdo; resultados pagos incertos bloqueiam repetição automática.
- Produção com Amazon Polly/Leo, SSML bilíngue, integridade e duração WAV de até dez minutos.
- Publicação automática configurável, catálogo e áudio privados no S3, Scheduler às 8h30 de São Paulo.
- Aplicativo web instalável, Cognito/PKCE, sessão persistente, progresso de escuta e avisos Web Push.
- CloudFormation, acesso OIDC para GitHub Actions, testes sem serviços pagos e documentação de operação/privacidade.
- Três diagramas de arquitetura e fluxo em PNG e SVG editável.

### Limites conhecidos

O fluxo acompanhado e os avisos em Android real foram confirmados pelo proprietário. Os agentes e o ciclo automático possuem testes simulados; a primeira edição agendada sem intervenção nessa versão ainda precisa ser observada. A avaliação usa resumos RSS e não equivale a checagem factual independente. Falhas técnicas não disparam aviso push genérico; revisão humana possui aviso próprio. O código público não implica acesso público ao aplicativo ou aos episódios.

- Revisão humana após duas reprovações, com os pareceres no app; retomada automática após decisão vinculada ao roteiro.
- Memória editorial privada de aprovações humanas e observações, consumida como contexto limitado nas próximas edições.

- Interface organizada em Para ouvir, Biblioteca e Análise e aprovação; detalhes recolhidos, indicador de pendência e player compartilhado.

- Aviso de revisão humana vinculado ao roteiro pendente, com abertura da área de análise e descarte de avisos antigos.
- Painel de refinamento com referências humanas consultadas, versões e comparação textual.
- Demonstração local sem credenciais/cobranças, capturas fictícias e organograma completo em PNG, SVG e Mermaid.
