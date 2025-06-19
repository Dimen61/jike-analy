import unittest

import tests.test_setup  # noqa: F401
from core.enums import PostType, SentimentType, ContentLengthType


class TestEnums(unittest.TestCase):

    def test_post_type_from_string_valid(self):
        self.assertEqual(PostType.from_string("knowledge"), PostType.KNOWLEDGE)
        self.assertEqual(PostType.from_string("OPINION"), PostType.OPINION)
        self.assertEqual(PostType.from_string("lifestyle"), PostType.LIFESTYLE)
        self.assertEqual(PostType.from_string("ENTERTAINMENT"), PostType.ENTERTAINMENT)
        self.assertEqual(PostType.from_string("interactive"), PostType.INTERACTIVE)
        self.assertEqual(PostType.from_string("PRODUCT_MARKETING"), PostType.PRODUCT_MARKETING)
        self.assertEqual(PostType.from_string("none"), PostType.NONE)

    def test_post_type_from_string_invalid(self):
        with self.assertRaises(ValueError) as cm:
            PostType.from_string("invalid_type")
        self.assertEqual(str(cm.exception), "Invalid post type: invalid_type")

    def test_sentiment_type_from_string_valid(self):
        self.assertEqual(SentimentType.from_string("neutral"), SentimentType.NEUTRAL)
        self.assertEqual(SentimentType.from_string("NEGATIVE"), SentimentType.NEGATIVE)
        self.assertEqual(SentimentType.from_string("positive"), SentimentType.POSITIVE)
        self.assertEqual(SentimentType.from_string("NONE"), SentimentType.NONE)

    def test_sentiment_type_from_string_invalid(self):
        with self.assertRaises(ValueError) as cm:
            SentimentType.from_string("unknown_sentiment")
        self.assertEqual(str(cm.exception), "Invalid sentiment type: unknown_sentiment")

    def test_content_length_type_from_content_length(self):
        self.assertEqual(ContentLengthType.from_content_length(50), ContentLengthType.SHORT)
        self.assertEqual(ContentLengthType.from_content_length(99), ContentLengthType.SHORT)
        self.assertEqual(ContentLengthType.from_content_length(100), ContentLengthType.MEDIUM)
        self.assertEqual(ContentLengthType.from_content_length(499), ContentLengthType.MEDIUM)
        self.assertEqual(ContentLengthType.from_content_length(500), ContentLengthType.LONG)
        self.assertEqual(ContentLengthType.from_content_length(1999), ContentLengthType.LONG)
        self.assertEqual(ContentLengthType.from_content_length(2000), ContentLengthType.LONGER)
        self.assertEqual(ContentLengthType.from_content_length(5000), ContentLengthType.LONGER)
        self.assertEqual(ContentLengthType.from_content_length(0), ContentLengthType.SHORT) # Edge case for length 0


if __name__ == '__main__':
    unittest.main()
