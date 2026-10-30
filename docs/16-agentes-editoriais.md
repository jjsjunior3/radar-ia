# 16 · Agentes editoriais e ciclo de revisão

O Radar IA usa agentes especializados coordenados em Python. Os agentes de relevância, roteiro e avaliação fazem chamadas LLM separadas, com prompts e saídas estruturadas próprios. Coleta e produção são agentes determinísticos: não precisam de uma LLM para ler RSS ou chamar o Polly. Eles não são processos autônomos soltos nem dependem de um framework de agentes.

```mermaid
flowchart TD
    S[Scheduler: seg–sex, 8h30] --> C[Agente coletor: RSS, datas, URLs, deduplicação]
    C --> PRE[Pré-seleção por tema e diversidade: até 7 candidatas]
    PRE --> R[Agente de relevância: nota de 0 a 5 e justificativa]
    R -->|Nenhuma nota >= 3| N[Sem episódio: nenhum áudio ou aviso de pronto]
    R -->|Selecionadas| W[Agente roteirista: português + inglês contextualizado]
    W --> V[Validação Python: esquema, IDs, glossário, limite de texto]
    V -->|Válido| A[Agente avaliador: fidelidade, clareza, atribuições, concisão]
    V -->|Erro conhecido na resposta| F[Análise para o roteirista]
    A -->|Reprovado| F
    F -->|Uma correção após a primeira reprovação| W
    F -->|Segunda reprovação| H[Revisão humana: roteiro + dois pareceres]
    H -->|Aprovar e registrar preferências| Q
    H --> M[Memória privada: últimas 5 aprovações em 14 dias]
    M -. orienta próximas edições .-> R
    M -. orienta próximas edições .-> W
    M -. orienta próximas edições .-> A
    B[Bloquear resultado inválido ou incerto]
    A -->|Aprovado: qualidade >= 4 e sem bloqueantes| P[Autorização vinculada ao hash do roteiro]
    P --> Q[SQS: uma tarefa por edição e conteúdo]
    Q --> T[Agente produtor: Polly / Leo]
    T --> I[Verificar WAV, hash e duração até 10 minutos]
    I -->|Válido| U[Publicar no catálogo S3 privado]
    I -->|Inválido| B
    U --> X[Web Push: episódio disponível]
```

## Responsabilidades

| Agente | Implementação | Entrada e saída |
|---|---|---|
| Coletor | `CollectionAgent` + módulos de RSS e planejamento | Feeds → notícias elegíveis e pauta preliminar |
| Relevância | `RelevanceAgent` | Até 7 candidatas da pré-seleção → nota e motivo por ID; mantém notas a partir de 3 |
| Roteirista | `ScriptWriterAgent` | Evidências selecionadas + análise anterior → roteiro estruturado |
| Avaliador | `ScriptReviewerAgent` | Roteiro + resumos originais → aprovação, nota e correções por notícia |
| Produtor/publicador | `worker.py` + `Production` | Roteiro com aprovação válida → áudio verificado, catálogo e aviso |

A seleção LLM atua nas candidatas já filtradas pelo planejamento existente, não em toda a internet ou em todas as entradas RSS. O modelo não pode inventar IDs, incluir notícias externas ou aprovar um roteiro com problemas bloqueantes. O avaliador recebe as evidências originais e é instruído a não tratar publicidade como comprovação independente. Mesmo assim, avaliação por LLM não equivale a checagem factual externa.

## Reprovação e custos

São permitidas duas versões de roteiro: uma inicial e uma correção. Cada versão válida recebe uma avaliação separada. No pior caso normal são cinco chamadas LLM: uma de relevância, duas de roteiro e duas de avaliação. A coleta não usa tokens. O limite de tempo compartilhado pode encerrar a edição antes de consumir todas as tentativas.

Uma resposta estruturalmente inválida recebida pode orientar a próxima correção. Uma chamada sem resposta salva é incerta: o sistema para, não tenta cobrar de novo. Duas reprovações encaminham o roteiro válido, com os pareceres, à decisão humana. Até essa decisão, o Polly fica bloqueado. Não há garantia de geração de episódio todos os dias nem de qualidade perfeita do avaliador.

## Rastreamento

O checkpoint privado de cada edição contém:

- `agents/original-brief.json`: candidatas originais antes da seleção LLM.
- `agents/relevance-decision.json`: notas e justificativas.
- `agents/relevance/`, `agents/writer-N/`, `agents/reviewer-N/`: marcador anterior à chamada e resposta original, incluindo uso informado pelo provedor.
- `agents/review-N.json`: parecer estruturado do avaliador.
- `agents/approval.json`: versão da política, número da versão aprovada, qualidade e hash do conteúdo aprovado.
- Autorizações do roteiro e do áudio com `mode=automatic`, distintas de aprovação humana.

Esses arquivos ficam no S3 privado e podem ser baixados pelo diagnóstico/status de produção; não devem ser enviados ao GitHub. Alterar o roteiro invalida a aprovação editorial. O worker confere essa vinculação antes de chamar o Polly.

## Testes e implantação

`tests/test_agents.py` usa respostas simuladas para verificar reprovação → análise → correção → aprovação; encaminhamento humano após duas reprovações; ausência de notícias relevantes; referências inválidas; aprovação contraditória; cache de respostas e resultado pago incerto. Os testes de produção verificam publicação antes da notificação e desativação do modo automático.

O helper `examples/configurar_automacao.py --plan --enable` empacota a versão com agentes e prepara a atualização, sem executar o change set. O processo de ativação/pausa está no [guia de operação](15-publicacao-automatica.md). O modo automático precisa ser validado em uma edição diária real após a implantação; testes simulados não comprovam esse ciclo externo.


## Aprovação humana e evolução editorial

Após duas reprovações do avaliador, um roteiro estruturalmente válido fica em `awaiting_human_review`. O app apresenta o texto e os dois pareceres. A decisão do responsável fica vinculada ao hash, com autor e horário; ela substitui a decisão editorial dos agentes nessa edição, mas não remove as verificações técnicas do áudio.

No modo automático, o botão de aprovação informa que retoma Polly e publicação, usando créditos AWS. As preferências escritas no formulário se aplicam às próximas edições e não alteram silenciosamente o roteiro exibido. Sem aprovação humana, não há voz ou publicação. Respostas estruturalmente inválidas ou chamadas pagas incertas continuam bloqueadas: não podem ser aprovadas como um roteiro válido.

Cada aprovação humana pelo app registra uma observação opcional e um trecho do texto aceito em `production/feedback/AAAA-MM-DD.json`, no S3 privado. A gravação é idempotente por data e ocorre após a confirmação condicional do roteiro. Apenas registros do responsável configurado são consumidos. Os agentes recebem as últimas cinco aprovações dos 14 dias anteriores como dados editoriais, mantendo as instruções de fontes e validação acima dessas preferências. Aprovações automáticas não alimentam essa memória, evitando reforçar indiscriminadamente os próprios erros.

Isso é memória contextual, não treinamento ou fine-tuning do modelo. Não garante melhoria em toda edição e não reescreve código, prompts de sistema ou regras de segurança sozinho. As observações explícitas tornam o refinamento mais útil que uma aprovação sem comentário. A memória ativa é limitada à janela de leitura; os registros S3 não são apagados automaticamente após 14 dias. Para retirar uma preferência, o administrador pode remover o objeto correspondente no prefixo privado de feedback.

O aviso Web Push continua sendo de episódio publicado. A solicitação de decisão humana aparece no painel do app; um aviso push específico de revisão ainda não foi implementado.
