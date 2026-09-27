from __future__ import annotations

from datetime import datetime
from typing import Any

from entrelos_comnect.domain.errors import AuthorizationRevoked
from entrelos_comnect.domain.models import AuthorizationGrant, ExecutionRequest

from .mtls_http import MtlsJsonClient


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class HttpControlPlaneClient:
    """Adaptador do contrato v1 de controle; nenhum lote do ERP passa por aqui."""

    def __init__(self, base_url: str, http: MtlsJsonClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http

    def next_execution(self, organization_id: str, installation_id: str) -> ExecutionRequest | None:
        response = self._http.post(
            f"{self._base_url}/v1/comnect/commands:next",
            {
                "contract_version": "v1",
                "organization_id": organization_id,
                "installation_id": installation_id,
            },
        )
        if response.get("kind") == "no_command":
            return None
        return ExecutionRequest(
            execution_id=response["execution_id"],
            organization_id=response["organization_id"],
            installation_id=response["installation_id"],
            operation_id=response["operation_id"],
            parameters=response["parameters"],
            contract_version=response["contract_version"],
        )

    def authorize(self, request: ExecutionRequest) -> AuthorizationGrant:
        response = self._http.post(
            f"{self._base_url}/v1/comnect/executions:authorize",
            {
                "contract_version": "v1",
                "kind": "execution_command",
                "execution_id": request.execution_id,
                "organization_id": request.organization_id,
                "installation_id": request.installation_id,
                "operation_id": request.operation_id,
                "parameters": dict(request.parameters),
            },
        )
        if not response.get("authorized"):
            raise AuthorizationRevoked("control_plane_denied")
        return AuthorizationGrant(
            execution_id=response["execution_id"],
            organization_id=response["organization_id"],
            installation_id=response["installation_id"],
            operation_id=response["operation_id"],
            source_id=response["source_id"],
            secret_reference=response["secret_reference"],
            expires_at=_parse_time(response["expires_at"]),
            parameter_scope=response["parameter_scope"],
            authorized=True,
        )

    def assert_execution_active(self, execution_id: str, now: datetime) -> None:
        response = self._http.post(
            f"{self._base_url}/v1/comnect/executions:active",
            {"contract_version": "v1", "execution_id": execution_id, "checked_at": now.isoformat()},
        )
        if not response.get("active"):
            raise AuthorizationRevoked("execution_revoked")

    def report_status(
        self,
        execution_id: str,
        state: str,
        *,
        batch_count: int = 0,
        row_count: int = 0,
        error_code: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "contract_version": "v1",
            "kind": "execution_status",
            "execution_id": execution_id,
            "state": state,
            "batch_count": batch_count,
            "row_count": row_count,
        }
        if error_code is not None:
            body["error_code"] = error_code
        self._http.post(f"{self._base_url}/v1/comnect/executions:status", body)
