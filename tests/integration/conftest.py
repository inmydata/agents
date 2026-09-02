"""Configuration for the integration tests, which talk to a real inmydata platform.

These tests are skipped unless you pass --integration, so an ordinary `pytest` run
stays offline and needs no credentials. That flag, and --include-write-tests, are
declared in tests/conftest.py, because pytest parses arguments before it loads nested
conftest files.

Which platform they talk to comes from environment variables, read from a .env file
in the repository root if one is present. INMYDATA_ENV selects a profile, and each
profile has its own base URL and API key, so live and test credentials never have to
be swapped in and out of the same variable:

    INMYDATA_ENV=test                 # or live; defaults to test
    INMYDATA_TEST_BASE_URL=https://test.test-inmydata.com
    INMYDATA_TEST_API_KEY=...
    INMYDATA_LIVE_BASE_URL=https://demo.inmydata.com
    INMYDATA_LIVE_API_KEY=...

The default is deliberately `test`, so forgetting to set INMYDATA_ENV cannot send a
test run at production.

A note on the base URL. The SDK does not accept one: every driver builds its URLs as
`https://{tenant}.{server}/api/developer/v1/ai/...` from the two constructor
arguments. So a base URL given here is split at the first dot of its host, and the
halves are passed as `tenant` and `server`. For https://test.test-inmydata.com that
means tenant="test", server="test-inmydata.com", which reassembles to the host you
asked for. The platform takes the real tenant from the imd_tenant claim on the API
key rather than from the hostname, so the tenant half being a routing artefact rather
than a tenant name does not matter to the server.

Use test.test-inmydata.com for test and demo.inmydata.com for live. Both are tenant
subdomains, the shape the SDK is built for, and both serve these routes. Do not use
api.inmydata.com: it is an AWS API Gateway fronting the OData Lambda, expects
SigV4-signed requests, and cannot serve the SDK. See TESTING.md.
"""

import os
from urllib.parse import urlparse

import pytest

from inmydata.CalendarAssistant import CalendarAssistant
from inmydata.StructuredData import StructuredDataDriver

# Load .env if python-dotenv is installed, so a plain `pytest --integration` in a
# terminal picks up the same file VS Code uses. Absent, real environment variables
# still work.
try:
    from dotenv import load_dotenv

    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_dotenv(os.path.join(_repo_root, ".env"))
except ImportError:  # pragma: no cover - dotenv is a convenience, not a requirement
    pass


class Profile:
    """The resolved settings for one environment.

    Attributes:
        name: The profile name, "test" or "live".
        base_url: The base URL as configured, for error messages.
        tenant: The first label of the host, passed to the drivers.
        server: The rest of the host, passed to the drivers.
        api_key: The API key for this environment.
        subject: The subject to query in the data tests.
        calendar: The calendar name for the CalendarAssistant tests.
    """

    def __init__(self, name, base_url, tenant, server, api_key, subject, calendar):
        self.name = name
        self.base_url = base_url
        self.tenant = tenant
        self.server = server
        self.api_key = api_key
        self.subject = subject
        self.calendar = calendar

    @property
    def host(self):
        return f"{self.tenant}.{self.server}"


def _split_host(base_url: str):
    """Splits a base URL into the tenant and server halves the SDK expects.

    Args:
        base_url: A URL such as https://test.test-inmydata.com. A bare host without a
            scheme is accepted too.

    Returns:
        tuple[str, str]: The first host label, and everything after the first dot.

    Raises:
        ValueError: If the URL has no host, carries a path, or its host has no dot,
            since none of those can be expressed as tenant + "." + server.
    """
    candidate = base_url if "//" in base_url else "https://" + base_url
    parsed = urlparse(candidate)
    host = parsed.hostname
    if not host:
        raise ValueError(f"No host found in base URL {base_url!r}.")
    if parsed.path not in ("", "/"):
        raise ValueError(
            f"Base URL {base_url!r} has a path. The SDK always appends "
            f"/api/developer/v1/ai/..., so give the host only."
        )
    if parsed.port:
        raise ValueError(
            f"Base URL {base_url!r} has a port. The SDK builds its URLs by string "
            f"concatenation and cannot express one."
        )
    if "." not in host:
        raise ValueError(
            f"Host {host!r} has no dot. The SDK builds tenant + '.' + server, so a "
            f"single-label host cannot be expressed."
        )
    tenant, server = host.split(".", 1)
    return tenant, server


@pytest.fixture(scope="session")
def profile() -> Profile:
    """Resolves the environment to test against, skipping if it is not configured."""
    name = os.environ.get("INMYDATA_ENV", "test").strip().lower()
    if name not in ("test", "live"):
        pytest.fail(f"INMYDATA_ENV must be 'test' or 'live', not {name!r}.")

    prefix = f"INMYDATA_{name.upper()}"
    base_url = os.environ.get(f"{prefix}_BASE_URL", "").strip()
    api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()

    missing = [
        var
        for var, value in ((f"{prefix}_BASE_URL", base_url), (f"{prefix}_API_KEY", api_key))
        if not value
    ]
    if missing:
        pytest.skip(
            f"{name} environment is not configured: {', '.join(missing)} not set. "
            f"Copy .env.example to .env and fill it in; see TESTING.md."
        )

    try:
        tenant, server = _split_host(base_url)
    except ValueError as e:
        pytest.fail(f"{prefix}_BASE_URL is unusable: {e}")

    return Profile(
        name=name,
        base_url=base_url,
        tenant=os.environ.get(f"{prefix}_TENANT", "").strip() or tenant,
        server=os.environ.get(f"{prefix}_SERVER", "").strip() or server,
        api_key=api_key,
        subject=os.environ.get(f"{prefix}_SUBJECT", "").strip(),
        calendar=os.environ.get(f"{prefix}_CALENDAR", "").strip(),
    )


@pytest.fixture(scope="session")
def announce_target(profile, request):
    """Prints which platform is being hit, once, so a run is never ambiguous.

    Never prints the API key, only its length, which is enough to tell a populated
    value from an empty or truncated one.
    """
    reporter = request.config.pluginmanager.get_plugin("terminalreporter")
    if reporter:
        reporter.write_line("")
        reporter.write_line(
            f"integration target: {profile.host}  (INMYDATA_ENV={profile.name}, "
            f"api key {len(profile.api_key)} chars)",
            bold=True,
        )
    return profile


@pytest.fixture
def live_driver(profile, announce_target) -> StructuredDataDriver:
    """A StructuredDataDriver pointed at the configured platform."""
    return StructuredDataDriver(
        tenant=profile.tenant,
        server=profile.server,
        api_key=profile.api_key,
        timeout=(10, 120),
    )


@pytest.fixture
def bad_key_driver(profile, announce_target) -> StructuredDataDriver:
    """A driver with a deliberately invalid key, to prove the platform rejects it."""
    return StructuredDataDriver(
        tenant=profile.tenant,
        server=profile.server,
        api_key="not-a-valid-api-key",
        timeout=(10, 60),
    )


@pytest.fixture
def live_calendar(profile, announce_target) -> CalendarAssistant:
    """A CalendarAssistant pointed at the configured platform."""
    if not profile.calendar:
        pytest.skip(
            f"INMYDATA_{profile.name.upper()}_CALENDAR is not set, so there is no "
            f"calendar to query."
        )
    return CalendarAssistant(
        tenant=profile.tenant,
        server=profile.server,
        calendar_name=profile.calendar,
        api_key=profile.api_key,
        timeout=(10, 120),
    )


@pytest.fixture
def subject(profile) -> str:
    """The subject to query, skipping if none is configured."""
    if not profile.subject:
        pytest.skip(
            f"INMYDATA_{profile.name.upper()}_SUBJECT is not set, so there is no "
            f"subject to query. Run the schema test first to see what is available."
        )
    return profile.subject
