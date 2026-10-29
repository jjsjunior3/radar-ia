# 14 · Preparação para código aberto

## O que está preparado

O repositório tem licença MIT, README com arquitetura, `.env.example` sem valores secretos, modo de demonstração sem AWS, testes, guias operacionais, instruções de contribuição, política de relato de segurança, descrição de dados/privacidade e modelos de issue/PR. Os diagramas e o logo incluem fontes SVG editáveis.

O código pode ser aberto enquanto a instância e os episódios continuam privados. Esta preparação **não alterou a visibilidade do repositório**, não publicou episódios e não enviou post ao LinkedIn.

## Auditoria realizada

A ferramenta `tools/auditar_repositorio.py --history` verificou arquivos atuais e objetos no histórico Git, com padrões para chaves AWS, tokens de provedores/GitHub, JWTs e chaves privadas. Também procurou contas AWS, e-mails pessoais e caminhos locais. Não imprimiu os valores encontrados. O resultado inicial desta entrega foi zero candidatos e zero arquivos de produção proibidos rastreados. Os novos arquivos devem ser verificados novamente antes da abertura.

Uma consulta à base OSV verificou versões dos pacotes públicos da venv e dos pacotes Lambda. Não identificou avisos para as dependências empacotadas nas Lambdas. Identificou avisos na ferramenta pip antiga da venv; ela foi atualizada para 26.2.2. A segunda consulta verificou 35 pacotes da venv sem avisos retornados; a consulta dos pacotes Lambda verificou 37 dependências, também sem avisos retornados. Esses resultados são uma fotografia do momento, não uma garantia de segurança nem uma avaliação completa de vulnerabilidades.

Imagens de arquitetura foram revisadas visualmente. A ferramenta não inspeciona o conteúdo visual de imagens, PDFs ou arquivos binários; arquivos grandes acima do limite do scanner também exigem revisão separada. Relatórios ficam em `local-output/` e não são publicados.

## Checklist de abertura

- [x] Licença e autoria definidas.
- [x] Configuração de exemplo sem chaves ou identificadores da instância.
- [x] Instruções para testar e abrir demonstração sem serviços pagos.
- [x] CONTRIBUTING, SECURITY, PRIVACY e modelos de issue/PR.
- [x] Auditoria inicial de arquivos e histórico, sem candidatos encontrados.
- [x] Código e recursos editáveis registrados no Git.
- [ ] Confirmar o teste de aviso em um Android real.
- [ ] Validar a primeira edição diária completa do Scheduler.
- [ ] Revisar novamente o diff e o histórico imediatamente antes de abrir.
- [ ] O proprietário decidir quando alterar a visibilidade para público.

Os dois testes operacionais pendentes devem aparecer como limites conhecidos no README, mesmo que o proprietário decida abrir antes de concluí-los. Não apresente uma funcionalidade como validada em Android apenas porque um teste de navegador simulado passou.
