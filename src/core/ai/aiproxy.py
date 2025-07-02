import ast
import functools
import os
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from google import genai

import constants
from core.enums import PostType, SentimentType


@dataclass
class AIModel:
    name: str
    max_call_num_per_min: int
    max_call_num_per_day: int


class NoAvailableModelError(Exception):
    """Exception raised when there is no available model in models pool."""
    pass


class ConfigurationManager:
    """Manages configuration for AI models and API settings."""

    def __init__(self):
        self._models_config = self._load_models_config()
        self._api_config = self._load_api_config()

    def _load_models_config(self) -> List[AIModel]:
        """Load models configuration from environment or defaults."""
        return [
            AIModel(name="gemini-2.0-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-thinking-exp-01-21", max_call_num_per_min=10, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-exp", max_call_num_per_min=10, max_call_num_per_day=1500),
            AIModel(name="gemini-1.5-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
            AIModel(name="gemini-1.5-flash-8b", max_call_num_per_min=15, max_call_num_per_day=1500),
        ]

    def _load_api_config(self) -> Dict[str, Any]:
        """Load API configuration from environment."""
        return {
            'api_key': os.environ.get("GEMINI_API_KEY"),
            'retry_max_num': getattr(constants, 'MODEL_RETRY_MAX_NUM', 3),
            'retry_delay': 60
        }

    def get_models_pool(self) -> List[AIModel]:
        """Get the configured models pool."""
        return self._models_config.copy()

    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        return self._api_config.copy()


class ModelManager:
    """Manages AI model pool, switching, and retry logic."""

    def __init__(self, models_pool: List[AIModel]):
        if not models_pool:
            raise ValueError("Models pool cannot be empty")

        self._models_pool = models_pool.copy()
        self._current_model = self._models_pool[0]
        self._retry_count = 0

    def get_current_model(self) -> AIModel:
        """Get the currently active model."""
        return self._current_model

    def update_model(self) -> AIModel:
        """Switch to the next available model in the pool."""
        if len(self._models_pool) <= 1:
            raise NoAvailableModelError("Available models pool is empty...")

        # Remove current model and switch to next
        self._models_pool.pop(0)
        self._current_model = self._models_pool[0]

        print(f'Updated model: {self._current_model.name}')

        # Reset retry count for new model
        self.reset_retry_count()

        return self._current_model

    def increment_retry_count(self):
        """Increment the retry count for the current model."""
        self._retry_count += 1

    def reset_retry_count(self):
        """Reset the retry count for the current model."""
        self._retry_count = 0

    def should_switch_model(self, max_retries: int) -> bool:
        """Check if model should be switched based on retry count."""
        return self._retry_count >= max_retries

    def have_more_available_models(self) -> bool:
        """Check if there are available models in the pool."""
        return len(self._models_pool) > 1

    def get_models_count(self) -> int:
        """Get the number of available models in the pool."""
        return len(self._models_pool)


class RateLimitStatus(Enum):
    """Enum for rate limit status returns."""
    PROCEED = "proceed"
    MINUTE_LIMIT_REACHED = "minute_limit_reached"
    DAY_LIMIT_REACHED = "day_limit_reached"


class RateLimiter:
    """Manages API call rate limiting for AI models."""

    def __init__(self, model: AIModel):
        self._model = model
        self._call_count_per_min = 0
        self._call_count_per_day = 0
        self._last_begin_call_time_per_min = datetime.now(timezone.utc)
        self._last_success_call_time = datetime.now(timezone.utc)

    def check_and_wait_if_needed(self) -> RateLimitStatus:
        """
        Check rate limits and wait if necessary.
        Returns: RateLimitStatus enum value
        """
        now = datetime.now(timezone.utc)
        time_since_last_call_per_min = now - self._last_begin_call_time_per_min

        # Check if minute limit is reached
        if (
            self._call_count_per_min >= self._model.max_call_num_per_min
            and time_since_last_call_per_min.total_seconds() <= 60
        ):
            sleep_time_in_second = 60 - time_since_last_call_per_min.total_seconds()

            print('API call reached minute limit')
            print(f'Sleeping for {sleep_time_in_second} seconds...')
            time.sleep(sleep_time_in_second)
            print('Retry API')

            # Reset minute counter and timestamp
            self._call_count_per_min = 0
            self._last_begin_call_time_per_min = datetime.now(timezone.utc)

            return RateLimitStatus.MINUTE_LIMIT_REACHED

        # Check if day limit is reached
        elif self._call_count_per_day >= self._model.max_call_num_per_day:
            print('API call reached day limit')
            return RateLimitStatus.DAY_LIMIT_REACHED

        # Reset last_begin_call_time_per_min if more than a minute has passed
        elif time_since_last_call_per_min.total_seconds() > 60:
            self._last_begin_call_time_per_min = now
            self._call_count_per_min = 0

        return RateLimitStatus.PROCEED

    def record_call_attempt(self):
        """Record an API call attempt."""
        self._call_count_per_min += 1
        self._call_count_per_day += 1

        print(f"Current call count per minute: {self._call_count_per_min}")
        print(f"Current call count per day: {self._call_count_per_day}")

    def record_successful_call(self):
        """Record a successful API call."""
        self._last_success_call_time = datetime.now(timezone.utc)

    def get_time_since_last_success(self) -> float:
        """Get time in seconds since last successful call."""
        now = datetime.now(timezone.utc)
        return (now - self._last_success_call_time).total_seconds()

    def reset_for_new_model(self, new_model: AIModel):
        """Reset rate limiter state for a new model."""
        self._model = new_model
        self._call_count_per_min = 0
        self._call_count_per_day = 0
        self._last_begin_call_time_per_min = datetime.now(timezone.utc)


class APIClient:
    """Dedicated API client for Google Gemini models."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required")

        self._client = genai.Client(api_key=api_key)
        self._chat = None
        self._current_model = None

    def initialize_chat(self, model: AIModel, initial_prompt: str):
        """Initialize chat session with the specified model."""
        try:
            print(f'Initializing chat with model: {model.name}')
            print(f'Model limits - Per minute: {model.max_call_num_per_min}, Per day: {model.max_call_num_per_day}')

            self._chat = self._client.chats.create(model=model.name)
            response = self._chat.send_message(initial_prompt)
            self._current_model = model

            print(f'Chat initialized successfully. Response: {response.text}')
            return response
        except Exception as e:
            print(f'Failed to initialize chat with model {model.name}: {e}')
            raise RuntimeError(f"Chat initialization failed: {e}")

    def send_message(self, prompt: str):
        """Send a message to the current chat session."""
        if not self._chat:
            raise RuntimeError("Chat not initialized")

        return self._chat.send_message(prompt)

    def is_chat_initialized(self) -> bool:
        """Check if chat is initialized."""
        return self._chat is not None

    def get_current_model(self) -> Optional[AIModel]:
        """Get the current model in use."""
        return self._current_model


class PromptManager:
    """Manages prompts for different content analysis tasks."""

    def __init__(self) -> None:
        self._prompts = {
            'init': '我将给你一段文本，然后给你一系列任务，对于现在这个问题，你不用回答.\n 文本内容:\n{content_txt}',

            'tags': "请根据上面给定的文本，总结能代表文本的主题关键词标签，你回答的格式为: ['tag1', 'tag2', 'tag3']",

            'post_type': (
                "请根据上面给定的文本，总结最代表文本的类型。\n"
                "有以下类型：知识类（技术教程、行业预测、工具测评）、观点类（时事评论、行业观察、书评）、生活类（成长感悟、随笔、旅行美食）、娱乐类（吐槽搞笑、迷因、段子）、互动类（投票、接龙挑战、测试）、产品营销类（产品介绍、营销活动）\n"
                "你回答的格式为:KNOWLEDGE or OPINION or LIFESTYLE or ENTERTAINMENT or INTERACTIVE or PRODUCT_MARKETING\n"
                "对回答类型的解释：\n"
                "KNOWLEDGE：知识类，包括技术教程、行业预测、工具测评等。\n"
                "OPINION：观点类，包括时事评论、行业观察、书评等。\n"
                "LIFESTYLE：生活类，包括成长感悟、随笔、旅行美食等。\n"
                "ENTERTAINMENT：娱乐类，包括吐槽搞笑、迷因、段子等。\n"
                "INTERACTIVE：互动类，包括投票、接龙挑战、测试等。\n"
                "PRODUCT_MARKETING：产品营销类，包括产品介绍、营销活动等。\n"
            ),

            'sentiment_type': '请根据上面给定的文本，总结能文本情绪偏向，正向、中立还是负向，回答的格式为: NEUTRAL or NEGATIVE or POSITIVE',

            'is_hotspot': '请根据上面给定的文本，判断是否为热点话题，热点话题就是在最近两年内热门讨论的话题。回答的格式为: True or False',

            'is_creative': '请根据上面给定的文本，判断是否为创意内容，创意内容是指具有独特性、新颖性、创新性的内容。回答的格式为: True or False'
        }

    def get_init_prompt(self, content_txt: str) -> str:
        return self._prompts['init'].format(content_txt=content_txt)

    def get_tags_prompt(self) -> str:
        return self._prompts['tags']

    def get_post_type_prompt(self) -> str:
        return self._prompts['post_type']

    def get_sentiment_type_prompt(self) -> str:
        return self._prompts['sentiment_type']

    def get_is_hotspot_prompt(self) -> str:
        return self._prompts['is_hotspot']

    def get_is_creative_prompt(self) -> str:
        return self._prompts['is_creative']



class ContentAnalysisOperation(ABC):
    """Abstract base class for content analysis operations."""

    def __init__(self, api_client: APIClient, prompt_manager: PromptManager):
        self._api_client = api_client
        self._prompt_manager = prompt_manager

    @abstractmethod
    def execute(self) -> Any:
        """Execute the content analysis operation."""
        pass

    @abstractmethod
    def parse_response(self, response_text: str) -> Any:
        """Parse the API response text into the expected format."""
        pass


class TagsAnalysisOperation(ContentAnalysisOperation):
    """Operation for extracting tags from content."""

    def execute(self) -> List[str]:
        prompt = self._prompt_manager.get_tags_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(tags): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> List[str]:
        try:
            return ast.literal_eval(str(response_text).strip())
        except Exception as e:
            print(f"Error parsing tags: {e}")
            traceback.print_exc()
            return []


class PostTypeAnalysisOperation(ContentAnalysisOperation):
    """Operation for determining post type from content."""

    def execute(self) -> PostType:
        prompt = self._prompt_manager.get_post_type_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(PostType): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> PostType:
        try:
            return PostType.from_string(str(response_text).strip())
        except Exception as e:
            print(f"Error parsing post type: {e}")
            traceback.print_exc()
            return PostType.NONE


class SentimentAnalysisOperation(ContentAnalysisOperation):
    """Operation for analyzing sentiment from content."""

    def execute(self) -> SentimentType:
        prompt = self._prompt_manager.get_sentiment_type_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(SentimentType): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> SentimentType:
        try:
            return SentimentType.from_string(str(response_text).strip())
        except Exception as e:
            print(f"Error parsing sentiment type: {e}")
            traceback.print_exc()
            return SentimentType.NONE


class HotspotAnalysisOperation(ContentAnalysisOperation):
    """Operation for determining if content is about hotspot topics."""

    def execute(self) -> Optional[bool]:
        prompt = self._prompt_manager.get_is_hotspot_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(is_hotspot): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> Optional[bool]:
        try:
            response_text = str(response_text).strip().lower()
            return response_text == 'true'
        except Exception as e:
            print(f"Error parsing is_hotspot: {e}")
            traceback.print_exc()
            return None


class CreativeAnalysisOperation(ContentAnalysisOperation):
    """Operation for determining if content is creative."""

    def execute(self) -> Optional[bool]:
        prompt = self._prompt_manager.get_is_creative_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(is_creative): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> Optional[bool]:
        try:
            response_text = str(response_text).strip().lower()
            return response_text == 'true'
        except Exception as e:
            print(f"Error parsing is_creative: {e}")
            traceback.print_exc()
            return None


class AIProxy:
    """
    Redesigned AI Proxy class with better separation of concerns.
    Orchestrates content analysis using dedicated components.
    """

    def __init__(self, content_txt: str):
        if not content_txt or not content_txt.strip():
            raise ValueError("Content text cannot be empty")

        self._content_txt = content_txt

        # Initialize configuration
        self._config_manager = ConfigurationManager()
        api_config = self._config_manager.get_api_config()

        # Initialize core components
        self._model_manager = ModelManager(self._config_manager.get_models_pool())
        self._rate_limiter = RateLimiter(self._model_manager.get_current_model())
        self._prompt_manager = PromptManager()
        self._api_client = APIClient(api_config['api_key'])

        # Store configuration
        self._retry_max_num = api_config['retry_max_num']
        self._retry_delay = api_config['retry_delay']

        # Initialize operations
        self._operations = {
            'tags': TagsAnalysisOperation(self._api_client, self._prompt_manager),
            'post_type': PostTypeAnalysisOperation(self._api_client, self._prompt_manager),
            'sentiment': SentimentAnalysisOperation(self._api_client, self._prompt_manager),
            'hotspot': HotspotAnalysisOperation(self._api_client, self._prompt_manager),
            'creative': CreativeAnalysisOperation(self._api_client, self._prompt_manager),
        }

        # Initialize chat
        self._initialize_chat()

    def _api_decorator(self, func):
        """
        Clean API decorator using component-based architecture.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check rate limits
            rate_limit_status = self._rate_limiter.check_and_wait_if_needed()

            # Handle day limit reached - switch model
            if rate_limit_status == RateLimitStatus.DAY_LIMIT_REACHED:
                print('Change model...')
                self._model_manager.update_model()
                self._rate_limiter.reset_for_new_model(self._model_manager.get_current_model())
                self._initialize_chat()
                return wrapper(*args, **kwargs)

            # Handle minute limit reached (already waited in rate limiter)
            elif rate_limit_status == RateLimitStatus.MINUTE_LIMIT_REACHED:
                return wrapper(*args, **kwargs)

            # Proceed with API call
            try:
                # Record the call attempt
                self._rate_limiter.record_call_attempt()

                # Execute the actual function
                ret = func(*args, **kwargs)

                # Record successful call
                self._model_manager.reset_retry_count()
                self._rate_limiter.record_successful_call()

                return ret

            except Exception as e:
                # Handle API call failure
                self._model_manager.increment_retry_count()

                # Check if should switch model based on retry count
                if self._model_manager.should_switch_model(self._retry_max_num):
                    print('Model retry num meets the limit')
                    print('Change model...')

                    self._model_manager.update_model()
                    self._rate_limiter.reset_for_new_model(self._model_manager.get_current_model())
                    self._initialize_chat()

                    return wrapper(*args, **kwargs)

                # Retry after delay
                else:
                    print(f'API Error: {e}')
                    print(f'Error type: {type(e).__name__}')
                    traceback.print_exc()

                    print(f'Sleeping for {self._retry_delay} seconds...')
                    time.sleep(self._retry_delay)
                    print('Retry API')

                    return wrapper(*args, **kwargs)

        return wrapper

    def _initialize_chat(self):
        """Initialize chat with current model."""
        current_model = self._model_manager.get_current_model()
        initial_prompt = self._prompt_manager.get_init_prompt(self._content_txt)

        # Apply decorator to the API client initialization
        decorated_init = self._api_decorator(self._api_client.initialize_chat)
        decorated_init(current_model, initial_prompt)

    def get_tags_from_content_text(self) -> List[str]:
        """Get tags from content text using the tags analysis operation."""
        if not self._api_client.is_chat_initialized():
            raise RuntimeError("Chat not initialized")

        decorated_execute = self._api_decorator(self._operations['tags'].execute)
        return decorated_execute()

    def get_post_type_from_content_text(self) -> PostType:
        """Get post type from content text using the post type analysis operation."""
        if not self._api_client.is_chat_initialized():
            raise RuntimeError("Chat not initialized")

        decorated_execute = self._api_decorator(self._operations['post_type'].execute)
        return decorated_execute()

    def get_sentiment_type_from_content_text(self) -> SentimentType:
        """Get sentiment type from content text using the sentiment analysis operation."""
        if not self._api_client.is_chat_initialized():
            raise RuntimeError("Chat not initialized")

        decorated_execute = self._api_decorator(self._operations['sentiment'].execute)
        return decorated_execute()

    def is_hotspot_from_content_text(self) -> Optional[bool]:
        """Determine if content is about hotspot topics using the hotspot analysis operation."""
        if not self._api_client.is_chat_initialized():
            raise RuntimeError("Chat not initialized")

        decorated_execute = self._api_decorator(self._operations['hotspot'].execute)
        return decorated_execute()

    def is_creative_from_content_text(self) -> Optional[bool]:
        """Determine if content is creative using the creative analysis operation."""
        if not self._api_client.is_chat_initialized():
            raise RuntimeError("Chat not initialized")

        decorated_execute = self._api_decorator(self._operations['creative'].execute)
        return decorated_execute()
