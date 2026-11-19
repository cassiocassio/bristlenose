"""Doctor tells Azure's two 404s apart.

Azure answers a missing deployment with ``DeploymentNotFound``, and everything else
it cannot route (a portal or classic URL pasted as the endpoint, an ``http://``
endpoint, a wrong path) with a generic ``404 Resource not found``. Both bodies below
are Azure's own, recorded on 19 Nov 2026. Until then doctor said "Deployment not
found" for every 404 and showed the credentials fix, and because doctor runs before
the preflight on every ``run``, its answer was the one a researcher saw.
"""

from __future__ import annotations

import json

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.doctor import _validate_azure_key, check_api_key
from tests.test_azure_cli_reliability import DEPLOYMENT, azure_server  # noqa: F401

DEPLOYMENT_NOT_FOUND = {"error": {
    "type": "invalid_request_error", "code": "DeploymentNotFound",
    "message": "The API deployment for this resource does not exist. If you created the "
               "deployment within the last 5 minutes, please wait a moment and try again."}}
GENERIC_404 = {"error": {"code": "404", "message": "Resource not found"}}


def _serve(server: dict, status: int, body: object) -> None:
    server["status"] = status
    server["body"] = body if isinstance(body, bytes) else json.dumps(body).encode()


def test_deployment_not_found_keeps_its_sentence(azure_server) -> None:  # noqa: F811
    _serve(azure_server, 404, DEPLOYMENT_NOT_FOUND)
    assert _validate_azure_key(azure_server["endpoint"], "k", DEPLOYMENT, "2024-10-21") == (
        False, f"Deployment '{DEPLOYMENT}' not found")


def test_a_generic_404_is_said_in_azures_words(azure_server) -> None:  # noqa: F811
    _serve(azure_server, 404, GENERIC_404)
    assert _validate_azure_key(azure_server["endpoint"], "k", DEPLOYMENT, "2024-10-21") == (
        False, "HTTP 404: Resource not found")


def test_an_unreadable_404_does_not_name_the_deployment(azure_server) -> None:  # noqa: F811
    _serve(azure_server, 404, b"<html>not json</html>")
    assert _validate_azure_key(azure_server["endpoint"], "k", DEPLOYMENT, "2024-10-21") == (
        False, "HTTP 404")


def test_the_key_never_appears_in_the_404_detail(azure_server) -> None:  # noqa: F811
    _serve(azure_server, 404, {"error": {"code": "404", "message": "no route for key sk-echo-12345678"}})
    valid, detail = _validate_azure_key(azure_server["endpoint"], "sk-echo-12345678", DEPLOYMENT, "2024-10-21")
    assert valid is False and "sk-echo-12345678" not in detail


@pytest.mark.parametrize(
    ("body", "fix_key"),
    [(DEPLOYMENT_NOT_FOUND, "api_key_invalid_azure"), (GENERIC_404, "")],
)
def test_only_a_missing_deployment_gets_the_credentials_fix(azure_server, body, fix_key) -> None:  # noqa: F811
    # The credentials fix lists "Deployment name exists"; a wrong URL must not be sent there.
    _serve(azure_server, 404, body)
    settings = BristlenoseSettings(
        llm_provider="azure", azure_api_key="k",
        azure_endpoint=azure_server["endpoint"], azure_deployment=DEPLOYMENT,
    )
    result = check_api_key(settings)
    assert result.fix_key == fix_key
