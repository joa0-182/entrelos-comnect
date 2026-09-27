from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from entrelos_comnect.application.ports import SecretMaterial
from entrelos_comnect.domain.errors import (
    DependencyUnavailable,
    IsolationViolation,
    OperationNotAllowed,
)
from entrelos_comnect.domain.models import DataBatch, OperationDefinition
from entrelos_comnect.operations.lojas_sp import LojasSpOperationCatalog

from .settings import SqlServerSourceSettings


class SqlServerBatchReader:
    """Adaptador somente leitura para operações catalogadas e parâmetros vinculados."""

    def __init__(
        self,
        sources: Mapping[str, SqlServerSourceSettings],
        catalog: LojasSpOperationCatalog,
    ) -> None:
        self._sources = sources
        self._catalog = catalog

    def read_batches(
        self,
        operation: OperationDefinition,
        parameters: Mapping[str, Any],
        secret: SecretMaterial,
    ) -> Iterable[DataBatch]:
        sql_operation = self._catalog.sql_server_operation(operation.operation_id)
        if sql_operation.definition != operation:
            raise OperationNotAllowed("untrusted_operation_definition")
        try:
            source = self._sources[operation.source_id]
        except KeyError as error:
            raise IsolationViolation("source_not_configured_for_installation") from error

        credential = self._decode_credential(secret)
        try:
            import pyodbc
        except ImportError as error:
            raise DependencyUnavailable("sqlserver_extra_not_installed") from error

        # A string é criada somente durante a chamada ao driver e não é registrada.
        connection_options = (
            f"DRIVER={{{source.driver}}};SERVER={source.host};DATABASE={source.database};"
            f"UID={credential['username']};PWD={credential['password']};"
            "Encrypt=yes;TrustServerCertificate=no;ApplicationIntent=ReadOnly"
        )
        try:
            with pyodbc.connect(connection_options, autocommit=True) as connection:
                cursor_value = int(parameters.get("codigo_inicial", 0))
                sequence = 1
                while True:
                    bound = (source.batch_size, parameters["filial_codigo"], cursor_value)
                    cursor = connection.cursor()
                    try:
                        cursor.execute(sql_operation.query, bound)
                        columns = tuple(column[0] for column in cursor.description)
                        raw_rows = cursor.fetchall()
                    finally:
                        cursor.close()
                    if not raw_rows:
                        break
                    rows = tuple(dict(zip(columns, row, strict=True)) for row in raw_rows)
                    yield DataBatch(sequence=sequence, rows=rows)
                    cursor_value = int(rows[-1][sql_operation.cursor_column])
                    sequence += 1
        finally:
            # Remove referências às cópias de texto tão logo o driver tenha terminado.
            credential.clear()
            connection_options = ""

    @staticmethod
    def _decode_credential(secret: SecretMaterial) -> dict[str, str]:
        try:
            decoded = json.loads(secret.bytes().decode("utf-8"))
            username = decoded["username"]
            password = decoded["password"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise IsolationViolation("invalid_database_secret_shape") from error
        is_valid = (
            isinstance(username, str)
            and isinstance(password, str)
            and bool(username)
            and bool(password)
        )
        if not is_valid:
            raise IsolationViolation("invalid_database_secret_shape")
        return {"username": username, "password": password}
