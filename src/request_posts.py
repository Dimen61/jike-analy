"""
This script retrieves, parses, and saves posts from the Jike social media platform.

It uses the Jike GraphQL API to fetch a user's posts, extracts relevant information
(title, link, and date) from each post, and categorizes them as either "news" or
"user posts." The script then displays the extracted data and saves the user
posts to a JSON file. It continues fetching posts in a paginated manner until
a specified number of dates' worth of posts have been retrieved.

Key functionalities:

- **Authentication:** Uses hardcoded Jike access and refresh tokens for API access.
- **Pagination:** Handles API pagination using the `loadMoreKey` and `lastId` fields.
- **Data Extraction:** Parses the raw post content to identify individual news items and links.
- **Data Filtering:** Separates posts into "news" and "user posts" based on the URL.
- **Data Storage:** Saves the extracted user posts to a JSON file.
- **Rate Limiting:** Includes a short sleep period to avoid overwhelming the API.

The script is designed to fetch posts for a specific user (implied by the
hardcoded authentication tokens) and save them for later analysis.
"""


import json
import time
from enum import Enum
from typing import List

import requests

import constants


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

def load_graphql_query(last_id=None):
    """Loads the GraphQL query from a JSON file and updates it with the last ID if provided.

    Args:
        last_id (str, optional): The last ID for pagination. Defaults to None.

    Returns:
        dict: The loaded GraphQL query payload.
    """
    with open(constants.GRAPHQL_PAYLOAD_JSON_FILE, 'rt', encoding='utf-8') as file:
        payload = json.load(file)

    if last_id:
        payload['variables']['loadMoreKey'] = {'lastId': str(last_id)}
    return payload

def construct_header():
    """Constructs the request header for the Jike API.

    Returns:
        dict: The constructed request header.  Includes necessary headers like
        User-Agent, Content-Type, and authentication tokens.
    """
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.7,ja;q=0.6",
        "Content-Type": "application/json",
        "Origin": "https://web.okjike.com",
        "Priority": "u=1, i",
        "Sec-Ch-Ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        # "Cookie": "_gid=GA1.2.1836417803.1740363107; fetchRankedUpdate=1740363449633; _ga_LQ23DKJDEL=GS1.2.1740391370.7.1.1740392140.60.0.0; _ga_5ES45LSTYC=GS1.1.1740392602.7.1.1740393474.60.0.0; _ga=GA1.1.1091261079.1723031242; x-jike-access-token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoiMWRua2F3K2RFOVNOOFFPWUp5MGhCSHRGVzdIUThKaWtNeEJDMVJcL2twMUk2ZXZ1RUNsTStseFBLQXAwV0VWblE2YVhPd05WRlN4aEZGejRLTGlmU2lneEtoTzBjdFwvMFYxS3lTNmFoZDdLaThJRFE0VTQ3SnpsNEppb3Q2a2RNQ1pPcVhYbllcL05ZNHhPNkp3NnVBd2VDY2Z6S0J6VzdjSGhYYXhXc0txMDhHMWNYaVdrNUZYenY4UThST3NMWGJnVjk2NWJ3NjhLZDEwTTlVUFA0a29FWEppOEFyM3M5ZXVcL25zeEVoQXc5OWlwc0JWZW1IOWVwNnlOcGRVanJaN0Z3d2RvVzh2dnRJVmxzMDdjRFdQVENUdGN1MVJQcG8yNkh5V0dzVktMOFwvV0N2am5KazR5ZFN4MjdqanNxOTlpRHF6TjhiQ1RQbUI2VnpoTVBcL2FGU1FMZFphMGlRT1UxV2oyR3B0VHh2WWVzPSIsInYiOjMsIml2IjoiRHVicEZrUU9naDR2VVJleDJjaGg1dz09IiwiaWF0IjoxNzQwMzk0NTkwLjMxOH0.RIdo7lJS96aGS5gHQ9SGxg_LahrxCXA0PRkqyg_O_sE; x-jike-refresh-token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoidHRpM2MrR1hFOHBBOGdEdWZWbnU0UjZNWkIzUDA5Z3NZT0I4Y3ZjQkJvOFlJTFRzRm0zVWZYYVhyRVNpY3V5eGJYMXlPdDBmeE5uMStzcEdQVjcxMVkwdHM5Sk9KbUk3Z1cxaGd4akp3ZlJVZlpaM0F4RGpEVGdGVGZIZ1I1SlpEbDZEWEdhcU5IbHc3cGcxM2pmaTBxdGtSbXNQQmt4bGhGMXQxczBubm5ZPSIsInYiOjMsIml2IjoiU1FCSFNWcU1tYml6TW9CcSs5cmlwdz09IiwiaWF0IjoxNzQwMzk0NTkwLjMxOH0.bgN9qXiUfTEKMABPs3Ab46rQK8CpGNk_ewYQ3CdxC94",

        'x-jike-access-token':
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoieFF0K1FDUlc3YnJUc3dhVitLVVVwSVg1NmFXOU1SbzA2WHJcL21SYWdqbjB5TGQ2Y1k5c0JmXC9wdzg0VWt2VFUwYnpUWFoxUkk3M0hMREtiYVwvR3ZpTzZxZllCSG9lUVpmMWZ3RUFianpVUnJIY1Qxcnh5ZlwvbUNWMnVOYjhOWGNhcDRXK1wvUnZCOHZcL3FZQWVzeGwzZXJMZDFoMzRYMFFoT2dsWWdOK1Rta2pNT2dTNWRCeFNwb1pReXdMZ3pWemo4eGl4azZnTXBCVDUxS0xaSWIxenJQVVBLMVZXbWlrakxvMExqZExXQmZcL01QS1MyRDhQY1F6VXhSZ2hkUjNrVVI2bG5OVjRkaSsxcEhSVkxrdWdDM2h6QWNIeHhxMWxXXC9PaUlLdHZDeDd0dGdQMDdtRm41R0tQNDVjWlRpYlZuTVZGcm9mS0dWTVFETUwwdGRMbWxrSXVLS3BWRldlTVREekl1OXFVdzhSUzA9IiwidiI6MywiaXYiOiJrY1VqSnFXcDc4cDZrZENYMElHYVdnPT0iLCJpYXQiOjE3NDA0NjA3OTMuODUyfQ.4PqGx0bfAk43KVly--xebOxC4ylLyegw_VQ1lRLoUbQ',
        'x-jike-refresh-token':
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoiekJ0UTArTVZCUEFVTklCYjBiMTlkWHFCN3RaOFBBKzNHYURET0FoSkdNa0VyTldFOUMyeCtxMmlOQXlzQUpLclVZQ1U3S3U0S1FqYnpmXC9QVTFiNjVNeGNDYStDTFwvK0ZPdzNuWFJMSXNtZGUzdUg4cGh0dHphbGhsR1N2ekltM1RKNk1PSmFidDgwVnRCbHRDTlkwVnI2Rk03Mk1qQTlmbitzU1YzUGpidXM9IiwidiI6MywiaXYiOiJaamJZOU9pSHVEUHNsQWY5aWQ3TFh3PT0iLCJpYXQiOjE3NDA0NjA3OTMuODUyfQ.xkThng4f_OL917hRnYJqtu0S4LQQTLiPIX9jkvBePbQ',
    }

def make_graphql_request(last_id=None):
    """Makes a GraphQL request to the Jike API.

    Args:
        last_id (str, optional): The last ID for pagination. Defaults to None.

    Returns:
        dict: The JSON response from the API.  Also saves the raw response to
        a file.
    """
    headers = construct_header()
    payload = load_graphql_query(last_id)
    response = requests.post(constants.JIKE_API_URL, json=payload, headers=headers)

    with open(constants.RAW_RESPONSE_JSON_FILE_FROM_JIKE, 'wt', encoding='utf-8') as f:
        json.dump(response.json(), f, indent=2, ensure_ascii=False)

    return response.json()

def parse_post_content(post_content:str):
    """Parses the content of a post to extract individual brief posts.

    Args:
        post_content (str): The raw content string of a Jike post.

    Returns:
        List[BriefPost]: A list of extracted BriefPost objects.
    """
    lst = post_content.split('\n')
    selected_date = lst[0]
    title = None
    link = None
    brief_posts = []
    for i, item in enumerate(lst[2:]):
        if i % 2 == 0:
            # Sample:
            # 1、2025年研考国家线发布
            lst = item.split('、')
            title = lst[0] if len(lst) == 1 else lst[1]
        else:
            link = item

            if title and link:
                brief_posts.append(BriefPost(title, link, selected_date))

    return brief_posts

def extract_data(json_data):
    """Extracts relevant data from the Jike API JSON response.

    Args:
        json_data (dict): The JSON response from the Jike API.

    Returns:
        Tuple[List[List[BriefPost]], List[List[BriefPost]], str]: A tuple containing:
            - A list of lists, where each inner list contains user posts for a single original post.
            - A list of lists, where each inner list contains news posts for a single original post.
            - The last ID for pagination (None if there's no next page).
    """
    post_dict_list = json_data["data"]["userProfile"]["feeds"]["nodes"]

    last_id = None
    has_next_page = json_data["data"]["userProfile"]["feeds"]["pageInfo"]["hasNextPage"]
    if has_next_page:
        last_id = json_data["data"]["userProfile"]["feeds"]["pageInfo"]["loadMoreKey"]["lastId"]

    selected_user_post_groups = []
    selected_news_groups = []
    for post_dict in post_dict_list:
        selected_posts = parse_post_content(post_dict["content"])

        user_posts = list(filter(lambda post: post.type == BriefPost.PostType.USER_POST, selected_posts))
        news_posts = list(filter(lambda post: post.type == BriefPost.PostType.NEWS, selected_posts))

        selected_user_post_groups.append(user_posts)
        selected_news_groups.append(news_posts)

    return [selected_user_post_groups, selected_news_groups, last_id]

def display_posts_groups(posts_groups: List[List[BriefPost]]):
    """Displays the extracted brief posts grouped by their original post.

    Args:
        posts_groups (List[List[BriefPost]]):  A list of lists, where each inner
            list contains BriefPost objects for a single original post.
    """
    for posts in posts_groups:
        flag = False
        print('=' * 30)

        for post in posts:
            if not flag:
                flag = True
                print(f'Data: {post.selected_date}')

            print(f'Title: {post.title}')
            print(f'Link: {post.link}')
            print('-' * 10)

def save_posts(posts: List[BriefPost]):
    """Saves the extracted user posts to a JSON file.

    Args:
        posts (List[BriefPost]): A list of BriefPost objects to be saved.
    """
    with open(constants.USER_POSTS_JSON_FILE, 'wt', encoding='utf-8') as f:
        json.dump(
            [{'date': post.selected_date, 'title': post.title, 'link': post.link} for post in posts],
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write('\n')

def request_posts(max_date_num: int):
    """Requests, parses, and saves Jike posts until a specified number of dates are retrieved.

    This function iteratively fetches posts from the Jike API, extracts user and
    news posts, displays them, and saves the user posts to a file.  It continues
    fetching until the total number of dates retrieved reaches `max_date_num`.

    Args:
        max_date_num (int): The maximum number of dates to retrieve posts for.
    """
    last_id = None
    date_count = 0
    total_user_posts = []

    while True:
        json_data = make_graphql_request(last_id)
        selected_user_post_groups, _, last_id = extract_data(json_data)

        for posts in selected_user_post_groups:
            total_user_posts.extend(posts)
        save_posts(total_user_posts)

        print(f'Last ID: {last_id}')
        display_posts_groups(selected_user_post_groups)

        date_count += len(selected_user_post_groups)
        print(f'Date Count: {date_count}')

        if date_count >= max_date_num:
            break

        print('Start to sleep...')
        time.sleep(2)
        print('End sleep...')


if __name__ == '__main__':
    request_posts(365 + 60)
