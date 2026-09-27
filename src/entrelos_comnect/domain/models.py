from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .errors import (
    AuthorizationExpired,
    AuthorizationRevoked,
    IsolationViolation,
    OperationNotAllowed,
    ParameterScopeViolation,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ParameterRule:
    name: str
    value_type: type
    required: bool = True
    allowed_values: frozenset[Any] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    max_length: int | None = None

    def validate(self, value: Any) -> None:
        if self.value_type is int and isinstance(value, bool):
            raise ParameterScopeViolation(self.name)
        if not isinstance(value, self.value_type):
            raise ParameterScopeViolation(self.name)
        if self.allowed_values is not None and value not in self.allowed_values:
            raise ParameterScopeViolation(self.name)
        if self.minimum is not None and value < self.minimum:
            raise ParameterScopeViolation(self.name)
        if self.maximum is not None and value > self.maximum:
            raise ParameterScopeViolation(self.name)
        if self.max_length is not None and isinstance(value, str) and len(value) > self.max_length:
            raise ParameterScopeViolation(self.name)


@dataclass(frozen=True)
class OperationDefinition:
    operation_id: str
    source_id: str
    parameters: tuple[ParameterRule, ...]

    def validate_parameters(self, supplied: Mapping[str, Any]) -> None:
        rules = {rule.name: rule for rule in self.parameters}
        if set(supplied) - set(rules):
            raise ParameterScopeViolation("unknown_parameter")
        for rule in self.parameters:
            if rule.required and rule.name not in supplied:
                raise ParameterScopeViolation(rule.name)
            if rule.name in supplied:
                rule.validate(supplied[rule.name])


@dataclass(frozen=True)
class ExecutionRequest:
    execution_id: str
    organization_id: str
    installation_id: str
    operation_id: str
    parameters: Mapping[str, Any]
    contract_version: str = "v1"


@dataclass(frozen=True)
class AuthorizationGrant:
    execution_id: str
    organization_id: str
    installation_id: str
    operation_id: str
    source_id: str
    secret_reference: str
    expires_at: datetime
    parameter_scope: Mapping[str, Mapping[str, Any]]
    authorized: bool = True

    def assert_matches(self, request: ExecutionRequest, *, now: datetime | None = None) -> None:
        if not self.authorized:
            raise AuthorizationRevoked("grant_not_authorized")
        if (
            self.execution_id != request.execution_id
            or self.organization_id != request.organization_id
            or self.installation_id != request.installation_id
        ):
            raise IsolationViolation("grant_identity_mismatch")
        if self.operation_id != request.operation_id:
            raise OperationNotAllowed("grant_operation_mismatch")
        if self.expires_at <= (now or utc_now()):
            raise AuthorizationExpired("grant_expired")
        self.assert_parameter_scope(request.parameters)

    def assert_parameter_scope(self, parameters: Mapping[str, Any]) -> None:
        for name, scope in self.parameter_scope.items():
            if name not in parameters:
                continue
            value = parameters[name]
            allowed_values = scope.get("allowed_values")
            if allowed_values is not None and value not in allowed_values:
                raise ParameterScopeViolation(name)
            minimum = scope.get("minimum")
            maximum = scope.get("maximum")
            if minimum is not None and value < minimum:
                raise ParameterScopeViolation(name)
            if maximum is not None and value > maximum:
                raise ParameterScopeViolation(name)


@dataclass(frozen=True)
class DataBatch:
    sequence: int
    rows: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ExecutionSummary:
    execution_id: str
    batch_count: int
    row_count: int
