"""Tests for CalendarAssistant's error handling and its not-found semantics."""

import json
from datetime import date
from unittest import mock

import pytest
import responses

from helpers import CALENDAR_DETAILS_URL, CALENDAR_RANGE_URL
from inmydata.CalendarAssistant import CalendarPeriodType
from inmydata.exceptions import (
    InmydataAPIError,
    InmydataAccessDeniedError,
    InmydataAuthenticationError,
    InmydataNotFoundError,
    InmydataResponseError,
    InmydataServerError,
)

ERROR_STATUSES = [
    (401, InmydataAuthenticationError),
    (403, InmydataAccessDeniedError),
    (404, InmydataNotFoundError),
    (500, InmydataServerError),
]

DETAILS_BODY = json.dumps(
    {
        "value": {
            "dateDetails": {
                "year": 2026,
                "month": 9,
                "week": 36,
                "quarter": 3,
                "yearseq": 1,
                "monthseq": 9,
                "weekseq": 36,
                "quarterseq": 3,
                "yearid": 2026,
                "monthid": 202609,
                "weekid": 202636,
                "quarterid": 20263,
                "date": "2026-09-01",
            }
        }
    }
)


@responses.activate
def test_period_range_returns_the_dates(calendar):
    body = json.dumps({"value": {"startDate": "2026-09-01", "endDate": "2026-09-30"}})
    responses.add(responses.POST, CALENDAR_RANGE_URL, body=body, status=200)
    result = calendar.get_calendar_period_date_range(2026, 9, CalendarPeriodType.month)
    assert result is not None
    assert result.StartDate == date(2026, 9, 1)
    assert result.EndDate == date(2026, 9, 30)


@responses.activate
def test_period_range_null_value_still_returns_none(calendar):
    """A null value is the legitimate not-found case, e.g. a period in a future year."""
    responses.add(
        responses.POST, CALENDAR_RANGE_URL, body=json.dumps({"value": None}), status=200
    )
    assert calendar.get_calendar_period_date_range(2099, 9, CalendarPeriodType.month) is None


@responses.activate
@pytest.mark.parametrize("status,expected", ERROR_STATUSES)
def test_period_range_raises_the_typed_exception(calendar, status, expected):
    responses.add(responses.POST, CALENDAR_RANGE_URL, body="failed", status=status)
    with pytest.raises(expected) as excinfo:
        calendar.get_calendar_period_date_range(2026, 9, CalendarPeriodType.month)
    assert excinfo.value.status_code == status


@responses.activate
def test_period_range_empty_body_raises_response_error(calendar):
    """0.0.18 silently returned None for a 200 with no body."""
    responses.add(responses.POST, CALENDAR_RANGE_URL, body="", status=200)
    with pytest.raises(InmydataResponseError):
        calendar.get_calendar_period_date_range(2026, 9, CalendarPeriodType.month)


@responses.activate
def test_period_range_undecodable_body_raises_response_error(calendar):
    responses.add(responses.POST, CALENDAR_RANGE_URL, body="not json", status=200)
    with pytest.raises(InmydataResponseError):
        calendar.get_calendar_period_date_range(2026, 9, CalendarPeriodType.month)


@responses.activate
def test_financial_periods_returns_the_details(calendar):
    responses.add(responses.POST, CALENDAR_DETAILS_URL, body=DETAILS_BODY, status=200)
    periods = calendar.get_financial_periods(date(2026, 9, 1))
    assert (periods.year, periods.month, periods.week, periods.quarter) == (2026, 9, 36, 3)


@responses.activate
@pytest.mark.parametrize("status,expected", ERROR_STATUSES)
def test_financial_periods_raises_the_typed_exception(calendar, status, expected):
    """0.0.18 turned every one of these into 'Calendar details not found'."""
    responses.add(responses.POST, CALENDAR_DETAILS_URL, body="failed", status=status)
    with pytest.raises(expected):
        calendar.get_financial_periods(date(2026, 9, 1))


@responses.activate
@pytest.mark.parametrize(
    "method",
    ["get_week_number", "get_financial_year", "get_quarter", "get_month"],
)
def test_every_details_caller_surfaces_auth_failure(calendar, method):
    responses.add(responses.POST, CALENDAR_DETAILS_URL, body="expired", status=401)
    with pytest.raises(InmydataAuthenticationError):
        getattr(calendar, method)(date(2026, 9, 1))


@responses.activate
def test_details_null_value_keeps_the_not_found_value_error(calendar):
    responses.add(
        responses.POST, CALENDAR_DETAILS_URL, body=json.dumps({"value": None}), status=200
    )
    with pytest.raises(ValueError, match="Calendar details not found"):
        calendar.get_financial_periods(date(2026, 9, 1))


@responses.activate
def test_details_malformed_value_raises_response_error(calendar):
    responses.add(
        responses.POST,
        CALENDAR_DETAILS_URL,
        body=json.dumps({"value": {"dateDetails": {"year": 2026}}}),
        status=200,
    )
    with pytest.raises(InmydataResponseError):
        calendar.get_financial_periods(date(2026, 9, 1))


@responses.activate
def test_details_undecodable_body_raises_response_error(calendar):
    responses.add(responses.POST, CALENDAR_DETAILS_URL, body="not json", status=200)
    with pytest.raises(InmydataResponseError):
        calendar.get_financial_periods(date(2026, 9, 1))


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_calendar_period_date_range(2026, 9, CalendarPeriodType.month),
        lambda c: c.get_financial_periods(date(2026, 9, 1)),
    ],
)
def test_every_request_passes_a_timeout(calendar, call):
    with mock.patch("inmydata.CalendarAssistant.requests.post") as post:
        post.return_value = mock.Mock(status_code=500, text="boom")
        with pytest.raises(InmydataAPIError):
            call(calendar)
    assert post.call_args.kwargs["timeout"] is not None


def test_timeout_can_be_overridden_per_assistant():
    from inmydata.CalendarAssistant import CalendarAssistant
    from inmydata._http import DEFAULT_TIMEOUT

    default = CalendarAssistant(tenant="t", calendar_name="c", server="s", api_key="k")
    assert default.timeout == DEFAULT_TIMEOUT
    custom = CalendarAssistant(
        tenant="t", calendar_name="c", server="s", api_key="k", timeout=5
    )
    assert custom.timeout == 5
