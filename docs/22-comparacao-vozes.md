
## Gemini gratuito com alternativa OpenRouter

O worker pode usar Gemini TTS diretamente e recorrer ao OpenRouter após uma
rejeição explícita HTTP 429. Timeout, erro de autenticação, resposta inválida e
erros 5xx bloqueiam nova geração até inspeção. Um registro de tentativa sem
resposta concluída também bloqueia a troca de provedor.

GEMINI_API_KEY e OPENROUTER_API_KEY ficam no .env para execução local.
TTS_FALLBACK_BUDGET_USD tem valor inicial 0.30 USD. Antes de uma chamada paga,
o código consulta os preços publicados no OpenRouter e faz uma estimativa
conservadora usando o tamanho do pedido e até 25 tokens de áudio por segundo
para o limite de duração. Uma estimativa acima desse valor bloqueia a chamada.

Esse bloqueio é prévio por estimativa. A API de fala do OpenRouter não oferece
um teto financeiro por chamada. Um áudio que ultrapasse a duração é rejeitado
depois de recebido e pode ter sido cobrado. Para impor um teto de cobrança,
configure também um limite em uma chave dedicada no OpenRouter. O valor
estimado não deve ser exibido como cobrança real. O identificador da geração
fica salvo para consultar o gasto no provedor.

Para preparar o exemplo local, execute python examples/voz_com_fallback.py.
A opção --generate autoriza a geração. As pastas guardam o provedor, as vozes,
o modelo, o uso retornado pelo Gemini e os hashes do áudio. Uma nova execução
reutiliza o resultado íntegro. As vozes iniciais são Puck e Kore.

Na AWS, a configuração fica em um segredo separado do Secrets Manager.
O parâmetro TtsSecretArn habilita o novo caminho no worker. A permissão de
leitura vale somente para esse segredo. O armazenamento do segredo e as
leituras são serviços AWS com cobrança própria.

Áudios novos são normalizados para WAV mono de 16 bits e 16 kHz, compatível
com as validações existentes. Tentativas Polly já iniciadas continuam pelo
caminho original. O código atual usa audioop para conversão de taxa, disponível
nos ambientes Python 3.11 e 3.12 testados. A migração para Python 3.13 exige
substituir esse conversor.
