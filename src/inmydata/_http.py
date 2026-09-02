"""Shared HTTP defaults for the inmydata SDK drivers.

Internal module. Kept separate from the drivers so that CalendarAssistant does not
have to import StructuredData, and its pandas dependency, to share a constant.
"""

from typing import Any, Tuple

DEFAULT_TIMEOUT: Tuple[float, float] = (10, 300)
"""Default (connect, read) timeout in seconds for requests to the inmydata platform.

Without a timeout a platform that accepts the connection but never responds hangs
the calling thread indefinitely. Override per driver with the `timeout` argument.
"""


def unwrap_value(payload: Any) -> Any:
    """Returns the payload the platform actually sent, envelope or not.

    The developer API returns its result at the top level: /ai/data answers
    {"noRows": ..., "csvDataString": ...} directly, and the other endpoints behave
    the same way. Some responses have historically been wrapped in a {"value": ...}
    envelope, and get_schema has always tolerated both, so this keeps accepting
    either rather than betting on one.

    An explicit {"value": null} is passed through as None, because that is how the
    calendar endpoints say "not defined", which is a legitimate answer rather than a
    shape the SDK failed to understand.

    Args:
        payload: The decoded response body.

    Returns:
        The contents of the "value" key when the body is a dict carrying one,
        otherwise the body unchanged.
    """
    if isinstance(payload, dict) and "value" in payload:
        return payload["value"]
    return payload
