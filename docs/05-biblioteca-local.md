# Biblioteca local — primeira interface

## Executar

Na raiz do projeto:

```bat
.\.venv\Scripts\python.exe -m radar_ia.local_app
```

Abra http://127.0.0.1:8765 no navegador do computador. Deixe o terminal aberto. Ctrl+C encerra. --demo usa uma entrada fictícia e não consulta AWS; o player dessa demonstração não toca áudio. O modo normal usa o catálogo privado S3 real e o perfil AWS do .env.

## Experiência implementada

Biblioteca responsiva com filtros Todos, Não ouvidos, Em andamento e Ouvidos. Player HTML com controles de reprodução, saltos de 15s e velocidade. Acesso ao áudio por URL temporária de cinco minutos, gerada pelo backend; renovar clicando novamente em Ouvir/Continuar se expirar. O catálogo não contém links assinados persistentes. Não gravar URLs em logs.

Progresso salvo em local-output/app/progress.sqlite3, a cada dez segundos durante reprodução, nas pausas, buscas e quando a página é ocultada. No encerramento abrupto pode haver perda dos últimos segundos; fetch keepalive é tentativa, não garantia. Persistência é local e não sincroniza dispositivos.

A marcação automática ocorre ao atravessar 95% da posição ou ao terminar. É posição alcançada, não comprovação de que cada segundo foi ouvido; avançar perto do fim pode concluir a marcação. Marcar/desmarcar manualmente preserva a posição. Ouvir um episódio marcado como ouvido começa do início.

## Arquitetura e limites

Servidor Python padrão, sem novas dependências; credenciais AWS no backend. Bind fixo em 127.0.0.1, validação de Host, origem e header para escritas. Sem login neste protótipo restrito ao computador; não é implantação privada remota. Não expor via 0.0.0.0, proxy público ou túnel. HTTPS, autenticação, sessão por usuário, banco compartilhado, instalação PWA e escuta Android são próximos marcos.

Não há service worker ou cache offline de episódios/URLs nesta etapa. Roteiro/fontes estão no S3, mas sua exibição no app é pendente. O protótipo mostra biblioteca e progresso; não integra ainda a conclusão editorial com a publicação diária.

## Verificação

Testes de persistência após reinício, limite 95%, marcação manual sem apagar posição, validação de dados, episódios independentes, rotas de leitura/escrita e bloqueio de host/origem indevidos. JavaScript passou na verificação sintática. Acesso HTTP e conferência visual não foram possíveis a partir do ambiente de execução: conexão local expirou. Validar no terminal/navegador do usuário, incluindo reprodução S3, retomada, filtros e carregamento dos arquivos. Testes de rotas usam handlers sem socket e não substituem testes reais no navegador.

## Próximo teste acompanhado

1. Abrir o app no modo normal e confirmar episódio do catálogo S3.
2. Ouvir cerca de 20 segundos, pausar e recarregar a página.
3. Confirmar Em andamento e Continuar na posição salva.
4. Marcar ouvido e conferir o filtro Ouvidos; desmarcar e conferir preservação da posição.
5. Após validar a interface, definir hospedagem HTTPS e login para Android.
