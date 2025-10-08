from typing import Optional
from dataclasses import dataclass
from enum import Enum
from datetime import date
from io import StringIO
from signalrcore.hub_connection_builder import HubConnectionBuilder
import json
import pandas as pd
import os
import aiohttp
import logging

class Model(Enum):
    """
    Enum representing the model to use when answering the question.

    Attributes:
        gpt4: OpenAI's gpt4 model.
        o3mini: OpenAI's o3mini model, which is a smaller and more efficient version.
    """
    gpt4 = 0
    o3mini = 1

class AIQuestionOutputTypeEnum(Enum):
    """
    Enum representing the different types of outputs an AI question can produce.

    Attributes:
        text: A plain text response.
        data: A structured data response (e.g., table or raw output).
        chart: A visual chart representation.
    """
    text = 0
    data = 1
    chart = 2

class AITypeEnum(Enum):
    """
    Enum representing the different platform options used to respond to the question.

    Attributes:
        azureopenai: Microsoft Azure OpenAI service.
        openai: OpenAI's own API service.
    """
    azureopenai = 0
    openai = 1    

@dataclass
class Answer:
    """
    A data class for providing a string response to a question.

    Attributes:
        answer (str): The string response to the question.
        subject (str): The subject that was used to generate the answer.
    """
    answer: str
    subject: str

@dataclass
class QuestionResponse:
    """
    A data class for providing a structured response to a question.
    This class provides a string and a dataframe property to return a both a string and dataframe in response to a question.
    
    Attributes:
        answer (str): The string response to the question.  
        dataFrame (pd.DataFrame): The pandas DataFrame containing the structured data in response to the question.
        subject (str): The subject that was used to generate the answer.
    """
    def __init__(self, answer: str, dataFrame: pd.DataFrame, subject: str):
        """
        Initializes the QuestionResponse with a string answer and a pandas DataFrame.
        Args:
            answer (str): The string response to the question.
            dataFrame (pd.DataFrame): The pandas DataFrame containing the structured data in response to the question.
            subject (str): The subject of the question, which can be used to generate the answer.
        """
        self.answer = answer
        self.dataFrame = dataFrame
        self.subject = subject
    
    def toJSON(self):
        """
        Returns a JSON representation of the QuestionResponse object.

        Returns:
            str: A JSON string representation of the QuestionResponse object.
        """
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

class ConversationalDataDriver:
    """
    This class provides methods for querying data in the inmydata platform using a conversational interface.
    It allows users to ask questions about their data and receive answers in various formats, including text and structured data.
    It uses the inmydata API to fetch data and returns it as a pandas DataFrame or a string response.
    
    Attributes
    ----------
    tenant : str
        The tenant identifier for the inmydata platform.
    server : str
        The server address for the inmydata platform, default is "inmydata.com".
    user : Optional[str]
        The user for whom the driver is initialized, if None, no user is set. Useful to identify the user when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
    session_id : Optional[str]      
        The session ID for the driver, if None, no session ID is set. Useful to identify the session when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
    api_key (Optional[str]): 
        The API key for authenticating with the inmydata platform. If None, it will attempt to read from the environment variable 'INMYDATA_API_KEY'.    
    logging_level : Optional[int]
        The logging level for the logger, default is logging.INFO.
    log_file : Optional[str]
        The file to log messages to, if None, logs to console.
    """

    class _AIQuestionAPIRequest:
        def __init__(self, Subject,Question,Date,Model,OutputType,AIType,SkipZeroQuestion,SkipGeneralQuestion,SummariseComments,ShowinChartComponent,User,SessionID):
          self.Subject = Subject
          self.Question = Question
          self.Date = Date
          self.model = Model
          self.outputtype = OutputType
          self.aitype = AIType
          self.SkipZeroQuestion = SkipZeroQuestion
          self.SkipGeneralQuestion = SkipGeneralQuestion
          self.SummariseComments = SummariseComments
          self.ShowinChartComponent = ShowinChartComponent
          self.User = User
          self.SessionID = SessionID
        def toJSON(self):
          return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    class _AIQuestionAPIResponse:
        def __init__(self, answer,answerDataJson,subject):
          self.answer = answer
          self.answerDataJson = answerDataJson
          self.subject = subject
        def toJSON(self):
          return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    class _AIQuestionStatus:
        def __init__(self, ConversationID,User,StatusMessage,StatusCommand,Sequence):
          self.ConversationID = ConversationID
          self.User = User
          self.StatusMessage = StatusMessage
          self.StatusCommand = StatusCommand
          self.Sequence = Sequence
        def toJSON(self):
          return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def __init__(self, tenant: str, server:str ="inmydata.com", user: Optional[str] = None, session_id: Optional[str] = None,  api_key: Optional[str] = None, logging_level: Optional[int] = logging.INFO, log_file: Optional[str] = None):
        """
        Initializes the ConversationalDataDriver with the specified tenant, server, logging level, and optional log file.
        
        Args:
            tenant : str
                The tenant identifier for the inmydata platform.
            server : str
                The server address for the inmydata platform, default is "inmydata.com".
            user : Optional[str]
                The user for whom the driver is initialized, if None, no user is set. Useful to identify the user when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
            session_id : Optional[str]      
                The session ID for the driver, if None, no session ID is set. Useful to identify the session when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
            api_key (Optional[str]): 
                The API key for authenticating with the inmydata platform. If None, it will attempt to read from the environment variable 'INMYDATA_API_KEY'.    
            logging_level : Optional[int]
                The logging level for the logger, default is logging.INFO.
            log_file : Optional[str]
                The file to log messages to, if None, logs to console.
        """
        self._callbacks = {} 
        self.server = server
        self.tenant = tenant
        self.user = user
        self.session_id = session_id
        
        # Create a logger specific to this class/instance
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}.{tenant}")
        if logging_level is None:
            logging_level = logging.INFO
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

        if api_key:
            self.api_key = api_key
        else:
            try:
               self.api_key = os.environ['INMYDATA_API_KEY']
            except KeyError:
               self.api_key = ""
               self.logger.warning("Environment variable INMYDATA_API_KEY not set. API requests to the inmydata platform will fail.")

        self.hub_connection = HubConnectionBuilder()\
            .with_url("https://" + tenant + "." + server + "/datahub",
                options={"access_token_factory": self.__get_api_key})\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()
        self.hub_connection.on("AIQuestionStatus", self.__process_server_message)
        self.hub_connection.start()
        self.hub_connection.on_open(lambda: self.logger.info("Connection opened"))
        self._session = None
        self.logger.info("ConversationalDataDriver initialized.")
        pass

    def get_user(self):
        """ 
        Returns the user. The user is used to identify the user when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
        
        Returns:
            Optional[str]: The user, or None if no user is set.
        """
        return self.user
    
    def set_user(self, user: str):
        """ 
        Sets the user for the driver.
        
        Args:
            user (str): The user to set for the driver. The user is used to identify the user when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
        """
        self.user = user
        self.logger.info(f"User set to {user}")
    
    def get_session_id(self):
        """ 
        Returns the session ID for the driver.
        
        Returns:
            Optional[str]: The session ID for the driver, or None if no session ID is set. The session ID is used to identify the session when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
        """
        return self.session_id

    def set_session_id(self, session_id: str):
        """ 
        Sets the session ID for the driver.
        
        Args:
            session_id (str): The session ID to set for the driver. The session ID is used to identify the session when generating a chart (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664).
        """
        self.session_id = session_id
        self.logger.info(f"Session ID set to {session_id}")

    async def get_answer(self, question: str, subject: Optional[str] = None, generate_chart: Optional[bool] = False) -> Answer:
        """
        Returns a text response for a given question.

        Args:
            question (str): The question you want to ask.
            subject (str, optional): The subject you want to ask the question about. If None provided, copilot with choose the subject.
            generate_chart (bool, optional): If True, the response will generate a chart. Default is False. (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664)

        Raises:
            ai_question_update: This event is triggered when the AI question status is updated. The callback function will receive the instance of this class and a string containing the status message as parameters.

        Returns:
            Answer: A string response to the question.
        """
        self.logger.info("query_for_answer question: " + question)        
        answer = await self.__get_answer(subject, question,generate_chart)
        self.logger.info("query_for_answer answer: " + str(answer))    
        return answer is not None and answer or Answer("No answer available.","No subject provided.")

    async def get_data_frame(self, question: str, subject: Optional[str] = None, generate_chart: Optional[bool] = False) -> Optional[pd.DataFrame]:
        """
        Returns a pandas DataFrame response for a given question.

        Args:
            question (str): The question you want to ask.
            subject (str, optional): The subject you want to ask the question about. If None provided, copilot with choose the subject.
            generate_chart (bool, optional): If True, the response will generate a chart. Default is False. (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664)

        Raises:
            ai_question_update: This event is triggered when the AI question status is updated. The callback function will receive the instance of this class and a string containing the status message as parameters.

        Returns:
            pd.DataFrame: A pandas DataFrame containing the data in response to the question.
        """
        airesp = await self.__get_answer_object(subject,question, generate_chart,AIQuestionOutputTypeEnum.data.value)
        if airesp is not None and hasattr(airesp, 'answerDataJson') and airesp.answerDataJson:
            return pd.read_json(StringIO(airesp.answerDataJson))
        else:
            self.logger.info("No answer data available.")
            return None
        
    async def get_answer_and_data_frame(self, question: str, subject: Optional[str] = None, generate_chart: Optional[bool] = False) -> Optional[QuestionResponse]:
        """
        Returns a stext and pandas DataFrame response for a given question.

        Args:
            question (str): The question you want to ask.
            subject (str, optional): The subject you want to ask the question about. If None provided, copilot with choose the subject.
            generate_chart (bool, optional): If True, the response will generate a chart. Default is False. (see https://developer.inmydata.com/a/solutions/articles/36000577995?portalId=36000061664)

        Raises:
            ai_question_update: This event is triggered when the AI question status is updated. The callback function will receive the instance of this class and a string containing the status message as parameters.

        Returns:
            QuestionResponse: A structured response containing both a string and a pandas DataFrame.
        """
        airesp = await self.__get_answer_object(subject,question,generate_chart,AIQuestionOutputTypeEnum.data.value)
        if airesp is not None and hasattr(airesp, 'answerDataJson') and airesp.answerDataJson:
            return QuestionResponse(answer=airesp.answer, dataFrame=pd.read_json(StringIO(airesp.answerDataJson)), subject=airesp.subject)
        else:
            self.logger.info("No answer data available.")
            return None
        
    def on(self, event_name, callback):
        """ Registers a callback function for a specific event.

        Args:
            event_name (str): The name of the event to listen for.
            callback (function): The function to call when the event is triggered. The function should accept two parameters: the instance of this class and the event data.

        Raises:
            ai_question_update: This event is triggered when the AI question status is updated. The callback function will receive the instance of this class and a string containing the status message as parameters.
        """
        if self._callbacks is None:
            self._callbacks = {}

        if event_name not in self._callbacks:
            self._callbacks[event_name] = [callback]
        else:
            self._callbacks[event_name].append(callback)

    def __get_api_key(self):
        if self.api_key:
            return self.api_key
        else:
            raise ValueError("API key is not set. Please set the INMYDATA_API_KEY environment variable.")
        
    async def __get_answer_object(self, subject,question,generate_chart,outputtype = AIQuestionOutputTypeEnum.text.value):
        aireq = self._AIQuestionAPIRequest(
            subject,
            question,
            date.today().strftime("%m/%d/%Y"),
            Model.o3mini.value,
            outputtype,AITypeEnum.azureopenai.value, 
            True, 
            True, 
            True, 
            generate_chart,
            self.user,
            self.session_id)
        self.logger.debug("AIQuestionAPIRequest")
        self.logger.debug(aireq.toJSON())
        x = await self.__post_request('https://' + self.tenant + '.' + self.server + '/api/developer/v1/ai/question', data=json.loads(aireq.toJSON()))
        self.logger.debug("Post request to inmydata complete")
        self.logger.debug(x)
        if x is not None:                
            return self._AIQuestionAPIResponse(x['answer'], x['answerDataJson'], x['subject'])
        else:
            self.logger.warning("Unsuccessful request")
        return None

    async def __get_answer(self, subject, question, generate_chart) -> Optional[Answer]:
        airesp = await self.__get_answer_object(subject,question, generate_chart)
        if airesp is not None:
            self.logger.info("Answer received: " + airesp.answer)
            return Answer(answer=airesp.answer, subject=airesp.subject)
        else:
            return None
    
    def __process_server_message(self, message):
        aiqs = self._AIQuestionStatus(**json.loads(message[0]))
        self.__trigger("ai_question_update", aiqs.StatusMessage)

    def __trigger(self, event_name, event_data):
        if self._callbacks is not None and event_name in self._callbacks:
            for callback in self._callbacks[event_name]:
                callback(self, event_data)
    
    async def __post_request(self, url, data):
        if self._session is None:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        async with self._session.post(url, json=data) as response:
            return await response.json()