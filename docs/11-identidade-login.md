# 11 · Identidade visual do login

A tela de autenticação usa o **Hosted UI clássico do Amazon Cognito**. A personalização mantém o formulário e o fluxo OAuth/PKCE hospedados na AWS: o aplicativo não recebe a senha.

## O que foi aplicado

- Logo Radar IA com símbolo de radar, assinatura **jrsantosdev** e subtítulo do projeto.
- Cartão azul-escuro `#101c2b`, campos em azul e botão verde `#c1ed80`, alinhados à interface do app.
- Campos e botão com 48 px de altura e contraste adequado para uso no celular.
- Links de recuperação e mensagens de erro com cores legíveis sobre o cartão escuro.

O Cognito clássico limita os seletores CSS permitidos. O fundo cinza externo, a estrutura do formulário e os textos padrão em inglês permanecem sob controle da plataforma. Uma identidade visual totalmente personalizada e localização exigem avaliar outra experiência de login; isso não foi migrado neste incremento. A versão do login, plano do pool, política de senha e duração de sessão continuam como estavam.

## Arquivos editáveis

- `infra/cognito/logo.svg`: origem vetorial editável.
- `infra/cognito/logo.png`: imagem enviada ao Cognito, gerada a partir do SVG.
- `infra/cognito/login.css`: regras de aparência permitidas pelo Hosted UI clássico.
- `examples/personalizar_login.py`: valida os arquivos e envia a personalização para o client existente.

O PNG tem 350 × 146 pixels e cerca de 10 KiB. A fonte SVG permanece no repositório para permitir mudanças sem redesenhar o logo. Para regenerar o PNG, use um editor vetorial ou Sharp com `sharp('infra/cognito/logo.svg').png().toFile('infra/cognito/logo.png')`.

## Aplicar em um ambiente

Configure sua sessão AWS e tenha os outputs da implantação em `local-output/deploy/outputs.json`. O comando sem flag apenas valida os arquivos:

```bat
.\.venv\Scripts\python.exe examples\personalizar_login.py
```

Para enviar:

```bat
.\.venv\Scripts\python.exe examples\personalizar_login.py --apply
```

O script confirma o vínculo entre domínio e user pool e exige a versão clássica. Ele salva a configuração visual anterior em `local-output/login-branding/backup-*.json`, aplica CSS/logo ao app client e consulta o resultado para conferir o envio. Não migra versão, não recria usuários e não solicita a senha do aplicativo. A propagação pode levar cerca de um minuto.

Permissões administrativas usadas: `cognito-idp:DescribeUserPoolDomain`, `cognito-idp:GetUICustomization` e `cognito-idp:SetUICustomization`. Essas permissões não são concedidas ao navegador nem à Lambda da API. A personalização é uma etapa separada da implantação CloudFormation; reaplique o comando ao criar um novo ambiente ou alterar os arquivos de marca.

## Verificação realizada em 29/10/2026

A configuração foi aplicada ao client existente. Um navegador Chrome isolado abriu a **página publicada real do Cognito**, sem fornecer credenciais, e conferiu carregamento do logo, cor verde do botão e ausência de rolagem horizontal a 390 px. Capturas do computador e celular estão em `local-output/login-branding/`. Não houve envio do formulário ou alteração da sessão do proprietário durante a verificação.

Referência: [personalização oficial do Hosted UI clássico](https://docs.aws.amazon.com/cognito/latest/developerguide/hosted-ui-classic-branding.html).
