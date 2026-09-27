from __future__ import annotations

import unittest
from datetime import timedelta
from typing import Any

from entrelos_comnect.application.execute_operation import ExecuteOperation
from entrelos_comnect.application.ports import SecretMaterial
from entrelos_comnect.domain.errors import (
    AuthorizationExpired,
    AuthorizationRevoked,
    DependencyUnavailable,
    IsolationViolation,
    ParameterScopeViolation,
)
from entrelos_comnect.domain.models import AuthorizationGrant, DataBatch, ExecutionRequest, utc_now
from entrelos_comnect.operations.lojas_sp import LojasSpOperationCatalog

NOW = utc_now()


def request(**overrides: Any) -> ExecutionRequest:
    values = {
        "execution_id": "exec_001",
        "organization_id": "org_lojas_sp",
        "installation_id": "inst_lojas_sp_01",
        "operation_id": "lojas_sp.sqlserver.produto_catalogo.v1",
        "parameters": {"filial_codigo": "001", "codigo_inicial": 0},
    }
    values.update(overrides)
    return ExecutionRequest(**values)


def grant(**overrides: Any) -> AuthorizationGrant:
    values = {
        "execution_id": "exec_001",
        "organization_id": "org_lojas_sp",
        "installation_id": "inst_lojas_sp_01",
        "operation_id": "lojas_sp.sqlserver.produto_catalogo.v1",
        "source_id": "lojas_sp_sqlserver",
        "secret_reference": "opaque-secret-reference",
        "expires_at": NOW + timedelta(minutes=5),
        "parameter_scope": {"filial_codigo": {"allowed_values": ["001"]}},
    }
    values.update(overrides)
    return AuthorizationGrant(**values)


class FakeControlPlane:
    def __init__(
        self,
        authorization: AuthorizationGrant,
        *,
        revoke_after_checks: int | None = None,
    ) -> None:
        self.authorization = authorization
        self.revoke_after_checks = revoke_after_checks
        self.checks = 0
        self.statuses: list[tuple[str, str, int, int, str | None]] = []

    def authorize(self, _: ExecutionRequest) -> AuthorizationGrant:
        return self.authorization

    def assert_execution_active(self, _: str, __: object) -> None:
        self.checks += 1
        if self.revoke_after_checks is not None and self.checks > self.revoke_after_checks:
            raise AuthorizationRevoked("revoked_by_test")

    def report_status(
        self,
        execution_id: str,
        state: str,
        *,
        batch_count: int = 0,
        row_count: int = 0,
        error_code: str | None = None,
    ) -> None:
        self.statuses.append((execution_id, state, batch_count, row_count, error_code))


class TrackingSecrets:
    def __init__(self) -> None:
        self.material: SecretMaterial | None = None
        self.calls: list[tuple[str, str]] = []

    def fetch(self, *, organization_id: str, secret_reference: str) -> SecretMaterial:
        self.calls.append((organization_id, secret_reference))
        self.material = SecretMaterial(b"discardable-test-material")
        return self.material


class FakeReader:
    def __init__(self, batches: list[DataBatch]) -> None:
        self.batches = batches
        self.called = False

    def read_batches(self, *_: object):
        self.called = True
        yield from self.batches


class CapturingSink:
    def __init__(self) -> None:
        self.batches: list[DataBatch] = []

    def publish(self, _: str, batch: DataBatch) -> None:
        self.batches.append(batch)


class ExecuteOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.control = FakeControlPlane(grant())
        self.secrets = TrackingSecrets()
        self.reader = FakeReader(
            [
                DataBatch(1, ({"Codigo": 1}, {"Codigo": 2})),
                DataBatch(2, ({"Codigo": 3},)),
            ]
        )
        self.sink = CapturingSink()
        self.executor = ExecuteOperation(
            organization_id="org_lojas_sp",
            installation_id="inst_lojas_sp_01",
            control_plane=self.control,
            secrets=self.secrets,
            reader=self.reader,
            sink=self.sink,
            catalog=LojasSpOperationCatalog(),
            clock=lambda: NOW,
        )

    def test_executes_only_in_batches_and_discards_secret(self) -> None:
        with self.assertNoLogs():
            summary = self.executor.execute(request())

        self.assertEqual((summary.batch_count, summary.row_count), (2, 3))
        self.assertEqual([batch.sequence for batch in self.sink.batches], [1, 2])
        self.assertEqual(self.secrets.calls, [("org_lojas_sp", "opaque-secret-reference")])
        # Assert lifecycle without retaining a real credential in the test suite.
        self.assertTrue(self.secrets.material._closed)
        self.assertEqual(self.control.statuses[-1], ("exec_001", "completed", 2, 3, None))

    def test_rejects_parameter_outside_control_plane_scope_before_secret_lookup(self) -> None:
        with self.assertRaises(ParameterScopeViolation):
            self.executor.execute(request(parameters={"filial_codigo": "999", "codigo_inicial": 0}))
        self.assertEqual(self.secrets.calls, [])

    def test_rejects_expired_grant_before_secret_lookup(self) -> None:
        self.control.authorization = grant(expires_at=NOW - timedelta(seconds=1))
        with self.assertRaises(AuthorizationExpired):
            self.executor.execute(request())
        self.assertEqual(self.secrets.calls, [])

    def test_rejects_other_organization_before_control_plane_or_secret(self) -> None:
        with self.assertRaises(IsolationViolation):
            self.executor.execute(request(organization_id="org_other"))
        self.assertEqual(self.secrets.calls, [])

    def test_stops_when_revoked_between_batches_and_discards_secret(self) -> None:
        self.control.revoke_after_checks = 1
        with self.assertRaises(AuthorizationRevoked):
            self.executor.execute(request())
        self.assertEqual(len(self.sink.batches), 1)
        self.assertTrue(self.secrets.material._closed)

    def test_unknown_parameter_never_reaches_secret_provider(self) -> None:
        with self.assertRaises(ParameterScopeViolation):
            self.executor.execute(request(parameters={"filial_codigo": "001", "sql": "SELECT 1"}))
        self.assertEqual(self.secrets.calls, [])

    def test_control_plane_indisponibility_never_reaches_secret_provider(self) -> None:
        class UnavailableControlPlane(FakeControlPlane):
            def authorize(self, _: ExecutionRequest) -> AuthorizationGrant:
                raise DependencyUnavailable("control_plane_unavailable")

        unavailable_executor = ExecuteOperation(
            organization_id="org_lojas_sp",
            installation_id="inst_lojas_sp_01",
            control_plane=UnavailableControlPlane(grant()),
            secrets=self.secrets,
            reader=self.reader,
            sink=self.sink,
            catalog=LojasSpOperationCatalog(),
            clock=lambda: NOW,
        )
        with self.assertRaises(DependencyUnavailable):
            unavailable_executor.execute(request())
        self.assertEqual(self.secrets.calls, [])

    def test_grant_for_other_organization_is_rejected_before_secret_lookup(self) -> None:
        self.control.authorization = grant(organization_id="org_other")
        with self.assertRaises(IsolationViolation):
            self.executor.execute(request())
        self.assertEqual(self.secrets.calls, [])
