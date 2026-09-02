"""Tests for StructuredDataDriver's error handling, empty results and filter semantics."""

import json
from unittest import mock

import pandas as pd
import pytest
import responses

from helpers import CHART_URL, COLUMN_TYPES, DATA_URL, SCHEMA_URL, data_response
from inmydata.StructuredData import (
    AIDataFilter,
    AIDataSimpleFilter,
    ChartType,
    ConditionOperator,
    LogicalOperator,
)
from inmydata.exceptions import (
    InmydataAPIError,
    InmydataAccessDeniedError,
    InmydataAuthenticationError,
    InmydataNotFoundError,
    InmydataResponseError,
    InmydataServerError,
)

CSV = "Customer,Sales Value\nAcme,100.5\nUmbrella,200.25\n"

ERROR_STATUSES = [
    (401, InmydataAuthenticationError),
    (403, InmydataAccessDeniedError),
    (404, InmydataNotFoundError),
    (500, InmydataServerError),
]


def _filters():
    return [
        AIDataFilter(
            Field="Customer",
            ConditionOperator=ConditionOperator.Equals,
            LogicalOperator=LogicalOperator.And,
            Value="Acme",
            StartGroup=0,
            EndGroup=0,
            CaseInsensitive=False,
        )
    ]


@responses.activate
def test_get_data_returns_the_decoded_frame(driver):
    responses.add(responses.POST, DATA_URL, body=data_response(CSV, no_rows=2), status=200)
    frame = driver.get_data("Sales", ["Customer", "Sales Value"], _filters())
    assert list(frame.columns) == ["Customer", "Sales Value"]
    assert len(frame) == 2
    assert frame["Customer"].tolist() == ["Acme", "Umbrella"]
    assert frame["Sales Value"].tolist() == [100.5, 200.25]


@responses.activate
def test_zero_rows_returns_an_empty_frame_not_none(driver):
    responses.add(responses.POST, DATA_URL, body=data_response(None, no_rows=0), status=200)
    frame = driver.get_data("Sales", list(COLUMN_TYPES), _filters())
    assert frame is not None
    assert isinstance(frame, pd.DataFrame)
    assert frame.empty
    assert list(frame.columns) == list(COLUMN_TYPES)


@responses.activate
def test_zero_rows_frame_carries_the_declared_dtypes(driver):
    """An all-object empty frame would behave differently from a populated one."""
    responses.add(responses.POST, DATA_URL, body=data_response(None, no_rows=0), status=200)
    frame = driver.get_data("Sales", list(COLUMN_TYPES), _filters())
    dtypes = {name: str(dtype) for name, dtype in frame.dtypes.items()}
    assert dtypes == {
        "Customer": "object",
        "Sales Value": "float64",
        "Financial Year": "int64",
        "Date": "datetime64[ns]",
        # System.Date is the platform's date-only marker, not a CLR type name.
        "Delivery Date": "datetime64[ns]",
        "Order Count": "int64",
        "Is Active": "bool",
    }
    # The point of the dtypes: numeric aggregation works on the empty frame.
    assert frame["Sales Value"].sum() == 0


@responses.activate
def test_zero_rows_frame_preserves_the_requested_column_order(driver):
    """The platform keys columnNamesandTypes on the requested fields, in request order."""
    columns = {"Region": "System.String", "Sales Value": "System.Decimal", "Year": "System.Int32"}
    responses.add(
        responses.POST,
        DATA_URL,
        body=data_response(None, no_rows=0, columns=columns),
        status=200,
    )
    frame = driver.get_data("Sales", ["Region", "Sales Value", "Year"], _filters())
    assert list(frame.columns) == ["Region", "Sales Value", "Year"]


@responses.activate
def test_unrecognised_column_type_falls_back_to_object(driver):
    columns = {"Odd": "System.Guid", "Name": "System.String"}
    responses.add(
        responses.POST,
        DATA_URL,
        body=data_response(None, no_rows=0, columns=columns),
        status=200,
    )
    frame = driver.get_data("Sales", ["Odd", "Name"], _filters())
    assert [str(d) for d in frame.dtypes] == ["object", "object"]


@responses.activate
@pytest.mark.parametrize("status,expected", ERROR_STATUSES)
def test_get_data_raises_the_typed_exception(driver, status, expected):
    responses.add(responses.POST, DATA_URL, body="denied", status=status)
    with pytest.raises(expected) as excinfo:
        driver.get_data("Sales", ["Customer"], _filters())
    assert excinfo.value.status_code == status


@responses.activate
def test_get_data_403_is_distinguishable_from_an_empty_result(driver):
    """The distinction the ingestion job depends on: no rows versus not allowed."""
    responses.add(responses.POST, DATA_URL, body="not API enabled", status=403)
    with pytest.raises(InmydataAccessDeniedError):
        driver.get_data("Sales", ["Customer"], _filters())


@responses.activate
def test_get_data_undecodable_body_raises_response_error(driver):
    responses.add(responses.POST, DATA_URL, body="<html>not json</html>", status=200)
    with pytest.raises(InmydataResponseError):
        driver.get_data("Sales", ["Customer"], _filters())


@responses.activate
def test_get_data_missing_value_raises_response_error(driver):
    responses.add(responses.POST, DATA_URL, body=json.dumps({"other": 1}), status=200)
    with pytest.raises(InmydataResponseError):
        driver.get_data("Sales", ["Customer"], _filters())


@responses.activate
def test_get_data_response_error_still_caught_as_value_error(driver):
    """0.0.18 raised bare ValueError here; existing handlers must keep working."""
    responses.add(responses.POST, DATA_URL, body=json.dumps({"value": None}), status=200)
    with pytest.raises(ValueError):
        driver.get_data("Sales", ["Customer"], _filters())


@responses.activate
def test_get_data_unexpected_value_shape_raises_response_error(driver):
    responses.add(
        responses.POST, DATA_URL, body=json.dumps({"value": {"unexpected": True}}), status=200
    )
    with pytest.raises(InmydataResponseError):
        driver.get_data("Sales", ["Customer"], _filters())


@responses.activate
@pytest.mark.parametrize("status,expected", ERROR_STATUSES)
def test_get_schema_raises_instead_of_returning_error_text(driver, status, expected):
    responses.add(responses.POST, SCHEMA_URL, body="failed", status=status)
    with pytest.raises(expected):
        driver.get_schema("tests")


@responses.activate
def test_get_schema_success_returns_the_json_string(driver):
    body = json.dumps(
        {
            "value": {
                "subjects": [
                    {
                        "name": "Sales",
                        "factFieldTypes": {"Customer": {}, "Date": {}},
                        "metricFieldTypes": {"Sales Value": {}},
                    }
                ]
            }
        }
    )
    responses.add(responses.POST, SCHEMA_URL, body=body, status=200)
    schema = driver.get_schema("tests")
    assert isinstance(schema, str)
    parsed = json.loads(schema)
    assert parsed["subjectsCount"] == 1
    assert parsed["source"] == "tests"
    assert parsed["subjects"][0]["numDimensions"] == 2
    assert parsed["subjects"][0]["numMetrics"] == 1


@responses.activate
def test_get_schema_undecodable_body_raises_response_error(driver):
    responses.add(responses.POST, SCHEMA_URL, body="not json", status=200)
    with pytest.raises(InmydataResponseError):
        driver.get_schema("tests")


@responses.activate
@pytest.mark.parametrize("status,expected", ERROR_STATUSES)
def test_get_chart_raises_the_typed_exception(driver, status, expected):
    responses.add(responses.POST, CHART_URL, body="failed", status=status)
    with pytest.raises(expected):
        driver.get_chart("Sales", ["Customer"], [], ["Sales Value"], [], ChartType.Bar, "Caption")


@responses.activate
def test_get_chart_success_returns_the_visualisation_id(driver):
    body = json.dumps({"value": {"visualisationID": "vis-123"}})
    responses.add(responses.POST, CHART_URL, body=body, status=200)
    result = driver.get_chart(
        "Sales", ["Customer"], [], ["Sales Value"], [], ChartType.Bar, "Caption"
    )
    assert result == "vis-123"


@responses.activate
def test_get_chart_works_without_the_optional_topn_argument(driver):
    """0.0.18 raised AttributeError when TopNUsed was left at its documented default."""
    body = json.dumps({"value": {"visualisationID": "vis-456"}})
    responses.add(responses.POST, CHART_URL, body=body, status=200)
    assert (
        driver.get_chart("Sales", ["Customer"], [], ["Sales Value"], [], ChartType.Bar, "Caption")
        == "vis-456"
    )


@pytest.mark.parametrize(
    "case_sensitive,expected_case_insensitive",
    [(True, False), (False, True), (None, False)],
)
def test_get_data_simple_case_sensitivity_is_not_inverted(
    driver, case_sensitive, expected_case_insensitive
):
    """caseSensitive=True must produce CaseInsensitive=False; None means the documented default."""
    with mock.patch.object(driver, "get_data", return_value=pd.DataFrame()) as get_data:
        driver.get_data_simple(
            "Sales",
            ["Customer"],
            [AIDataSimpleFilter("Customer", "Acme")],
            caseSensitive=case_sensitive,
        )
    built = get_data.call_args[0][2]
    assert len(built) == 1
    assert built[0].CaseInsensitive is expected_case_insensitive


def test_get_data_simple_defaults_to_case_sensitive(driver):
    with mock.patch.object(driver, "get_data", return_value=pd.DataFrame()) as get_data:
        driver.get_data_simple("Sales", ["Customer"], [AIDataSimpleFilter("Customer", "Acme")])
    assert get_data.call_args[0][2][0].CaseInsensitive is False


@responses.activate
@pytest.mark.parametrize(
    "call",
    [
        lambda d: d.get_data("Sales", ["Customer"], _filters()),
        lambda d: d.get_schema("tests"),
        lambda d: d.get_chart(
            "Sales", ["Customer"], [], ["Sales Value"], [], ChartType.Bar, "Caption"
        ),
    ],
)
def test_every_request_passes_a_timeout(driver, call):
    """Without a timeout a platform that never responds hangs the calling thread."""
    with mock.patch("inmydata.StructuredData.requests.post") as post:
        post.return_value = mock.Mock(status_code=500, text="boom")
        with pytest.raises(InmydataAPIError):
            call(driver)
    assert post.call_args.kwargs["timeout"] is not None


def test_timeout_can_be_overridden_per_driver():
    from inmydata.StructuredData import DEFAULT_TIMEOUT, StructuredDataDriver

    default = StructuredDataDriver(tenant="t", server="s", api_key="k")
    assert default.timeout == DEFAULT_TIMEOUT
    custom = StructuredDataDriver(tenant="t", server="s", api_key="k", timeout=5)
    assert custom.timeout == 5
