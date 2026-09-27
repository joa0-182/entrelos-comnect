from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from entrelos_comnect.domain.errors import ComnectError, IsolationViolation, OperationNotAllowed
from entrelos_comnect.domain.models import ExecutionRequest, ExecutionSummary, utc_now

from .ports import (
    BatchReaderPort,
    BatchSinkPort,
    ControlPlanePort,
    OperationCatalogPort,
    SecretProviderPort,
)


class ExecuteOperation:
    """Orquestra uma execução autorizada sem expor segredo ou SQL ao chamador."""

    def __init__(
        self,
        *,
        organization_id: str,
        installation_id: str,
        control_plane: ControlPlanePort,
        secrets: SecretProviderPort,
        reader: BatchReaderPort,
        sink: BatchSinkPort,
        catalog: OperationCatalogPort,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._organization_id = organization_id
        self._installation_id = installation_id
        self._control_plane = control_plane
        self._secrets = secrets
        self._reader = reader
        self._sink = sink
        self._catalog = catalog
        self._clock = clock

    def execute(self, request: ExecutionRequest) -> ExecutionSummary:
        if (
            request.organization_id != self._organization_id
            or request.installation_id != self._installation_id
        ):
            raise IsolationViolation("request_not_for_this_installation")

        operation = self._catalog.get(request.operation_id)
        if operation.source_id == "":
            raise OperationNotAllowed("operation_without_source")
        operation.validate_parameters(request.parameters)

        grant = self._control_plane.authorize(request)
        grant.assert_matches(request, now=self._clock())
        if grant.source_id != operation.source_id:
            raise IsolationViolation("grant_source_mismatch")

        batch_count = 0
        row_count = 0
        with self._secrets.fetch(
            organization_id=self._organization_id,
            secret_reference=grant.secret_reference,
        ) as secret:
            for batch in self._reader.read_batches(operation, request.parameters, secret):
                self._assert_active(request.execution_id)
                self._sink.publish(request.execution_id, batch)
                batch_count += 1
                row_count += len(batch.rows)

        summary = ExecutionSummary(request.execution_id, batch_count, row_count)
        self._control_plane.report_status(
            request.execution_id,
            "completed",
            batch_count=summary.batch_count,
            row_count=summary.row_count,
        )
        return summary

    def _assert_active(self, execution_id: str) -> None:
        now: datetime = self._clock()
        self._control_plane.assert_execution_active(execution_id, now)


class ComnectWorker:
    """Faz long polling de saída; não abre listeners de rede."""

    def __init__(
        self,
        control_plane: ControlPlanePort,
        executor: ExecuteOperation,
        organization_id: str,
        installation_id: str,
    ) -> None:
        self._control_plane = control_plane
        self._executor = executor
        self._organization_id = organization_id
        self._installation_id = installation_id

    def run_once(self) -> bool:
        request = self._control_plane.next_execution(self._organization_id, self._installation_id)
        if request is None:
            return False
        try:
            self._executor.execute(request)
        except ComnectError as error:
            self._control_plane.report_status(request.execution_id, "failed", error_code=error.code)
        except Exception:
            self._control_plane.report_status(
                request.execution_id,
                "failed",
                error_code="internal_error",
            )
        return True
