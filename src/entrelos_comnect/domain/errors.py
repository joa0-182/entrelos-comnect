class ComnectError(Exception):
    """Erro esperado e seguro para telemetria por código, sem dados sensíveis."""

    code = "comnect_error"


class AuthorizationDenied(ComnectError):
    code = "authorization_denied"


class AuthorizationExpired(ComnectError):
    code = "authorization_expired"


class AuthorizationRevoked(ComnectError):
    code = "authorization_revoked"


class IsolationViolation(ComnectError):
    code = "organization_isolation_violation"


class ParameterScopeViolation(ComnectError):
    code = "parameter_scope_violation"


class OperationNotAllowed(ComnectError):
    code = "operation_not_allowed"


class DependencyUnavailable(ComnectError):
    code = "dependency_unavailable"
