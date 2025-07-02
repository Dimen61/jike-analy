import functools
import time
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from google import genai

from core.ai.analysis import (
    CreativeAnalysisOperation,
    HotspotAnalysisOperation,
    PostTypeAnalysisOperation,
    PromptManager,
    SentimentAnalysisOperation,
    TagsAnalysisOperation,
)
from core.ai.model import AIModel, ConfigurationManager, ModelManager
from core.enums import PostType, SentimentType


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
