"""Typed exceptions for the inmydata SDK.

Raised by StructuredDataDriver and CalendarAssistant when the inmydata platform
returns a non-success status or a response the SDK cannot interpret. Before
0.0.19 these conditions returned None or an error string, which callers could
not distinguish from legitimate empty results.
"""


class InmydataAPIError(Exception):
    """Base class for errors returned by the inmydata platform API.

    Attributes:
        status_code: The HTTP status code, or None for a malformed 200 response.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class InmydataAuthenticationError(InmydataAPIError):
    """The request was not authenticated (HTTP 401): missing, expired or invalid token."""


class InmydataAccessDeniedError(InmydataAPIError):
    """The request was authenticated but refused (HTTP 403).

    The common cause for the data endpoints is a subject that is not flagged
    API-enabled in tenant administration.
    """


class InmydataNotFoundError(InmydataAPIError):
    """The requested resource does not exist (HTTP 404)."""


class InmydataServerError(InmydataAPIError):
    """The platform failed to process the request (HTTP 5xx)."""


class InmydataResponseError(InmydataAPIError, ValueError):
    """The platform returned success but the response body was not interpretable.

    Also inherits ValueError so that the `except ValueError` blocks written
    against the 0.0.18 malformed-response paths keep catching this condition.
    """


def raise_for_status(status_code: int, text: str, url: str) -> None:
    """Raise the typed exception for a non-success status code.

    Args:
        status_code: The HTTP status code of the response.
        text: The response body; truncated to 500 characters in the message.
        url: The request URL, included in the message for diagnosis.

    Raises:
        InmydataAuthenticationError: On 401.
        InmydataAccessDeniedError: On 403.
        InmydataNotFoundError: On 404.
        InmydataServerError: On any 5xx.
        InmydataAPIError: On any other non-2xx status.
    """
    if 200 <= status_code < 300:
        return
    message = f"{url} returned {status_code}: {text[:500]}"
    if status_code == 401:
        raise InmydataAuthenticationError(message, status_code)
    if status_code == 403:
        raise InmydataAccessDeniedError(message, status_code)
    if status_code == 404:
        raise InmydataNotFoundError(message, status_code)
    if status_code >= 500:
        raise InmydataServerError(message, status_code)
    raise InmydataAPIError(message, status_code)
