from __future__ import annotations

import unittest

from entrelos_comnect.adapters.aws_secrets import AwsSecretsManagerProvider
from entrelos_comnect.domain.errors import IsolationViolation


class FrozenCredentials:
    def __init__(self, token: object | None) -> None:
        self.token = token


class Credentials:
    def __init__(self, token: object | None) -> None:
        self._token = token

    def get_frozen_credentials(self) -> FrozenCredentials:
        return FrozenCredentials(self._token)


class Session:
    def __init__(self, token: object | None) -> None:
        self._credentials = Credentials(token)
        self.created_client = False

    def get_credentials(self) -> Credentials:
        return self._credentials

    def client(self, _: str) -> object:
        self.created_client = True
        return object()


class AwsSecretsManagerProviderTests(unittest.TestCase):
    def test_rejects_non_temporary_aws_identity(self) -> None:
        session = Session(token=None)
        provider = AwsSecretsManagerProvider(region_name="sa-east-1", session=session)
        with self.assertRaises(IsolationViolation):
            provider._secrets_client()
        self.assertFalse(session.created_client)

    def test_accepts_temporary_aws_identity(self) -> None:
        session = Session(token=object())
        provider = AwsSecretsManagerProvider(region_name="sa-east-1", session=session)
        provider._secrets_client()
        self.assertTrue(session.created_client)
