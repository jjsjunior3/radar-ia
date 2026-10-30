# 19 · Demonstração e material para divulgação

## Rodar sem AWS e sem chave LLM

Na raiz do repositório, instale o projeto conforme o README. Depois execute:

```bat
.\.venv\Scripts\python.exe -m radar_ia.local_app --demo
```

No Linux/macOS, use `.venv/bin/python -m radar_ia.local_app --demo`. Abra o endereço local mostrado no terminal. O servidor aceita apenas loopback; não é um ambiente de produção para publicar na internet.

A demonstração tem dados fictícios nas três áreas, progresso de exemplo, dois pareceres, memória editorial, versões e comparação de texto. Aprovar **simula** a conclusão; não chama LLM, Polly ou AWS e não publica um episódio. Não inclui áudio real; os botões de reprodução ficam identificados como exemplo sem áudio. A simulação de decisão é reiniciada ao encerrar o servidor. Progresso marcado na biblioteca pode ficar na base SQLite local.

## Capturas públicas

As imagens abaixo usam exclusivamente dados fictícios. As capturas foram verificadas em navegador isolado com dados gerados pelo backend de demonstração e transporte simulado; os handlers locais também possuem testes. Não representam métricas ou resultados de uma edição real.

- [Para ouvir — celular](assets/demo/01-para-ouvir.png)
- [Biblioteca — desktop](assets/demo/02-biblioteca.png)
- [Revisão e refinamento — celular](assets/demo/03-refinamento.png)
- [Organograma completo](assets/arquitetura-completa.png) · [SVG editável](assets/arquitetura-completa.svg) · [Mermaid editável](assets/arquitetura-completa.mmd)

## Rascunho para LinkedIn

> Transformei uma necessidade pessoal em um projeto de engenharia: acompanhar notícias de IA sem passar o dia lendo feeds.
>
> O Radar IA reúne notícias e prepara episódios de até dez minutos, em português, com termos técnicos em inglês explicados no contexto. O app privado funciona no Android e guarda meu ponto de escuta.
>
> A parte mais interessante foi construir o fluxo editorial: coleta e validação em Python; agentes separados de relevância, roteiro e avaliação; retorno ao roteirista com análise; e decisão humana após duas reprovações. Só depois da aprovação o áudio segue ao Amazon Polly.
>
> Minhas aprovações e observações entram como memória editorial nas próximas edições. Isso é contexto rastreável, não treinamento do modelo. Consigo consultar as referências usadas e comparar versões do roteiro.
>
> Na AWS, o projeto usa Lambda, S3 privado, SQS, DynamoDB, Cognito, CloudFront, API Gateway, EventBridge Scheduler, Secrets Manager, IAM e CloudWatch, com infraestrutura em CloudFormation e testes no GitHub Actions.
>
> O fluxo acompanhado e os avisos no Android já foram usados em produção. O próximo marco é observar uma edição diária completa com os novos agentes sem intervenção. O repositório documenta esse limite e inclui uma demonstração com dados fictícios, sem precisar de credenciais AWS.
>
> Projeto desenvolvido com apoio de IA, com decisões de arquitetura, revisão e validação ao longo da implementação. Código sob licença MIT; minha instância e os episódios continuam privados.
>
> Código e documentação: https://github.com/jjsjunior3/radar-ia
>
> Feito por jrsantosdev.
>
> #Python #AWS #InteligenciaArtificial #OpenSource #EngenhariaDeSoftware

O texto está preparado para revisão do autor. Nenhuma publicação ou mensagem no LinkedIn foi enviada.
