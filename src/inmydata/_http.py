"""Shared HTTP defaults for the inmydata SDK drivers.

Internal module. Kept separate from the drivers so that CalendarAssistant does not
have to import StructuredData, and its pandas dependency, to share a constant.
"""

from typing import Tuple

DEFAULT_TIMEOUT: Tuple[float, float] = (10, 300)
"""Default (connect, read) timeout in seconds for requests to the inmydata platform.

Without a timeout a platform that accepts the connection but never responds hangs
the calling thread indefinitely. Override per driver with the `timeout` argument.
"""
