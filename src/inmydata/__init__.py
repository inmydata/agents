"""Simple API access to the inmydata platform.

The typed exceptions raised by the drivers are re-exported here so that callers
have one import path for them; they remain importable from `inmydata.exceptions`.
"""

from .exceptions import (
    InmydataAPIError,
    InmydataAccessDeniedError,
    InmydataAuthenticationError,
    InmydataNotFoundError,
    InmydataResponseError,
    InmydataServerError,
    raise_for_status,
)

__all__ = [
    "InmydataAPIError",
    "InmydataAccessDeniedError",
    "InmydataAuthenticationError",
    "InmydataNotFoundError",
    "InmydataResponseError",
    "InmydataServerError",
    "raise_for_status",
]
