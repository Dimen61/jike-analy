import os
import time
import unittest
from unittest.mock import patch

import tests.test_setup  # noqa: F401
import constants
from core.ai.aiproxy import AIProxy
from core.ai.model import AIModel, NoAvailableModelError
from core.enums import PostType, SentimentType


class TestIntegrationAIProxy(unittest.TestCase):
    """
    Integration tests for AIProxy that test real AI model interactions.
    These tests require a valid GEMINI_API_KEY environment variable.
    """

    @classmethod
    def setUpClass(cls):
        # Check if API key is available
        cls.api_key = os.environ.get('GEMINI_API_KEY')
        if not cls.api_key:
            raise unittest.SkipTest("GEMINI_API_KEY environment variable not set. Skipping integration tests.")

        # Set up test constants
        cls.original_retry_max = constants.MODEL_RETRY_MAX_NUM
        constants.MODEL_RETRY_MAX_NUM = 2  # Reduce retry count for faster tests

    @classmethod
    def tearDownClass(cls):
        # Restore original constants
        constants.MODEL_RETRY_MAX_NUM = cls.original_retry_max

    def setUp(self):
        # Reset AIProxy class variables before each test
        # AIProxy.models_pool = [
        #     AIModel(name="gemini-2.0-flash", max_call_num_per_min=30, max_call_num_per_day=1500),
        #     AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500),
        # ]
        # AIProxy.model = AIProxy.models_pool[0]
        # AIProxy.model_retry_count = 0
        # AIProxy.call_count_per_min = 0
        # AIProxy.call_count_per_day = 0
        # AIProxy.last_begin_call_time_per_min = AIProxy.last_success_call_time = AIProxy.last_success_call_time
        pass

    def test_aiproxy_initialization_with_real_api(self):
        """Test that AIProxy can be initialized with real API and send initial message."""
        content_txt = "这是一个关于Python编程的简单介绍文本。"

        # This should work without raising exceptions
        proxy = AIProxy(content_txt)

        # Verify initialization
        self.assertEqual(proxy.content_txt, content_txt)
        self.assertIsNotNone(proxy.client)
        self.assertIsNotNone(proxy.chat)

        # The chat should have been initialized with initial message
        # We can't easily verify the exact response, but the fact it didn't raise an exception is good

    def test_get_tags_from_content_text_integration(self):
        """Test getting tags from content with real AI model."""
        content_txt = "Python是一种高级编程语言，广泛用于Web开发、数据科学和人工智能。它具有简洁的语法和强大的库支持。"
        proxy = AIProxy(content_txt)

        tags = proxy.get_tags_from_content_text()

        # Verify response format and content
        self.assertIsInstance(tags, list)
        self.assertGreater(len(tags), 0, "Should return at least one tag")

        # Check that all tags are strings
        for tag in tags:
            self.assertIsInstance(tag, str)
            self.assertGreater(len(tag.strip()), 0, "Tag should not be empty")

        # Tags should be relevant to the content (Python programming)
        # Note: This is a basic check - actual tags may vary
        tags_str = ' '.join(tags).lower()
        relevant_keywords = ['python', '编程', '语言', '开发', '数据', '人工智能', '技术']
        has_relevant_tag = any(keyword in tags_str for keyword in relevant_keywords)
        self.assertTrue(has_relevant_tag, f"Tags should contain relevant keywords. Got: {tags}")

    def test_get_post_type_from_content_text_integration(self):
        """Test getting post type from content with real AI model."""
        # Test knowledge type content
        knowledge_content = "今天我们来学习如何使用Django框架创建Web应用。首先安装Django：pip install django"
        proxy = AIProxy(knowledge_content)

        post_type = proxy.get_post_type_from_content_text()

        # Verify response
        self.assertIsInstance(post_type, PostType)
        self.assertNotEqual(post_type, PostType.NONE)
        # Knowledge content should likely be classified as KNOWLEDGE
        # Note: AI might classify differently, so we just check it's not NONE

    def test_get_sentiment_type_from_content_text_integration(self):
        """Test getting sentiment type from content with real AI model."""
        # Test positive sentiment
        positive_content = "这个产品真的太棒了！我非常喜欢它的设计和功能，强烈推荐给大家！"
        proxy = AIProxy(positive_content)

        sentiment = proxy.get_sentiment_type_from_content_text()

        # Verify response
        self.assertIsInstance(sentiment, SentimentType)
        self.assertNotEqual(sentiment, SentimentType.NONE)
        # This should likely be positive, but we just verify it's not NONE

        # Test negative sentiment
        negative_content = "这个服务太糟糕了，完全不值得购买。浪费时间和金钱。"
        proxy_negative = AIProxy(negative_content)

        sentiment_negative = proxy_negative.get_sentiment_type_from_content_text()
        self.assertIsInstance(sentiment_negative, SentimentType)
        self.assertNotEqual(sentiment_negative, SentimentType.NONE)

    def test_is_hotspot_from_content_text_integration(self):
        """Test hotspot detection from content with real AI model."""
        # Test hotspot content (AI/ChatGPT is definitely a hot topic)
        hotspot_content = "ChatGPT和人工智能的发展正在改变我们的工作方式。大语言模型的应用越来越广泛。"
        proxy = AIProxy(hotspot_content)

        is_hotspot = proxy.is_hotspot_from_content_text()

        # Verify response
        self.assertIsInstance(is_hotspot, bool)
        # AI/ChatGPT should likely be considered a hotspot, but we just verify it's a boolean

    def test_is_creative_from_content_text_integration(self):
        """Test creativity detection from content with real AI model."""
        # Test creative content
        creative_content = "在月光下，我看到了一只会说话的猫，它告诉我关于平行宇宙的秘密。这是一个融合了科幻和童话的奇幻故事。"
        proxy = AIProxy(creative_content)

        is_creative = proxy.is_creative_from_content_text()

        # Verify response
        self.assertIsInstance(is_creative, bool)
        # This fantastical content should likely be considered creative

    def test_multiple_requests_with_same_proxy(self):
        """Test making multiple requests with the same proxy instance."""
        content_txt = "区块链技术是一种分布式账本技术，具有去中心化、透明和安全的特点。"
        proxy = AIProxy(content_txt)

        # Make multiple requests
        tags = proxy.get_tags_from_content_text()
        post_type = proxy.get_post_type_from_content_text()
        sentiment = proxy.get_sentiment_type_from_content_text()

        # All should return valid responses
        self.assertIsInstance(tags, list)
        self.assertIsInstance(post_type, PostType)
        self.assertIsInstance(sentiment, SentimentType)

        # Verify the chat session is maintained
        self.assertIsNotNone(proxy.chat)

    def test_rate_limiting_behavior(self):
        """Test that rate limiting works correctly with real API calls."""
        content_txt = "测试内容"
        proxy = AIProxy(content_txt)

        # Record initial state
        initial_call_count_min = AIProxy.call_count_per_min
        initial_call_count_day = AIProxy.call_count_per_day

        # Make a request
        tags = proxy.get_tags_from_content_text()

        # Verify counters were incremented
        self.assertGreater(AIProxy.call_count_per_min, initial_call_count_min)
        self.assertGreater(AIProxy.call_count_per_day, initial_call_count_day)

        # Verify we got a valid response
        self.assertIsInstance(tags, list)

    def test_model_switching_on_error(self):
        """Test that model switching works when encountering errors."""
        # This test is tricky because we need to simulate an error condition
        # We'll test the model switching logic by forcing an error scenario

        content_txt = "测试模型切换"

        # Set up a scenario where we have limited models
        AIProxy.models_pool = [
            AIModel(name="gemini-2.0-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=15, max_call_num_per_day=1500),
        ]
        AIProxy.model = AIProxy.models_pool[0]
        AIProxy.call_count_per_day = 0
        AIProxy.call_count_per_min = 0

        proxy = AIProxy(content_txt)

        # This should use the first model
        initial_model_name = AIProxy.model.name

        # Force day limit to trigger model switching
        AIProxy.call_count_per_day = AIProxy.model.max_call_num_per_day

        # Make another request - this should switch models
        tags = proxy.get_tags_from_content_text()

        # Verify model was switched
        self.assertNotEqual(AIProxy.model.name, initial_model_name)
        self.assertIsInstance(tags, list)

    def test_no_available_model_error(self):
        """Test NoAvailableModelError is raised when no models are available."""
        # Set up scenario with only one model
        AIProxy.models_pool = [
            AIModel(name="single-model", max_call_num_per_min=1, max_call_num_per_day=1)
        ]
        AIProxy.model = AIProxy.models_pool[0]

        # This should raise NoAvailableModelError when trying to update
        with self.assertRaises(NoAvailableModelError):
            AIProxy.update_model()

    def test_different_content_types_end_to_end(self):
        """Test end-to-end processing of different content types."""
        test_cases = [
            {
                "content": "如何使用Python进行数据分析：pandas和numpy库的基础教程",
                "expected_type": "technical/knowledge"
            },
            {
                "content": "今天的天气真好，和朋友一起去公园散步，心情特别愉快。生活中的小确幸就是这样。",
                "expected_type": "lifestyle"
            },
            {
                "content": "最近看了一部科幻电影，剧情脑洞大开，特效也很震撼。推荐给喜欢科幻的朋友们。",
                "expected_type": "entertainment/opinion"
            }
        ]

        for i, test_case in enumerate(test_cases):
            with self.subTest(case=i):
                proxy = AIProxy(test_case["content"])

                # Get all analysis results
                tags = proxy.get_tags_from_content_text()
                post_type = proxy.get_post_type_from_content_text()
                sentiment = proxy.get_sentiment_type_from_content_text()
                is_hotspot = proxy.is_hotspot_from_content_text()
                is_creative = proxy.is_creative_from_content_text()

                # Verify all results are valid
                self.assertIsInstance(tags, list)
                self.assertIsInstance(post_type, PostType)
                self.assertIsInstance(sentiment, SentimentType)
                self.assertIsInstance(is_hotspot, bool)
                self.assertIsInstance(is_creative, bool)

                # At least tags should be non-empty for meaningful content
                self.assertGreater(len(tags), 0, f"Should have tags for content: {test_case['content'][:50]}...")

    @patch('time.sleep')  # Speed up tests by mocking sleep
    def test_api_call_timing_and_limits(self, mock_sleep):
        """Test that API call timing and limits work correctly."""
        content_txt = "测试API调用时机"
        proxy = AIProxy(content_txt)

        # Reset counters
        AIProxy.call_count_per_min = 0
        AIProxy.call_count_per_day = 0

        # Make several rapid calls
        for i in range(3):
            tags = proxy.get_tags_from_content_text()
            self.assertIsInstance(tags, list)

        # Verify call counts were tracked
        self.assertEqual(AIProxy.call_count_per_min, 3)
        self.assertEqual(AIProxy.call_count_per_day, 3)


if __name__ == '__main__':
    unittest.main()
