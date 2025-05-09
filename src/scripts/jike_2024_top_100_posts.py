"""
This script prints the top 100 posts in Jike 2024 which contains
the title, like count, and link for each post.
"""

import json

from constants import JIKE_2024_TOP_100_POSTS_FILE


def display_post(index: int, post: dict):
    """Displays a single post with its title, like count, and link."""
    print(f'{index}. {post["title"]}')
    print(f'  点赞数：{post["like_count"]}')
    print(f'  {post["link"]}')


with open(JIKE_2024_TOP_100_POSTS_FILE, "rt") as f:
    posts = json.load(f)

    for index, post in enumerate(posts, start=1):
        display_post(index, post)
