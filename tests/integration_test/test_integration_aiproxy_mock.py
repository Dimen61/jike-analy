import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import tests.test_setup  # noqa: F401
import constants
from core.aiproxy import AIModel, AIProxy, NoAvailableModelError
from core.enums import PostType, SentimentType


class TestIntegrationAIProxyMock(unittest.TestCase):
    """
    Integration tests for AIProxy using mocked API responses.
    These tests verify the full workflow without requiring a real API key.
    """

    @classmethod
    def setUpClass(cls):
        # Set up test environment
        cls.original_retry_max = constants.MODEL_RETRY_MAX_NUM
        constants.MODEL_RETRY_MAX_NUM = 2  # Reduce retry count for faster tests

    @classmethod
    def tearDownClass(cls):
        # Restore original constants
        constants.MODEL_RETRY_MAX_NUM = cls.original_retry_max

    def setUp(self):
        # Reset AIProxy class variables before each test
        AIProxy.models_pool = [
            AIModel(name="gemini-2.0-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500),
            AIModel(name="gemini-1.5-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
        ]
        AIProxy.model = AIProxy.models_pool[0]
        AIProxy.model_retry_count = 0
        AIProxy.call_count_per_min = 0
        AIProxy.call_count_per_day = 0
        AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc)
        AIProxy.last_success_call_time = datetime.now(timezone.utc)

        # Set up mock API key
        os.environ['GEMINI_API_KEY'] = 'test_api_key'

        # Mock genai.Client and its methods
        self.mock_client = MagicMock()
        self.mock_chat = MagicMock()
        self.mock_client.chats.create.return_value = self.mock_chat

        # Patch genai.Client
        self.patcher_genai_client = patch('google.genai.Client', return_value=self.mock_client)
        self.mock_genai_client = self.patcher_genai_client.start()

    def tearDown(self):
        self.patcher_genai_client.stop()
        if 'GEMINI_API_KEY' in os.environ:
            del os.environ['GEMINI_API_KEY']

    def test_full_workflow_content_analysis(self):
        """Test the complete workflow of analyzing content with all methods."""
        content_txt = "Python是一种强大的编程语言，广泛应用于人工智能和数据科学领域。"

        # Set up mock responses for different analysis methods
        mock_responses = {
            "init": MagicMock(text="收到文本，准备分析"),
            "tags": MagicMock(text="['Python', '编程语言', '人工智能', '数据科学']"),
            "post_type": MagicMock(text="KNOWLEDGE"),
            "sentiment": MagicMock(text="NEUTRAL"),
            "hotspot": MagicMock(text="True"),
            "creative": MagicMock(text="False")
        }

        # Configure mock to return different responses based on call order
        self.mock_chat.send_message.side_effect = [
            mock_responses["init"],     # Initial chat setup
            mock_responses["tags"],     # get_tags_from_content_text
            mock_responses["post_type"], # get_post_type_from_content_text
            mock_responses["sentiment"], # get_sentiment_type_from_content_text
            mock_responses["hotspot"],   # is_hotspot_from_content_text
            mock_responses["creative"]   # is_creative_from_content_text
        ]

        # Initialize proxy
        proxy = AIProxy(content_txt)

        # Verify initialization
        self.assertEqual(proxy.content_txt, content_txt)
        self.assertIsNotNone(proxy.client)
        self.assertIsNotNone(proxy.chat)

        # Test all analysis methods
        tags = proxy.get_tags_from_content_text()
        post_type = proxy.get_post_type_from_content_text()
        sentiment = proxy.get_sentiment_type_from_content_text()
        is_hotspot = proxy.is_hotspot_from_content_text()
        is_creative = proxy.is_creative_from_content_text()

        # Verify results
        self.assertEqual(tags, ['Python', '编程语言', '人工智能', '数据科学'])
        self.assertEqual(post_type, PostType.KNOWLEDGE)
        self.assertEqual(sentiment, SentimentType.NEUTRAL)
        self.assertTrue(is_hotspot)
        self.assertFalse(is_creative)

        # Verify API call count tracking
        self.assertEqual(AIProxy.call_count_per_min, 6)  # 1 init + 5 analysis calls
        self.assertEqual(AIProxy.call_count_per_day, 6)

        # Verify all expected prompts were sent
        self.assertEqual(self.mock_chat.send_message.call_count, 6)

    def test_model_switching_integration(self):
        """Test model switching behavior in an integrated scenario."""
        content_txt = "测试模型切换功能"

        # Mock initial response
        self.mock_chat.send_message.return_value = MagicMock(text="初始响应")

        # Initialize proxy with first model
        proxy = AIProxy(content_txt)
        initial_model_name = AIProxy.model.name

        # Force day limit to trigger model switching
        AIProxy.call_count_per_day = AIProxy.model.max_call_num_per_day

        # Mock response for the next call that should trigger model switch
        self.mock_chat.send_message.return_value = MagicMock(text="['测试标签']")

        # This call should trigger model switching
        tags = proxy.get_tags_from_content_text()

        # Verify model was switched
        self.assertNotEqual(AIProxy.model.name, initial_model_name)
        self.assertEqual(tags, ['测试标签'])

        # Verify counters were reset after model switch
        self.assertEqual(AIProxy.call_count_per_day, 2)  # init 1 + 1 new call
        self.assertEqual(AIProxy.model_retry_count, 0)

    @patch('time.sleep')
    def test_rate_limiting_integration(self, mock_sleep):
        """Test rate limiting behavior with multiple rapid calls."""
        content_txt = "测试频率限制"

        # Mock responses
        self.mock_chat.send_message.side_effect = [
            MagicMock(text="初始响应"),  # init
            MagicMock(text="['标签1']"),  # first call
            MagicMock(text="['标签2']"),  # second call (should trigger rate limit)
        ]

        # Initialize proxy
        proxy = AIProxy(content_txt)

        # Set up rate limiting scenario
        AIProxy.call_count_per_min = AIProxy.model.max_call_num_per_min - 1
        AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc) - timedelta(seconds=30)

        # Make a call that should trigger rate limiting
        tags = proxy.get_tags_from_content_text()
        tags = proxy.get_tags_from_content_text()

        # Verify sleep was called for rate limiting
        mock_sleep.assert_called()
        self.assertEqual(tags, ['标签2'])

    @patch('time.sleep')
    def test_error_handling_and_retry_integration(self, mock_sleep):
        """Test error handling and retry mechanism integration."""
        content_txt = "测试错误处理"

        # Mock responses: first call succeeds, second fails then succeeds
        self.mock_chat.send_message.side_effect = [
            MagicMock(text="初始响应"),  # init - success
            Exception("API Error"),      # first analysis - fail
            MagicMock(text="['重试成功']")  # retry - success
        ]

        # Initialize proxy
        proxy = AIProxy(content_txt)

        # Make call that should fail once then succeed
        tags = proxy.get_tags_from_content_text()

        # Verify retry mechanism worked
        self.assertEqual(tags, ['重试成功'])
        mock_sleep.assert_called()  # Should have slept during retry

        # Verify retry count was reset after success
        self.assertEqual(AIProxy.model_retry_count, 0)

    @patch('time.sleep')
    def test_max_retry_model_switching_integration(self, mock_sleep):
        """Test model switching when max retries are reached."""
        content_txt = "测试最大重试后切换模型"

        # Set up responses: init succeeds, then multiple failures, then success after model switch
        self.mock_chat.send_message.side_effect = [
            MagicMock(text="初始响应"),  # init
            Exception("API Error 1"),   # first call - fail
            Exception("API Error 2"),   # retry - fail (triggers model switch)
            MagicMock(text="初始响应"),  # re-init after model switch
            MagicMock(text="['切换成功']") # final success
        ]

        # Initialize proxy
        proxy = AIProxy(content_txt)
        initial_model_name = AIProxy.model.name

        # Set retry count near limit
        AIProxy.model_retry_count = constants.MODEL_RETRY_MAX_NUM - 1

        # Make call that should trigger max retry and model switch
        tags = proxy.get_tags_from_content_text()

        # Verify model was switched and call succeeded
        self.assertNotEqual(AIProxy.model.name, initial_model_name)
        self.assertEqual(tags, ['切换成功'])
        self.assertEqual(AIProxy.model_retry_count, 0)
        mock_sleep.assert_called()  # Should have slept during retry

    def test_no_available_model_integration(self):
        """Test behavior when no models are available."""
        content_txt = "测试无可用模型"

        # Reduce models pool to one
        AIProxy.models_pool = [AIModel(name="only-model", max_call_num_per_min=1, max_call_num_per_day=1)]
        AIProxy.model = AIProxy.models_pool[0]

        # Should raise error when trying to update with no remaining models
        with self.assertRaises(NoAvailableModelError):
            AIProxy.update_model()

    def test_invalid_response_handling_integration(self):
        """Test handling of invalid AI responses in integrated workflow."""
        content_txt = "测试无效响应处理"

        # Mock responses with invalid formats
        self.mock_chat.send_message.side_effect = [
            MagicMock(text="初始响应"),        # init
            MagicMock(text="invalid tags"),   # invalid tags format
            MagicMock(text="INVALID_TYPE"),   # invalid post type
            MagicMock(text="invalid_sentiment"), # invalid sentiment
            MagicMock(text="maybe"),          # invalid boolean
            MagicMock(text="not_boolean")     # invalid boolean
        ]

        # Initialize proxy
        proxy = AIProxy(content_txt)

        # Test all methods with invalid responses
        tags = proxy.get_tags_from_content_text()
        post_type = proxy.get_post_type_from_content_text()
        sentiment = proxy.get_sentiment_type_from_content_text()
        is_hotspot = proxy.is_hotspot_from_content_text()
        is_creative = proxy.is_creative_from_content_text()

        # Verify fallback values are returned
        self.assertEqual(tags, [])  # Empty list for invalid tags
        self.assertEqual(post_type, PostType.NONE)  # NONE for invalid type
        self.assertEqual(sentiment, SentimentType.NONE)  # NONE for invalid sentiment
        self.assertFalse(is_hotspot)  # False for invalid boolean
        self.assertFalse(is_creative)  # False for invalid boolean

    def test_class_variable_persistence_across_instances(self):
        """Test that class variables are properly shared across instances."""
        content_txt_1 = "第一个实例"
        content_txt_2 = "第二个实例"

        # Mock responses
        self.mock_chat.send_message.side_effect = [
            MagicMock(text="响应1"),  # proxy1 init
            MagicMock(text="响应2"),  # proxy2 init
            MagicMock(text="['标签1']"),  # proxy1 call
            MagicMock(text="['标签2']")   # proxy2 call
        ]

        # Create first instance
        proxy1 = AIProxy(content_txt_1)
        call_count_after_first = AIProxy.call_count_per_day

        # Create second instance
        proxy2 = AIProxy(content_txt_2)
        call_count_after_second = AIProxy.call_count_per_day

        # Verify call counts are shared
        self.assertEqual(call_count_after_second, call_count_after_first + 1)

        # Make calls with both instances
        proxy1.get_tags_from_content_text()
        call_count_after_proxy1_call = AIProxy.call_count_per_day

        proxy2.get_tags_from_content_text()
        call_count_after_proxy2_call = AIProxy.call_count_per_day

        # Verify counts continue to be shared
        self.assertEqual(call_count_after_proxy1_call, call_count_after_second + 1)
        self.assertEqual(call_count_after_proxy2_call, call_count_after_proxy1_call + 1)


if __name__ == '__main__':
    unittest.main()
