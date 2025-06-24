import json  # noqa: I001
import unittest
from unittest.mock import MagicMock, mock_open, patch
from requests.exceptions import HTTPError, RequestException

import tests.test_setup  # noqa: F401
import constants
from core.crawler import (
    BriefPost,
    crawl_posts,
    extract_data_v1,
    extract_post_content,
    fetch_jike_data,
    load_checkpoint,
)

# Sample data for mocking
MOCK_API_RESPONSE_SUCCESS = {
  "success": True,
  "data": [
    {
      "actionTime": "2025-06-19T23:05:18.000Z",
      "id": "685497ae21698a42e54cc102",
      "type": "ORIGINAL_POST",
      "content": "2025年6月20日\n🌍资讯快读\n1、小米以约6.35亿元拿下北京亦庄新城一宗工业用地\nhttps://www.jiemian.com/article/12927878.html\n2、已有1600余名中国公民从伊朗安全撤离，数百名中国公民从以色列撤离\nhttps://www.jiemian.com/article/12926681.html\n3、国家禁毒办决定将尼秦类物质和12种新精神活性物质纳入管制\nhttps://www.jiemian.com/article/12926577.html\n4、网传上海“国补”停发消息不实\nhttps://www.jiemian.com/article/12925203.html\n\n👬即刻镇小报\n1、好好笑，又抽象又立体\nhttps://m.okjike.com/originalPosts/6853b255058533d925bb8d46\n2、刘强东今天传出来的那份内部讲话还是很有水平的\nhttps://m.okjike.com/originalPosts/685292f6f43242116421303d\n3、讲一个真实的职场权力斗争\nhttps://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651\n4、如果生活在经济上行期，是什么感觉\nhttps://m.okjike.com/originalPosts/6852471adecb244934cfa6de\n\n今日即刻镇小报内容来自 @兔撕鸡大老爷 @阑夕ོ @读书耕田 @广屿Ocean ，感谢以上即友的创作与分享。",
        "loadMoreKey": {"lastId": "12345"},
    }
  ],
  "loadMoreKey": {
      "lastId": "685497ae1fa39e9e7df066ed"
  }
}

MOCK_API_RESPONSE_NO_NEXT_PAGE = {
    "data": [
        {
            "content": "2024-07-25\n\n1、Sample Title 1\nhttps://example.com/link1"
        },
    ],
}

MOCK_API_RESPONSE_EMPTY_DATA = {
    "data": [],
    "loadMoreKey": None,
}

MOCK_BRIEF_POSTS = [
    BriefPost("Sample Title 1", "https://example.com/link1", "2024-07-25"),
    BriefPost("Sample Title 2", "https://example.com/link2", "2024-07-25"),
]

MOCK_CHECKPOINT_DATA = {
    "last_id": "123456",
    "date_count": 5,
    "total_user_posts": [post.to_dict() for post in MOCK_BRIEF_POSTS],
}


# Patching constants globally for all tests in this class
@patch.object(constants, 'JIKE_API_URL', 'http://mock-api.com/data')
@patch.object(constants, 'GRAPHQL_PAYLOAD_JSON_FILE', 'mock_payload.json')
@patch.object(constants, 'RAW_RESPONSE_FILE_FROM_JIKE', 'mock_raw_response.json')
@patch.object(constants, 'SIMPLE_USER_POSTS_FILE', 'mock_user_posts.json')
@patch.object(constants, 'CHECKPOINT_FILE', 'mock_checkpoint.json')
@patch.object(constants, 'JIKE_ACCESS_TOKEN', 'mock_access_token')
class TestCrawler(unittest.TestCase):

    # Tests for fetch_jike_data
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_fetch_jike_data_success(self, mock_json_dump, mock_file_open, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_API_RESPONSE_SUCCESS
        mock_post.return_value = mock_response

        result = fetch_jike_data(10)

        mock_post.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_file_open.assert_called_once_with(constants.RAW_RESPONSE_FILE_FROM_JIKE, 'wt', encoding='utf-8')
        mock_json_dump.assert_called_once_with(MOCK_API_RESPONSE_SUCCESS, mock_file_open(), indent=2, ensure_ascii=False)
        self.assertEqual(result, MOCK_API_RESPONSE_SUCCESS)

    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    @patch('time.sleep') # Patch sleep during retries
    def test_fetch_jike_data_http_error(self, mock_sleep, mock_json_dump, mock_file_open, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("Bad Request")
        mock_post.return_value = mock_response

        result = fetch_jike_data(10)

        # Check retries (1 initial + 2 retries)
        self.assertEqual(mock_post.call_count, 3)
        self.assertIsNone(result)
        mock_file_open.assert_not_called() # No successful response to save
        mock_json_dump.assert_not_called()
        self.assertEqual(mock_sleep.call_count, 2) # Sleep called between retries

    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    @patch('time.sleep') # Patch sleep during retries
    def test_fetch_jike_data_request_exception(self, mock_sleep, mock_json_dump, mock_file_open, mock_post):
        mock_post.side_effect = RequestException("Network error")

        result = fetch_jike_data(10)

        # Check retries
        self.assertEqual(mock_post.call_count, 3)
        self.assertIsNone(result)
        mock_file_open.assert_not_called()
        mock_json_dump.assert_not_called()
        self.assertEqual(mock_sleep.call_count, 2) # Sleep called between retries

    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_fetch_jike_data_json_decode_error(self, mock_json_dump, mock_file_open, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # The JSONDecodeError happens when calling .json()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_post.return_value = mock_response

        result = fetch_jike_data(10)

        self.assertIsNone(result)
        # file should still be opened and dump attempted before the JSON error on .json() call
        mock_file_open.assert_called_once_with(constants.RAW_RESPONSE_FILE_FROM_JIKE, 'wt', encoding='utf-8')
        mock_json_dump.assert_not_called()

    # Tests for extract_post_content
    def test_extract_post_content_valid_data(self):
        content = MOCK_API_RESPONSE_SUCCESS["data"][0]["content"]
        brief_posts = extract_post_content(content)

        self.assertEqual(len(brief_posts), 8)
        self.assertEqual(brief_posts[0].title, "小米以约6.35亿元拿下北京亦庄新城一宗工业用地")
        self.assertEqual(brief_posts[0].link, "https://www.jiemian.com/article/12927878.html")
        self.assertEqual(brief_posts[0].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[0].type, BriefPost.PostType.NEWS)

        self.assertEqual(brief_posts[1].title, "已有1600余名中国公民从伊朗安全撤离，数百名中国公民从以色列撤离")
        self.assertEqual(brief_posts[1].link, "https://www.jiemian.com/article/12926681.html")
        self.assertEqual(brief_posts[1].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[1].type, BriefPost.PostType.NEWS)

        self.assertEqual(brief_posts[2].title, "国家禁毒办决定将尼秦类物质和12种新精神活性物质纳入管制")
        self.assertEqual(brief_posts[2].link, "https://www.jiemian.com/article/12926577.html")
        self.assertEqual(brief_posts[2].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[2].type, BriefPost.PostType.NEWS)

        self.assertEqual(brief_posts[3].title, "网传上海“国补”停发消息不实")
        self.assertEqual(brief_posts[3].link, "https://www.jiemian.com/article/12925203.html")
        self.assertEqual(brief_posts[3].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[3].type, BriefPost.PostType.NEWS)

        self.assertEqual(brief_posts[4].title, "好好笑，又抽象又立体")
        self.assertEqual(brief_posts[4].link, "https://m.okjike.com/originalPosts/6853b255058533d925bb8d46")
        self.assertEqual(brief_posts[4].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[4].type, BriefPost.PostType.USER_POST)

        self.assertEqual(brief_posts[5].title, "刘强东今天传出来的那份内部讲话还是很有水平的")
        self.assertEqual(brief_posts[5].link, "https://m.okjike.com/originalPosts/685292f6f43242116421303d")
        self.assertEqual(brief_posts[5].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[5].type, BriefPost.PostType.USER_POST)

        self.assertEqual(brief_posts[6].title, "讲一个真实的职场权力斗争")
        self.assertEqual(brief_posts[6].link, "https://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651")
        self.assertEqual(brief_posts[6].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[6].type, BriefPost.PostType.USER_POST)

        self.assertEqual(brief_posts[7].title, "如果生活在经济上行期，是什么感觉")
        self.assertEqual(brief_posts[7].link, "https://m.okjike.com/originalPosts/6852471adecb244934cfa6de")
        self.assertEqual(brief_posts[7].selected_date, "2025年6月20日")
        self.assertEqual(brief_posts[7].type, BriefPost.PostType.USER_POST)

    def test_extract_post_content_only_date(self):
        content = "2025年6月20日\n\n"
        brief_posts = extract_post_content(content)

        self.assertEqual(len(brief_posts), 0)

    def test_extract_post_content_malformed_missing_link(self):
        content = "2025年6月20日\n🌍资讯快读\n1、小米以约6.35亿元拿下北京亦庄新城一宗工业用地"
        brief_posts = extract_post_content(content)

        self.assertEqual(len(brief_posts), 0)

    def test_extract_post_content_empty(self):
        content = ""
        brief_posts = extract_post_content(content)

        self.assertEqual(len(brief_posts), 0)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps(MOCK_CHECKPOINT_DATA))
    @patch('json.load', return_value=MOCK_CHECKPOINT_DATA)
    def test_load_checkpoint_exists(self, mock_json_load, mock_file_open, mock_exists):
        last_id, date_count, total_user_posts = load_checkpoint()

        mock_exists.assert_called_once_with(constants.CHECKPOINT_FILE)
        mock_file_open.assert_called_once_with(constants.CHECKPOINT_FILE, 'rt', encoding='utf-8')
        mock_json_load.assert_called_once() # json.load is called on the file handle from mock_file_open
        self.assertEqual(last_id, "123456")
        self.assertEqual(date_count, 5)
        self.assertEqual(len(total_user_posts), len(MOCK_BRIEF_POSTS))
        # Check that BriefPost objects are correctly created
        self.assertEqual(total_user_posts[0].title, MOCK_BRIEF_POSTS[0].title)


    @patch('os.path.exists', return_value=False)
    @patch('builtins.open', new_callable=mock_open) # Mocked but shouldn't be called
    @patch('json.load') # Mocked but shouldn't be called
    def test_load_checkpoint_not_exists(self, mock_json_load, mock_file_open, mock_exists):
        last_id, date_count, total_user_posts = load_checkpoint()

        mock_exists.assert_called_once_with(constants.CHECKPOINT_FILE)
        mock_file_open.assert_not_called()
        mock_json_load.assert_not_called()
        self.assertIsNone(last_id)
        self.assertEqual(date_count, 0)
        self.assertEqual(total_user_posts, [])

    # Tests for extract_data_v1
    def test_extract_data_v1_success(self):
        user_post_groups, news_groups, last_id = extract_data_v1(MOCK_API_RESPONSE_SUCCESS)

        # MOCK_API_RESPONSE_SUCCESS contains one data item (one original post content)
        # This one content item contains both news and user posts.
        # Thus, we expect one group for user posts and one group for news posts.
        self.assertEqual(len(user_post_groups), 1)
        self.assertEqual(len(news_groups), 1)
        self.assertEqual(last_id, MOCK_API_RESPONSE_SUCCESS.get("loadMoreKey", {}).get("lastId", None))

        # Check content of user post group
        # MOCK_API_RESPONSE_SUCCESS has 4 user posts in its content
        self.assertEqual(len(user_post_groups[0]), 4)
        self.assertEqual(user_post_groups[0][0].title, "好好笑，又抽象又立体")
        self.assertEqual(user_post_groups[0][1].title, "刘强东今天传出来的那份内部讲话还是很有水平的")
        self.assertEqual(user_post_groups[0][2].title, "讲一个真实的职场权力斗争")
        self.assertEqual(user_post_groups[0][3].title, "如果生活在经济上行期，是什么感觉")

        # Check content of news group
        # MOCK_API_RESPONSE_SUCCESS has 4 news items in its content
        self.assertEqual(len(news_groups[0]), 4)
        self.assertEqual(news_groups[0][0].title, "小米以约6.35亿元拿下北京亦庄新城一宗工业用地")
        self.assertEqual(news_groups[0][1].title, "已有1600余名中国公民从伊朗安全撤离，数百名中国公民从以色列撤离")
        self.assertEqual(news_groups[0][2].title, "国家禁毒办决定将尼秦类物质和12种新精神活性物质纳入管制")
        self.assertEqual(news_groups[0][3].title, "网传上海“国补”停发消息不实")

    def test_extract_data_v1_no_next_page(self):
        user_post_groups, news_groups, last_id = extract_data_v1(MOCK_API_RESPONSE_NO_NEXT_PAGE)

        self.assertEqual(len(user_post_groups), 1)
        self.assertEqual(len(news_groups), 1)
        self.assertIsNone(last_id)

    def test_extract_data_v1_empty_data(self):
        user_post_groups, news_groups, last_id = extract_data_v1(MOCK_API_RESPONSE_EMPTY_DATA)

        self.assertEqual(len(user_post_groups), 0)
        self.assertEqual(len(news_groups), 0)
        self.assertIsNone(last_id)

    # Tests for crawl_posts
    @patch('core.crawler.load_checkpoint')
    @patch('core.crawler.fetch_jike_data')
    @patch('core.crawler.extract_data_v1')
    @patch('core.crawler.save_posts')
    @patch('core.crawler.save_checkpoint')
    @patch('core.crawler.display_posts_groups')
    @patch('os.remove')
    @patch('time.sleep')
    def test_crawl_posts_completes(self, mock_time_sleep, mock_os_remove, mock_display_posts_groups, mock_save_checkpoint, mock_save_posts, mock_extract_data_v1, mock_fetch_jike_data, mock_load_checkpoint):
        mock_load_checkpoint.return_value = (None, 0, []) # Start fresh

        # Simulate fetching data for 2 dates
        api_response_page1 = {
            "data": [{"content": "2024-07-25\n\n1、Title 1\nhttp://link1"}],
            "loadMoreKey": {"lastId": "id1"},
        }
        api_response_page2 = {
            "data": [{"content": "2024-07-24\n\n1、Title 2\nhttp://link2"}],
            "loadMoreKey": None,
        }

        # Configure fetch_jike_data to return different responses on successive calls
        mock_fetch_jike_data.side_effect = [api_response_page1, api_response_page2]

        # Configure extract_data_v1 based on the responses
        extracted_data_page1 = ([[BriefPost("Title 1", "http://link1", "2024-07-25")]], [], "id1")
        extracted_data_page2 = ([[BriefPost("Title 2", "http://link2", "2024-07-24")]], [], None)
        mock_extract_data_v1.side_effect = [extracted_data_page1, extracted_data_page2]

        crawl_posts(total_date_num=2)

        mock_load_checkpoint.assert_called_once()
        self.assertEqual(mock_fetch_jike_data.call_count, 2) # Called twice to get 2 dates
        self.assertEqual(mock_extract_data_v1.call_count, 2)
        self.assertEqual(mock_save_posts.call_count, 2) # Called after each successful fetch
        self.assertEqual(mock_save_checkpoint.call_count, 2) # Called after each successful fetch
        self.assertEqual(mock_display_posts_groups.call_count, 2)
        mock_os_remove.assert_called_once_with(constants.CHECKPOINT_FILE) # Checkpoint removed at the end
        self.assertEqual(mock_time_sleep.call_count, 2) # Sleep after each fetch

    @patch('core.crawler.load_checkpoint')
    @patch('core.crawler.fetch_jike_data')
    @patch('core.crawler.extract_data_v1')
    @patch('core.crawler.save_posts')
    @patch('core.crawler.save_checkpoint')
    @patch('core.crawler.display_posts_groups')
    @patch('os.remove')
    @patch('time.sleep')
    def test_crawl_posts_resumes_from_checkpoint(self, mock_time_sleep, mock_os_remove, mock_display_posts_groups, mock_save_checkpoint, mock_save_posts, mock_extract_data_v1, mock_fetch_jike_data, mock_load_checkpoint):
        initial_posts = [BriefPost("Existing Title", "http://existing.link", "2024-07-26")]
        mock_load_checkpoint.return_value = ("resume_id", 1, initial_posts) # Load from checkpoint

        # Simulate fetching data for 1 more date to reach total_date_num = 2
        api_response_page2 = {
            "data": [{"content": "2024-07-24\n\n1、Title 2\nhttp://link2"}],
            "loadMoreKey": None,
        }
        mock_fetch_jike_data.return_value = api_response_page2

        extracted_data_page2 = ([[BriefPost("Title 2", "http://link2", "2024-07-24")]], [], None)
        mock_extract_data_v1.return_value = extracted_data_page2

        crawl_posts(total_date_num=2)

        mock_load_checkpoint.assert_called_once()
        # Should request remaining 1 date, starting from resume_id
        mock_fetch_jike_data.assert_called_once_with(1, "resume_id")
        mock_extract_data_v1.assert_called_once_with(api_response_page2)
        mock_save_posts.assert_called_once() # Called once after the fetch
        # Check that save_posts was called with initial_posts + new posts
        saved_posts_arg = mock_save_posts.call_args[0][0]
        self.assertEqual(len(saved_posts_arg), 2)
        self.assertEqual(saved_posts_arg[0].title, "Existing Title")
        self.assertEqual(saved_posts_arg[1].title, "Title 2")

        mock_save_checkpoint.assert_called_once() # Called once after the fetch
        # Check that save_checkpoint was called with updated state
        saved_checkpoint_args = mock_save_checkpoint.call_args[0]
        self.assertIsNone(saved_checkpoint_args[0]) # last_id from the last fetch
        self.assertEqual(saved_checkpoint_args[1], 2) # date_count = 1 (loaded) + 1 (fetched)
        self.assertEqual(len(saved_checkpoint_args[2]), 2) # total_user_posts = 1 (loaded) + 1 (fetched)

        mock_display_posts_groups.assert_called_once()
        mock_os_remove.assert_called_once_with(constants.CHECKPOINT_FILE)
        mock_time_sleep.assert_called_once()

    @patch('core.crawler.load_checkpoint', return_value=(None, 0, []))
    @patch('core.crawler.fetch_jike_data', return_value=None)
    @patch('core.crawler.extract_data_v1')
    @patch('core.crawler.save_posts')
    @patch('core.crawler.save_checkpoint')
    @patch('core.crawler.display_posts_groups')
    @patch('os.remove')
    @patch('time.sleep') # Patch sleep to ensure it's not called on fetch failure
    def test_crawl_posts_fetch_fails(self, mock_time_sleep, mock_os_remove, mock_display_posts_groups, mock_save_checkpoint, mock_save_posts, mock_extract_data_v1, mock_fetch_jike_data, mock_load_checkpoint):
        crawl_posts(total_date_num=5)

        mock_load_checkpoint.assert_called_once()
        mock_fetch_jike_data.assert_called_once() # Called once, returns None
        mock_extract_data_v1.assert_not_called()
        mock_save_posts.assert_not_called()
        # Checkpoint should be saved with the state *before* the failed fetch
        mock_save_checkpoint.assert_not_called()
        mock_display_posts_groups.assert_not_called()
        mock_os_remove.assert_not_called()
        mock_time_sleep.assert_not_called() # No sleep if fetch fails immediately


if __name__ == '__main__':
    unittest.main()
