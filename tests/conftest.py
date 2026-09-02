"""Shared pytest configuration and unit-test fixtures.

The command-line options live here rather than in tests/integration/conftest.py
because pytest parses arguments before it loads nested conftest files, so
pytest_addoption is only honoured in the initial conftest.

The constants and response builders live in helpers.py so the test modules can import
them by name; see the note at the top of that file.
"""

import pytest

from helpers import SERVER, TENANT
from inmydata.CalendarAssistant import CalendarAssistant
from inmydata.StructuredData import StructuredDataDriver


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run the integration tests against a real inmydata platform.",
    )
    parser.addoption(
        "--include-write-tests",
        action="store_true",
        default=False,
        help=(
            "Also run integration tests that create something on the platform, "
            "currently only get_chart, which registers a visualisation."
        ),
    )


def pytest_collection_modifyitems(config, items):
    """Skips anything marked `integration` unless --integration was passed."""
    if config.getoption("--integration"):
        return
    skip = pytest.mark.skip(reason="needs --integration (talks to a real platform)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def driver():
    """A StructuredDataDriver pointed at the mocked host, with a fixed API key."""
    return StructuredDataDriver(tenant=TENANT, server=SERVER, api_key="test-key")


@pytest.fixture
def calendar():
    """A CalendarAssistant pointed at the mocked host, with a fixed API key."""
    return CalendarAssistant(
        tenant=TENANT, calendar_name="Default", server=SERVER, api_key="test-key"
    )
