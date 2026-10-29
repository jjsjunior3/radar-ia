# Radar IA — definição do MVP

PWA para Android, acesso privado e código preparado para open source.

## Regras editoriais
- Até 10 minutos de áudio, incluindo abertura e encerramento.
- Quantidade variável: cinco como referência, normalmente três a sete; nunca preencher espaço com notícia fraca.
- Uma ou duas notícias: edição curta. Nenhuma válida: registrar ausência de edição, sem áudio.
- Notícias excedentes podem aparecer como links adicionais.
- Validar datas, URLs e duplicação. URL acessível não comprova veracidade.
- Janela proposta: 48 horas, configurável.
- Produção às 8h30 America/Sao_Paulo; processamento e atrasos podem afetar a disponibilidade.

## Duração real
Estimar palavras para orientar o roteiro. Medir o áudio após a síntese. Acima de 600 segundos, encurtar e sintetizar novamente, com limite de tentativas e custo. Nunca cortar uma fala no meio. Se persistir, falhar sem concluir a publicação.

Pendente: implementar essa verificação e substituir a exigência atual de exatamente cinco notícias.

## Telas
1. Entrar: acesso restrito ao proprietário, sem cadastro público.
2. Início: episódio recente, Continuar e filtros Todos, Não ouvidos, Em andamento e Ouvidos. Mostrar data, título e duração real. Diferenciar falta de notícias de falha na geração.
3. Episódio: player, saltos de 15 segundos, velocidade, roteiro e fontes. Progresso salvo na conta. Marcar ouvido aos 95%, com correção manual. Posição e marcação são campos separados.

## Android
HTTPS, instalação na tela inicial e testes reais de tela bloqueada, controles de mídia, interrupção e retomada. Offline fica para evolução futura.

## Etapas acompanhadas
Produto → ambiente Python → coleta RSS → curadoria variável e testes → roteiro e voz → S3 privado e autenticação → PWA e progresso → agendamento e documentação pública.

Em cada etapa: explicar, implementar pouco, executar e interpretar juntos. Credenciais, dados de conta e episódios privados ficam fora do repositório público.

## Inglês técnico contextualizado

Decisão de 28/10/2026: o roteiro e a interface permanecem em português brasileiro. Na narração, selecionar de dois a quatro termos úteis de inglês técnico por episódio, presentes nas notícias selecionadas, e explicar o significado em português imediatamente após a primeira ocorrência.

Exemplo de estilo: "A novidade usa tool calling, ou chamada de ferramentas: o modelo solicita que uma função execute uma tarefa."

Priorizar vocabulário de equipes internacionais, quando pertinente à notícia: deployment, code review, breaking change, latency, rollout, retrieval e tool calling. Não inserir termos só para cumprir uma cota; não inventar recursos ou exemplos atribuídos à fonte. Preservar nomes de produtos e explicar siglas quando necessário.

Na interface, apresentar um pequeno glossário com termo original, significado em português e trecho contextual. O glossário deriva do roteiro final e não acrescenta notícias. Transcrição e áudio devem corresponder.

Pronúncia: testar os termos com a voz pt-BR escolhida. Não presumir que inserir palavras inglesas produz pronúncia inglesa correta. Avaliar recursos compatíveis da voz/engine no Polly antes de usar SSML, léxicos ou trechos em outra voz. No texto exibido, manter a grafia correta, sem transliteração improvisada. O áudio deve permitir associar o som do termo à explicação em português.

O limite de 10 minutos inclui essas explicações. Começar com uma voz e tom de conversa; formato com apresentadores, vinhetas e diálogos fica para evolução futura. Diálogos deverão continuar ancorados nas fontes e não simular entrevistas reais.

Estado: requisito registrado; prompt, glossário e tratamento de pronúncia ainda não implementados. O MVP já gera um episódio em áudio; feed para aplicativos de podcast e formato conversacional são evoluções distintas.

## Triagem editorial inicial implementada

O módulo editorial.py classifica títulos/resumos por regras explícitas. Técnico: alta ou média; institucional/promocional: baixa; mercado: complementar; sem sinais: revisão. Regras não comprovam qualidade ou veracidade e podem errar.

Parâmetros iniciais para experimentar: dia fraco significa menos de três candidatas técnicas; nesse caso acrescentar no máximo duas de mercado. Não há obrigação de preencher quantidade. Estes parâmetros são ajustáveis e não substituem o teto real de 10 minutos. A ordem dentro de uma prioridade preserva a ordem de entrada; ainda não representa um ranking fino.

Mercado inclui expansão, contratação, demissões e demanda de competências. Confirmar fonte, região, período e metodologia quando se alegar tendência. O exemplo atual ainda consulta apenas AWS: a classificação de mercado está testada com dados locais, mas depende de novas fontes para ter cobertura real.

O exemplo usa a triagem; o fluxo principal cli.py ainda precisa ser atualizado para curadoria variável e estas regras.

## Grade semanal — experimento aprovado

Segunda: Panorama da semana. Terça: Carreira e mercado. Quarta: Caixa de ferramentas. Quinta: Engenharia de IA. Sexta: Fechamento da semana. Usar America/Sao_Paulo para determinar o dia. Sem edição regular no fim de semana.

Implementação inicial: weekly.py e examples/planejar_semana.py. Fila local por URL, com publicação, fonte e used_in (histórico de uso editorial, separado do progresso de escuta). Planejar não publica nem altera used_in. Retenção editorial inicial de sete dias; conteúdos fora dela ou sem data exigem recoleta/revisão. Mesmo tema pode reaparecer somente com contexto explícito; sexta separa notícias já usadas em possíveis retomadas, não em novidades.

O plano não é roteiro final e não verifica links novamente: revalidar antes de gerar episódio. Urgência não é inferida automaticamente por palavras-chave. Ainda falta seleção editorial de destaques urgentes, diversidade de fontes, avaliação de aprofundamentos e preenchimento alternativo para dias com poucas notícias do tema.

A coleta didática ainda usa 48 horas. A fila acumula candidatas entre execuções, mas não recupera lacunas de dias sem coleta. Próxima evolução: coleta desde a última edição concluída com janela inicial/recuperação configurável. O fluxo principal cli.py continua antigo e não deve ser usado como implementação completa desta grade.

Arquivos locais: coleta.json (última coleta), fila-editorial.json (acúmulo), plano-editorial.json (simulação). Sem chamadas pagas neste planejamento. Teto de áudio: 600 segundos; medição real permanece pendente.

## Coleta multifuentes e recuperação

examples/ler_rss.py agora lê config/sources.json: AWS, GitHub AI/ML e Google AI. Endereços e domínios autorizados ficam explícitos por fonte. Falhas são registradas isoladamente; outras fontes continuam. O relatório v2 registra fontes, candidatas e descartes. A seleção genérica anterior foi removida do exemplo: o planejamento semanal é uma etapa separada.

A janela começa em last_completed_at do arquivo local-output/edicoes.json, com uma hora de sobreposição e limite MAX_RECOVERY_DAYS (padrão 7). Sem esse registro, INITIAL_LOOKBACK_DAYS (padrão 7). Somente a conclusão real de uma edição deverá escrever o registro; coleta e planejamento não o atualizam. Não é necessário criar esse arquivo manualmente agora. O fluxo de publicação que fará isso ainda não foi integrado.

Um feed não garante cobertura histórica integral: registrar essa limitação e consultar no máximo 100 entradas por fonte. Google e GitHub adicionam diversidade técnica; não representam cobertura suficiente de emprego e mercado. Essa cobertura depende de fontes adicionais a selecionar e validar.

O fluxo principal cli.py ainda usa a configuração antiga. As variáveis novas são usadas no exemplo de coleta. Esta é uma entrega intermediária acompanhada, não o pipeline final.

## Expansão da cobertura e motivos do tema

Adicionados TechCrunch e The Verge como imprensa de tecnologia. Verificação real: feeds HTTP acessíveis, XML interpretado sem irregularidade e amostra com publicação. A validação de cada artigo ocorre durante a coleta, com allowlist própria; não habilitar domínios externos automaticamente.

Esses feeds gerais podem trazer conteúdo fora do escopo. Mercado exige sinal no título e continua sujeito a revisão de contexto, região e metodologia. Ainda falta fonte de levantamentos de competências/vagas, especialmente Brasil. Não inferir tendência a partir de uma empresa. A triagem atual é lexical e pode confundir empregos com outros usos de jobs, ou investimentos de tecnologia com assuntos mais gerais.

No planejamento, mostrar fonte e motivo em cada candidata. Quarta: termo de ferramenta no título ou expressão específica no resumo (SDK, API, biblioteca, framework, developer tools). tools isolado no resumo não define o tema. Essa regra reduz um falso positivo observado com prompt caching, mas não substitui avaliação editorial.

Validação: 46 testes locais passaram. Novos feeds consultados diretamente; coleta completa dos artigos adicionais ainda deve ser conferida no uso real.

## Revisão em lote e preparação do roteiro

Classificação de mercado ampliada para IPO, aquisição, captação e mudança de liderança explicitada no título. Regras continuam heurísticas: não transformam anúncio individual em tendência nem comprovam contexto setorial.

planejar_semana.py gera também revisao-editorial.md, incluindo alerta de concentração em uma fonte. --date YYYY-MM-DD permite simular outro dia às 08h30 de São Paulo; não publica nem avança o marco de edição concluída. O plano é sobrescrito com a simulação escolhida, então conferir planned_for antes de produzir.

examples/preparar_roteiro.py lê o plano salvo e escreve briefing-roteiro.json sem acessar serviços. Seleciona no máximo sete candidatas do tema (não exige sete), alternando fontes quando disponíveis, e atribui IDs rastreáveis. Resumo ausente impede envio da candidata; resumo limitado a 2400 caracteres. Esse limite contém custo/contexto, mas pode omitir detalhes e não substitui leitura integral.

Instruções registradas para roteiro em português e glossário contextual de inglês, voz sintética declarada, atribuição, preservação de números e máximo de 600 segundos. Orçamento inicial de 1000 palavras é aproximado; medir áudio permanece obrigatório. O briefing não chama LLM nem representa aprovação editorial.

Os títulos do relatório permanecem no idioma original; tradução do conteúdo é responsabilidade da próxima etapa. O fluxo principal antigo de services.py/cli.py ainda exige integração/refatoração antes de uso pago. As instruções do briefing não foram conectadas à API.

## Geração estruturada de roteiro

Implementado src/radar_ia/script.py, com Pydantic explicitamente declarado nas dependências. Schema estrito para intro, notícias (ID, título/resumo/narração em português), glossário e encerramento. A aplicação copia fontes do briefing; o modelo não gera URLs de referência.

Validação local: IDs iguais e na ordem do briefing, 1..7 notícias, campos não vazios, glossário de até quatro termos com IDs válidos e termo/explicação presentes na fala correspondente. Declaração de voz sintética é inserida pelo aplicativo. Narração até 1000 palavras/12000 caracteres; links não são lidos. Rejeitar resposta incompleta, recusa ou JSON inválido. Validação estrutural não verifica idioma, tradução, números ou fidelidade factual; avaliação dessas propriedades é pendente.

Demo fictícia: python examples/demo_roteiro.py. Arquivos em local-output/demo-roteiro, claramente identificados como fictícios; não são tradução da coleta real.

Preparação de geração real: python examples/gerar_roteiro.py verifica o briefing e a presença da configuração, sem rede e sem mostrar credencial. Com --generate, chama Responses com JSON Schema, store=False e limite de 6000 tokens de saída. Sem retentativas automáticas para evitar reenvio cobrado sem controle. Recusas/limites exigem revisão. Uso retornado é registrado na geração concluída; tentativas inválidas ainda podem ser cobradas pelo provedor.

Antes da chamada real: exigir briefing planejado há no máximo 24 horas, conferir modelo/chave e revalidar páginas sob a allowlist de cada fonte. Esses controles não validam a verdade dos resumos. OPENAI_MODEL fica explícito para escolha consciente; API é cobrada separadamente de assinatura do ChatGPT.

Arquivos de cada geração concluída ficam em pasta própria de local-output/roteiros, com texto para revisão, JSON, briefing e metadados. Nenhuma execução desta etapa marca notícia como publicada nem chama Polly/S3. Antes da produção real ainda integrar validação factual e teto de duração de áudio. O fluxo cli.py legado continua separado.

Referência oficial consultada: https://developers.openai.com/api/docs/guides/structured-outputs
