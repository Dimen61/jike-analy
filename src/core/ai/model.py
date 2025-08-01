import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from google import genai

import constants


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
