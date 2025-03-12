import json
import traceback
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from google.genai.operations import Optional

import constants
from aiproxy import AIProxy
from post_types import ContentLengthType, PostType, SentimentType


class Author:
    """Represents an author on the Jike platform.

    Attributes:
        url (str): The URL of the author's profile page.
        name (str): The author's screen name.
        follower_num (int): The number of followers the author has.
        following_num (int): The number of users the author is following.
        soup (BeautifulSoup): The BeautifulSoup object for the author's profile page.
    """

    def __init__(self, link_path, enable_auto_parse=True):
        """Initializes an Author object.

        Args:
            link_path (str): The path portion of the author's profile URL.
            enable_auto_parse (bool, optional): Whether to automatically parse author data upon initialization.
                Defaults to True.
        """
        self.url= urljoin(constants.JIKE_URL, link_path)
        self.name = None
        self.follower_num = None
        self.following_num = None

        self.soup = None

        if enable_auto_parse:
            self._init_request()
            self._parse_name()
            self._parse_follower()

    def _init_request(self):
        """Sends an HTTP request to the author's profile page and initializes the BeautifulSoup object."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

        response = requests.get(self.url, headers=headers)
        self.soup = BeautifulSoup(response.text, 'html.parser')

    def _parse_name(self):
        """Parses the author's name from the BeautifulSoup object."""
        if not self.soup:
           raise RuntimeError("Soup is not initialized. Author({self.url})")

        self.name= self.soup.find('div', class_='user-screenname').text.strip()

    def _parse_follower(self):
        """Parses the author's follower and following counts from the BeautifulSoup object."""
        if not self.soup:
           raise RuntimeError("Soup is not initialized. Author({self.url})")

        user_status_div = self.soup.find('div', class_='user-status')
        count_elements = user_status_div.find_all('span', class_='count')
        try:
            self.following_num = self._parse_follower_num(count_elements[0].text)
            self.follower_num = self._parse_follower_num(count_elements[1].text)
        except ValueError:
            self.follower_num = None
            print(f'Failed to parse number. Author({self.url})')

    def _parse_follower_num(self, num_str) -> int:
        """Parses a string representation of a number (e.g., '111', '11k') to an integer.

        Args:
            num_str (str): The string to parse.

        Returns:
            int: The parsed integer.
        """
        if not num_str:
            return 0

        # Remove any whitespace
        num_str = num_str.strip()

        # Check if the string ends with 'k' (thousands)
        if num_str.lower().endswith('k'):
            # Remove the 'k' and convert to thousands
            return int(float(num_str[:-1]) * 1000)

        # Handle regular numbers
        try:
            return int(num_str)
        except ValueError:
            # If conversion fails, return 0
            return 0

    def __str__(self) -> str:
        return f"Author(url={self.url}, follower_num={self.follower_num})"

    def __repr__(self) -> str:
        return f"Author(url={self.url}, follower_num={self.follower_num})"

    def to_dict(self):
        """Converts the Author object to a dictionary.

        Returns:
            dict: A dictionary representation of the author.
        """
        return {
            'url': self.url,
            'name': self.name,
            'follower_num': self.follower_num,
            'following_num': self.following_num
        }


class Post:
    """Represents a post on the Jike platform.

    Attributes:
        title (str): The title of the post.
        link (str): The URL of the post.
        selected_date (str): The date the post was selected for analysis.
        content (str): The content of the post.
        content_length_type (ContentLengthType): The length category of the post content.
        tags (List[str]): Tags associated with the post.
        topic (str): The topic of the post.
        author (Author): The author of the post.
        like_count (Optional[int]): The number of likes the post has received.
        post_type (PostType): The type of the post (e.g., question, share).
        sentiment_type (SentimentType): The sentiment expressed in the post (e.g., positive, negative).
        is_hotspot (bool): Whether the post discusses a current hotspot.
        is_creative (bool): Whether the post is considered creative.
        soup (BeautifulSoup): The BeautifulSoup object for the post's page.
        aiproxy (AIProxy): An instance of AIProxy for analyzing the post content.
    """

    def __init__(self, title, link, selected_date, enable_auto_parse=True):
        """Initializes a Post object.

        Args:
            title (str): The title of the post.
            link (str): The URL of the post.
            selected_date (str): The date the post was selected for analysis.
            enable_auto_parse (bool, optional): Whether to automatically parse post data upon initialization.
                Defaults to True.
        """
        self.title = title
        self.link = link
        self.selected_date = selected_date
        self.content = None
        self.content_length_type = ContentLengthType.NONE

        # Metrics of analyzing posts
        self.tags = [] # Find which tags are popular
        self.topic = None # Find which topics are popular
        self.author = None # Find which authors are popular. Does authors who have more followers have more likely to be picked?
        self.like_count:Optional[int] = None
        self.post_type = PostType.NONE
        self.sentiment_type = SentimentType.NONE
        self.is_hotspot = None
        self.is_creative = None
        # self.word_num_count = None  #Considered but not used

        self.soup = None
        self.aiproxy = None

        if enable_auto_parse:
            self._init_request()
            self._parse_content_text()
            self._parse_like_count()
            self._parse_author()
            self._parse_topic()

            self._init_aiproxy()

            self._parse_tags()
            self._parse_post_type()
            self._parse_sentiment_type()

            self._parse_is_hotspot()
            self._parse_is_creative()

    def _init_aiproxy(self):
        """Initializes the AIProxy object for content analysis."""
        self.aiproxy = AIProxy(self.content)

    def _init_request(self):
        """Sends an HTTP request to the post's page and initializes the BeautifulSoup object."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

        response = requests.get(self.link, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            self.soup = soup
        else:
            raise ConnectionError(
                f"Failed to retrieve the page."
                f" Status code:{response.status_code}."
                f" Post title: {self.title}"
                f" Response content: {response.content}"
            )

    def _parse_tags(self):
        """Parses tags from the post content using the AIProxy."""
        if self.aiproxy:
            self.tags = self.aiproxy.get_tags_from_content_text()

    def _parse_is_hotspot(self):
        """Determines if the post is a hotspot using the AIProxy."""
        if self.aiproxy:
            self.is_hotspot = self.aiproxy.is_hotspot_from_content_text()

    def _parse_is_creative(self):
        """Determines if the post is creative using the AIProxy."""
        if self.aiproxy:
            self.is_creative = self.aiproxy.is_creative_from_content_text()

    def _parse_topic(self):
        """Parses the topic of the post from the BeautifulSoup object."""
        if not self.soup:
            raise RuntimeError('Soup is not well inited since bad request')

        try:
            h3 = self.soup.find('div', class_='post-page').find('a', class_='wrap').find('h3')
            self.topic = h3.text.strip()
        except AttributeError:
            print('No topic found')
            self.topic = None
        except RuntimeError as e:
            print(f"Error parsing topic for post '{self.title}': {e}")

    def _parse_post_type(self):
        """Determines the post type using the AIProxy."""
        if self.aiproxy:
            self.post_type = self.aiproxy.get_post_type_from_content_text()

    def _parse_sentiment_type(self):
        """Determines the sentiment type using the AIProxy."""
        if self.aiproxy:
            self.sentiment_type = self.aiproxy.get_sentiment_type_from_content_text()

    def _parse_like_count(self):
        """Parses the like count from the BeautifulSoup object."""
        if not self.soup:
            raise RuntimeError('Soup is not well inited since bad request')

        like_span = self.soup.find("span", class_="like-count")
        if like_span:
            like_count = like_span.text.strip()
            self.like_count = int(like_count)

    def _parse_author(self):
        """Parses the author information from the BeautifulSoup object."""
        if not self.soup:
            raise RuntimeError('Soup is not well inited since bad request')

        author_a = self.soup.find("a", class_="avatar")
        if author_a and author_a.has_attr("href"):
            self.author = Author(author_a['href'])

    def _parse_content_text(self):
        """Parses the content text from the BeautifulSoup object."""
        if not self.soup:
            raise RuntimeError('Soup is not well inited since bad request')

        divs = self.soup.find_all('div', class_='jsx-3930310120 wrap')
        text =""
        for div in divs:
            text += div.get_text(strip=True, separator="\n")
            text += "\n"

        self.content = text
        self.content_length_type = ContentLengthType.from_content_length(len(text))

    def __str__(self) -> str:
        return (
            f"Title: {self.title}\nLink: {self.link}\nContent: {self.content}\nLike Count: {self.like_count}\nTopic: {self.topic}\n"
            f"Author: {self.author}\n"
            f"Post Type: {self.post_type}\n"
            f"Sentiment Type: {self.sentiment_type}\n"
            f"Content Length Type: {self.content_length_type}\n"
            f"Tags: {self.tags}\n"
            f"Is Creative: {self.is_creative}\n"
            f"Is Hotspot: {self.is_hotspot}\n"
        )

    def __repr__(self) -> str:
        return (
            f"Post(title={self.title}, link={self.link}, content={self.content}, like_count={self.like_count}, topic={self.topic},"
            f"author={self.author}, post_type={self.post_type}, sentiment_type={self.sentiment_type}, content_length_type={self.content_length_type},"
            f"tags={self.tags}, is_creative={self.is_creative}, is_hotspot={self.is_hotspot})"
        )

    def to_dict(self):
        """Converts the Post object to a dictionary.

        Returns:
            dict: A dictionary representation of the post.
        """
        return {
            'title': self.title,
            'link': self.link,
            'content': self.content,
            'author': self.author.to_dict() if self.author else None,
            'like_count': self.like_count,
            'topic': self.topic,
            'tags': self.tags,
            'post_type': self.post_type.name,
            'sentiment_type': self.sentiment_type.name,
            'content_length_type': self.content_length_type.name,
            'is_creative': self.is_creative,
            'is_hotspot': self.is_hotspot
        }

    def __lt__(self, other):
        """Less than, used for sorting (ascending order by like_count)"""
        if not isinstance(other, Post):
            return NotImplemented  # Handle comparison with non-Post objects

        # Handle cases where like_count might be None
        if self.like_count is None:
            return True  # Treat as smallest
        if other.like_count is None:
            return False  # Other is smallest

        return self.like_count < other.like_count

    def __gt__(self, other):
        """Greater than, used for sorting (descending order by like_count)"""
        if not isinstance(other, Post):
            return NotImplemented

        # Handle cases where like_count might be None
        if self.like_count is None:
            return False  # Treat as smallest
        if other.like_count is None:
            return True   # Other is smallest

        return self.like_count > other.like_count

    def __eq__(self, other):
        """Equal, used for checking equality by like_count"""
        if not isinstance(other, Post):
            return NotImplemented
        return self.like_count == other.like_count

    def __le__(self, other):
        """Less than or equal to"""
        return self < other or self == other

    def __ge__(self, other):
        """Greater than or equal to"""
        return self > other or self == other


def load_local_posts() -> List[dict]:
    """Loads posts from a local JSON file.

    Returns:
        List[dict]: A list of dictionaries, each representing a post.
    """
    with open(constants.USER_POSTS_JSON_FILE, 'rt', encoding='utf-8') as f:
        return json.load(f)

def dump_top_100_posts_in_2024(posts: List[Post]):
    """Dumps the top 100 posts (by like count) to a JSON file.

    Args:
        posts (List[Post]):  A list of Post Objects.
    """
    json_file = './jike_2024_top_100_posts.json'

    # Sort posts in descending order of like_count (most likes first)
    sorted_posts = sorted(posts, reverse=True)

    # Take the top 100 posts
    top_100_posts = sorted_posts[:100]

    # Convert to a list of dictionaries
    top_100_posts_dicts = [post.to_dict() for post in top_100_posts]

    # Write to JSON file
    with open(json_file, 'wt', encoding='utf-8') as f:
        json.dump(top_100_posts_dicts, f, indent=4, ensure_ascii=False)

def dump_posts_to_json(posts: List[Post], json_file: str):
    """Dumps a list of posts to a JSON file.

    Args:
        posts (List[Post]): A list of Post objects.
        json_file (str): The path to the output JSON file.
    """
    # Convert posts to dictionaries
    post_dicts = [post.to_dict() for post in posts]

    # Add into JSON file
    with open(json_file, 'wt', encoding='utf-8') as f:
        json.dump(post_dicts, f, indent=4, ensure_ascii=False)

    print(f"Successfully dumped {len(posts)} posts to {json_file}")

def load_posts_from_json(json_file: str) -> List[Post]:
    """Loads posts from a JSON file.

    Args:
        json_file (str): The path to the JSON file.

    Returns:
        List[Post]: A list of Post objects.
    """
    posts = []

    with open(json_file, 'rt', encoding='utf-8') as f:
        post_dicts = json.load(f)
        for post_dict in post_dicts:
            author_dict = post_dict.get('author')
            author = None
            if author_dict:
                author = Author(author_dict['url'], enable_auto_parse=False)
                author.name = author_dict['name']
                author.follower_num = author_dict['follower_num']
                author.following_num = author_dict['following_num']

            post = Post(post_dict['title'], post_dict['link'], "", enable_auto_parse=False)
            post.content = post_dict['content']
            post.like_count = post_dict['like_count']
            post.topic = post_dict['topic']
            post.tags = post_dict['tags']
            post.author = author
            post.post_type = PostType[post_dict['post_type']]
            post.sentiment_type = SentimentType[post_dict['sentiment_type']]
            post.content_length_type = ContentLengthType[post_dict['content_length_type']]
            post.is_creative = post_dict['is_creative']
            post.is_hotspot = post_dict['is_hotspot']
            posts.append(post)

    return posts

def main():
    """Main function to process and analyze Jike posts."""
    posts = load_posts_from_json(constants.ANALYSED_POSTS_JSON_FILE)

    # backup posts
    dump_posts_to_json(posts, constants.BACKUP_ANALYSED_POSTS_JSON_FILE)

    init_posts_len = len(posts)
    # init_posts_len = 355 #  Used during the development
    increase_len = 3
    target_posts_len = init_posts_len + increase_len

    count = 0
    for dic in load_local_posts():
        count += 1
        if count <= init_posts_len:
            continue

        print(f'Processed post {count}: {dic["title"]}')

        try:
            post = Post(dic['title'], dic['link'], dic['date'])
            posts.append(post)
        except Exception as e:
            print(f'Error message: {str(e)}')
            print(f'Error type: {type(e).__name__}')
            traceback.print_exc()

            break

        if count == target_posts_len:
            break

    dump_posts_to_json(posts, constants.ANALYSED_POSTS_JSON_FILE)

if __name__ == "__main__":
    main()
