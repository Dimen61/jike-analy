import unittest

import tests.test_setup  # noqa: F401
from core.data_models import Author, BriefPost, Post
from core.enums import ContentLengthType, PostType, SentimentType


class TestBriefPost(unittest.TestCase):

    def test_brief_post_init_user_post(self):
        title = "真正值得聊天的人只有两类"
        link = "https://m.okjike.com/originalPosts/684fef6bf432421164f3a6d1"
        date = "2025年6月19日"
        post = BriefPost(title, link, date)
        self.assertEqual(post.title, title)
        self.assertEqual(post.link, link)
        self.assertEqual(post.selected_date, date)
        self.assertEqual(post.type, BriefPost.PostType.USER_POST)

    def test_brief_post_init_news_post(self):
        title = "已有791名中国公民自伊朗转移至安全地区"
        link = "https://www.jiemian.com/article/12921294.html"
        date = "2025年6月19日"
        post = BriefPost(title, link, date)
        self.assertEqual(post.title, title)
        self.assertEqual(post.link, link)
        self.assertEqual(post.selected_date, date)
        self.assertEqual(post.type, BriefPost.PostType.NEWS)

    def test_brief_post_to_dict(self):
        title = "已有791名中国公民自伊朗转移至安全地区"
        link = "https://www.jiemian.com/article/12921294.html"
        date = "2025年6月19日"
        post = BriefPost(title, link, date)
        expected_dict = {
            'title': title,
            'link': link,
            'selected_date': date
        }
        self.assertEqual(post.to_dict(), expected_dict)

    def test_brief_post_from_dict(self):
        data = {
            'title': "已有791名中国公民自伊朗转移至安全地区",
            'link': "https://www.jiemian.com/article/12921294.html",
            'selected_date': "2025年6月19日"
        }
        post = BriefPost.from_dict(data)
        self.assertEqual(post.title, data['title'])
        self.assertEqual(post.link, data['link'])
        self.assertEqual(post.selected_date, data['selected_date'])
        # Check the type is also set correctly by __init__ when from_dict calls it
        self.assertEqual(post.type, BriefPost.PostType.NEWS)


class TestAuthor(unittest.TestCase):

    def test_author_init_minimal(self):
        url = "https://m.okjike.com/users/4CEE8E01-B41D-4019-8801-B25543F95CC0"
        author = Author(url=url)
        self.assertEqual(author.url, url)
        self.assertIsNone(author.name)
        self.assertIsNone(author.follower_num)
        self.assertIsNone(author.following_num)

    def test_author_init_full(self):
        url = "https://m.okjike.com/users/4CEE8E01-B41D-4019-8801-B25543F95CC0"
        name = "Test Author"
        followers = 100
        following = 50
        author = Author(url=url, name=name, follower_num=followers, following_num=following)
        self.assertEqual(author.url, url)
        self.assertEqual(author.name, name)
        self.assertEqual(author.follower_num, followers)
        self.assertEqual(author.following_num, following)

    def test_author_to_dict_minimal(self):
        url = "https://m.okjike.com/users/4CEE8E01-B41D-4019-8801-B25543F95CC0"
        author = Author(url=url)
        expected_dict = {
            'url': url,
            'name': None,
            'follower_num': None,
            'following_num': None
        }
        self.assertEqual(author.to_dict(), expected_dict)

    def test_author_to_dict_full(self):
        url = "https://m.okjike.com/users/4CEE8E01-B41D-4019-8801-B25543F95CC0"
        name = "Test Author"
        followers = 100
        following = 50
        author = Author(url=url, name=name, follower_num=followers, following_num=following)
        expected_dict = {
            'url': url,
            'name': name,
            'follower_num': followers,
            'following_num': following
        }
        self.assertEqual(author.to_dict(), expected_dict)


class TestPost(unittest.TestCase):

    def setUp(self):
        self.common_args = {
            "title": "真正值得聊天的人只有两类",
            "link": "https://m.okjike.com/originalPosts/684fef6bf432421164f3a6d1",
            "selected_date": "2025年6月19日"
        }
        self.author_data = Author(
            url="https://m.okjike.com/users/4CEE8E01-B41D-4019-8801-B25543F95CC0",
            name="Test Author"
        )

    def test_post_init_minimal(self):
        post = Post(**self.common_args)
        self.assertEqual(post.title, self.common_args["title"])
        self.assertEqual(post.link, self.common_args["link"])
        self.assertEqual(post.selected_date, self.common_args["selected_date"])
        self.assertIsNone(post.content)
        self.assertEqual(post.content_length_type, ContentLengthType.NONE)
        self.assertEqual(post.tags, [])
        self.assertIsNone(post.topic)
        self.assertIsNone(post.author)
        self.assertIsNone(post.like_count)
        self.assertEqual(post.post_type, PostType.NONE)
        self.assertEqual(post.sentiment_type, SentimentType.NONE)
        self.assertIsNone(post.is_hotspot)
        self.assertIsNone(post.is_creative)

    def test_post_init_full(self):
        full_args = {
            **self.common_args,
            "content": "This is the post content.",
            "content_length_type": ContentLengthType.MEDIUM,
            "tags": ["tag1", "tag2"],
            "topic": "Technology",
            "author": self.author_data,
            "like_count": 42,
            "post_type": PostType.KNOWLEDGE,
            "sentiment_type": SentimentType.POSITIVE,
            "is_hotspot": True,
            "is_creative": False
        }
        post = Post(**full_args)
        self.assertEqual(post.title, full_args["title"])
        self.assertEqual(post.link, full_args["link"])
        self.assertEqual(post.selected_date, full_args["selected_date"])
        self.assertEqual(post.content, full_args["content"])
        self.assertEqual(post.content_length_type, full_args["content_length_type"])
        self.assertEqual(post.tags, full_args["tags"])
        self.assertEqual(post.topic, full_args["topic"])
        self.assertEqual(post.author, full_args["author"])
        self.assertEqual(post.like_count, full_args["like_count"])
        self.assertEqual(post.post_type, full_args["post_type"])
        self.assertEqual(post.sentiment_type, full_args["sentiment_type"])
        self.assertEqual(post.is_hotspot, full_args["is_hotspot"])
        self.assertEqual(post.is_creative, full_args["is_creative"])

    def test_post_equality(self):
        post1 = Post(**self.common_args)
        post1.link = "link1"
        post2 = Post(**self.common_args)
        post2.link = "link1"
        post3 = Post(**self.common_args)
        post3.link = "link3"
        self.assertEqual(post1, post2)
        self.assertNotEqual(post1, post3)
        self.assertNotEqual(post1, "not a post") # Test comparison with non-Post object

    def test_post_comparison_like_count(self):
        post_low_likes = Post(**self.common_args, like_count=10)
        post_medium_likes = Post(**self.common_args, like_count=50)
        post_high_likes = Post(**self.common_args, like_count=100)
        post_no_likes = Post(**self.common_args, like_count=None)

        self.assertTrue(post_low_likes < post_medium_likes)
        self.assertTrue(post_high_likes > post_medium_likes)
        self.assertTrue(post_medium_likes <= post_high_likes)
        self.assertTrue(post_high_likes >= post_medium_likes)
        self.assertEqual(post_medium_likes, post_medium_likes) # Equality by value (like_count)

        # Test comparisons involving None
        self.assertTrue(post_no_likes < post_low_likes) # None is considered less than any number
        self.assertFalse(post_low_likes < post_no_likes)

        self.assertTrue(post_low_likes > post_no_likes) # Any number is considered greater than None
        self.assertFalse(post_no_likes > post_low_likes)

        self.assertTrue(post_no_likes <= post_low_likes)
        self.assertTrue(post_low_likes >= post_no_likes)
        self.assertFalse(post_low_likes <= post_no_likes)
        self.assertFalse(post_no_likes >= post_low_likes)

    def test_post_to_dict_minimal(self):
        post = Post(**self.common_args)
        expected_dict = {
            'title': self.common_args["title"],
            'link': self.common_args["link"],
            'selected_date': self.common_args["selected_date"],
            'content': None,
            'content_length_type': ContentLengthType.NONE.name,
            'tags': [],
            'topic': None,
            'author': None,
            'like_count': None,
            'post_type': PostType.NONE.name,
            'sentiment_type': SentimentType.NONE.name,
            'is_hotspot': None,
            'is_creative': None
        }
        self.assertEqual(post.to_dict(), expected_dict)

    def test_post_to_dict_full(self):
        full_args = {
            **self.common_args,
            "content": "Full content.",
            "content_length_type": ContentLengthType.LONG,
            "tags": ["python", "testing"],
            "topic": "Software Development",
            "author": self.author_data,
            "like_count": 99,
            "post_type": PostType.KNOWLEDGE,
            "sentiment_type": SentimentType.NEGATIVE,
            "is_hotspot": False,
            "is_creative": True
        }
        post = Post(**full_args)
        expected_dict = {
            'title': full_args["title"],
            'link': full_args["link"],
            'selected_date': full_args["selected_date"],
            'content': full_args["content"],
            'content_length_type': full_args["content_length_type"].name,
            'tags': full_args["tags"],
            'topic': full_args["topic"],
            'author': self.author_data.to_dict(), # Nested author dict
            'like_count': full_args["like_count"],
            'post_type': full_args["post_type"].name,
            'sentiment_type': full_args["sentiment_type"].name,
            'is_hotspot': full_args["is_hotspot"],
            'is_creative': full_args["is_creative"]
        }
        self.assertEqual(post.to_dict(), expected_dict)


if __name__ == '__main__':
    unittest.main()
