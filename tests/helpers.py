"""Constants and response builders shared by the unit tests.

These live in a named module rather than in conftest.py so that the unit tests can
import them explicitly. There are two conftest.py files in this repository, one per
suite, and both import under the module name `conftest`, so importing from `conftest`
resolves to whichever pytest loaded first.
"""

import base64
import gzip
import io
import json
from typing import Optional

TENANT = "testtenant"
SERVER = "inmydata.test"
BASE_URL = f"https://{TENANT}.{SERVER}/api/developer/v1/ai"

DATA_URL = f"{BASE_URL}/data"
CHART_URL = f"{BASE_URL}/chart"
SCHEMA_URL = f"{BASE_URL}/getapisubjectlistinfo"
CALENDAR_RANGE_URL = f"{BASE_URL}/getcalendarperiodrange"
CALENDAR_DETAILS_URL = f"{BASE_URL}/getcalendardetails"

# The platform sends Dictionary<string, string>, field name to .NET type name, keyed on
# the fields the caller requested and in request order. "System.Date" is the platform's
# own date-only marker rather than a CLR type name, and reaches the client verbatim.
COLUMN_TYPES = {
    "Customer": "System.String",
    "Sales Value": "System.Decimal",
    "Financial Year": "System.Int32",
    "Date": "System.DateTime",
    "Delivery Date": "System.Date",
    "Order Count": "System.Int64",
    "Is Active": "System.Boolean",
}


def gzip_csv(csv_text: str) -> str:
    """Encodes CSV text the way the platform does: gzip, then standard base64."""
    buff = io.BytesIO()
    with gzip.GzipFile(fileobj=buff, mode="wb") as gz:
        gz.write(csv_text.encode("utf-8"))
    return base64.standard_b64encode(buff.getvalue()).decode("ascii")


def data_response(
    csv_text: Optional[str] = None,
    no_rows: int = 0,
    columns=None,
    envelope: bool = False,
) -> str:
    """Builds the JSON body of a successful /ai/data response.

    Args:
        csv_text: The CSV payload, or None for a zero-row response.
        no_rows: The row count the platform reports.
        columns: The column name to declared type map; defaults to COLUMN_TYPES.
        envelope: Wrap the payload in a {"value": ...} envelope. The live platform
            returns it at the top level, which is the default here; both shapes are
            supported, so both are tested.

    Returns:
        str: The response body.
    """
    payload = {
        "noRows": no_rows,
        "fileSize": 0 if csv_text is None else len(csv_text),
        "csvDataString": "" if csv_text is None else gzip_csv(csv_text),
        "columnNamesandTypes": COLUMN_TYPES if columns is None else columns,
    }
    return json.dumps({"value": payload} if envelope else payload)
