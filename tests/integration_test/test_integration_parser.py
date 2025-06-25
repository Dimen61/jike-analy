import json
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

import tests.test_setup  # noqa: F401
from core.crawler import (
    BriefPost,  # BriefPost is a simple data structure for posts
)
from core.data_models import (  # Import necessary data models for mocking
    Author,
    PostType,
    SentimentType,
)
from core.parser import JikeParser, PostDataIO


class TestIntegrationParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up a temporary directory for test artifacts
        cls.test_dir = "temp_test_jike_analy_parser"
        os.makedirs(cls.test_dir, exist_ok=True)
        # Define paths for test files within the temporary directory
        cls.raw_response_path = os.path.join(cls.test_dir, "raw_response_parser.json")
        cls.simple_user_posts_path = os.path.join(cls.test_dir, "simple_user_posts_parser.json")
        # Initialize JikeParser for the tests
        cls.jike_parser = JikeParser()

    @classmethod
    def tearDownClass(cls):
        # Clean up the temporary directory after all tests are done
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        # Clean up files before each test to ensure a clean state
        if os.path.exists(self.raw_response_path):
            os.remove(self.raw_response_path)
        if os.path.exists(self.simple_user_posts_path):
            os.remove(self.simple_user_posts_path)

    def _create_mock_html_response(self, html_content):
        """Helper to create a mock requests response object with HTML content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.raise_for_status.return_value = None
        return mock_response

    @patch('requests.get')
    def test_jike_parser_parse_author_integration(self, mock_get):
        """
        Tests the integration of JikeParser's parse_author method,
        including its internal call to _fetch_page.
        """
        # Mock HTML content for an author's page, matching current JikeParser expectations
        mock_author_html = """
        <html><body>
            <div class='user-screenname'>Test Author Name</div>
            <div class='user-status'>
                <span class='count'>100</span>
                <span class='count'>10k</span>
            </div>
        </body></html>
        """
        mock_get.return_value = self._create_mock_html_response(mock_author_html)

        author_info = self.jike_parser.parse_author("/user/author_id_123") # Use relative path as per JikeParser

        # Assertions
        # JikeParser.parse_author will prepend constants.JIKE_URL
        mock_get.assert_called_once_with("https://m.okjike.com/user/author_id_123", headers=self.jike_parser.headers)
        self.assertIsNotNone(author_info)
        self.assertEqual(author_info.name, "Test Author Name")
        self.assertEqual(author_info.following_num, 100)
        self.assertEqual(author_info.follower_num, 10000)
        self.assertEqual(author_info.url, "https://m.okjike.com/user/author_id_123")


    @patch('requests.get')
    @patch('core.parser.AIProxy', autospec=True) # Corrected AIProxy patch target
    @patch('core.parser.JikeParser.parse_author') # Patch parse_author for this test
    def test_jike_parser_parse_post_integration(self, mock_parse_author, mock_aiproxy, mock_get):
        """
        Tests the integration of JikeParser's parse_post method,
        including its internal calls to _fetch_page and AIProxy.
        """
        # Mock HTML content for a Jike post page, matching parser's expected structure
        # Using `jsx-3930310120 wrap` for content, `like-count` span, `avatar` a tag with `href`
        # and `post-page a.wrap h3` for topic as per parser.py
        mock_post_html = """
        <html><body>
            <div class="jsx-3930310120 wrap">This is a **test** post content. With <a href="#">a link</a>.</div>
            <span class="like-count">999</span>
            <a class="avatar" href="/user/integration_author_id">
                <img class="avatar-img" data-src="http://avatar.jike.com/test_avatar.jpg">
            </a>
            <div class="post-page">
                <a class="wrap">
                    <h3># Integration Topic</h3>
                </a>
            </div>
            </body></html>
        """
        mock_get.return_value = self._create_mock_html_response(mock_post_html)

        # Configure the mocked JikeParser.parse_author method
        # This will be called by _parse_post_author
        mock_parse_author.return_value = Author(
            url="https://m.okjike.com/user/integration_author_id",
            name="Integration Post Author",
            follower_num=1000,
            following_num=50
        )

        # Configure the mocked AIProxy's methods
        mock_aiproxy_instance = mock_aiproxy.return_value
        mock_aiproxy_instance.get_tags_from_content_text.return_value = ["integration-tag", "parser-test"]
        mock_aiproxy_instance.get_post_type_from_content_text.return_value = PostType.KNOWLEDGE
        mock_aiproxy_instance.get_sentiment_type_from_content_text.return_value = SentimentType.NEUTRAL
        mock_aiproxy_instance.is_hotspot_from_content_text.return_value = True
        mock_aiproxy_instance.is_creative_from_content_text.return_value = True

        post_data = self.jike_parser.parse_post(
            title="Mock Post Title",
            link="http://mock.jike.com/post/integration_test_id",
            selected_date="2024-07-22"
        )

        # Assertions
        mock_get.assert_called_once_with("http://mock.jike.com/post/integration_test_id", headers=self.jike_parser.headers)
        self.assertIsNotNone(post_data)
        self.assertEqual(post_data.title, "Mock Post Title")
        self.assertEqual(post_data.link, "http://mock.jike.com/post/integration_test_id")
        self.assertEqual(post_data.selected_date, "2024-07-22")
        self.assertEqual(post_data.content, "This is a **test** post content. With\\na link\\n.\\n")
        self.assertEqual(post_data.like_count, 999)
        self.assertIsNotNone(post_data.author)
        self.assertEqual(post_data.author.name, "Integration Post Author")
        self.assertEqual(post_data.author.url, "https://m.okjike.com/user/integration_author_id") # URL from mocked parse_author
        self.assertEqual(post_data.topic, "# Integration Topic")
        self.assertTrue(post_data.is_hotspot)
        self.assertTrue(post_data.is_creative)
        self.assertListEqual(post_data.tags, ["integration-tag", "parser-test"])
        self.assertEqual(post_data.post_type, PostType.KNOWLEDGE)
        self.assertEqual(post_data.sentiment_type, SentimentType.NEUTRAL)
        self.assertIsNotNone(post_data.content_length_type) # Ensure it's set

        # Verify JikeParser.parse_author was called with the correct path from the mock HTML
        mock_parse_author.assert_called_once_with("https://m.okjike.com/user/integration_author_id")

    def test_post_data_io_dump_and_load_posts_to_json_integration(self):
        """
        Tests the full workflow of dumping posts to JSON and then loading them back,
        simulating a common data persistence scenario.
        """
        posts_to_save = [
            BriefPost(title="First Test Post", link="http://example.com/post1", selected_date="2024-07-20"),
            BriefPost(title="Second Test Post", link="http://example.com/post2", selected_date="2024-07-21")
        ]

        # Dump posts
        PostDataIO.dump_posts_to_json(posts_to_save, self.simple_user_posts_path)

        self.assertTrue(os.path.exists(self.simple_user_posts_path))

        # Load posts
        loaded_posts = PostDataIO.load_posts_from_json(self.simple_user_posts_path)

        # Assertions
        self.assertEqual(len(loaded_posts), len(posts_to_save))
        self.assertEqual(loaded_posts[0].title, "First Test Post")
        self.assertEqual(loaded_posts[0].link, "http://example.com/post1")
        self.assertEqual(loaded_posts[0].selected_date, "2024-07-20")
        self.assertEqual(loaded_posts[1].title, "Second Test Post")
        self.assertEqual(loaded_posts[1].link, "http://example.com/post2")
        self.assertEqual(loaded_posts[1].selected_date, "2024-07-21")

    def test_post_data_io_load_raw_posts_integration(self):
        """
        Tests loading raw JSON response data from a file.
        """
        raw_response_data = [
            {
                "date": "2025年6月20日",
                "title": "好好笑，又抽象又立体",
                "link": "https://m.okjike.com/originalPosts/6853b255058533d925bb8d46"
            },
            {
                "date": "2025年6月20日",
                "title": "刘强东今天传出来的那份内部讲话还是很有水平的",
                "link": "https://m.okjike.com/originalPosts/685292f6f43242116421303d"
            },
            {
                "date": "2025年6月20日",
                "title": "讲一个真实的职场权力斗争",
                "link": "https://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651"
            },
            {
                "date": "2025年6月20日",
                "title": "如果生活在经济上行期，是什么感觉",
                "link": "https://m.okjike.com/originalPosts/6852471adecb244934cfa6de"
            }
        ]

        # Write raw data to a temporary file
        with open(self.raw_response_path, 'w', encoding='utf-8') as f:
            json.dump(raw_response_data, f, ensure_ascii=False, indent=4)

        # Load raw data
        loaded_raw_data = PostDataIO.load_raw_posts(self.raw_response_path)

        # Assertions
        self.assertEqual(len(loaded_raw_data), len(raw_response_data))
        self.assertEqual(loaded_raw_data[0]['title'], "好好笑，又抽象又立体")
        self.assertEqual(loaded_raw_data[2]['date'], "2025年6月20日")


if __name__ == '__main__':
    unittest.main()
