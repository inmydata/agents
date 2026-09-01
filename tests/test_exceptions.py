"""Unit tests for the typed exceptions and the raise_for_status status table."""

import pytest

from inmydata.exceptions import (
    InmydataAPIError,
    InmydataAccessDeniedError,
    InmydataAuthenticationError,
    InmydataNotFoundError,
    InmydataResponseError,
    InmydataServerError,
    raise_for_status,
)

URL = "https://testtenant.inmydata.test/api/developer/v1/ai/data"


@pytest.mark.parametrize("status", [200, 201, 204, 299])
def test_success_statuses_do_not_raise(status):
    assert raise_for_status(status, "", URL) is None


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, InmydataAuthenticationError),
        (403, InmydataAccessDeniedError),
        (404, InmydataNotFoundError),
        (500, InmydataServerError),
        (502, InmydataServerError),
        (503, InmydataServerError),
        (400, InmydataAPIError),
        (429, InmydataAPIError),
        (302, InmydataAPIError),
    ],
)
def test_status_maps_to_exception(status, expected):
    with pytest.raises(expected) as excinfo:
        raise_for_status(status, "body", URL)
    assert excinfo.value.status_code == status
    # The specific classes must not be satisfied by a bare base-class raise.
    assert type(excinfo.value) is expected


def test_every_error_is_an_api_error():
    for status in (401, 403, 404, 500, 400):
        with pytest.raises(InmydataAPIError):
            raise_for_status(status, "body", URL)


def test_message_carries_url_status_and_body():
    with pytest.raises(InmydataAPIError) as excinfo:
        raise_for_status(403, "subject is not API enabled", URL)
    message = str(excinfo.value)
    assert URL in message
    assert "403" in message
    assert "subject is not API enabled" in message


def test_body_is_truncated_to_500_characters():
    with pytest.raises(InmydataServerError) as excinfo:
        raise_for_status(500, "x" * 5000, URL)
    message = str(excinfo.value)
    assert message.count("x") == 500


def test_response_error_is_also_a_value_error():
    """0.0.18 raised bare ValueError for a malformed 200; those handlers must keep working."""
    assert issubclass(InmydataResponseError, ValueError)
    with pytest.raises(ValueError):
        raise InmydataResponseError("malformed")


def test_status_code_defaults_to_none():
    assert InmydataAPIError("no status").status_code is None


def test_exceptions_are_importable_from_the_package_root():
    import inmydata

    assert inmydata.InmydataAccessDeniedError is InmydataAccessDeniedError
    assert inmydata.raise_for_status is raise_for_status
