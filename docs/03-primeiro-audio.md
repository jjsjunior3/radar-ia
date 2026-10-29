# Primeiro roteiro real e preparação de áudio

Geração revisada: local-output/roteiros/20261028T145020657999Z. Uso informado pelo OpenRouter: 1240 tokens de entrada, 1543 de saída, custo US$0,0042295. Não inclui tentativa anterior.

Revisão local preserva original e arquivos em revisao-local. Correções: marca Amazon Quick preservada, guia não apresentado como lançamento, eliminação da repetição SFT, training loop em inglês com explicação, datas e concentração em uma fonte explicitadas. Comparação limitada aos resumos RSS; não é verificação independente. Narração revisada: 534 palavras.

## Áudio preparado, sem chamada AWS

Novo módulo audio.py: divide por palavras em trechos de até 2500 caracteres; requisita PCM mono 16 kHz, 16 bits; monta WAV e mede duração pelos frames. Rejeita áudio acima de 600 segundos sem cortar a fala. Pode haver pequena descontinuidade de prosódia entre trechos; avaliar na escuta. O limite de duração é validado, mas redução automática de roteiro ainda não implementada.

examples/gerar_audio.py --script CAMINHO_NARRACAO verifica apenas o arquivo local. Acrescentar --generate chama Polly, com possível cobrança, usando a cadeia de credenciais padrão boto3. Não imprime credenciais. AWS_REGION obrigatório. Voz/engine iniciais Camila/neural, sujeitos à disponibilidade regional e confirmação no serviço. Medição real e pronúncia só podem ser avaliadas após geração. Termos em inglês ainda usam a voz pt-BR, sem SSML específico.

Texto é normalizado em espaços antes dos trechos, sem preservar pausas de parágrafo; recurso de prosódia é evolução futura. Falhas não são repetidas automaticamente; trechos já sintetizados podem ter sido cobrados. Checkpoint por trecho permanece pendente. Nenhum S3 ou histórico de publicação é alterado. Saída local inclui WAV, duração medida e SHA256 do texto para rastreabilidade.

Próximo requisito externo: configuração AWS/IAM para polly:SynthesizeSpeech, sem usar usuário root. Preferir perfil local temporário/SSO quando disponível. Configuração de identidade será feita com o usuário antes da geração real.

## Retorno de escuta e comparação de vozes

Usuário rejeitou primeiro áudio: metálico/robótico, entonação variável e inglês acelerado ou pronunciado como português. O áudio tinha Camila neural, PCM 16kHz e dois trechos independentes; não foi determinada uma causa única. Não atribuir todas as mudanças a divisão em trechos.

Novo teste examples/comparar_vozes.py: três versões do mesmo texto curto em MP3 24kHz, cada uma em uma única requisição: A neural simples; B neural com parágrafos SSML e lang en-US nos termos; C generativa com a mesma marcação. Comparar A/B isola o efeito da marcação; B/C compara motores. Comparação com o episódio anterior também muda texto, formato e quantidade de requisições, portanto não isola a causa da sonoridade original.

SSML é gerado localmente com escape XML, parágrafos preservados e termos por limites de palavra. Marcação de idioma não garante sotaque nativo ou consistência: avaliar pela escuta. A configuração padrão do episódio ainda não foi alterada. Se nenhuma amostra atender, avaliar outro serviço de TTS em vez de insistir em ajustes indefinidos no Polly. Arquivos e respostas são locais; nenhum upload.

Fontes oficiais: https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html e https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html . Camila generativa listada para pt-BR; us-east-1 listada como região disponível. Confirmar por resposta real da API, registrada em resultados.json.

## Escolha de voz para v1

Usuário escolheu amostra C: Camila generativa com SSML de parágrafos e lang en-US para termos ingleses. .env e .env.example atualizados para generative. make_audio agora usa SSML por padrão e recebe termos do glossário. gerar_audio.py carrega roteiro.json ao lado da narração para identificar esses termos. Cortes preferem parágrafos/frases; frases excepcionalmente longas usam divisão por palavras. O limite por requisição considera texto e marcação separadamente.

O episódio completo ainda usa PCM/WAV 16kHz para montagem e medição sem dependência externa; as amostras comparadas eram MP3 24kHz. Motor/marcação foram adotados, mas o resultado completo precisa de escuta porque formato e múltiplas requisições diferem da amostra. MP3 final de distribuição fica pendente. Nenhuma nova síntese ocorreu ao aplicar a preferência.

## Ajuste de ritmo e comparação masculina — 29/10/2026

Na escuta do episódio de 29/10, o proprietário aprovou a pronúncia inglesa, mas pediu mais separação entre frases. A marcação passa a envolver frases com `<s>`, inserir `<break time="450ms"/>` entre elas e `<break time="950ms"/>` após parágrafos. Esses tempos são marcações solicitadas; o resultado percebido precisa de escuta e pode incluir pausas naturais do motor. Decimais e abreviações comuns não disparam cortes de frase. A marcação `<lang xml:lang="en-US">` dos termos ingleses foi preservada.

O renderizador é identificado como `bilingual-pauses-v2` nos metadados dos novos áudios. Áudios prontos não são substituídos automaticamente; trechos em produção mantêm a proteção por digest do SSML. Uma comparação usa arquivos locais separados da edição, sem aprovar ou publicar o episódio.

A API `describe-voices`, em us-east-1, confirmou a voz masculina **Leo** com suporte generative, além de Thiago neural e Ricardo standard. Foram geradas amostras Leo e Camila, ambas generativas, com o mesmo trecho do roteiro e as mesmas pausas, em `local-output/comparacao-vozes/2026-10-29-pausas-v2/`. Durações medidas: Leo 64,8 s e Camila 63,0 s. São amostras para escolha, não uma troca da voz padrão nem uma publicação.

Referências: [pausas explícitas no Polly](https://docs.aws.amazon.com/polly/latest/dg/break-tag.html) e [vozes disponíveis](https://docs.aws.amazon.com/polly/latest/dg/available-voices.html). A disponibilidade foi conferida na API porque as tabelas da documentação podem estar defasadas durante lançamentos.

## Voz padrão escolhida: Leo generativo

Após comparar as amostras de 29/10/2026, o proprietário escolheu **Leo de agora em diante**. Configuração local, exemplo de ambiente, código, workflow e material de arquitetura passam a usar Leo com engine generative, mantendo as pausas e o inglês da marcação v2. Camila permanece registrada acima como escolha histórica.

Trocar a voz de um áudio completo ainda em revisão exige uma nova versão. A opção `production audio --execute --new-audio-revision` arquiva primeiro o snapshot remoto anterior em `production/audio-archives/`, move o cache de voz para backup local e preserva o roteiro aprovado. Depois gera o novo áudio em checkpoints separados. Cada versão precisa de sua própria escuta e aprovação; uma voz escolhida não aprova a publicação automaticamente.

Tentativas incertas, áudios já aprovados e episódios publicados não podem ser reiniciados por essa opção. Se o backup falhar, o áudio existente permanece. O arquivo arquivado fica separado do snapshot ativo para não somar dois WAVs e caches PCM no limite de 50 MiB por edição. Rascunhos arquivados ocupam armazenamento e ainda não têm retenção automática.
