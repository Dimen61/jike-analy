from enum import Enum


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
