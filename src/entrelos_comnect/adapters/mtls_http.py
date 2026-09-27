from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.request import Request, urlopen

from entrelos_comnect.domain.errors import DependencyUnavailable

from .settings import MtlsSettings


class MtlsJsonClient:
    """Cliente HTTP de saída com mTLS; não registra corpos, cabeçalhos ou URLs completas."""

    def __init__(self, mtls: MtlsSettings, *, timeout_seconds: float = 30.0) -> None:
        context = ssl.create_default_context(cafile=str(mtls.ca_bundle_path))
        context.load_cert_chain(str(mtls.certificate_path), str(mtls.private_key_path))
        self._context = context
        self._timeout_seconds = timeout_seconds

    def post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
            request = Request(
                url,
                data=encoded,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, context=self._context, timeout=self._timeout_seconds) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise DependencyUnavailable("mtls_remote_unavailable") from error
