"""
calendar_assistant.py

Provides tools for integrating calendar data with AI agents via the inmydata platform.
"""

import os
import json
import requests
import jsonpickle
from datetime import date, datetime
import logging
from typing import Optional
from enum import Enum
   
class FinancialPeriodDetails:
    """
    A structure class for passing financial periods.
    It contains the year, month, week, and quarter for a given date.
    
    Attributes:
        year (int): The financial year.
        month (int): The financial month (1-12).            
        week (int): The financial week (1-53).
        quarter (int): The financial quarter (1-4).
    """
    def __init__(self, year: int, month: int, week: int, quarter: int):
        self.year = year
        self.month = month
        self.week = week
        self.quarter = quarter
    def __repr__(self):
        return f"FinancialPeriodDetails(year={self.year}, month={self.month}, week={self.week}, quarter={self.quarter})"
    
class CalendarPeriodType(Enum):
    """Enum for different calendar period types.
    This enum defines the types of financial periods.

    Attributes:
        year (int): Represents the financial year.
        month (int): Represents the financial month.
        quarter (int): Represents the financial quarter.
        week (int): Represents the financial week.
    """
    year = 1
    month = 2
    quarter = 3
    week = 4

class CalendarPeriodDateRange:
    """A structure class for passing calendar period date ranges.
    It contains the start and end dates of a calendar period.
    
    Attributes:
        StartDate (date): The start date of the calendar period.
        EndDate (date): The end date of the calendar period.
    """
    def __init__(self, StartDate: date, EndDate: date):      
      self.StartDate = StartDate
      self.EndDate = EndDate
    def toJSON(self):
      return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

class CalendarAssistant:
    """
    This class provides methods to retrieve financial periods (year, month, week, quarter) based on a given date.
    It uses the inmydata API to fetch calendar details and returns them in a structured format.
    
    Attributes:
        tenant (str): The tenant identifier for the inmydata platform.
        calendar_name (str): The name of the calendar to use for financial periods.
        server (str): The server address for the inmydata platform, default is "inmydata.com".
        logging_level (int): The logging level for the logger, default is logging.INFO.
        log_file (Optional[str]): The file to log messages to, if None, logs to console.
    """

    class _GetCalendarDetailsRequest:
        def __init__(self,UseDate,CalendarName):      
          self.UseDate = UseDate
          self.CalendarName = CalendarName
        def toJSON(self):
            """ Converts the _GetCalendarDetailsRequest object to a JSON string.
            
            Returns:
                str: A JSON string representation of the _GetCalendarDetailsRequest object.
            """
            return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    class _GetCalendarDetailsResponse:
        def __init__(self,dateDetails):      
          self.dateDetails = dateDetails
        def toJSON(self):
            """ Converts the _GetCalendarDetailsResponse object to a JSON string.
            
            Returns:
                str: A JSON string representation of the _GetCalendarDetailsResponse object.
            """
            return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    class _DateDetails:
        def __init__(self,year:int,month:int,week:int,quarter:int,yearseq:int,monthseq:int,weekseq:int,quarterseq:int,yearid:int,monthid:int,weekid:int,quarterid:int,date:date):      
          self.year = year
          self.month = month
          self.week = week
          self.quarter = quarter
          self.yearseq = yearseq
          self.monthseq = monthseq
          self.weekseq = weekseq
          self.quarterseq = quarterseq
          self.yearid = yearid
          self.monthid = monthid
          self.quarterid = quarterid
          self.weekid = weekid
          self.date = date
        def toJSON(self):
            """ Converts the _DateDetails object to a JSON string.
            
            Returns:
                str: A JSON string representation of the _DateDetails object.
            """
            # Convert date to string for JSON serialization
            self.date = self.date.isoformat() if isinstance(self.date, date) else self.date
            return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
        
    class _GetCalendarPeriodDateRangeRequest:
        def __init__(self,PeriodType:CalendarPeriodType,Year:int,PeriodNumber:int,CalendarName:str):      
          self.PeriodType = PeriodType
          self.Year = Year
          self.PeriodNumber = PeriodNumber
          self.CalendarName = CalendarName
        def to_dict(self):
            return {
                "PeriodType": self.PeriodType.value,
                "Year": self.Year,
                "PeriodNumber": self.PeriodNumber,
                "CalendarName": self.CalendarName
            }

    def __init__(self, tenant: str, calendar_name: str, server: str = "inmydata.com", logging_level=logging.INFO, log_file: Optional[str] = None ):
        """
        Initializes the CalendarAssistant with the specified tenant, calendar name, server, logging level, and optional log file.
        
        
        Args:            
            tenant (str): The tenant identifier for the inmydata platform.
            calendar_name (str): The name of the calendar to use for financial periods.
            server (str): The server address for the inmydata platform, default is "inmydata.com".  
            logging_level (int): The logging level for the logger, default is logging.INFO.
            log_file (Optional[str]): The file to log messages to, if None, logs to console.
        """
        self.tenant = tenant
        self.calendar_name = calendar_name
        self.server = server

        # Create a logger specific to this class/instance
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}.{tenant}")
        self.logger.setLevel(logging_level)
        
        # Avoid adding multiple handlers if this gets called multiple times
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')

            if log_file:
                handler = logging.FileHandler(log_file)
            else:
                handler = logging.StreamHandler()

            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.logger.propagate = False  # Prevent propagation to the root logger
        
        try:
           self.api_key = os.environ['INMYDATA_API_KEY']
        except KeyError:
           self.api_key = ""
           self.logger.warning("Environment variable INMYDATA_API_KEY not set. API requests to the inmydata platform will fail.")

        self.logger.info("CalendarAssistant initialized.")

    def get_financial_periods(self, input_date: date) -> FinancialPeriodDetails:
        """
        Returns the financial periods (year, month, week, quarter) for the given date.

        Args:
            input_date (date): The date you want to find the financial periods for.

        Returns:
            FinancialPeriodDetails: An object that contains a value for each financial period (year, month, week, quarter) for the given date.
        """
        cd = self.__get_calendar_details(input_date)
        if cd is None:
            raise ValueError("Calendar details not found for the given date.")
        return FinancialPeriodDetails(cd.dateDetails.year, cd.dateDetails.month, cd.dateDetails.week, cd.dateDetails.quarter)

    def get_week_number(self, input_date: date) -> int:
        """
        Returns the Week number (1–53) for a given date.

        Args:
            input_date (date): The date you want to find the financial week for.

        Returns:
            int: An integer that represents the financial week for the given date.
        """
        cd = self.__get_calendar_details(input_date)
        if cd is None:
            raise ValueError("Calendar details not found for the given date.")
        return cd.dateDetails.week

    def get_financial_year(self, input_date: date) -> int:
        """
        Returns the Financial Year for a given date.

        Args:
            input_date (date): The date you want to find the financial year for.

        Returns:
            int: An integer that represents the financial year for the given date.
        """
        cd = self.__get_calendar_details(input_date)
        if cd is None:
            raise ValueError("Calendar details not found for the given date.")
        return cd.dateDetails.year

    def get_quarter(self, input_date: date) -> int:
        """
        Returns the Financial Quarter (1-4) for a given date.

        Args:
            input_date (date): The date you want to find the financial quarter for.

        Returns:
            int: An integer that represents the financial quarter for the given date.
        """
        cd = self.__get_calendar_details(input_date)
        if cd is None:
            raise ValueError("Calendar details not found for the given date.")
        return cd.dateDetails.quarter

    def get_month(self, input_date: date) -> int:
        """
        Returns the Financial Month (1-12) for a given date.

        Args:
            input_date (date): The date you want to find the financial month for.

        Returns:
            int: An integer that represents the financial month for the given date.
        """
        cd = self.__get_calendar_details(input_date)
        if cd is None:
            raise ValueError("Calendar details not found for the given date.")
        return cd.dateDetails.month

    def get_calendar_period_date_range(self, year: int, periodnumber: int, periodtype: CalendarPeriodType) -> CalendarPeriodDateRange | None:
        """
        Returns the start and end dates of a calendar period based on the specified year, period number, and period type.

        Args:
            year (int): The year of the calendar period.
            periodnumber (int): The number of the period within the specified type (e.g., quarter number, month number, week number).
            periodtype (CalendarPeriodType): The type of calendar period (year, month, quarter, week).
            
        Returns:
            CalendarPeriodDateRange | None: An object containing the start and end dates of the calendar period, or None if not found.
        """
        result = None
        calreq = self._GetCalendarPeriodDateRangeRequest(periodtype,year,periodnumber,self.calendar_name)
        input_json_string  = jsonpickle.encode(calreq.to_dict(), unpicklable=False)
        if input_json_string is None:
            raise ValueError("input_json_string is None and cannot be loaded as JSON")
        myobj = json.loads(input_json_string)
        headers = {'Authorization': 'Bearer ' + self.__get_auth_token(),
                'Content-Type': 'application/json'}
        url = 'https://' + self.tenant + '.' + self.server + '/api/developer/v1/ai/getcalendarperiodrange'
        x = requests.post(url, json=myobj,headers=headers)
        if x.status_code == 200 and x.text:
            value = jsonpickle.decode(x.text).get("value")
            if value is not None:
                encoded_value = jsonpickle.encode(value)
                if encoded_value is not None:
                    rangedict = json.loads(encoded_value)
                    result = CalendarPeriodDateRange(
                        datetime.fromisoformat(rangedict["startDate"]).date(),
                        datetime.fromisoformat(rangedict["endDate"]).date()
                    )
        return result

    def __get_auth_token(self):        
        return os.environ['INMYDATA_API_KEY'] 
    
    def __get_calendar_details(self,input_date:date):
        result = None
        caldetreq = self._GetCalendarDetailsRequest(input_date,self.calendar_name)
        input_json_string  = jsonpickle.encode(caldetreq, unpicklable=False)
        if input_json_string is None:
            raise ValueError("input_json_string is None and cannot be loaded as JSON")
        myobj = json.loads(input_json_string)
        headers = {'Authorization': 'Bearer ' + self.__get_auth_token(),
                'Content-Type': 'application/json'}
        url = 'https://' + self.tenant + '.' + self.server + '/api/developer/v1/ai/getcalendardetails'
        x = requests.post(url, json=myobj,headers=headers)
        if x.status_code == 200:     
            response_json = json.loads(x.text)
            datedetailsdict = response_json["value"]["dateDetails"]
            datedetails = self._DateDetails(datedetailsdict["year"],datedetailsdict["month"],datedetailsdict["week"],datedetailsdict["quarter"],
                                      datedetailsdict["yearseq"],datedetailsdict["monthseq"],datedetailsdict["weekseq"],datedetailsdict["quarterseq"],
                                      datedetailsdict["yearid"],datedetailsdict["monthid"],datedetailsdict["weekid"],datedetailsdict["quarterid"],
                                      datedetailsdict["date"])
            result = self._GetCalendarDetailsResponse(datedetails)            
        return result