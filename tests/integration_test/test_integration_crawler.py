import json  # noqa: I001
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import RequestException

import tests.test_setup  # noqa: F401
import constants
from core.crawler import (
    BriefPost,
    crawl_posts,
    load_checkpoint,
    save_checkpoint,
    save_posts,
)


class TestIntegrationCrawler(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up a temporary directory for test artifacts
        cls.test_dir = "temp_test_jike_analy"
        os.makedirs(cls.test_dir, exist_ok=True)
        # Redirect constants to use the temporary directory
        constants.RAW_RESPONSE_FILE_FROM_JIKE = os.path.join(cls.test_dir, "raw_response.json")
        constants.SIMPLE_USER_POSTS_FILE = os.path.join(cls.test_dir, "user_posts.json")
        constants.CHECKPOINT_FILE = os.path.join(cls.test_dir, "checkpoint.json")

    @classmethod
    def tearDownClass(cls):
        # Clean up the temporary directory
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        # Clean up files before each test
        if os.path.exists(constants.RAW_RESPONSE_FILE_FROM_JIKE):
            os.remove(constants.RAW_RESPONSE_FILE_FROM_JIKE)
        if os.path.exists(constants.SIMPLE_USER_POSTS_FILE):
            os.remove(constants.SIMPLE_USER_POSTS_FILE)
        if os.path.exists(constants.CHECKPOINT_FILE):
            os.remove(constants.CHECKPOINT_FILE)

    def _create_mock_response(self, content_list, last_id=None):
        data: list[dict] = []
        for content in content_list:
            data.append({"content": content})

        mock_json_response: dict = {
            "data": data
        }
        if last_id:
            mock_json_response["loadMoreKey"] = {"lastId": last_id}
        else:
            mock_json_response["loadMoreKey"] = None # Simulate no more pages

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_json_response
        mock_response.raise_for_status.return_value = None
        return mock_response

    @patch('requests.post')
    @patch('time.sleep', return_value=None) # Mock time.sleep to speed up tests
    def test_crawl_posts_integrates_all_components(self, mock_sleep, mock_post):
        """
        Tests the full crawl_posts workflow, including fetching, parsing,
        saving, and checkpointing over multiple iterations.
        """
        # Mock responses for two pages of data
        mock_post.side_effect = [
            self._create_mock_response(
                [
                    "2024-07-20\n\n1、Title One\nhttp://link1.com\n2、Title Two\nhttp://link2.com",
                    "2024-07-19\n\n1、Title Three\nhttp://link3.com",
                ],
                last_id="page1_last_id"
            ),
            self._create_mock_response(
                [
                    "2025年6月20日\n🌍资讯快读\n1、小米以约6.35亿元拿下北京亦庄新城一宗工业用地\nhttps://www.jiemian.com/article/12927878.html\n2、已有1600余名中国公民从伊朗安全撤离，数百名中国公民从以色列撤离\nhttps://www.jiemian.com/article/12926681.html\n3、国家禁毒办决定将尼秦类物质和12种新精神活性物质纳入管制\nhttps://www.jiemian.com/article/12926577.html\n4、网传上海“国补”停发消息不实\nhttps://www.jiemian.com/article/12925203.html\n\n👬即刻镇小报\n1、好好笑，又抽象又立体\nhttps://m.okjike.com/originalPosts/6853b255058533d925bb8d46\n2、刘强东今天传出来的那份内部讲话还是很有水平的\nhttps://m.okjike.com/originalPosts/685292f6f43242116421303d\n3、讲一个真实的职场权力斗争\nhttps://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651\n4、如果生活在经济上行期，是什么感觉\nhttps://m.okjike.com/originalPosts/6852471adecb244934cfa6de\n\n今日即刻镇小报内容来自 @兔撕鸡大老爷 @阑夕ོ @读书耕田 @广屿Ocean ，感谢以上即友的创作与分享。",
                ],
                last_id=None # No more pages
            )
        ]

        # Call the main function
        crawl_posts(total_date_num=3)

        # Assertions
        # 1. Check if requests.post was called correctly
        self.assertEqual(mock_post.call_count, 2)
        # Verify the first call
        first_call_args, first_call_kwargs = mock_post.call_args_list[0]
        self.assertIn(constants.JIKE_API_URL, first_call_args)
        self.assertIn('json', first_call_kwargs)
        self.assertEqual(first_call_kwargs['json']['limit'], 3)
        self.assertNotIn('loadMoreKey', first_call_kwargs['json']) # No checkpoint

        # Verify the second call with last_id
        second_call_args, second_call_kwargs = mock_post.call_args_list[1]
        self.assertIn(constants.JIKE_API_URL, second_call_args)
        self.assertIn('json', second_call_kwargs)
        self.assertEqual(second_call_kwargs['json']['limit'], 3-2) # Remaining dates
        self.assertEqual(second_call_kwargs['json']['loadMoreKey']['lastId'], "page1_last_id")

        # 2. Check if user posts were saved correctly
        self.assertTrue(os.path.exists(constants.SIMPLE_USER_POSTS_FILE))
        with open(constants.SIMPLE_USER_POSTS_FILE, 'r', encoding='utf-8') as f:
            saved_posts = json.load(f)
        self.assertEqual(len(saved_posts), 4) # 2 from first, 1 from second, total unique posts
        self.assertIn({'date': '2025年6月20日', 'title': '讲一个真实的职场权力斗争', 'link': 'https://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651'}, saved_posts)

        # 3. Check checkpointing: should be removed at the end
        self.assertFalse(os.path.exists(constants.CHECKPOINT_FILE))

        # 4. Check raw response file (last fetched)
        self.assertTrue(os.path.exists(constants.RAW_RESPONSE_FILE_FROM_JIKE))
        with open(constants.RAW_RESPONSE_FILE_FROM_JIKE, 'r', encoding='utf-8') as f:
            raw_response = json.load(f)
        self.assertEqual(len(raw_response['data']), 1) # Last response had 1 post

    @patch('requests.post')
    @patch('time.sleep', return_value=None)
    def test_crawl_posts_resumes_from_checkpoint_integration(self, mock_sleep, mock_post):
        """
        Tests if crawl_posts correctly resumes from a previously saved checkpoint.
        """
        # Simulate an existing checkpoint
        initial_posts = [
            BriefPost("Existing Title 1", "http://existing1.com", "2024-07-22"),
            BriefPost("Existing Title 2", "http://existing2.com", "2024-07-21")
        ]
        save_checkpoint("initial_last_id", 2, initial_posts) # 2 dates already processed

        # Mock response for the continuation
        mock_post.return_value = self._create_mock_response(
            [
                "2025年6月20日\n🌍资讯快读\n1、小米以约6.35亿元拿下北京亦庄新城一宗工业用地\nhttps://www.jiemian.com/article/12927878.html\n2、已有1600余名中国公民从伊朗安全撤离，数百名中国公民从以色列撤离\nhttps://www.jiemian.com/article/12926681.html\n3、国家禁毒办决定将尼秦类物质和12种新精神活性物质纳入管制\nhttps://www.jiemian.com/article/12926577.html\n4、网传上海“国补”停发消息不实\nhttps://www.jiemian.com/article/12925203.html\n\n👬即刻镇小报\n1、好好笑，又抽象又立体\nhttps://m.okjike.com/originalPosts/6853b255058533d925bb8d46\n2、刘强东今天传出来的那份内部讲话还是很有水平的\nhttps://m.okjike.com/originalPosts/685292f6f43242116421303d\n3、讲一个真实的职场权力斗争\nhttps://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651\n4、如果生活在经济上行期，是什么感觉\nhttps://m.okjike.com/originalPosts/6852471adecb244934cfa6de\n\n今日即刻镇小报内容来自 @兔撕鸡大老爷 @阑夕ོ @读书耕田 @广屿Ocean ，感谢以上即友的创作与分享。",
            ],
            last_id=None
        )

        # Call the main function to crawl for 3 dates total
        crawl_posts(total_date_num=3)

        # Assertions
        # 1. Check if requests.post was called with the correct last_id from checkpoint
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['loadMoreKey']['lastId'], "initial_last_id")
        self.assertEqual(kwargs['json']['limit'], 1) # 3 total - 2 existing = 1 remaining

        # 2. Check if all posts (initial + new) are saved
        self.assertTrue(os.path.exists(constants.SIMPLE_USER_POSTS_FILE))
        with open(constants.SIMPLE_USER_POSTS_FILE, 'r', encoding='utf-8') as f:
            saved_posts = json.load(f)
        self.assertEqual(len(saved_posts), 2+4)
        self.assertIn({'date': '2025年6月20日', 'title': '讲一个真实的职场权力斗争', 'link': 'https://m.okjike.com/originalPosts/6852747f2d05f8d12aea4651'}, saved_posts)

        # 3. Check checkpointing: should be removed at the end
        self.assertFalse(os.path.exists(constants.CHECKPOINT_FILE))

    @patch('requests.post', side_effect=RequestException("Simulated Network Error"))
    @patch('time.sleep', return_value=None)
    def test_crawl_posts_handles_fetch_failure(self, mock_sleep, mock_post):
        """
        Tests if crawl_posts gracefully handles a complete fetch failure
        and leaves the checkpoint in place.
        """
        # Call the main function
        crawl_posts(total_date_num=1)

        # Assertions
        # 1. requests.post should be called multiple times due to retries (max_retries=3)
        self.assertEqual(mock_post.call_count, 3)

        # 2. No user posts should be saved if no data was ever successfully fetched
        self.assertFalse(os.path.exists(constants.SIMPLE_USER_POSTS_FILE))

        # 3. Checkpoint file should exist if the crawl was interrupted due to fetch failure
        # (It gets written at the end of each successful iteration, or loaded from start.
        # If no data is ever fetched, date_count doesn't increment, so loop breaks,
        # and checkpoint isn't removed because crawl didn't complete successfully.)
        # If it was a first run, it won't exist. If it was resumed, it will.
        # For this test, it's a fresh run, so it shouldn't exist.
        self.assertFalse(os.path.exists(constants.CHECKPOINT_FILE))

        # Test case where a checkpoint exists and then failure happens
        initial_posts = [
            BriefPost("Existing Title 1", "http://existing1.com", "2024-07-22")
        ]
        save_checkpoint("initial_last_id", 1, initial_posts)

        mock_post.reset_mock() # Reset mock call count for the next part
        mock_post.side_effect = RequestException("Simulated Network Error again") # Re-set side effect

        crawl_posts(total_date_num=2) # Try to get 2 dates, but only 1 exists, and fetching next fails

        # requests.post should be called multiple times due to retries
        self.assertEqual(mock_post.call_count, 3)

        # Checkpoint file should still exist
        self.assertTrue(os.path.exists(constants.CHECKPOINT_FILE))
        last_id, date_count, total_user_posts = load_checkpoint()
        self.assertEqual(last_id, "initial_last_id")
        self.assertEqual(date_count, 1)


if __name__ == '__main__':
    unittest.main()
