import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import tests.test_setup  # noqa: F401
import constants
from core.ai.aiproxy import AIProxy, RateLimiter, RateLimitStatus
from core.ai.model import AIModel, NoAvailableModelError, APIClient, ModelManager, ConfigurationManager
from core.ai.analysis import PromptManager
from core.enums import PostType, SentimentType


class TestAIProxy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set a dummy API key for testing
        os.environ['GEMINI_API_KEY'] = 'dummy_api_key'

    def setUp(self):
        # Mock genai.Client and its methods for APIClient's internal use.
        # This prevents real API calls during tests.
        self.mock_genai_client_instance = MagicMock()
        self.mock_genai_chat_instance = MagicMock()
        self.mock_genai_client_instance.chats.create.return_value = self.mock_genai_chat_instance
        self.mock_genai_chat_instance.send_message.return_value.text = "Mock response from genai"
        self.patcher_genai_client = patch('google.genai.Client', return_value=self.mock_genai_client_instance)
        self.mock_genai_client_class = self.patcher_genai_client.start()

        # Mock external dependencies of AIProxy
        self.mock_config_manager = MagicMock(spec=ConfigurationManager)
        self.mock_model_manager = MagicMock(spec=ModelManager)
        self.mock_rate_limiter = MagicMock(spec=RateLimiter)
        self.mock_prompt_manager = MagicMock(spec=PromptManager)
        self.mock_api_client = MagicMock(spec=APIClient) # This APIClient mock will be returned

        # Configure mock ConfigurationManager
        self.mock_config_manager.get_api_config.return_value = {
            'api_key': 'dummy_api_key',
            'retry_max_num': 3,
            'retry_delay': 60
        }
        self.mock_config_manager.get_models_pool.return_value = [
            AIModel(name="gemini-2.0-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500),
        ]

        # Configure mock ModelManager
        self.mock_model_manager.get_current_model.return_value = self.mock_config_manager.get_models_pool()[0]
        self.mock_model_manager.should_switch_model.return_value = False
        self.mock_model_manager.update_model.return_value = self.mock_config_manager.get_models_pool()[1] # Simulate model switch

        # Configure mock RateLimiter
        self.mock_rate_limiter.check_and_wait_if_needed.return_value = RateLimitStatus.PROCEED

        # Configure mock APIClient methods
        self.mock_api_client.is_chat_initialized.return_value = True # Assume initialized after AIProxy init
        self.mock_api_client.send_message.return_value = MagicMock(text='["mock_tag"]')
        self.mock_api_client.initialize_chat.return_value = MagicMock(text="Initial chat response")

        # Configure mock PromptManager
        self.mock_prompt_manager.get_init_prompt.return_value = "Mock initial prompt"
        self.mock_prompt_manager.get_tags_prompt.return_value = "Mock tags prompt"
        self.mock_prompt_manager.get_post_type_prompt.return_value = "Mock post type prompt"
        self.mock_prompt_manager.get_sentiment_type_prompt.return_value = "Mock sentiment prompt"
        self.mock_prompt_manager.get_is_hotspot_prompt.return_value = "Mock hotspot prompt"
        self.mock_prompt_manager.get_is_creative_prompt.return_value = "Mock creative prompt"


        # Patch the classes that AIProxy instantiates
        self.patcher_config_manager = patch('core.ai.aiproxy.ConfigurationManager', return_value=self.mock_config_manager)
        self.patcher_model_manager = patch('core.ai.aiproxy.ModelManager', return_value=self.mock_model_manager)
        self.patcher_rate_limiter = patch('core.ai.aiproxy.RateLimiter', return_value=self.mock_rate_limiter)
        self.patcher_prompt_manager = patch('core.ai.aiproxy.PromptManager', return_value=self.mock_prompt_manager)
        self.patcher_api_client = patch('core.ai.aiproxy.APIClient', return_value=self.mock_api_client)

        self.mock_config_manager_class = self.patcher_config_manager.start()
        self.mock_model_manager_class = self.patcher_model_manager.start()
        self.mock_rate_limiter_class = self.patcher_rate_limiter.start()
        self.mock_prompt_manager_class = self.patcher_prompt_manager.start()
        self.mock_api_client_class = self.patcher_api_client.start()

    def tearDown(self):
        self.patcher_genai_client.stop() # Stop the genai client patcher
        self.patcher_config_manager.stop()
        self.patcher_model_manager.stop()
        self.patcher_rate_limiter.stop()
        self.patcher_prompt_manager.stop()
        self.patcher_api_client.stop()

    def test_init(self):
        content_txt = "Test content"
        proxy = AIProxy(content_txt)

        self.assertEqual(proxy._content_txt, content_txt)

        # Verify components were initialized
        self.mock_config_manager_class.assert_called_once()
        self.mock_model_manager_class.assert_called_once_with(self.mock_config_manager.get_models_pool.return_value)
        self.mock_rate_limiter_class.assert_called_once_with(self.mock_model_manager.get_current_model.return_value)
        self.mock_prompt_manager_class.assert_called_once()
        self.mock_api_client_class.assert_called_once_with('dummy_api_key')

        # Verify _initialize_chat was called
        self.mock_prompt_manager.get_init_prompt.assert_called_once_with(content_txt)
        self.mock_api_client.initialize_chat.assert_called_once_with(
            self.mock_model_manager.get_current_model.return_value,
            self.mock_prompt_manager.get_init_prompt.return_value
        )
        self.mock_rate_limiter.record_call_attempt.assert_called_once()
        self.mock_model_manager.reset_retry_count.assert_called_once()
        self.mock_rate_limiter.record_successful_call.assert_called_once()

    def test_update_model(self):
        # This test now verifies the internal logic of AIProxy interacting with ModelManager
        # and RateLimiter during a model update scenario.
        content_txt = "Test content"
        proxy = AIProxy(content_txt) # Initialize the proxy

        # Simulate day limit reached, which should trigger a model update
        self.mock_rate_limiter.check_and_wait_if_needed.side_effect = [
            RateLimitStatus.DAY_LIMIT_REACHED,  # First call
            RateLimitStatus.PROCEED,             # Second call
            RateLimitStatus.PROCEED,
        ]

        # Reset call counts on APIClient mock as they get incremented during proxy init
        # We need to ensure we only check for the calls made during the day limit scenario.
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.initialize_chat.reset_mock()
        self.mock_model_manager.update_model.reset_mock()
        # Set the return value for update_model to the expected next model
        self.mock_model_manager.update_model.return_value = AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500)
        self.mock_rate_limiter.reset_for_new_model.reset_mock()

        # Trigger a call that would cause the day limit to be hit and model to update
        proxy.get_tags_from_content_text()

        # Assert ModelManager.update_model was called
        self.mock_model_manager.update_model.assert_called_once()

        # Verify the wrapper called record_call_attempt and record_successful_call for the new attempt
        self.mock_rate_limiter.record_call_attempt.assert_called() # Called by the retry mechanism
        self.mock_model_manager.reset_retry_count.assert_called()
        self.mock_rate_limiter.record_successful_call.assert_called()

        # Test NoAvailableModelError scenario
        self.mock_model_manager.update_model.side_effect = NoAvailableModelError("No more models")
        self.mock_rate_limiter.check_and_wait_if_needed.side_effect = [
            RateLimitStatus.DAY_LIMIT_REACHED,
            RateLimitStatus.PROCEED,
        ]

        with self.assertRaises(NoAvailableModelError):
            proxy.get_tags_from_content_text() # This should now raise the error

    def test_api_decorator_minute_limit(self):
        content_txt = "Test content"
        proxy = AIProxy(content_txt)

        # Reset mocks that were called during proxy init
        self.mock_rate_limiter.check_and_wait_if_needed.reset_mock()
        self.mock_rate_limiter.record_call_attempt.reset_mock()
        self.mock_rate_limiter.record_successful_call.reset_mock()
        self.mock_model_manager.reset_retry_count.reset_mock()
        self.mock_api_client.send_message.reset_mock()

        # Configure RateLimiter to signal minute limit reached on the first check
        self.mock_rate_limiter.check_and_wait_if_needed.side_effect = [
            RateLimitStatus.MINUTE_LIMIT_REACHED, # First call attempt triggers sleep and retry
            RateLimitStatus.PROCEED # Second call attempt proceeds
        ]

        # Call a method that uses the decorator
        proxy.get_tags_from_content_text()

        # Assert check_and_wait_if_needed was called twice (initial check + after sleep)
        self.assertEqual(self.mock_rate_limiter.check_and_wait_if_needed.call_count, 2)

        # Assert that the function (APIClient.send_message) was ultimately called
        self.mock_api_client.send_message.assert_called_once()
        self.mock_rate_limiter.record_call_attempt.assert_called_once()
        self.mock_model_manager.reset_retry_count.assert_called_once()
        self.mock_rate_limiter.record_successful_call.assert_called_once()

    def test_api_decorator_day_limit(self):
        content_txt = "Test content"
        proxy = AIProxy(content_txt)

        # Reset mocks from initial AIProxy setup
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.initialize_chat.reset_mock()
        self.mock_model_manager.update_model.reset_mock()
        self.mock_rate_limiter.reset_for_new_model.reset_mock()
        self.mock_rate_limiter.record_call_attempt.reset_mock()
        self.mock_model_manager.reset_retry_count.reset_mock()
        self.mock_rate_limiter.record_successful_call.reset_mock()


        # Configure RateLimiter to signal day limit reached
        self.mock_rate_limiter.check_and_wait_if_needed.side_effect = [
            RateLimitStatus.DAY_LIMIT_REACHED, # First call attempt triggers model switch
            RateLimitStatus.PROCEED, # Second call attempt proceeds after model switch
            RateLimitStatus.PROCEED
        ]

        # Call a method that uses the decorator
        proxy.get_tags_from_content_text()

        # Assert that model update was triggered
        self.mock_model_manager.update_model.assert_called_once()

        # Assert send_message was ultimately called after model switch
        self.mock_api_client.send_message.assert_called_once_with(self.mock_prompt_manager.get_tags_prompt.return_value)

        # Verify the wrapper called record_call_attempt and record_successful_call for the new attempt
        self.assertEqual(self.mock_rate_limiter.record_call_attempt.call_count, 2)
        self.assertEqual(self.mock_rate_limiter.record_successful_call.call_count, 2)
        self.assertEqual(self.mock_model_manager.reset_retry_count.call_count, 2)

    @patch('time.sleep', MagicMock())
    def test_api_decorator_retry_on_exception(self):
        # Modify the mock configuration for this specific test, ensuring retry_max_num > 1
        self.mock_config_manager.get_api_config.return_value = {
            'api_key': 'test_api_key',
            'retry_max_num': 2,  # Allow one retry before considering model switch
            'retry_delay': 0
        }
        content_txt = "Test content"
        # Instantiate AIProxy - it will use the mocked ConfigurationManager setup above
        proxy = AIProxy(content_txt)

        # Reset mocks from initial AIProxy setup and instantiation within test
        self.mock_rate_limiter.record_call_attempt.reset_mock()
        self.mock_model_manager.increment_retry_count.reset_mock()
        self.mock_model_manager.reset_retry_count.reset_mock()
        self.mock_model_manager.should_switch_model.reset_mock()
        self.mock_api_client.send_message.reset_mock()
        # Reset initialize_chat because AIProxy.__init__ calls it
        self.mock_api_client.initialize_chat.reset_mock()

        # Mock send_message to raise an exception once, then succeed on retry
        self.mock_api_client.send_message.side_effect = [
            Exception("Test API Error - First Call"),
            MagicMock(text="['success_tag']") # Success on retry
        ]

        # Simulate model manager behavior: should_switch_model returns False for the first check
        # This confirms that the model is NOT switched after the first failure.
        self.mock_model_manager.should_switch_model.return_value = False

        # Call the method that triggers the retry logic within the decorator
        tags = proxy.get_tags_from_content_text()

        # Assertions
        # ModelManager.increment_retry_count should be called once (for the first failure)
        self.mock_model_manager.increment_retry_count.assert_called_once()

        # ModelManager.should_switch_model should be called once (to check if retry limit is reached)
        self.mock_model_manager.should_switch_model.assert_called_once_with(
            self.mock_config_manager.get_api_config.return_value['retry_max_num']
        )

        # update_model should not be called if retry_count < MODEL_RETRY_MAX_NUM
        self.mock_model_manager.update_model.assert_not_called()

        # APIClient.initialize_chat should not be called again (since no model switch occurred)
        self.mock_api_client.initialize_chat.assert_not_called()

        # APIClient.send_message should be called twice (initial attempt + one retry)
        self.assertEqual(self.mock_api_client.send_message.call_count, 2)

        # The returned tags should be from the successful retry
        self.assertEqual(tags, ['success_tag'])

        # Reset retry count should be called on success (after the second successful call)
        self.mock_model_manager.reset_retry_count.assert_called_once()


    @patch('time.sleep', MagicMock())
    def test_api_decorator_update_model_on_max_retry(self):
        # Modify the mock configuration for this specific test
        self.mock_config_manager.get_api_config.return_value = {
            'api_key': 'test_api_key',
            'retry_max_num': 1,  # Set retry_max_num to 1 for this test case
            'retry_delay': 0
        }

        # Simulate API client behavior: initial chat response, then an error, then success after model switch
        self.mock_api_client.send_message.side_effect = [
            Exception("API call failed - simulated error for retry"), # First call fails
            MagicMock(text="['success_tag_after_model_switch']")          # Second call (after retry/model switch) succeeds
        ]

        # Simulate model manager behavior: should_switch_model returns True after 1 retry
        self.mock_model_manager.should_switch_model.side_effect = [True]

        # Instantiate AIProxy - it will use the mocked ConfigurationManager setup above
        ai_proxy = AIProxy(content_txt="test content")

        # Call the method that triggers the retry logic within the decorator
        tags = ai_proxy.get_tags_from_content_text()

        # Assertions
        self.assertEqual(tags, ['success_tag_after_model_switch'])
        self.mock_model_manager.increment_retry_count.assert_called_once()
        self.mock_model_manager.should_switch_model.assert_called_once_with(1)
        self.mock_model_manager.update_model.assert_called_once()
        self.assertEqual(self.mock_model_manager.reset_retry_count.call_count, 3)


    def test_get_tags_from_content_text(self):
        content_txt = "这是一篇关于Python编程的文章"
        proxy = AIProxy(content_txt)
        # Reset send_message mock for this specific test after init
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "['Python', '编程', '技术']"

        tags = proxy.get_tags_from_content_text()
        self.assertEqual(tags, ['Python', '编程', '技术'])

        # Verify the prompt for tags was sent
        self.mock_prompt_manager.get_tags_prompt.assert_called_once()
        self.mock_api_client.send_message.assert_called_once_with(self.mock_prompt_manager.get_tags_prompt.return_value)


        # Test invalid response
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "not a list"
        tags = proxy.get_tags_from_content_text()
        self.assertEqual(tags, []) # ast.literal_eval will raise ValueError, caught and return empty list

    def test_get_post_type_from_content_text(self):
        content_txt = "这是一个关于如何使用Django框架的教程"
        proxy = AIProxy(content_txt)
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "KNOWLEDGE"

        post_type = proxy.get_post_type_from_content_text()
        self.assertEqual(post_type, PostType.KNOWLEDGE)

        # Verify the prompt for post type was sent
        self.mock_prompt_manager.get_post_type_prompt.assert_called_once()
        self.mock_api_client.send_message.assert_called_once_with(self.mock_prompt_manager.get_post_type_prompt.return_value)


        # Test invalid response
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "INVALID_TYPE"
        post_type = proxy.get_post_type_from_content_text()
        self.assertEqual(post_type, PostType.NONE)

    def test_get_sentiment_type_from_content_text(self):
        content_txt = "这个产品太棒了，我非常喜欢！"
        proxy = AIProxy(content_txt)
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "POSITIVE"

        sentiment_type = proxy.get_sentiment_type_from_content_text()
        self.assertEqual(sentiment_type, SentimentType.POSITIVE)

        # Verify the prompt for sentiment type was sent
        self.mock_prompt_manager.get_sentiment_type_prompt.assert_called_once()
        self.mock_api_client.send_message.assert_called_once_with(self.mock_prompt_manager.get_sentiment_type_prompt.return_value)


        # Test invalid response
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "UNKNOWN"
        sentiment_type = proxy.get_sentiment_type_from_content_text()
        self.assertEqual(sentiment_type, SentimentType.NONE)

    def test_is_hotspot_from_content_text(self):
        content_txt = "讨论最近AIGC技术的发展"
        proxy = AIProxy(content_txt)
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "True"

        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertTrue(is_hotspot)

        # Verify the prompt for hotspot was sent
        self.mock_prompt_manager.get_is_hotspot_prompt.assert_called_once()
        self.mock_api_client.send_message.assert_called_once_with(self.mock_prompt_manager.get_is_hotspot_prompt.return_value)


        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "False"
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertFalse(is_hotspot)

        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "TRue" # Test case insensitivity
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertTrue(is_hotspot)

        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "NotABool" # Test invalid response
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertFalse(is_hotspot)

    def test_is_creative_from_content_text(self):
        content_txt = "一篇结合诗歌和科幻的独特小说"
        proxy = AIProxy(content_txt)
        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "True"

        is_creative = proxy.is_creative_from_content_text()
        self.assertTrue(is_creative)

        # Verify the prompt for creative was sent
        self.mock_prompt_manager.get_is_creative_prompt.assert_called_once()
        self.mock_api_client.send_message.assert_called_once_with(self.mock_prompt_manager.get_is_creative_prompt.return_value)


        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "False"
        is_creative = proxy.is_creative_from_content_text()
        self.assertFalse(is_creative)

        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "falsE" # Test case insensitivity
        is_creative = proxy.is_creative_from_content_text()
        self.assertFalse(is_creative)

        self.mock_api_client.send_message.reset_mock()
        self.mock_api_client.send_message.return_value.text = "NotABool" # Test invalid response
        is_creative = proxy.is_creative_from_content_text()
        self.assertFalse(is_creative)


if __name__ == '__main__':
    unittest.main()
