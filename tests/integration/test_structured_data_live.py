"""StructuredDataDriver against a real inmydata platform.

Every test here is read-only, except the get_chart one, which registers a
visualisation on the platform and therefore needs --include-write-tests as well as
--integration.
"""

import json

import pandas as pd
import pytest

from inmydata.StructuredData import (
    AIDataSimpleFilter,
    ChartType,
)
from inmydata.exceptions import (
    InmydataAccessDeniedError,
    InmydataAPIError,
    InmydataResponseError,
)

pytestmark = pytest.mark.integration

# A value no real dimension should hold, used to force a zero-row result.
NO_SUCH_VALUE = "__inmydata_sdk_integration_test_no_such_value__"


def _is_zero_row_platform_bug(error):
    """True if this error is the platform failing on a zero-row query.

    AIChatLogic.AIAPIData downloaded the export file from S3 without checking NoRows,
    so a query matching nothing threw "The specified key does not exist". Fixed in
    datapaltd/inmydata#270, but an environment that has not taken that build yet still
    fails, and the two environments surface it differently:

    - test, post-fix build: 500 carrying the S3 message.
    - demo, pre-fix build: bare 405 with an empty body, because the unhandled
      exception is turned into an error route that only serves GET and HEAD. A 405 on
      an endpoint that answers the same POST correctly for a non-empty result is not
      something the SDK can cause, so it is safe to read as this bug.

    Confirmed on demo by filtering on a real value ("Dr. Aaliyah Andrews" returned one
    row) versus a value matching nothing, which 405s. Filters themselves work.
    """
    if "specified key does not exist" in str(error).lower():
        return True
    return getattr(error, "status_code", None) == 405


def test_get_schema_returns_usable_subjects(live_driver, request):
    """Reads the schema and reports what is available, which you need for .env."""
    schema = json.loads(live_driver.get_schema("integration test, schema"))

    assert schema["schemaVersion"] == 1
    assert isinstance(schema["subjects"], list)

    reporter = request.config.pluginmanager.get_plugin("terminalreporter")
    if reporter:
        reporter.write_line("")
        reporter.write_line(f"  API-enabled subjects ({schema['subjectsCount']}):")
        for subj in schema["subjects"]:
            reporter.write_line(
                f"    {subj.get('name')!r}  "
                f"{subj.get('numDimensions')} dimensions, {subj.get('numMetrics')} metrics"
            )
        if not schema["subjects"]:
            reporter.write_line(
                "    none. Flag a subject as API-enabled in tenant administration, "
                "or the data tests cannot run."
            )

    assert schema["subjectsCount"] > 0, (
        "No subjects are flagged API-enabled for this API key, so no data test can "
        "succeed. This is a tenant administration setting, not an SDK problem."
    )


def test_a_subject_can_be_queried(live_driver, subject):
    """The core round trip: request fields, get a DataFrame back."""
    schema = json.loads(live_driver.get_schema("integration test, field discovery"))
    match = next((s for s in schema["subjects"] if s.get("name") == subject), None)
    assert match is not None, (
        f"Subject {subject!r} is not in the API-enabled list. Available: "
        f"{[s.get('name') for s in schema['subjects']]}"
    )

    dimension = next(iter(match.get("factFieldTypes") or {}), None)
    metric = next(iter(match.get("metricFieldTypes") or {}), None)
    if not dimension or not metric:
        pytest.skip(f"Subject {subject!r} has no usable dimension/metric pair.")

    frame = live_driver.get_data(subject, [dimension, metric], [])

    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == [dimension, metric], (
        f"Columns came back as {list(frame.columns)}, expected the requested fields "
        f"in request order."
    )


def test_a_filter_matching_nothing_returns_an_empty_frame(live_driver, subject):
    """The 0.0.19 behaviour that matters most, verified against the real platform.

    Before 0.0.19 this returned None, which was indistinguishable from a rejected
    token. It must now be an empty DataFrame carrying the requested columns.
    """
    schema = json.loads(live_driver.get_schema("integration test, empty result"))
    match = next((s for s in schema["subjects"] if s.get("name") == subject), None)
    if match is None:
        pytest.skip(f"Subject {subject!r} is not API-enabled.")

    dimension = next(iter(match.get("factFieldTypes") or {}), None)
    metric = next(iter(match.get("metricFieldTypes") or {}), None)
    if not dimension or not metric:
        pytest.skip(f"Subject {subject!r} has no usable dimension/metric pair.")

    try:
        frame = live_driver.get_data_simple(
            subject,
            [dimension, metric],
            [AIDataSimpleFilter(dimension, NO_SUCH_VALUE)],
        )
    except InmydataAPIError as e:
        if _is_zero_row_platform_bug(e):
            # Platform bug, not an SDK one. AIChatLogic.AIAPIData downloads the
            # export file from S3 unconditionally, without checking NoRows, so a
            # query matching nothing writes no file and the download 500s. The
            # SDK cannot return an empty frame until the API can express one.
            # Raising here rather than returning None is still the 0.0.19
            # improvement: 0.0.18 turned this 500 into None, indistinguishable
            # from the empty result it is not.
            pytest.xfail(
                f"Platform fails a zero-row query instead of returning an empty "
                f"result (fixed in inmydata#270, not on this build): {e}"
            )
        raise

    assert frame is not None, "A zero-row result must not be None."
    assert isinstance(frame, pd.DataFrame)
    assert frame.empty, f"Expected no rows for {dimension} == {NO_SUCH_VALUE!r}."
    assert list(frame.columns) == [dimension, metric]


def test_an_unknown_subject_is_refused(live_driver):
    """A subject that is not API-enabled must raise, not return None.

    What it raises depends on the build. 403 is the documented answer, and a 400 or 500
    is defensible for a name the platform cannot resolve at all. The demo build instead
    answers 200 with an AWS Lambda style error envelope carrying a "statusCode" key,
    which the SDK cannot read as data and reports as InmydataResponseError with no
    status code. All three are acceptable; returning None would not be.
    """
    with pytest.raises(InmydataAPIError) as excinfo:
        live_driver.get_data("__inmydata_sdk_no_such_subject__", ["anything"], [])

    error = excinfo.value
    assert error.status_code is not None or isinstance(error, InmydataResponseError), (
        f"An unknown subject must fail with either a status code or a response-shape "
        f"error, got {error!r}"
    )


def test_case_sensitivity_is_not_inverted(live_driver, subject):
    """Checks the 0.0.19 caseSensitive fix against real data.

    Finds a real value, then queries for its case-flipped form. Case-insensitive
    should match at least as many rows as case-sensitive. Skips unless a value with
    letters in it can be found, since the comparison is meaningless otherwise.
    """
    schema = json.loads(live_driver.get_schema("integration test, case sensitivity"))
    match = next((s for s in schema["subjects"] if s.get("name") == subject), None)
    if match is None:
        pytest.skip(f"Subject {subject!r} is not API-enabled.")

    fields = match.get("factFieldTypes") or {}
    dimension = next(
        (
            name
            for name, meta in fields.items()
            if (meta.get("type") if isinstance(meta, dict) else meta) == "System.String"
        ),
        None,
    )
    metric = next(iter(match.get("metricFieldTypes") or {}), None)
    if not dimension or not metric:
        pytest.skip(f"Subject {subject!r} has no string dimension to test case on.")

    sample = live_driver.get_data(subject, [dimension, metric], [])
    if sample.empty:
        pytest.skip(f"{subject!r} returned no rows, so there is no value to flip.")

    values = [v for v in sample[dimension].dropna().astype(str) if v.lower() != v.upper()]
    if not values:
        pytest.skip(f"No values in {dimension!r} contain letters.")
    flipped = values[0].swapcase()

    def query(case_sensitive):
        try:
            return live_driver.get_data_simple(
                subject, [dimension, metric],
                [AIDataSimpleFilter(dimension, flipped)],
                caseSensitive=case_sensitive,
            )
        except InmydataAPIError as e:
            if _is_zero_row_platform_bug(e):
                pytest.xfail(
                    f"Platform returns 500 rather than an empty result when a "
                    f"filter matches no rows, so the case-sensitive half of this "
                    f"comparison cannot be measured: {e}"
                )
            raise

    sensitive = query(True)
    insensitive = query(False)

    assert len(insensitive) >= len(sensitive), (
        f"Case-insensitive matching on {dimension!r}={flipped!r} returned "
        f"{len(insensitive)} rows, fewer than case-sensitive's {len(sensitive)}. "
        f"That is the inversion 0.0.19 fixed reappearing."
    )


def test_get_chart_registers_a_visualisation(live_driver, subject, request):
    """get_chart on the real platform. Creates something, so it is opt-in.

    Also covers the 0.0.19 fix for omitting the optional TopNUsed argument, which
    previously raised AttributeError before any request was sent.
    """
    if not request.config.getoption("--include-write-tests"):
        pytest.skip("needs --include-write-tests (registers a visualisation)")

    schema = json.loads(live_driver.get_schema("integration test, chart"))
    match = next((s for s in schema["subjects"] if s.get("name") == subject), None)
    if match is None:
        pytest.skip(f"Subject {subject!r} is not API-enabled.")

    dimension = next(iter(match.get("factFieldTypes") or {}), None)
    metric = next(iter(match.get("metricFieldTypes") or {}), None)
    if not dimension or not metric:
        pytest.skip(f"Subject {subject!r} has no usable dimension/metric pair.")

    try:
        visualisation_id = live_driver.get_chart(
            subject, [dimension], [], [metric], [], ChartType.Bar,
            "inmydata SDK integration test",
        )
    except InmydataAccessDeniedError as e:
        pytest.skip(f"Chart generation is not permitted for this key: {e}")

    assert visualisation_id, "get_chart returned no visualisation ID."
