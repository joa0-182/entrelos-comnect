from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, Protocol

from entrelos_comnect.domain.models import (
    AuthorizationGrant,
    DataBatch,
    ExecutionRequest,
    OperationDefinition,
)


class ControlPlanePort(Protocol):
    def next_execution(
        self,
        organization_id: str,
        installation_id: str,
    ) -> ExecutionRequest | None: ...

    def authorize(self, request: ExecutionRequest) -> AuthorizationGrant: ...

    def assert_execution_active(self, execution_id: str, now: datetime) -> None: ...

    def report_status(
        self,
        execution_id: str,
        state: str,
        *,
        batch_count: int = 0,
        row_count: int = 0,
        error_code: str | None = None,
    ) -> None: ...


class SecretMaterial:
    """Buffer efêmero que o chamador deve limpar ao fim da operação."""

    def __init__(self, payload: bytes) -> None:
        self._payload = bytearray(payload)
        self._closed = False

    def bytes(self) -> bytes:
        if self._closed:
            raise RuntimeError("secret material already discarded")
        return bytes(self._payload)

    def close(self) -> None:
        for index in range(len(self._payload)):
            self._payload[index] = 0
        self._closed = True

    def __enter__(self) -> SecretMaterial:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class SecretProviderPort(Protocol):
    def fetch(self, *, organization_id: str, secret_reference: str) -> SecretMaterial: ...


class BatchReaderPort(Protocol):
    def read_batches(
        self,
        operation: OperationDefinition,
        parameters: Mapping[str, Any],
        secret: SecretMaterial,
    ) -> Iterable[DataBatch]: ...


class BatchSinkPort(Protocol):
    def publish(self, execution_id: str, batch: DataBatch) -> None: ...


class OperationCatalogPort(Protocol):
    def get(self, operation_id: str) -> OperationDefinition: ...
