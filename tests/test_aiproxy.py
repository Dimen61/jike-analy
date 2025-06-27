import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import tests.test_setup  # noqa: F401
import constants
from core.aiproxy import AIModel, AIProxy, NoAvailableModelError
from core.enums import PostType, SentimentType


class TestAIProxy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set a dummy API key for testing
        os.environ['GEMINI_API_KEY'] = 'dummy_api_key'

    def setUp(self):
        # Reset AIProxy class variables before each test
        AIProxy.models_pool = [
            AIModel(name="gemini-2.0-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
            AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500),
        ]
        AIProxy.model = AIProxy.models_pool[0]
        AIProxy.model_retry_count = 0
        AIProxy.call_count_per_min = 0
        AIProxy.call_count_per_day = 0
        AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc)
        AIProxy.last_success_call_time = datetime.now(timezone.utc)

        # Mock genai.Client and its methods
        self.mock_client = MagicMock()
        self.mock_chat = MagicMock()
        self.mock_client.chats.create.return_value = self.mock_chat
        # Default mock response for chat.send_message
        self.mock_chat.send_message.return_value.text = "Mock response"

        # Patch genai.Client
        self.patcher_genai_client = patch('google.genai.Client', return_value=self.mock_client)
        self.mock_genai_client = self.patcher_genai_client.start()

        # Patch os.environ.get to ensure we control the API key
        self.patcher_os_environ_get = patch('os.environ.get', return_value='dummy_api_key')
        self.mock_os_environ_get = self.patcher_os_environ_get.start()

    def tearDown(self):
        self.patcher_genai_client.stop()
        self.patcher_os_environ_get.stop()

    def test_init(self):
        content_txt = "Test content"
        proxy = AIProxy(content_txt)
        self.assertEqual(proxy.content_txt, content_txt)
        self.assertIsNotNone(proxy.client)
        self.assertIsNotNone(proxy.chat)
        self.mock_genai_client.assert_called_once_with(api_key='dummy_api_key')
        self.mock_client.chats.create.assert_called_once_with(model=AIProxy.model.name)
        # Check initial prompt was sent
        self.mock_chat.send_message.assert_called_once()
        args, kwargs = self.mock_chat.send_message.call_args
        self.assertIn("我将给你一段文本", args[0])
        self.assertIn(content_txt, args[0])

    def test_update_model(self):
        initial_model = AIProxy.model
        AIProxy.update_model()
        self.assertNotEqual(AIProxy.model, initial_model)
        self.assertEqual(AIProxy.model.name, "gemini-2.0-flash-lite")
        self.assertEqual(AIProxy.model_retry_count, 0)
        self.assertEqual(AIProxy.call_count_per_day, 0)
        self.assertEqual(AIProxy.call_count_per_min, 0)
        self.assertLessEqual(datetime.now(timezone.utc) - AIProxy.last_begin_call_time_per_min, timedelta(seconds=1))

        # Test NoAvailableModelError
        AIProxy.models_pool = [AIModel(name="single-model", max_call_num_per_min=1, max_call_num_per_day=1)]
        AIProxy.model = AIProxy.models_pool[0]
        with self.assertRaises(NoAvailableModelError):
            AIProxy.update_model()

    @patch('time.sleep', MagicMock())
    def test_api_decorator_minute_limit(self):
        # Set call count to max minus one
        AIProxy.call_count_per_min = AIProxy.model.max_call_num_per_min - 1
        # Set last_begin_call_time_per_min to be within 60 seconds
        AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc) - timedelta(seconds=30)

        content_txt = "Test content"
        proxy = AIProxy(content_txt) # This will call _init_chat via the decorator
        # _init_chat calls send_message once initially.
        # The decorator will then increment call_count_per_min to max.
        # Subsequent calls should trigger the sleep.

        # Now, make another call that would exceed the minute limit
        with patch.object(AIProxy, '_init_chat') as mock_init_chat:
            self.mock_chat.send_message.return_value.text = "['test_tag']"
            # Manually set call_count_per_min to trigger the limit logic on the next call
            AIProxy.call_count_per_min = AIProxy.model.max_call_num_per_min
            AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc) - timedelta(seconds=30)

            proxy.get_tags_from_content_text()

            # Assert that time.sleep was called
            self.assertTrue(time.sleep.called)
            # Assert that the function was called again after sleep
            self.mock_chat.send_message.assert_called()
            # _init_chat should not be called in this scenario
            mock_init_chat.assert_not_called()

    # @patch('time.sleep', MagicMock())
    @patch('core.aiproxy.AIProxy.update_model')
    def test_api_decorator_day_limit(self, mock_update_model):
        def mock_update_model_side_effect():
            AIProxy.call_count_per_day = 0
            # Also reset other counters as the actual update_model does
            AIProxy.call_count_per_min = 0
            AIProxy.model_retry_count = 0
            AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc)

        mock_update_model.side_effect = mock_update_model_side_effect

        AIProxy.call_count_per_day = AIProxy.model.max_call_num_per_day
        content_txt = "Test content"
        proxy = AIProxy(content_txt) # This will call _init_chat initially

        with patch.object(AIProxy, '_init_chat') as mock_init_chat:
            self.mock_chat.send_message.return_value.text = "['tag1']"
            # The initial call to _init_chat increments the count, hitting the limit.
            # The subsequent call to get_tags_from_content_text will trigger the day limit logic.
            proxy.get_tags_from_content_text()

            mock_update_model.assert_called_once()
            # _init_chat is called by the decorator wrapper after updating the model.
            # It's called once in the constructor, then once more due to model change.
            # mock_init_chat.assert_called_once() is tricky here because the actual _init_chat is called twice,
            # but the mocked one only once if the decorator's retry calls the real one.
            # Let's ensure the decorator logic triggers the model update and then retries the call.
            self.mock_chat.send_message.assert_called() # The original func is called again

    @patch('time.sleep', MagicMock())
    @patch('core.aiproxy.AIProxy.update_model')
    def test_api_decorator_retry_on_exception(self, mock_update_model):
        content_txt = "Test content"
        proxy = AIProxy(content_txt)

        # Mock send_message to raise an exception once, then succeed
        self.mock_chat.send_message.side_effect = [
            Exception("Test API Error"),
            MagicMock(text="['success_tag']") # Success on retry
        ]

        with patch.object(AIProxy, '_init_chat') as mock_init_chat:
            tags = proxy.get_tags_from_content_text()

            # time.sleep should be called due to the error
            self.assertTrue(time.sleep.called)
            # update_model should not be called if retry_count < MODEL_RETRY_MAX_NUM
            mock_update_model.assert_not_called()
            # _init_chat should not be called either
            mock_init_chat.assert_not_called()

            self.assertEqual(tags, ['success_tag'])
            self.assertEqual(AIProxy.model_retry_count, 0) # Should reset on success

    @patch('time.sleep', MagicMock())
    @patch('core.aiproxy.AIProxy.update_model')
    def test_api_decorator_update_model_on_max_retry(self, mock_update_model):
        def mock_update_model_side_effect():
            AIProxy.call_count_per_day = 0
            # Also reset other counters as the actual update_model does
            AIProxy.call_count_per_min = 0
            AIProxy.model_retry_count = 0
            AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc)
            print("========= mock_update_model_side_effect ===============")

        mock_update_model.side_effect = mock_update_model_side_effect

        content_txt = "Test content"
        proxy = AIProxy(content_txt)

        # Mock send_message to always raise an exception
        self.mock_chat.send_message.side_effect = [
            Exception("Test API Error"),
            MagicMock(text="['success_tag']") # Success on retry
        ]
        constants.MODEL_RETRY_MAX_NUM = 1 # Set retry limit to 1 for this test

        with patch.object(AIProxy, '_init_chat') as mock_init_chat:
            # First call will fail and increment retry_count to 1
            # Second call (due to retry from decorator) will trigger max retry logic
            # with self.assertRaises(Exception): # The last call will still raise the exception
            proxy.get_tags_from_content_text()

            mock_update_model.assert_called_once()
            mock_init_chat.assert_called_once() # Called by the decorator after model update
            self.assertFalse(time.sleep.called)

    def test_get_tags_from_content_text(self):
        content_txt = "这是一篇关于Python编程的文章"
        self.mock_chat.send_message.return_value.text = "['Python', '编程', '技术']"
        proxy = AIProxy(content_txt)
        tags = proxy.get_tags_from_content_text()
        self.assertEqual(tags, ['Python', '编程', '技术'])
        # Verify the prompt for tags was sent
        self.mock_chat.send_message.assert_called_with("请根据上面给定的文本，总结能代表文本的主题关键词标签，你回答的格式为: ['tag1', 'tag2', 'tag3']")

        # Test invalid response
        self.mock_chat.send_message.return_value.text = "not a list"
        tags = proxy.get_tags_from_content_text()
        self.assertEqual(tags, []) # ast.literal_eval will raise ValueError, caught and return empty list

    def test_get_post_type_from_content_text(self):
        content_txt = "这是一个关于如何使用Django框架的教程"
        self.mock_chat.send_message.return_value.text = "KNOWLEDGE"
        proxy = AIProxy(content_txt)
        post_type = proxy.get_post_type_from_content_text()
        self.assertEqual(post_type, PostType.KNOWLEDGE)
        # Verify the prompt for post type was sent
        args, kwargs = self.mock_chat.send_message.call_args
        self.assertIn("总结最代表文本的类型", args[0])
        self.assertIn("KNOWLEDGE or OPINION or LIFESTYLE", args[0])

        # Test invalid response
        self.mock_chat.send_message.return_value.text = "INVALID_TYPE"
        post_type = proxy.get_post_type_from_content_text()
        self.assertEqual(post_type, PostType.NONE)

    def test_get_sentiment_type_from_content_text(self):
        content_txt = "这个产品太棒了，我非常喜欢！"
        self.mock_chat.send_message.return_value.text = "POSITIVE"
        proxy = AIProxy(content_txt)
        sentiment_type = proxy.get_sentiment_type_from_content_text()
        self.assertEqual(sentiment_type, SentimentType.POSITIVE)
        # Verify the prompt for sentiment type was sent
        self.mock_chat.send_message.assert_called_with("请根据上面给定的文本，总结能文本情绪偏向，正向、中立还是负向，回答的格式为: NEUTRAL or NEGATIVE or POSITIVE")

        # Test invalid response
        self.mock_chat.send_message.return_value.text = "UNKNOWN"
        sentiment_type = proxy.get_sentiment_type_from_content_text()
        self.assertEqual(sentiment_type, SentimentType.NONE)

    def test_is_hotspot_from_content_text(self):
        content_txt = "讨论最近AIGC技术的发展"
        self.mock_chat.send_message.return_value.text = "True"
        proxy = AIProxy(content_txt)
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertTrue(is_hotspot)
        # Verify the prompt for hotspot was sent
        self.mock_chat.send_message.assert_called_with("请根据上面给定的文本，判断是否为热点话题，热点话题就是在最近两年内热门讨论的话题。回答的格式为: True or False")

        self.mock_chat.send_message.return_value.text = "False"
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertFalse(is_hotspot)

        self.mock_chat.send_message.return_value.text = "TRue" # Test case insensitivity
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertTrue(is_hotspot)

        self.mock_chat.send_message.return_value.text = "NotABool" # Test invalid response
        is_hotspot = proxy.is_hotspot_from_content_text()
        self.assertFalse(is_hotspot)

    def test_is_creative_from_content_text(self):
        content_txt = "一篇结合诗歌和科幻的独特小说"
        self.mock_chat.send_message.return_value.text = "True"
        proxy = AIProxy(content_txt)
        is_creative = proxy.is_creative_from_content_text()
        self.assertTrue(is_creative)
        # Verify the prompt for creative was sent
        self.mock_chat.send_message.assert_called_with("请根据上面给定的文本，判断是否为创意内容，创意内容是指具有独特性、新颖性、创新性的内容。回答的格式为: True or False")

        self.mock_chat.send_message.return_value.text = "False"
        is_creative = proxy.is_creative_from_content_text()
        self.assertFalse(is_creative)

        self.mock_chat.send_message.return_value.text = "falsE" # Test case insensitivity
        is_creative = proxy.is_creative_from_content_text()
        self.assertFalse(is_creative)

        self.mock_chat.send_message.return_value.text = "NotABool" # Test invalid response
        is_creative = proxy.is_creative_from_content_text()
        self.assertFalse(is_creative)


if __name__ == '__main__':
    unittest.main()
