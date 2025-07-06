import os
import time
import unittest
from unittest.mock import patch

import tests.test_setup  # noqa: F401
import constants
from core.ai.aiproxy import AIProxy, RateLimitStatus
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
        # self.assertIsInstance(post_type, PostType)
        # self.assertNotEqual(post_type, PostType.NONE)
        self.assertEqual(post_type, PostType.KNOWLEDGE)

    def test_get_sentiment_type_from_content_text_integration(self):
        """Test getting sentiment type from content with real AI model."""
        # Test positive sentiment
        positive_content = "这个产品真的太棒了！我非常喜欢它的设计和功能，强烈推荐给大家！"
        proxy = AIProxy(positive_content)

        sentiment = proxy.get_sentiment_type_from_content_text()

        # Verify response
        self.assertEqual(sentiment, SentimentType.POSITIVE)

        # Test negative sentiment
        negative_content = "这个服务太糟糕了，完全不值得购买。浪费时间和金钱。"
        proxy_negative = AIProxy(negative_content)

        sentiment_negative = proxy_negative.get_sentiment_type_from_content_text()
        self.assertEqual(sentiment_negative, SentimentType.NEGATIVE)

    def test_is_hotspot_from_content_text_integration(self):
        """Test hotspot detection from content with real AI model."""
        # Test hotspot content (AI/ChatGPT is definitely a hot topic)
        hotspot_content = "ChatGPT和人工智能的发展正在改变我们的工作方式。大语言模型的应用越来越广泛。"
        proxy = AIProxy(hotspot_content)

        is_hotspot = proxy.is_hotspot_from_content_text()

        # Verify response
        self.assertTrue(is_hotspot)

    def test_is_creative_from_content_text_integration(self):
        """Test creativity detection from content with real AI model."""
        # Test creative content
        creative_content = "在月光下，我看到了一只会说话的猫，它告诉我关于平行宇宙的秘密。这是一个融合了科幻和童话的奇幻故事。"
        proxy = AIProxy(creative_content)

        is_creative = proxy.is_creative_from_content_text()

        # Verify response
        self.assertTrue(is_creative)

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

        # Verify the chat session is maintained (through the APIClient)
        self.assertTrue(proxy._api_client.is_chat_initialized())

    @patch('core.ai.aiproxy.RateLimiter.record_call_attempt')
    @patch('core.ai.aiproxy.RateLimiter.check_and_wait_if_needed', return_value=RateLimitStatus.PROCEED)
    def test_rate_limiting_behavior(self, mock_check_and_wait, mock_record_call):
        """Test that API calls go through the rate limiter and attempts are recorded."""
        content_txt = "测试内容"
        proxy = AIProxy(content_txt)

        # Make a request
        tags = proxy.get_tags_from_content_text()

        # Verify record_call_attempt was called
        self.assertEqual(mock_record_call.call_count, 2)
        self.assertEqual(mock_check_and_wait.call_count, 2)

        # Verify we got a valid response
        self.assertIsInstance(tags, list)

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


if __name__ == '__main__':
    unittest.main()
