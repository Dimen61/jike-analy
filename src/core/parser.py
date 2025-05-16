import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Optional
from dataclasses import dataclass, field, asdict
import json
import os
import time
import random
import traceback

# Assuming these are defined elsewhere
import constants
from core.aiproxy import AIProxy # Assuming AIProxy is in ai_proxy.py
from core.enums import ContentLengthType, PostType, SentimentType
from core.data_models import Author, Post

class JikeParser:
    """Parses Jike web pages to extract Author and Post data."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetches the HTML content of a URL and returns a BeautifulSoup object."""
        response = requests.get(url, headers=self.headers)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return BeautifulSoup(response.text, 'html.parser')

    def parse_author(self, link_path: str) -> Optional[Author]:
        """Fetches and parses an author's profile page."""
        author_url = urljoin(constants.JIKE_URL, link_path)
        try:
            soup = self._fetch_page(author_url)
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch author page {author_url}: {e}")
            return None

        name = None
        follower_num = None
        following_num = None

        try:
            # Use select_one for potentially more robust selection
            name_element = soup.select_one('div.user-screenname')
            if name_element:
                name = name_element.text.strip()
        except Exception as e:
            print(f"Error parsing author name for {author_url}: {e}")

        try:
            user_status_div = soup.select_one('div.user-status')
            if user_status_div:
                count_elements = user_status_div.find_all('span', class_='count')
                if len(count_elements) >= 2:
                    following_num = self._parse_follower_num(count_elements[0].text)
                    follower_num = self._parse_follower_num(count_elements[1].text)
        except Exception as e:
             print(f'Failed to parse follower/following counts for {author_url}: {e}')


        return Author(url=author_url, name=name, follower_num=follower_num, following_num=following_num)

    def _parse_follower_num(self, num_str: str) -> int:
        """Parses a string representation of a number (e.g., '111', '11k') to an integer."""
        if not num_str:
            return 0

        num_str = num_str.strip()

        if num_str.lower().endswith('k'):
            try:
                return int(float(num_str[:-1]) * 1000)
            except ValueError:
                return 0

        try:
            return int(num_str)
        except ValueError:
            return 0

    def parse_post(self, title: str, link: str, selected_date: str) -> Optional[Post]:
        """Fetches and parses a post page."""
        try:
            soup = self._fetch_page(link)
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch post page {link} (Title: {title}): {e}")
            return None

        content = self._parse_post_content_text(soup)
        like_count = self._parse_post_like_count(soup)
        author = self._parse_post_author(soup)
        topic = self._parse_post_topic(soup)

        # AIProxy analysis requires content
        aiproxy = AIProxy(content) if content else None
        tags = self._parse_post_tags(aiproxy)
        post_type = self._parse_post_type(aiproxy)
        sentiment_type = self._parse_post_sentiment_type(aiproxy)
        is_hotspot = self._parse_post_is_hotspot(aiproxy)
        is_creative = self._parse_post_is_creative(aiproxy)
        content_length_type = ContentLengthType.from_content_length(len(content) if content else 0)


        return Post(
            title=title,
            link=link,
            selected_date=selected_date,
            content=content,
            content_length_type=content_length_type,
            tags=tags,
            topic=topic,
            author=author,
            like_count=like_count,
            post_type=post_type,
            sentiment_type=sentiment_type,
            is_hotspot=is_hotspot,
            is_creative=is_creative
        )

    def _parse_post_content_text(self, soup: BeautifulSoup) -> Optional[str]:
        """Parses the content text from a post's BeautifulSoup object."""
        try:
            divs = soup.find_all('div', class_='jsx-3930310120 wrap')
            if divs:
                 # Find all inner text divs within the content div
                content_text = ""
                for div in divs:
                    content_text += div.get_text(strip=True, separator="\\n")
                    content_text += "\\n"
                return content_text.strip() if content_text else None
        except Exception as e:
            print(f"Error parsing post content: {e}")
            return None
        return None # Return None if the main content div is not found

    def _parse_post_like_count(self, soup: BeautifulSoup) -> Optional[int]:
        """Parses the like count from a post's BeautifulSoup object."""
        try:
            like_span = soup.select_one("span.like-count")
            if like_span:
                like_count_str = like_span.text.strip()
                if like_count_str: # Ensure the string is not empty
                    return int(like_count_str)
                else:
                    return 0 # Treat empty string as 0 likes
        except (ValueError, AttributeError) as e:
            print(f"Error parsing like count: {e}")
            return None
        return None # Return None if like_span is not found

    def _parse_post_author(self, soup: BeautifulSoup) -> Optional[Author]:
        """Parses the author information from a post's BeautifulSoup object."""
        try:
            author_a = soup.select_one("a.avatar")
            if author_a and author_a.has_attr("href"):
                author_link_path = author_a['href']
                # Call the dedicated parse_author method, but don't auto-parse fully here
                # Just return an Author with the URL, full author details can be parsed later if needed
                author_url = urljoin(constants.JIKE_URL, author_link_path)
                return self.parse_author(author_url)
        except Exception as e:
            print(f"Error parsing post author link: {e}")
            return None
        return None # Return None if author link is not found

    def _parse_post_topic(self, soup: BeautifulSoup) -> Optional[str]:
        """Parses the topic of the post from the BeautifulSoup object."""
        try:
            # Use select_one for the topic h3
            h3 = soup.select_one('div.post-page a.wrap h3')
            if h3:
                return h3.text.strip()
        except Exception as e:
            print(f"Error parsing post topic: {e}")
            return None
        return None # Return None if topic is not found

    # Methods that use AIProxy
    def _parse_post_tags(self, aiproxy: Optional[AIProxy]) -> List[str]:
        """Parses tags from the post content using the AIProxy."""
        if aiproxy:
            try:
                return aiproxy.get_tags_from_content_text()
            except Exception as e:
                print(f"Error getting tags from AIProxy: {e}")
        return []

    def _parse_post_is_hotspot(self, aiproxy: Optional[AIProxy]) -> Optional[bool]:
        """Determines if the post is a hotspot using the AIProxy."""
        if aiproxy:
            try:
                return aiproxy.is_hotspot_from_content_text()
            except Exception as e:
                print(f"Error checking hotspot from AIProxy: {e}")
        return None

    def _parse_post_is_creative(self, aiproxy: Optional[AIProxy]) -> Optional[bool]:
        """Determines if the post is creative using the AIProxy."""
        if aiproxy:
            try:
                return aiproxy.is_creative_from_content_text()
            except Exception as e:
                print(f"Error checking creative from AIProxy: {e}")
        return None

    def _parse_post_type(self, aiproxy: Optional[AIProxy]) -> PostType:
        """Determines the post type using the AIProxy."""
        if aiproxy:
            try:
                return aiproxy.get_post_type_from_content_text()
            except Exception as e:
                print(f"Error getting post type from AIProxy: {e}")
        return PostType.NONE # Default

    def _parse_post_sentiment_type(self, aiproxy: Optional[AIProxy]) -> SentimentType:
        """Determines the sentiment type using the AIProxy."""
        if aiproxy:
            try:
                return aiproxy.get_sentiment_type_from_content_text()
            except Exception as e:
                print(f"Error getting sentiment type from AIProxy: {e}")
        return SentimentType.NONE # Default


class PostDataIO:
    """
    Handles reading and writing post data to/from JSON files.
    Provides static methods to load raw post dictionaries and load/save parsed Post objects.
    """
    @staticmethod
    def dump_posts_to_json(posts: List[Post], json_file: str):
        """Dumps a list of Post objects to a JSON file."""
        posts_data = [post.to_dict() for post in posts]
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(posts_data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def load_posts_from_json(json_file: str) -> List[Post]:
        """Loads a list of Post objects from a JSON file."""
        posts = []
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                posts_data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: JSON file not found at {json_file}. Starting with an empty list of posts.")
            return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {json_file}: {e}")
            return []

        for data in posts_data:
            try:
                author_data = data.get('author')
                # Assuming Author dataclass can be initialized directly from its dictionary representation
                author_instance = Author(**author_data) if author_data else None

                # Convert enum names (strings) back to enum members, handle potential errors
                content_length_type = ContentLengthType.NONE
                if 'content_length_type' in data and data['content_length_type'] in ContentLengthType.__members__:
                    content_length_type = ContentLengthType[data['content_length_type']]

                post_type = PostType.NONE
                if 'post_type' in data and data['post_type'] in PostType.__members__:
                    post_type = PostType[data['post_type']]

                sentiment_type = SentimentType.NONE
                if 'sentiment_type' in data and data['sentiment_type'] in SentimentType.__members__:
                    sentiment_type = SentimentType[data['sentiment_type']]

                post_instance = Post(
                    title=data.get('title', ''),
                    link=data.get('link', ''),
                    selected_date=data.get('selected_date', ''),
                    content=data.get('content'),
                    content_length_type=content_length_type,
                    tags=data.get('tags', []),
                    topic=data.get('topic'),
                    author=author_instance,
                    like_count=data.get('like_count'),
                    post_type=post_type,
                    sentiment_type=sentiment_type,
                    is_creative=data.get('is_creative'),
                    is_hotspot=data.get('is_hotspot')
                )
                posts.append(post_instance)
            except Exception as e:
                print(f"Error loading post data {data.get('link', 'N/A')}: {e}")
                traceback.print_exc() # Print traceback for detailed error info
                continue # Skip this post and continue with the next

        return posts

    @staticmethod
    def load_raw_posts(json_file_path: str) -> List[dict]:
        """Loads raw post dictionaries from a JSON file."""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: The file {json_file_path} was not found.")
            return []
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {json_file_path}.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while loading posts from {json_file_path}: {e}")
            return []


def main():
    """Main function to process and analyze Jike posts."""
    parser = JikeParser()

    # Load previously analyzed posts if the file exists
    posts: List[Post] = []
    if os.path.exists(constants.ANALYSED_POSTS_FILE):
        posts = PostDataIO.load_posts_from_json(constants.ANALYSED_POSTS_FILE)
        print(f"Loaded {len(posts)} previously analyzed posts.")

    # Create a set of links for quick lookup of existing posts
    existing_post_links = {post.link for post in posts}

    # Load raw post data from the source file
    raw_posts_data = PostDataIO.load_raw_posts(constants.SIMPLE_USER_POSTS_FILE)
    print(f"Loaded {len(raw_posts_data)} raw posts to process.")

    new_posts_count = 0
    processed_count = 0

    # Process new posts
    for raw_post_data in raw_posts_data:
        link = raw_post_data.get('link', '')
        title = raw_post_data.get('title', 'No Title')
        selected_date = raw_post_data.get('date', 'N/A') # Assuming 'date' is the selected date in raw data

        # Skip if the post has already been processed
        if link in existing_post_links:
            processed_count += 1
            continue

        print(f"Processing new post {processed_count + 1}: {title}")

        try:
            # Use the parser to fetch and parse the post details
            post = parser.parse_post(title, link, selected_date)

            if post:
                posts.append(post)
                existing_post_links.add(post.link) # Add the new post's link to the set
                new_posts_count += 1
                print(f"Successfully parsed and added post: {title}")
            else:
                 print(f"Failed to parse post: {title} ({link})")

        except Exception as e:
            print(f"An error occurred while processing post {title} ({link}): {e}")
            traceback.print_exc() # Print traceback for detailed error info
            # Depending on desired behavior, you might break or continue
            # break # Uncomment to stop on first error
            continue # Continue to the next post on error

        # For testing
        if new_posts_count == 2:
            break

        # Add a delay to avoid hitting the server too hard
        time.sleep(random.uniform(2, 6))

    print(f"Finished processing. Added {new_posts_count} new posts.")
    print(f"Total posts analyzed: {len(posts)}")

    # Save the updated list of posts to the analyzed file
    if new_posts_count > 0: # Only save if new posts were added
        try:
            PostDataIO.dump_posts_to_json(posts, constants.ANALYSED_POSTS_FILE)
            print(f"Saved updated list of posts to {constants.ANALYSED_POSTS_FILE}")
        except Exception as e:
            print(f"Error saving posts to JSON: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
