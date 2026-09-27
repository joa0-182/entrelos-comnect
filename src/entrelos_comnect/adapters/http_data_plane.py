from __future__ import annotations

from typing import Any

from entrelos_comnect.domain.models import DataBatch

from .mtls_http import MtlsJsonClient


class HttpDataPlaneBatchSink:
    """Entrega lotes por conexão mTLS de saída fora do Control Plane."""

    def __init__(self, base_url: str, http: MtlsJsonClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http

    def publish(self, execution_id: str, batch: DataBatch) -> None:
        body: dict[str, Any] = {
            "contract_version": "v1",
            "execution_id": execution_id,
            "sequence": batch.sequence,
            "rows": list(batch.rows),
        }
        self._http.post(f"{self._base_url}/v1/comnect/batches", body)
