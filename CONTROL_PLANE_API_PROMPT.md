# Prompt para o Control Plane API

Copie o texto abaixo para o chat responsável pelo repositório `control-plane-api`.

---

Você está implementando a integração do **Control Plane API** com o serviço instalado **Entrelos Comnect**. Trabalhe somente no Control Plane; não implemente consulta a ERP, driver SQL Server, geração de XLSX/PDF nem transporte de lotes de ERP neste serviço.

## Contexto e fronteiras

O Comnect é instalado no ambiente da organização e abre conexões **somente de saída**, autenticadas por mTLS. Ele consulta uma fonte interna depois de autorizado e entrega lotes de dados pelo plano de dados separado. Produtos Entrelos (Octopus, Lince e BI) não executam SQL no ERP e não acessam AWS, KMS ou Secrets Manager.

O Control Plane é a autoridade para organização, instalação, fonte, operação, autorização, expiração, revogação, auditoria e referência do segredo. Ele não deve receber, armazenar, processar ou encaminhar lotes massivos do ERP e nunca deve devolver senha, token, material de conexão ou `SecretString` ao Comnect ou aos produtos.

## Objetivo

Implementar o contrato **v1** Control Plane ↔ Comnect, disponível em `contracts/control-plane-comnect.v1.schema.json` no repositório `entrelos-comnect`. O Control Plane deve emitir comandos e grants de curta duração apenas para a instalação, organização, fonte, operação e escopo de parâmetros autorizados.

## Endpoints mTLS esperados pelo Comnect

Todos os endpoints são chamados pelo Comnect por conexão de saída mTLS. A identidade do certificado deve ser associada a uma instalação ativa e a uma única organização; nunca confie nos identificadores enviados no corpo sem compará-los à identidade mTLS.

### `POST /v1/comnect/commands:next`

Recebe `contract_version`, `organization_id` e `installation_id`.

- Valida a instalação mTLS, sua organização e seu estado (ativa/não revogada).
- Retorna `{"kind":"no_command"}` quando não houver trabalho.
- Quando houver trabalho, retorna um `execution_command` v1 com `execution_id`, `organization_id`, `installation_id`, `operation_id` e parâmetros já autorizados.
- Não aceite SQL, texto de filtro livre, connection string ou qualquer campo de acesso.

### `POST /v1/comnect/executions:authorize`

Recebe um `execution_command` v1 e retorna um `authorization_grant` v1.

- Confirma que a execução pertence à instalação autenticada, à mesma organização e a uma fonte ativa.
- Confirma que a operação é permitida para a fonte e que sua versão está habilitada.
- Valida os parâmetros contra o escopo autorizado, incluindo valores permitidos e faixas numéricas.
- Emite `expires_at` curto e `secret_reference` opaco que a identidade AWS daquela organização está autorizada a ler. A referência não é a senha e não deve aparecer em logs.
- Retorna negação explícita quando a instalação, fonte, operação ou escopo tiver sido revogado.

### `POST /v1/comnect/executions:active`

Recebe `execution_id` e confirma se ele ainda está ativo. O Comnect chama esse endpoint entre lotes.

- Retorne `active: false` imediatamente para execução, instalação, operação ou fonte revogada/expirada.
- Não reautorize implicitamente uma execução expirada.

### `POST /v1/comnect/executions:status`

Recebe somente metadados: `execution_id`, estado (`accepted`, `completed`, `denied`, `expired`, `revoked` ou `failed`), contagem de lotes, contagem de linhas e um código de erro seguro.

- Grave auditoria com organização, instalação, fonte, operação, versão, execução, ator/origem, decisões e timestamps.
- Não grave parâmetros sensíveis, payload de lotes, segredo, token, connection string ou erro bruto de infraestrutura.

## Modelo mínimo de domínio

Crie entidades ou agregados independentes de HTTP e banco:

- `Organization`
- `ComnectInstallation` — identidade mTLS, organização, estado e última comunicação.
- `DataSource` — organização, tipo, referência opaca do segredo, estado.
- `TechnicalOperation` — identificador versionado, fonte/tipo compatível e schema de parâmetros permitido.
- `ExecutionAuthorization` — execução, instalação, operação, fonte, escopo imutável, expiração, estado e revogação.
- `AuditEvent` — metadados seguros e imutáveis.

Use isolamento obrigatório por `organization_id` em todas as consultas e comandos. Não permita que um identificador de outra organização seja aceito mesmo se ele existir no banco.

## Segurança obrigatória

- mTLS obrigatório para todos os endpoints do Comnect; revogue ou bloqueie certificados de instalações inativas.
- O Control Plane é a única autoridade de autorização. Não confie em `operation_id`, fonte ou escopo informados pelo cliente sem verificar a persistência autorizada.
- Faça grants curtos, específicos de uma execução e não reutilizáveis entre organizações ou instalações.
- A revogação deve ser efetiva antes do próximo lote.
- Retorne somente códigos de erro seguros. Não exponha detalhes de AWS, KMS, Secrets Manager, SQL Server ou credenciais.
- O Control Plane guarda apenas a referência opaca do segredo. A política AWS da identidade do Comnect limita `secretsmanager:GetSecretValue` e `kms:Decrypt` ao segredo/chave da organização.
- Não crie API de consulta ao ERP, proxy de SQL, upload de lote, cache de lote ou relatório no Control Plane.

## Plano de dados

O endpoint que recebe lotes do Comnect pertence a um **plano de dados separado**. Não implemente esse endpoint no processo, banco ou fila do Control Plane. O Control Plane pode emitir um identificador de entrega opaco e auditar metadados, mas não deve ver o conteúdo dos lotes.

## Qualidade e testes exigidos

Use DDD/Clean Architecture e mantenha domínio independente de HTTP, ORM, AWS e fila. Teste, no mínimo:

1. mTLS de instalação válida, inválida, revogada e associada a outra organização.
2. Autorização de operação e versão permitidas.
3. Rejeição de SQL livre e de parâmetros fora do schema/escopo.
4. Expiração e revogação durante uma execução.
5. Isolamento absoluto entre organizações, inclusive por tentativa de enumerar IDs.
6. Auditoria sem vazamento de segredo, token, connection string, payload de lote ou detalhes internos de exceção.
7. Indisponibilidade de dependência com código seguro e sem reautorização indevida.

Entregue migrations, testes, documentação dos endpoints e uma implementação que esteja pronta para homologar somente a operação `lojas_sp.sqlserver.produto_catalogo.v1` com a fonte `lojas_sp_sqlserver`. Não cadastre credenciais reais e não ative a fonte de produção.
