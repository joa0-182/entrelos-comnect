from __future__ import annotations

import unittest

from entrelos_comnect.adapters.settings import ServiceSettings


class ServiceSettingsTests(unittest.TestCase):
    def test_rejects_secret_bearing_configuration(self) -> None:
        safe = {
            "organization_id": "org_test",
            "installation_id": "inst_test",
            "control_plane_url": "https://control.example.invalid",
            "data_plane_url": "https://data.example.invalid",
            "aws_region": "sa-east-1",
            "mtls": {
                "certificate_path": "certificate.crt",
                "private_key_path": "identity.key",
                "ca_bundle_path": "ca.pem",
            },
            "sources": {
                "lojas_sp_sqlserver": {
                    "host": "db.internal",
                    "database": "ERP",
                    "driver": "ODBC",
                    "batch_size": 10,
                }
            },
        }
        with self.assertRaises(ValueError):
            ServiceSettings.from_mapping(safe | {"password": "forbidden"})

    def test_reads_configuration_without_secret(self) -> None:
        safe = {
            "organization_id": "org_test",
            "installation_id": "inst_test",
            "control_plane_url": "https://control.example.invalid/",
            "data_plane_url": "https://data.example.invalid/",
            "aws_region": "sa-east-1",
            "mtls": {
                "certificate_path": "certificate.crt",
                "private_key_path": "identity.key",
                "ca_bundle_path": "ca.pem",
            },
            "sources": {
                "lojas_sp_sqlserver": {
                    "host": "db.internal",
                    "database": "ERP",
                    "driver": "ODBC",
                    "batch_size": 10,
                }
            },
        }
        settings = ServiceSettings.from_mapping(safe)
        self.assertEqual(settings.organization_id, "org_test")
        self.assertEqual(settings.control_plane_url, "https://control.example.invalid")
