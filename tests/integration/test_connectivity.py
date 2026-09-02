"""Reachability and authentication checks against a real inmydata platform.

Run these first. They answer, in order, "is the host right", "does the SDK's route
exist there" and "is my API key accepted" — which between them explain most failures
in the other integration modules.
"""

import socket

import pytest
import requests

from inmydata.exceptions import (
    InmydataAPIError,
    InmydataAccessDeniedError,
    InmydataAuthenticationError,
)

pytestmark = pytest.mark.integration


def test_host_resolves(profile, announce_target):
    """A typo in the base URL shows up here rather than as a confusing timeout."""
    try:
        socket.getaddrinfo(profile.host, 443)
    except socket.gaierror as e:
        pytest.fail(f"{profile.host} does not resolve: {e}")


def test_endpoint_exists_and_requires_authentication(profile, announce_target):
    """An unauthenticated call must be refused, not 404.

    A 401 or 403 proves the route is served here. A 404, or an API Gateway style
    "Missing Authentication Token" body, means the base URL points at something that
    is not the inmydata web application, which is the failure worth catching early.
    """
    url = f"https://{profile.host}/api/developer/v1/ai/getapisubjectlistinfo"
    response = requests.post(url, json={"subject": None}, timeout=(10, 30))

    assert response.status_code in (401, 403), (
        f"{url} returned {response.status_code}, expected 401 or 403 for an "
        f"unauthenticated request. Body: {response.text[:200]!r}"
    )
    assert "Missing Authentication Token" not in response.text, (
        f"{url} answered with API Gateway's 'Missing Authentication Token'. That is "
        f"not the inmydata web application, so this base URL will not serve the SDK."
    )


def test_an_invalid_api_key_is_rejected(bad_key_driver):
    """Proves the 0.0.19 exception mapping works against the real platform.

    Before 0.0.19 this returned None, indistinguishable from an empty result. Either
    401 or 403 is an acceptable answer; the point is that it raises.
    """
    with pytest.raises((InmydataAuthenticationError, InmydataAccessDeniedError)) as excinfo:
        bad_key_driver.get_schema("integration test, invalid key")

    assert excinfo.value.status_code in (401, 403)
    # The message must not contain the credential that was sent.
    assert "not-a-valid-api-key" not in str(excinfo.value)


def test_a_valid_api_key_is_accepted(live_driver):
    """The configured key can reach the schema endpoint.

    Kept separate from the schema content test so that a credential problem is
    distinguishable from a data problem.
    """
    try:
        schema = live_driver.get_schema("integration test, connectivity")
    except InmydataAuthenticationError as e:
        pytest.fail(f"The configured API key was rejected: {e}")
    except InmydataAccessDeniedError as e:
        pytest.fail(
            f"The API key authenticated but access was refused. On the data endpoints "
            f"this usually means no subject is flagged API-enabled: {e}"
        )
    except InmydataAPIError as e:
        pytest.fail(f"The platform refused the request with {e.status_code}: {e}")

    assert isinstance(schema, str) and schema, "get_schema returned an empty result."
