
![Logo](https://inmydata.ai/hs-fs/hubfs/Horizontal-1.png?width=200&height=59&name=Horizontal-1.png)




# Agent SDK

The inmydata agent SDK enables you to build AI agents that can rapidly access data from the inmydata platform. 


## Features

- Conversational data interface - retrieve data with natural language queries
- Structured data interface - rapidly build data interfaces for you AI agents 
- Calendar assistant - empower your AI agent with detailed knowledge of your financial calendars


## Installation

Install the inmydata agent SDK with pip

```bash
  pip install inmydata
```
    
## Documentation

See [https://developer.inmydata.com](https://developer.inmydata.com) for quickstarts, documentation, and examples.

Maintainers: see [TESTING.md](TESTING.md) for running the test suites, including against a
live platform, and [RELEASING.md](RELEASING.md) for how a version reaches PyPI.


## Release notes

### 0.0.20

**Upgrade to this release if you use `get_data`, `get_chart` or `CalendarAssistant`.**
0.0.19 and every earlier version required the platform to wrap its responses in a
`{"value": ...}` envelope. That envelope was never intentional: the API's controllers used
to return `Ok(await logic(...))`, wrapping an `IActionResult` inside another `Ok()`, so
ASP.NET serialised the result object itself and its `Value` property became the envelope.
The platform has since stopped doing that, which left these calls unable to read a
perfectly good response:

| Call | Before this release, against the current API |
| --- | --- |
| `get_data`, `get_data_simple` | `ValueError: Response does not contain 'value' or it is None` |
| `get_chart` | the same |
| `get_financial_periods` and friends | `KeyError: 'value'` |
| `get_calendar_period_date_range` | returned `None`, meaning "period not defined" — a wrong answer, not an error |
| `get_schema` | worked; it always tolerated both shapes |

This release accepts a response with or without the envelope, so **it works against both
old and new platform builds**. You can upgrade before or after your platform is updated,
in either order.

No API changes and nothing else to do: if your code worked against an older platform it
keeps working, and if it was failing with the errors above it starts working.

### 0.0.19

This release makes failures visible. Up to 0.0.18 a rejected token, a subject that was not
API-enabled and a server error all came back looking like an ordinary empty result, so a
scheduled job could report zeros instead of stopping. There are four behaviour changes, all
deliberate.

**Errors now raise instead of returning `None`.** Every non-success response raises a typed
exception from `inmydata.exceptions`:

| Status | Exception |
| --- | --- |
| 401 | `InmydataAuthenticationError` |
| 403 | `InmydataAccessDeniedError` (commonly a subject not flagged API-enabled) |
| 404 | `InmydataNotFoundError` |
| 5xx | `InmydataServerError` |
| any other non-2xx | `InmydataAPIError` |
| 200 with a body the SDK cannot interpret | `InmydataResponseError` |

All of them subclass `InmydataAPIError` and carry a `status_code`. `InmydataResponseError` also
subclasses `ValueError`, so existing `except ValueError` handlers around a malformed response
keep working.

Two statuses are worth knowing by sight. A **403** on a data request usually means the subject is
not flagged API-enabled in tenant administration, rather than anything wrong with your token. A
**400** from `get_data` is most often the platform refusing a result set over 50MB; its message
says so, and the fix is to add filters or request fewer fields.

```python
from inmydata import InmydataAccessDeniedError, InmydataAuthenticationError

try:
    frame = driver.get_data("Sales", fields, filters)
except InmydataAuthenticationError:
    ...  # token missing, expired or invalid
except InmydataAccessDeniedError:
    ...  # authenticated, but this subject is not API-enabled
```

**`get_data` and `get_data_simple` return an empty DataFrame for zero rows**, with the queried
columns and their types, and are annotated `-> pd.DataFrame` with no `| None`. Previously zero
rows and an authentication failure were both `None`. Code that tests `if frame is None:` should
now test `if frame.empty:`.

**`get_schema` raises instead of returning `"Error retrieving schema: ..."`.** The success
return is unchanged, so callers that parse the JSON keep working; anything sniffing for the
error prefix should catch `InmydataAPIError` instead. Its return type is now correctly
documented as `str`.

**`caseSensitive` in `get_data_simple` now means what it says.** It was being passed straight
into the filter's `CaseInsensitive` field, so `caseSensitive=True` produced a case-insensitive
filter and vice versa. Queries relying on the old inverted behaviour will change results.

Also fixed, and not a behaviour change anyone can have depended on: `get_chart` raised
`AttributeError` when its optional `TopNUsed` argument was omitted. It now works on its
documented default.

Every request now sends a timeout, `(10, 300)` seconds connect and read by default, so an
unresponsive platform no longer hangs the calling thread forever. Override it per driver with
`StructuredDataDriver(..., timeout=...)` or `CalendarAssistant(..., timeout=...)`; a
`requests.Timeout` propagates to the caller unchanged.

`requires-python` is now `>=3.10`. This corrects a declaration that was already false: 0.0.18
claimed 3.9 support but its `pd.DataFrame | None` annotations raise `TypeError` on import there.


## Usage/Examples

For these examples you will need to set the following environment variables:

- INMYDATA_API_KEY
- INMYDATA_TENANT
- INMYDATA_CALENDAR

Example of retrieving structured data

```python
import os
from dotenv import load_dotenv
from inmydata.StructuredData import (
    StructuredDataDriver, 
    AIDataSimpleFilter, 
    AIDataFilter, 
    LogicalOperator, 
    ConditionOperator, 
    TopNOption, 
    ChartType
)

load_dotenv()

driver = StructuredDataDriver(os.environ['INMYDATA_TENANT'])
driver.user = "demo" # Events to display charts will be available to the user specified here
driver.session_id = "test-session" # Session ID passed in the event to display charts. Can optionally be used to only show charts for the current session

# -- Get a json document that details the available schema
# get_schema retrieves metadata about available subjects (datasets), including:
# - Field names and types (dimensions and metrics)
# - AI descriptions for fields
# - Number of available dimensions and metrics per subject
# The optional 'source' parameter helps track where schema requests originate from
schema = driver.get_schema("Readme Documentation")
print(schema)

# Example output:
# {
#   "schemaVersion": 1,
#   "generatedAt": "2025-11-18T11:24:16Z",
#   "source": "Readme Documentation",
#   "subjectsCount": 1,
#   "subjects": [
#     {
#       "name": "Inmystore Sales",
#       "aiDescription": "This subject (dataset) contains transactional data for a retail organisation...",
#       "factFieldTypes": {
#         "Customer": {"name": "Customer", "type": "System.String", "aiDescription": null},
#         "Date": {"name": "Date", "type": "System.DateTime", "aiDescription": null},
#         "Financial Year": {"name": "Financial Year", "type": "System.Int32", 
#                           "aiDescription": "This dimension contains a Year value..."}
#         # ... more dimension fields
#       },
#       "metricFieldTypes": {
#         "Cost of Sale": {"name": "Cost of Sale", "type": "System.Decimal", 
#                         "dimensionsUsed": null, "aiDescription": ""},
#         "Sales Value": {"name": "Sales Value", "type": "System.Decimal", 
#                        "dimensionsUsed": null, "aiDescription": ""}
#         # ... more metric fields
#       },
#       "numDimensions": 26,
#       "numMetrics": 14
#     }
#   ]
# }

# -- Use get_data_simple when your filter is simple (only equality filters, no bracketing, no ORs, etc.)

# Build our simple filter
filter = []
filter.append(
    AIDataSimpleFilter(
        "Store", # Field to filter on
        "Edinburgh") # Value to filter by
    ) 

# Build a TopN filter to only show the Top 10 Sales People based on Sales Value
TopN = TopNOption("Sales Value", 10) # Field to order by and number of records to return (Positive for TopN, negative for BottomN)
TopNOptions = {}
TopNOptions["Sales Person"] = TopN # Apply the Top N option to the Sales Person field

df = driver.get_data_simple(
    "Inmystore Sales", # Name of the subject we want to extract data from
    ["Sales Person","Sales Value"], # List of fields we want to extract
    filter, # Filters to apply
    False, # Whether filters are case sensitive
    TopNOptions) # Apply the Top 10 Sales People based on Sales Value filter

print(df)

# -- Use get_data when your filter more complex (non-equality matches, bracketing, ORs, etc.) --

# Build our filter
filter = [] 
filter.append(
    AIDataFilter(
        "Store",
        ConditionOperator.Equals, # Condition to use in the filter
        LogicalOperator.And, # Logical operator to use in the filter
        "Edinburgh", # Value to filter by
        0, # Number of brackets before this condition
        0, # Number of brackets after this condition
        False # Whether the filter is case sensitive
    )
)
filter.append(
    AIDataFilter(
        "Store",
        ConditionOperator.Equals, # Condition to use in the filter
        LogicalOperator.Or, # Logical operator to use in the filter
        "London", # Value to filter by
        0, # Number of brackets before this condition
        0, # Number of brackets after this condition
        False # Whether the filter is case sensitive
    )
)
df = driver.get_data(
    "Inmystore Sales", # Name of the subject we want to extract data from
    ["Financial Year","Store","Sales Value"], # List of fields we want to extract
    filter, # Filters to apply
    {}) # Apply no TopN options

print(df)

# -- Use get_chart to generate a chart based on the data -- see https://developer.inmydata.com/support/solutions/articles/36000577995-displaying-charts-generated-by-agentic-ai-workflows

# Build our filter
filter = [] 
filter.append(
    AIDataFilter(
        "Store",
        ConditionOperator.Equals, # Condition to use in the filter
        LogicalOperator.And, # Logical operator to use in the filter
        "Edinburgh", # Value to filter by
        0, # Number of brackets before this condition
        0, # Number of brackets after this condition
        False # Whether the filter is case sensitive
    )
)
filter.append(
    AIDataFilter(
        "Financial Year",
        ConditionOperator.Equals, # Condition to use in the filter
        LogicalOperator.And, # Logical operator to use in the filter
        "2025", # Value to filter by
        0, # Number of brackets before this condition
        0, # Number of brackets after this condition
        False # Whether the filter is case sensitive
    )
)

# Build a TopN filter to only show the Top 10 Sales People based on Sales Value
TopN = TopNOption("Sales Value", 10) # Field to order by and number of records to return (Positive for TopN, negative for BottomN)
TopNOptions = {}
TopNOptions["Sales Person"] = TopN # Apply the Top N option to the Sales Person field

chartId = driver.get_chart(
    "Inmystore Sales", # Name of the subject we want to extract data from
    ["Sales Person"], # Chart row fields
    [], # Chart Column Fields
    ["Sales Value"], # Chart value fields
    filter, # Filters to apply
    ChartType.Bar, # Type of chart to generate
    "Top 10 Sales People in Edinburgh for 2025", # Title of the chart
    TopNOptions, # Apply the Top 10 Sales People based on Sales Value filter
)
```

Example of retrieving conversational data

```python
import os

from dotenv import load_dotenv
from inmydata.ConversationalData import ConversationalDataDriver
import asyncio

load_dotenv()

# get_answer is an async function, so we need to run it in an event loop
async def main():
    driver = ConversationalDataDriver(os.environ['INMYDATA_TENANT'])

    # Register a callback to handle AI question updates
    def on_ai_question_update(caller, message):  
        print(message)

    # Register the callback handler for AI question updates
    driver.on("ai_question_update", on_ai_question_update) 

    question = "Give me the top 10 stores this year"
    answer = await driver.get_answer(question)
    
    print("=================================================================")
    print(f"The answer was: {answer.answer}")
    print(f"The subject used to generate the answer was: {answer.subject}")


asyncio.run(main())
```

Example of retrieving calendar periods

```python
import os

from datetime import date
from dotenv import load_dotenv
from inmydata.CalendarAssistant import CalendarAssistant

load_dotenv()

# Get today's date
today = date.today()

# Initialize the Calendar Assistant with tenant and calendar name
assistant = CalendarAssistant(os.environ['INMYDATA_TENANT'], os.environ['INMYDATA_CALENDAR'])

# Get the current financial year
print("The current financial year is:  " + str(assistant.get_financial_year(today)))
# Get the current financial quarter
print("The current financial quarter is: " + str(assistant.get_quarter(today)))
# Get the current financial month
print("The current financial month is: " + str(assistant.get_month(today)))
# Get the current financial week
print("The current financial week is: " + str(assistant.get_week_number(today)))
# Get the current financial periods
print("The current periods are:")
print(assistant.get_financial_periods(today))
# Get the date range for the current financial month
response = assistant.get_calendar_period_date_range(assistant.get_financial_year(today), assistant.get_month(today), CalendarPeriodType.month)
if response is not None:
    print("The current financial month date range is: " + response.StartDate.strftime("%A, %B %d, %Y") + " to " + response.EndDate.strftime("%A, %B %d, %Y"))
```



