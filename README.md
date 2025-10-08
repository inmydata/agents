
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
print(driver.get_schema("Readme Documentation"))

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



