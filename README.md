# Entrelos Comnect

Entrelos Comnect é o conector instalado no ambiente de cada organização. Ele só inicia conexões de saída protegidas por mTLS, valida uma autorização de curta duração no Control Plane, busca a credencial autorizada sob demanda e transmite lotes de dados para o plano de dados. Produtos Entrelos não recebem credenciais, não chamam AWS e não enviam SQL.

## Limites da primeira entrega

Esta base inclui o serviço Windows, o contrato versionado, as portas da aplicação, os adaptadores AWS/SQL Server e uma operação técnica de catálogo de produtos para Lojas São Paulo. Não contém credenciais, certificados, endpoints reais, fontes ativadas ou acesso a ambiente de homologação. A homologação e a ativação da credencial real continuam sendo passos operacionais separados.

O Control Plane autoriza e revoga execuções; ele não recebe nem encaminha lotes do ERP. O envio dos lotes é feito pelo adaptador de plano de dados, em uma conexão de saída mTLS distinta.

## Estrutura

```text
src/entrelos_comnect/
  domain/        # entidades, políticas de parâmetro e erros sem dependências de infraestrutura
  application/   # caso de uso e portas pequenas
  adapters/      # HTTP mTLS, AWS, SQL Server, Windows e configuração
  operations/    # catálogo imutável de operações SQL permitidas
contracts/       # esquema JSON versionado Control Plane ↔ Comnect
config/          # exemplo sem segredos
tests/           # autorização, expiração, revogação, escopo, isolamento e lotes
```

## Configuração da instalação

Copie `config/comnect.example.json` para `config/comnect.json` e preencha identificadores, URLs e caminhos locais dos certificados. O arquivo intencionalmente não aceita campos cujo nome indique senha, token, segredo ou connection string. Restrinja a leitura da chave privada mTLS à conta de serviço do Windows.

O SDK AWS usa a cadeia padrão de credenciais. Em instalação on-premises, ela deve entregar credenciais temporárias por uma identidade de workload, como AWS IAM Roles Anywhere, e nunca por chaves estáticas no arquivo de configuração. A política da identidade deve permitir apenas o ARN de segredo da própria organização e `kms:Decrypt` somente via Secrets Manager.

O modelo de menor privilégio está em `deployment/aws-iam-policy.template.json`. Ele exige a tag principal `organization_id`, um prefixo de segredo por organização e uma chave KMS específica daquela organização; substitua somente o placeholder do ARN de KMS no provisionamento seguro, nunca neste repositório com valores de produção.

Instale apenas os extras necessários ao host:

```powershell
uv sync --extra aws --extra sqlserver --extra windows-service --extra dev
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
```

Para uma execução de diagnóstico sem instalar o serviço, use `uv run entrelos-comnect --once --config config/comnect.json`. A operação só é executada quando o Control Plane entregar um comando autorizado e ainda ativo.

## Homologação Lojas São Paulo

1. Criar no AWS Secrets Manager uma credencial **de teste**, de leitura e limitada à tabela/visão aprovada.
2. Associar o ARN exclusivamente à organização Lojas São Paulo e à fonte `lojas_sp_sqlserver` no Control Plane.
3. Liberar somente `lojas_sp.sqlserver.produto_catalogo.v1`, com escopo de filial aprovado.
4. Instalar o serviço com certificado mTLS da instalação e identidade AWS temporária.
5. Executar a operação, conferir auditoria por `execution_id` e validar que os lotes chegam ao plano de dados.
6. Após homologação, cadastrar a credencial real, ativar a fonte e remover o legado somente em uma mudança operacional aprovada.

Não inclua valores de segredo, connection strings, payloads de lote, certificados privados ou logs de acesso em chamados, Git ou documentação.

## Integração do Control Plane

O prompt de implementação para a equipe ou repositório do Control Plane está em [CONTROL_PLANE_API_PROMPT.md](CONTROL_PLANE_API_PROMPT.md). Ele descreve o contrato que este serviço já consome, sem transferir ao Control Plane o plano de dados do ERP.
