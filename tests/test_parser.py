import json  # noqa: I001
import unittest
from unittest.mock import MagicMock, mock_open, patch

from bs4 import BeautifulSoup
from requests.exceptions import HTTPError, RequestException

import tests.test_setup  # Ensures src is in path is added to sys.path
import constants
from core.aiproxy import AIProxy
from core.data_models import Author, Post
from core.enums import ContentLengthType, PostType, SentimentType
from core.parser import JikeParser, PostDataIO


class TestJikeParser(unittest.TestCase):

    def setUp(self):
        self.parser = JikeParser()
        self.post_link = "https://m.okjike.com/originalPosts/test_post"
        self.author_link_path = "/users/test_author_id"
        self.author_url = constants.JIKE_URL + self.author_link_path

        self.mock_post_html_content = """
        <html><body>
            <div class='jsx-3930310120 wrap'>First line of content.<br/>Second line.</div>
            <div class='jsx-3930310120 wrap'>Another paragraph.</div>
            <span class='like-count'>123</span>
            <a class='avatar' href='/users/test_author_id'></a>
            <div class='post-page'>
                <a class='wrap'><h3>Test Topic</h3></a>
            </div>
        </body></html>
        """
        self.mock_soup_post = BeautifulSoup(self.mock_post_html_content, 'html.parser')

        self.mock_author_html_content = """
        <html><body>
            <div class='user-screenname'>Test Author Name</div>
            <div class='user-status'>
                <span class='count'>100</span>
                <span class='count'>10k</span>
            </div>
        </body></html>
        """
        self.mock_soup_author = BeautifulSoup(self.mock_author_html_content, 'html.parser')

    def test_init(self):
        self.assertIsInstance(self.parser.headers, dict)
        self.assertIn("User-Agent", self.parser.headers)

    @patch('requests.get')
    def test_fetch_page_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        soup = self.parser._fetch_page("http://example.com")
        mock_get.assert_called_once_with("http://example.com", headers=self.parser.headers)
        mock_response.raise_for_status.assert_called_once()
        self.assertIsInstance(soup, BeautifulSoup)
        self.assertEqual(soup.find('body').text, 'Test')

    @patch('requests.get')
    def test_fetch_page_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(HTTPError):
            self.parser._fetch_page("http://example.com/nonexistent")

    @patch('requests.get')
    def test_fetch_page_request_exception(self, mock_get):
        mock_get.side_effect = RequestException("Network unreachable")

        with self.assertRaises(RequestException):
            self.parser._fetch_page("http://example.com")

    @patch('core.parser.JikeParser._fetch_page')
    @patch('core.parser.JikeParser._parse_follower_num', side_effect=lambda x: int(float(x.replace('k', '')) * 1000) if 'k' in x else int(x))
    def test_parse_author_success(self, mock_parse_follower_num, mock_fetch_page):
        mock_fetch_page.return_value = self.mock_soup_author
        author = self.parser.parse_author(self.author_url)

        mock_fetch_page.assert_called_once_with(self.author_url)
        self.assertIsInstance(author, Author)
        self.assertEqual(author.url, self.author_url)
        self.assertEqual(author.name, "Test Author Name")
        self.assertEqual(author.follower_num, 10000)  # 10k -> 10000
        self.assertEqual(author.following_num, 100)
        self.assertEqual(mock_parse_follower_num.call_count, 2)

    @patch('core.parser.JikeParser._fetch_page')
    def test_parse_author_no_name_or_counts(self, mock_fetch_page):
        mock_fetch_page.return_value = BeautifulSoup("<html><body></body></html>", 'html.parser')
        author = self.parser.parse_author(self.author_url)

        self.assertIsInstance(author, Author)
        self.assertEqual(author.url, self.author_url)
        self.assertIsNone(author.name)
        self.assertIsNone(author.follower_num)
        self.assertIsNone(author.following_num)

    @patch('core.parser.JikeParser._fetch_page', side_effect=RequestException("Failed to fetch"))
    def test_parse_author_fetch_failure(self, mock_fetch_page):
        author = self.parser.parse_author(self.author_url)
        self.assertIsNone(author)

    def test_parse_follower_num(self):
        self.assertEqual(self.parser._parse_follower_num("123"), 123)
        self.assertEqual(self.parser._parse_follower_num("5k"), 5000)
        self.assertEqual(self.parser._parse_follower_num("5K"), 5000)
        self.assertEqual(self.parser._parse_follower_num("0"), 0)
        self.assertEqual(self.parser._parse_follower_num(""), 0)
        self.assertEqual(self.parser._parse_follower_num("invalid"), 0)
        self.assertEqual(self.parser._parse_follower_num("1.5k"), 1500)

    @patch('core.parser.JikeParser._fetch_page')
    @patch('core.parser.JikeParser._parse_post_content_text')
    @patch('core.parser.JikeParser._parse_post_like_count')
    @patch('core.parser.JikeParser._parse_post_author')
    @patch('core.parser.JikeParser._parse_post_topic')
    @patch('core.parser.AIProxy') # Mock the AIProxy class itself
    def test_parse_post_success(self, MockAIProxy, mock_parse_topic, mock_parse_author,
                                mock_parse_like_count, mock_parse_content_text, mock_fetch_page):
        mock_fetch_page.return_value = self.mock_soup_post
        mock_parse_content_text.return_value = "This is some test content."
        mock_parse_like_count.return_value = 500
        mock_parse_author.return_value = Author("test_url", "Test Author")
        mock_parse_topic.return_value = "Test Topic"

        # Mock AIProxy instance and its methods
        mock_aiproxy_instance = MagicMock(spec=AIProxy)
        mock_aiproxy_instance.get_tags_from_content_text.return_value = ["tag1", "tag2"]
        mock_aiproxy_instance.get_post_type_from_content_text.return_value = PostType.KNOWLEDGE
        mock_aiproxy_instance.get_sentiment_type_from_content_text.return_value = SentimentType.POSITIVE
        mock_aiproxy_instance.is_hotspot_from_content_text.return_value = True
        mock_aiproxy_instance.is_creative_from_content_text.return_value = False
        MockAIProxy.return_value = mock_aiproxy_instance # Return the mocked instance

        post_title = "Test Post Title"
        selected_date = "2024-07-27"
        post = self.parser.parse_post(post_title, self.post_link, selected_date)

        mock_fetch_page.assert_called_once_with(self.post_link)
        mock_parse_content_text.assert_called_once_with(self.mock_soup_post)
        mock_parse_like_count.assert_called_once_with(self.mock_soup_post)
        mock_parse_author.assert_called_once_with(self.mock_soup_post)
        mock_parse_topic.assert_called_once_with(self.mock_soup_post)

        MockAIProxy.assert_called_once_with("This is some test content.")
        mock_aiproxy_instance.get_tags_from_content_text.assert_called_once()
        mock_aiproxy_instance.get_post_type_from_content_text.assert_called_once()
        mock_aiproxy_instance.get_sentiment_type_from_content_text.assert_called_once()
        mock_aiproxy_instance.is_hotspot_from_content_text.assert_called_once()
        mock_aiproxy_instance.is_creative_from_content_text.assert_called_once()

        self.assertIsInstance(post, Post)
        self.assertEqual(post.title, post_title)
        self.assertEqual(post.link, self.post_link)
        self.assertEqual(post.selected_date, selected_date)
        self.assertEqual(post.content, "This is some test content.")
        self.assertEqual(post.content_length_type, ContentLengthType.SHORT) # Length is 26
        self.assertEqual(post.tags, ["tag1", "tag2"])
        self.assertEqual(post.topic, "Test Topic")
        self.assertEqual(post.author.name, "Test Author")
        self.assertEqual(post.like_count, 500)
        self.assertEqual(post.post_type, PostType.KNOWLEDGE)
        self.assertEqual(post.sentiment_type, SentimentType.POSITIVE)
        self.assertEqual(post.is_hotspot, True)
        self.assertEqual(post.is_creative, False)

    @patch('core.parser.JikeParser._fetch_page', side_effect=RequestException("Fetch failed"))
    def test_parse_post_fetch_failure(self, mock_fetch_page):
        post = self.parser.parse_post("Title", "link", "date")
        self.assertIsNone(post)

    def test_parse_post_content_text_success(self):
        content = self.parser._parse_post_content_text(self.mock_soup_post)
        # Verify that <br/> is replaced by newline and multiple divs are concatenated
        self.assertEqual(content, "First line of content.\\nSecond line.\\nAnother paragraph.\\n")

    def test_parse_post_content_text_no_content_div(self):
        soup = BeautifulSoup("<html><body>No content here.</body></html>", 'html.parser')
        content = self.parser._parse_post_content_text(soup)
        self.assertIsNone(content)

    def test_parse_post_content_text_empty_content_div(self):
        soup = BeautifulSoup("<html><body><div class='jsx-3930310120 wrap'></div></body></html>", 'html.parser')
        content = self.parser._parse_post_content_text(soup)
        self.assertIsNone(content) # Stripped text will be empty

    def test_parse_post_like_count_success(self):
        like_count = self.parser._parse_post_like_count(self.mock_soup_post)
        self.assertEqual(like_count, 123)

    def test_parse_post_like_count_zero(self):
        soup = BeautifulSoup("<html><body><span class='like-count'>0</span></body></html>", 'html.parser')
        like_count = self.parser._parse_post_like_count(soup)
        self.assertEqual(like_count, 0)

    def test_parse_post_like_count_empty_string(self):
        soup = BeautifulSoup("<html><body><span class='like-count'></span></body></html>", 'html.parser')
        like_count = self.parser._parse_post_like_count(soup)
        self.assertEqual(like_count, 0)

    def test_parse_post_like_count_no_span(self):
        soup = BeautifulSoup("<html><body>No likes here.</body></html>", 'html.parser')
        like_count = self.parser._parse_post_like_count(soup)
        self.assertIsNone(like_count)

    def test_parse_post_like_count_invalid_string(self):
        soup = BeautifulSoup("<html><body><span class='like-count'>abc</span></body></html>", 'html.parser')
        like_count = self.parser._parse_post_like_count(soup)
        self.assertIsNone(like_count) # Should catch ValueError and return None

    @patch('core.parser.JikeParser.parse_author')
    def test_parse_post_author_success(self, mock_parse_author):
        mock_parse_author.return_value = Author("test_url", "Test Author")
        author = self.parser._parse_post_author(self.mock_soup_post)
        mock_parse_author.assert_called_once_with(self.author_url)
        self.assertIsInstance(author, Author)
        self.assertEqual(author.name, "Test Author")

    @patch('core.parser.JikeParser.parse_author')
    def test_parse_post_author_no_avatar(self, mock_parse_author):
        soup = BeautifulSoup("<html><body></body></html>", 'html.parser')
        author = self.parser._parse_post_author(soup)
        mock_parse_author.assert_not_called()
        self.assertIsNone(author)

    @patch('core.parser.JikeParser.parse_author', return_value=None)
    def test_parse_post_author_sub_parse_fails(self, mock_parse_author):
        author = self.parser._parse_post_author(self.mock_soup_post)
        mock_parse_author.assert_called_once_with(self.author_url)
        self.assertIsNone(author)

    def test_parse_post_topic_success(self):
        topic = self.parser._parse_post_topic(self.mock_soup_post)
        self.assertEqual(topic, "Test Topic")

    def test_parse_post_topic_no_topic(self):
        soup = BeautifulSoup("<html><body><div class='post-page'></div></body></html>", 'html.parser')
        topic = self.parser._parse_post_topic(soup)
        self.assertIsNone(topic)

    # Tests for AIProxy dependent methods
    @patch('core.aiproxy.AIProxy.get_tags_from_content_text')
    def test_parse_post_tags_success(self, mock_get_tags):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_get_tags.return_value = ["tag1", "tag2"]
        mock_aiproxy.get_tags_from_content_text = mock_get_tags
        tags = self.parser._parse_post_tags(mock_aiproxy)
        mock_get_tags.assert_called_once()
        self.assertEqual(tags, ["tag1", "tag2"])

    @patch('core.aiproxy.AIProxy.get_tags_from_content_text', side_effect=Exception("AI error"))
    def test_parse_post_tags_aiproxy_error(self, mock_get_tags):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_aiproxy.get_tags_from_content_text = mock_get_tags
        tags = self.parser._parse_post_tags(mock_aiproxy)
        self.assertEqual(tags, []) # Should return empty list on error

    def test_parse_post_tags_no_aiproxy(self):
        tags = self.parser._parse_post_tags(None)
        self.assertEqual(tags, [])

    @patch('core.aiproxy.AIProxy.is_hotspot_from_content_text')
    def test_parse_post_is_hotspot_success(self, mock_is_hotspot):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_is_hotspot.return_value = True
        mock_aiproxy.is_hotspot_from_content_text = mock_is_hotspot
        is_hotspot = self.parser._parse_post_is_hotspot(mock_aiproxy)
        mock_is_hotspot.assert_called_once()
        self.assertTrue(is_hotspot)

    @patch('core.aiproxy.AIProxy.is_hotspot_from_content_text', side_effect=Exception("AI error"))
    def test_parse_post_is_hotspot_aiproxy_error(self, mock_is_hotspot):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_aiproxy.is_hotspot_from_content_text = mock_is_hotspot
        is_hotspot = self.parser._parse_post_is_hotspot(mock_aiproxy)
        self.assertIsNone(is_hotspot)

    @patch('core.aiproxy.AIProxy.is_creative_from_content_text')
    def test_parse_post_is_creative_success(self, mock_is_creative):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_is_creative.return_value = True
        mock_aiproxy.is_creative_from_content_text = mock_is_creative
        is_creative = self.parser._parse_post_is_creative(mock_aiproxy)
        mock_is_creative.assert_called_once()
        self.assertTrue(is_creative)

    @patch('core.aiproxy.AIProxy.is_creative_from_content_text', side_effect=Exception("AI error"))
    def test_parse_post_is_creative_aiproxy_error(self, mock_is_creative):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_aiproxy.is_creative_from_content_text = mock_is_creative
        is_creative = self.parser._parse_post_is_creative(mock_aiproxy)
        self.assertIsNone(is_creative)

    @patch('core.aiproxy.AIProxy.get_post_type_from_content_text')
    def test_parse_post_type_success(self, mock_get_post_type):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_get_post_type.return_value = PostType.ENTERTAINMENT
        mock_aiproxy.get_post_type_from_content_text = mock_get_post_type
        post_type = self.parser._parse_post_type(mock_aiproxy)
        mock_get_post_type.assert_called_once()
        self.assertEqual(post_type, PostType.ENTERTAINMENT)

    @patch('core.aiproxy.AIProxy.get_post_type_from_content_text', side_effect=Exception("AI error"))
    def test_parse_post_type_aiproxy_error(self, mock_get_post_type):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_aiproxy.get_post_type_from_content_text = mock_get_post_type
        post_type = self.parser._parse_post_type(mock_aiproxy)
        self.assertEqual(post_type, PostType.NONE)

    @patch('core.aiproxy.AIProxy.get_sentiment_type_from_content_text')
    def test_parse_post_sentiment_type_success(self, mock_get_sentiment_type):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_get_sentiment_type.return_value = SentimentType.NEUTRAL
        mock_aiproxy.get_sentiment_type_from_content_text = mock_get_sentiment_type
        sentiment_type = self.parser._parse_post_sentiment_type(mock_aiproxy)
        mock_get_sentiment_type.assert_called_once()
        self.assertEqual(sentiment_type, SentimentType.NEUTRAL)

    @patch('core.aiproxy.AIProxy.get_sentiment_type_from_content_text', side_effect=Exception("AI error"))
    def test_parse_post_sentiment_type_aiproxy_error(self, mock_get_sentiment_type):
        mock_aiproxy = MagicMock(spec=AIProxy)
        mock_aiproxy.get_sentiment_type_from_content_text = mock_get_sentiment_type
        sentiment_type = self.parser._parse_post_sentiment_type(mock_aiproxy)
        self.assertEqual(sentiment_type, SentimentType.NONE)


class TestPostDataIO(unittest.TestCase):

    def setUp(self):
        self.test_posts = [
            Post("Title 1", "link1", "2024-01-01", "Content 1", ContentLengthType.SHORT, ["tag1"], "topic1", Author("auth_url1", "Author1", 100, 50), 10, PostType.KNOWLEDGE, SentimentType.POSITIVE, True, False),
            Post("Title 2", "link2", "2024-01-02", "Content 2", ContentLengthType.MEDIUM, ["tag2"], "topic2", Author("auth_url2", "Author2", 200, 100), 20, PostType.OPINION, SentimentType.NEUTRAL, False, True)
        ]
        self.test_raw_posts_data = [
            {"title": "Raw Title 1", "link": "raw_link1", "date": "2024-01-03"},
            {"title": "Raw Title 2", "link": "raw_link2", "date": "2024-01-04"}
        ]
        self.mock_json_file = "mock_posts.json"
        self.mock_raw_json_file = "mock_raw_posts.json"
        self.mock_invalid_json_file = "invalid.json"

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_dump_posts_to_json(self, mock_json_dump, mock_file_open):
        PostDataIO.dump_posts_to_json(self.test_posts, self.mock_json_file)

        mock_file_open.assert_called_once_with(self.mock_json_file, 'w', encoding='utf-8')
        mock_json_dump.assert_called_once()
        # Verify the data passed to json.dump
        dumped_data = mock_json_dump.call_args[0][0]
        self.assertEqual(len(dumped_data), 2)
        self.assertEqual(dumped_data[0]['title'], "Title 1")
        self.assertEqual(dumped_data[0]['post_type'], "KNOWLEDGE") # Check enum conversion
        self.assertEqual(dumped_data[0]['author']['name'], "Author1") # Check nested author

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_load_posts_from_json_success(self, mock_json_load, mock_file_open):
        # Prepare the data that json.load would return
        mock_data_for_load = [post.to_dict() for post in self.test_posts]
        mock_json_load.return_value = mock_data_for_load

        loaded_posts = PostDataIO.load_posts_from_json(self.mock_json_file)

        mock_file_open.assert_called_once_with(self.mock_json_file, 'r', encoding='utf-8')
        mock_json_load.assert_called_once()
        self.assertEqual(len(loaded_posts), 2)
        self.assertIsInstance(loaded_posts[0], Post)
        self.assertEqual(loaded_posts[0].title, "Title 1")
        self.assertEqual(loaded_posts[0].post_type, PostType.KNOWLEDGE) # Check enum reconversion
        self.assertEqual(loaded_posts[0].author.name, "Author1") # Check nested author reconversion

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_load_posts_from_json_missing_author_or_enums(self, mock_json_load, mock_file_open):
        # Simulate data with missing author and invalid enum string
        mock_data_for_load = [
            {
                'title': "Title 1", 'link': "link1", 'selected_date': "2024-01-01", 'content': "Content 1",
                'content_length_type': "SHORT", 'tags': ["tag1"], 'topic': "topic1", 'author': None,
                'like_count': 10, 'post_type': "INVALID_TYPE", 'sentiment_type': "POSITIVE",
                'is_hotspot': True, 'is_creative': False
            },
            {
                'title': "Title 2", 'link': "link2", 'selected_date': "2024-01-02", 'content': "Content 2",
                'content_length_type': "MEDIUM", 'tags': ["tag2"], 'topic': "topic2",
                'like_count': 20, 'post_type': "OPINION", 'sentiment_type': "NEUTRAL",
                'is_hotspot': False, 'is_creative': True # author is implicitly None here
            }
        ]
        mock_json_load.return_value = mock_data_for_load

        loaded_posts = PostDataIO.load_posts_from_json(self.mock_json_file)

        self.assertEqual(len(loaded_posts), 2)
        self.assertIsNone(loaded_posts[0].author)
        self.assertEqual(loaded_posts[0].post_type, PostType.NONE) # Should fallback to NONE for invalid enum
        self.assertIsNone(loaded_posts[1].author) # Implicitly None
        self.assertEqual(loaded_posts[1].post_type, PostType.OPINION)

    def test_load_posts_from_json_file_not_found(self):
        loaded_posts = PostDataIO.load_posts_from_json(self.mock_json_file)
        self.assertEqual(loaded_posts, [])

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load', side_effect=json.JSONDecodeError("Bad JSON", "doc", 0))
    def test_load_posts_from_json_decode_error(self, mock_json_load, mock_file_open):
        loaded_posts = PostDataIO.load_posts_from_json(self.mock_json_file)
        mock_file_open.assert_called_once_with(self.mock_json_file, 'r', encoding='utf-8')
        mock_json_load.assert_called_once()
        self.assertEqual(loaded_posts, [])

    @patch('builtins.open', new_callable=mock_open)
    def test_load_raw_posts_success(self, mock_file_open):
        with patch('json.load', return_value=self.test_raw_posts_data) as mock_json_load:
            raw_posts = PostDataIO.load_raw_posts(self.mock_raw_json_file)

            mock_file_open.assert_called_once_with(self.mock_raw_json_file, 'r', encoding='utf-8')
            mock_json_load.assert_called_once()
            self.assertEqual(raw_posts, self.test_raw_posts_data)

    def test_load_raw_posts_file_not_found(self):
        raw_posts = PostDataIO.load_raw_posts(self.mock_raw_json_file)
        self.assertEqual(raw_posts, [])

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "doc", 0))
    def test_load_raw_posts_json_decode_error(self, mock_json_load, mock_file_open):
        raw_posts = PostDataIO.load_raw_posts(self.mock_raw_json_file)
        mock_file_open.assert_called_once_with(self.mock_raw_json_file, 'r', encoding='utf-8')
        mock_json_load.assert_called_once()
        self.assertEqual(raw_posts, [])


if __name__ == '__main__':
    unittest.main()
