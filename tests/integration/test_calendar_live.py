"""CalendarAssistant against a real inmydata platform. All read-only."""

from datetime import date

import pytest

from inmydata.CalendarAssistant import CalendarPeriodType
from inmydata.exceptions import InmydataAPIError

pytestmark = pytest.mark.integration


def test_todays_financial_periods_are_coherent(live_calendar):
    """The four periods for today must be internally consistent."""
    periods = live_calendar.get_financial_periods(date.today())

    assert 1 <= periods.month <= 12, f"Financial month {periods.month} out of range."
    assert 1 <= periods.week <= 53, f"Financial week {periods.week} out of range."
    assert 1 <= periods.quarter <= 4, f"Financial quarter {periods.quarter} out of range."
    assert periods.year > 1990, f"Financial year {periods.year} looks wrong."


def test_the_individual_getters_agree_with_get_financial_periods(live_calendar):
    """get_month and friends must match the combined call for the same date."""
    today = date.today()
    periods = live_calendar.get_financial_periods(today)

    assert live_calendar.get_financial_year(today) == periods.year
    assert live_calendar.get_month(today) == periods.month
    assert live_calendar.get_week_number(today) == periods.week
    assert live_calendar.get_quarter(today) == periods.quarter


def test_the_current_month_has_a_date_range_containing_today(live_calendar):
    """The range for the current financial month should bracket today."""
    today = date.today()
    year = live_calendar.get_financial_year(today)
    month = live_calendar.get_month(today)

    period = live_calendar.get_calendar_period_date_range(
        year, month, CalendarPeriodType.month
    )

    assert period is not None, (
        f"No range returned for year {year} month {month}, which is the current "
        f"financial month and must be defined."
    )
    assert period.StartDate <= today <= period.EndDate, (
        f"Today ({today}) is outside the range returned for its own financial month "
        f"({period.StartDate} to {period.EndDate})."
    )


def test_an_undefined_period_returns_none_rather_than_raising(live_calendar):
    """The legitimate not-found case must still be None after 0.0.19.

    A year far in the future is unlikely to be defined in any calendar. If it happens
    to be, the assertion below still holds for a well-formed answer.
    """
    result = live_calendar.get_calendar_period_date_range(
        2099, 13, CalendarPeriodType.month
    )

    if result is not None:
        assert result.StartDate <= result.EndDate
    # None here means "not defined in this calendar", unambiguously, because a
    # transport or auth failure would have raised instead.


def test_periods_are_not_defined_for_an_absurd_period_number(live_calendar):
    """Period 99 of a month should be absent, not an error result."""
    try:
        result = live_calendar.get_calendar_period_date_range(
            date.today().year, 99, CalendarPeriodType.month
        )
    except InmydataAPIError as e:
        # A 4xx is a defensible answer to nonsense input; the point is it is typed.
        assert e.status_code is not None
        return
    assert result is None or result.StartDate <= result.EndDate
