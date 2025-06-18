from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import List, Optional

from core.enums import ContentLengthType, PostType, SentimentType


class BriefPost:
    """Represents a brief post with title, link, and date."""

    class PostType(Enum):
        """Enum for post types: NEWS or USER_POST."""
        NEWS = "news"
        USER_POST = "user_post"

    def __init__(self, title, link, selected_date):
        """
        Initializes a BriefPost object.

        Args:
            title (str): The title of the post.
            link (str): The URL link of the post.
            selected_date (str): The date associated with the post.
        """
        self.title = title
        self.link = link
        self.selected_date = selected_date
        self.type = None

        # Sample case:
        # https://m.okjike.com/originalPosts/67bac4b2205950ba34848365
        # Determine post type based on the link.
        if 'm.okjike.com' in self.link:
            self.type = self.PostType.USER_POST
        else:
            self.type = self.PostType.NEWS

    def to_dict(self):
        """Converts the BriefPost object to a dictionary."""
        return {
            'title': self.title,
            'link': self.link,
            'selected_date': self.selected_date
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a BriefPost object from a dictionary."""
        return cls(data['title'], data['link'], data['selected_date'])


@dataclass
class Author:
    """Represents an author on the Jike platform."""
    url: str
    name: Optional[str] = None
    follower_num: Optional[int] = None
    following_num: Optional[int] = None

    def to_dict(self):
        """Converts the Author object to a dictionary."""
        # Using asdict is generally better for dataclasses, but manual dict is also fine
        return {
            'url': self.url,
            'name': self.name,
            'follower_num': self.follower_num,
            'following_num': self.following_num
        }


@dataclass
class Post:
    """Represents a post on the Jike platform."""
    title: str
    link: str
    selected_date: str # Date this post was selected for analysis
    content: Optional[str] = None
    content_length_type: ContentLengthType = field(default=ContentLengthType.NONE)
    tags: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    author: Optional[Author] = None
    like_count: Optional[int] = None
    post_type: PostType = field(default=PostType.NONE)
    sentiment_type: SentimentType = field(default=SentimentType.NONE)
    is_hotspot: Optional[bool] = None
    is_creative: Optional[bool] = None

    # Keep comparison methods if they are needed for sorting etc.
    def __lt__(self, other):
        """Less than, used for sorting (ascending order by like_count)"""
        if not isinstance(other, Post):
            return NotImplemented

        if self.like_count is None:
            return True
        if other.like_count is None:
            return False

        return self.like_count < other.like_count

    def __gt__(self, other):
        """Greater than, used for sorting (descending order by like_count)"""
        if not isinstance(other, Post):
            return NotImplemented

        if self.like_count is None:
            return False
        if other.like_count is None:
            return True

        return self.like_count > other.like_count

    def __eq__(self, other):
        """Equal, used for checking equality based on link"""
        if not isinstance(other, Post):
            return NotImplemented
        return self.link == other.link

    def __le__(self, other):
         return self < other or self == other

    def __ge__(self, other):
         return self > other or self == other

    def to_dict(self):
        """Converts the Post object to a dictionary."""
        # Use asdict for nested dataclass conversion if author is not None
        post_dict = asdict(self)
        # Manually convert enums to their names for serialization
        post_dict['content_length_type'] = self.content_length_type.name
        post_dict['post_type'] = self.post_type.name
        post_dict['sentiment_type'] = self.sentiment_type.name
        # Convert author if present
        if self.author:
            post_dict['author'] = self.author.to_dict()
        return post_dict
