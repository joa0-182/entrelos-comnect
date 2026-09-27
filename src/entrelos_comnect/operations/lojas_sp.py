from __future__ import annotations

from dataclasses import dataclass

from entrelos_comnect.domain.errors import OperationNotAllowed
from entrelos_comnect.domain.models import OperationDefinition, ParameterRule

LOJAS_SP_PRODUTO_CATALOGO_V1 = OperationDefinition(
    operation_id="lojas_sp.sqlserver.produto_catalogo.v1",
    source_id="lojas_sp_sqlserver",
    parameters=(
        ParameterRule("filial_codigo", str, max_length=20),
        ParameterRule("codigo_inicial", int, required=False, minimum=0),
    ),
)


@dataclass(frozen=True)
class SqlServerOperation:
    definition: OperationDefinition
    query: str
    parameter_names: tuple[str, ...]
    cursor_column: str


LOJAS_SP_SQL_OPERATIONS = {
    LOJAS_SP_PRODUTO_CATALOGO_V1.operation_id: SqlServerOperation(
        definition=LOJAS_SP_PRODUTO_CATALOGO_V1,
        query=(
            "SELECT TOP (?) Codigo, Descricao, Ativo, DataAlteracao "
            "FROM dbo.Produtos "
            "WHERE FilialCodigo = ? AND Codigo > ? "
            "ORDER BY Codigo ASC"
        ),
        parameter_names=("filial_codigo", "codigo_inicial"),
        cursor_column="Codigo",
    )
}


class LojasSpOperationCatalog:
    def get(self, operation_id: str) -> OperationDefinition:
        try:
            return LOJAS_SP_SQL_OPERATIONS[operation_id].definition
        except KeyError as error:
            raise OperationNotAllowed("operation_not_cataloged") from error

    def sql_server_operation(self, operation_id: str) -> SqlServerOperation:
        try:
            return LOJAS_SP_SQL_OPERATIONS[operation_id]
        except KeyError as error:
            raise OperationNotAllowed("operation_not_cataloged") from error
