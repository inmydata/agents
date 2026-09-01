"""Shared fixtures and response builders for the inmydata SDK tests."""

import base64
import gzip
import io
import json

import pytest

from inmydata.CalendarAssistant import CalendarAssistant
from inmydata.StructuredData import StructuredDataDriver

TENANT = "testtenant"
SERVER = "inmydata.test"
BASE_URL = f"https://{TENANT}.{SERVER}/api/developer/v1/ai"

DATA_URL = f"{BASE_URL}/data"
CHART_URL = f"{BASE_URL}/chart"
SCHEMA_URL = f"{BASE_URL}/getapisubjectlistinfo"
CALENDAR_RANGE_URL = f"{BASE_URL}/getcalendarperiodrange"
CALENDAR_DETAILS_URL = f"{BASE_URL}/getcalendardetails"

COLUMN_TYPES = {
    "Customer": "System.String",
    "Sales Value": "System.Decimal",
    "Financial Year": "System.Int32",
    "Date": "System.DateTime",
    "Is Active": "System.Boolean",
}


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


def gzip_csv(csv_text: str) -> str:
    """Encodes CSV text the way the platform does: gzip, then standard base64."""
    buff = io.BytesIO()
    with gzip.GzipFile(fileobj=buff, mode="wb") as gz:
        gz.write(csv_text.encode("utf-8"))
    return base64.standard_b64encode(buff.getvalue()).decode("ascii")


def data_response(csv_text: str | None = None, no_rows: int = 0, columns=None) -> str:
    """Builds the JSON body of a successful /ai/data response.

    Args:
        csv_text: The CSV payload, or None for a zero-row response.
        no_rows: The row count the platform reports.
        columns: The column name to declared type map; defaults to COLUMN_TYPES.

    Returns:
        str: The response body.
    """
    return json.dumps(
        {
            "value": {
                "noRows": no_rows,
                "fileSize": 0 if csv_text is None else len(csv_text),
                "csvDataString": "" if csv_text is None else gzip_csv(csv_text),
                "columnNamesandTypes": COLUMN_TYPES if columns is None else columns,
            }
        }
    )
