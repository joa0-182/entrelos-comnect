# Prompt de desenvolvimento — Entrelos Comnect

Você está desenvolvendo o **Entrelos Comnect**, um conector instalável no ambiente da organização. Siga estas regras sem ampliar o escopo:

## Objetivo

Permitir que produtos Entrelos consultem fontes internas da organização com segurança, sem credenciais de ERP no Octopus, instalador ou `.env` do produto.

## Responsabilidades

- **AWS KMS + Secrets Manager:** armazenam a credencial criptografada.
- **Control Plane:** é a autoridade de organização, instalação, autorização, revogação, auditoria e referência do segredo. Não deve processar dados massivos do ERP nem devolver a senha ao produto.
- **Comnect:** valida a autorização, obtém a credencial temporariamente, conecta à fonte e devolve somente dados em lotes.
- **Produtos (Octopus, Lince, BI):** aplicam regras de negócio, telas, arquivos XLSX/PDF e decisões do operador. Nunca executam SQL do ERP nem acessam segredos.

## Segurança obrigatória

- Serviço instalado na organização, com conexão **somente de saída** e mTLS; sem porta pública de entrada e sem VPN obrigatória.
- O Comnect recebe `operacao_id` e parâmetros autorizados; nunca SQL livre vindo do produto.
- Operações são versionadas, técnicas e específicas da fonte. Regra de negócio não pertence ao Comnect.
- Segredos são obtidos sob demanda, ficam somente em memória durante a execução e são descartados ao final.
- Menor privilégio: identidade do Comnect só lê o segredo da organização autorizada; Octopus não acessa AWS/KMS/Secrets Manager.
- Nunca registrar senha, token, connection string, payload sensível ou dados de acesso em logs, testes, documentação ou Git.

## Dados e escala

- Respostas usuais: JSON paginado/em lotes.
- Processamentos grandes: fluxo incremental; usar formato colunar/arquivo temporário protegido somente se o contrato exigir.
- O Comnect não gera XLSX, PDF ou relatórios finais.

## Ordem da entrega atual

1. Estruturar o serviço Windows, configuração sem segredos e identidade mTLS.
2. Criar contrato versionado Control Plane ↔ Comnect para autorização e execução.
3. Integrar AWS com identidade temporária e permissões mínimas.
4. Implementar adaptador SQL Server somente leitura e execução em lotes.
5. Homologar uma operação da Lojas São Paulo com credencial de teste limitada.
6. Só então cadastrar a credencial real no AWS Secrets Manager, ativar a fonte no Control Plane e retirar o `.env` legado.

## Critérios de qualidade

Use DDD/Clean Architecture: domínio independente de HTTP, AWS, Windows e banco; portas pequenas; adaptadores isolados. Teste autorização, expiração, revogação, escopo de parâmetros, indisponibilidade, ausência de vazamento e execução em lote. Preserve isolamento absoluto entre organizações.
