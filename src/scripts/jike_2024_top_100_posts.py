"""
This script prints the top 100 posts in Jike 2024 which contains
the title, like count, and link for each post.
"""

import json
from typing import List

from constants import JIKE_2024_TOP_100_POSTS_FILE
from core.parser import Post


def display_post(index: int, post: dict):
    """Displays a single post with its title, like count, and link."""
    print(f'{index}. {post["title"]}')
    print(f'  点赞数：{post["like_count"]}')
    print(f'  {post["link"]}')

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



with open(JIKE_2024_TOP_100_POSTS_FILE, "rt") as f:
    posts = json.load(f)

    for index, post in enumerate(posts, start=1):
        display_post(index, post)
