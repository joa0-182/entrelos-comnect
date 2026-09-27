from __future__ import annotations

from typing import Any

from entrelos_comnect.application.ports import SecretMaterial
from entrelos_comnect.domain.errors import DependencyUnavailable, IsolationViolation


class AwsSecretsManagerProvider:
    """Busca um segredo autorizado usando somente credenciais temporárias da cadeia AWS."""

    def __init__(
        self,
        *,
        region_name: str,
        client: Any | None = None,
        session: Any | None = None,
    ) -> None:
        self._region_name = region_name
        self._client = client
        self._session = session

    def _secrets_client(self) -> Any:
        if self._client is not None:
            return self._client
        session = self._session
        if session is None:
            try:
                import boto3
            except ImportError as error:
                raise DependencyUnavailable("aws_extra_not_installed") from error
            session = boto3.session.Session(region_name=self._region_name)
        credentials = session.get_credentials()
        if credentials is None or not credentials.get_frozen_credentials().token:
            raise IsolationViolation("aws_temporary_identity_required")
        # A cadeia padrão deve fornecer sessão temporária (por exemplo, IAM Roles Anywhere).
        return session.client("secretsmanager")

    def fetch(self, *, organization_id: str, secret_reference: str) -> SecretMaterial:
        # O vínculo organização → ARN é autorizado pelo Control Plane e reforçado por IAM/KMS.
        # Não inferimos nem aceitamos outro identificador de segredo nesta camada.
        if not organization_id or not secret_reference:
            raise IsolationViolation("missing_secret_scope")
        response = self._secrets_client().get_secret_value(SecretId=secret_reference)
        if "SecretBinary" in response:
            payload = bytes(response["SecretBinary"])
        else:
            payload = response["SecretString"].encode("utf-8")
        return SecretMaterial(payload)
