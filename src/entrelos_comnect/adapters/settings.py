from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_FORBIDDEN_KEY_PARTS = ("password", "senha", "secret", "token", "connection_string", "access_key")


def _reject_secret_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if any(part in str(key).lower() for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError(f"secret-bearing configuration key is forbidden: {key}")
            _reject_secret_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_secret_keys(child)


@dataclass(frozen=True)
class MtlsSettings:
    certificate_path: Path
    private_key_path: Path
    ca_bundle_path: Path


@dataclass(frozen=True)
class SqlServerSourceSettings:
    host: str
    database: str
    driver: str
    batch_size: int


@dataclass(frozen=True)
class ServiceSettings:
    organization_id: str
    installation_id: str
    control_plane_url: str
    data_plane_url: str
    aws_region: str
    mtls: MtlsSettings
    sources: Mapping[str, SqlServerSourceSettings]

    @classmethod
    def from_file(cls, path: str | Path) -> ServiceSettings:
        return cls.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ServiceSettings:
        _reject_secret_keys(raw)
        mtls = raw["mtls"]
        sources = {
            source_id: SqlServerSourceSettings(
                host=source["host"],
                database=source["database"],
                driver=source["driver"],
                batch_size=int(source["batch_size"]),
            )
            for source_id, source in raw["sources"].items()
        }
        if any(source.batch_size < 1 or source.batch_size > 10_000 for source in sources.values()):
            raise ValueError("batch_size must be between 1 and 10000")
        return cls(
            organization_id=raw["organization_id"],
            installation_id=raw["installation_id"],
            control_plane_url=raw["control_plane_url"].rstrip("/"),
            data_plane_url=raw["data_plane_url"].rstrip("/"),
            aws_region=raw["aws_region"],
            mtls=MtlsSettings(
                certificate_path=Path(mtls["certificate_path"]),
                private_key_path=Path(mtls["private_key_path"]),
                ca_bundle_path=Path(mtls["ca_bundle_path"]),
            ),
            sources=sources,
        )
