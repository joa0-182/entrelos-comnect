from __future__ import annotations

import argparse

from entrelos_comnect.adapters.aws_secrets import AwsSecretsManagerProvider
from entrelos_comnect.adapters.http_control_plane import HttpControlPlaneClient
from entrelos_comnect.adapters.http_data_plane import HttpDataPlaneBatchSink
from entrelos_comnect.adapters.mtls_http import MtlsJsonClient
from entrelos_comnect.adapters.settings import ServiceSettings
from entrelos_comnect.adapters.sql_server import SqlServerBatchReader
from entrelos_comnect.application.execute_operation import ComnectWorker, ExecuteOperation
from entrelos_comnect.operations.lojas_sp import LojasSpOperationCatalog


def build_worker(settings: ServiceSettings) -> ComnectWorker:
    http = MtlsJsonClient(settings.mtls)
    catalog = LojasSpOperationCatalog()
    control_plane = HttpControlPlaneClient(settings.control_plane_url, http)
    executor = ExecuteOperation(
        organization_id=settings.organization_id,
        installation_id=settings.installation_id,
        control_plane=control_plane,
        secrets=AwsSecretsManagerProvider(region_name=settings.aws_region),
        reader=SqlServerBatchReader(settings.sources, catalog),
        sink=HttpDataPlaneBatchSink(settings.data_plane_url, http),
        catalog=catalog,
    )
    return ComnectWorker(
        control_plane,
        executor,
        settings.organization_id,
        settings.installation_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrelos Comnect")
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    arguments = parser.parse_args()
    worker = build_worker(ServiceSettings.from_file(arguments.config))
    if arguments.once:
        worker.run_once()
        return 0
    from entrelos_comnect.adapters.windows_service import run_worker_loop

    run_worker_loop(worker.run_once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
