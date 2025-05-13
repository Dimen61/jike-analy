"""
This script retrieves, parses, and saves posts from the Jike social media platform.

It uses the Jike API(from GraphQL to restful, offical API changes) to fetch a user's posts, extracts relevant information
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

def construct_header_v0():
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

        'x-jike-access-token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoiXC91aFcrZFhQOTJGbHYrYTVpbDB3eGZaeVhQV2x0RWc5UXU5aDZvVHNhWTJMY1JEVXRwQzZKSHFlZVdERk1PRnpKUExqZ2x0VGNrN2NOck9tQW5WY2RUeWlXanY1RnJLT3lHXC9HbkdHY09OYWJtZUczXC8yOTAyTFwvSmJkWlI3SGsrWFFYd0JvVGpsSEVaZWQ4bU94Q01KV01VWGdmaXhcLzgyem03TWIrWEhqMHFcL0JTeld5ODdxc1QwZGUwb3U2S252WUluQ3p1WUVWWGZXSDQ0U084N1o4em5FTm9JNm1IeUV5Z1FLTGkxN1lUNTUydHZLXC9vMTRabFJ1VGxId3N2MkVkdjNJZHVKSXQ5UERNYTF2R1RMOWFFajNrTjUwQzdqYW9zeWRCRTdKbUp6eStVMzQ3TXZwK2F3WFBZbFRnY1NqVnVNREpBR0JBdUZ5TlFSd01ObWZPZ1gwQVBpbVZ1XC83akZodXhZRmNMclE9IiwidiI6MywiaXYiOiJaa3pacDZtaDM4cVwvSGhORzNtNTVvZz09IiwiaWF0IjoxNzQ2NzgxNTE0LjMzOX0._g8F7akT-7QTRKiSph__kuDkALKCtnmaJTtc-mNTmx0',
        'x-jike-refresh-token':
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoiekJ0UTArTVZCUEFVTklCYjBiMTlkWHFCN3RaOFBBKzNHYURET0FoSkdNa0VyTldFOUMyeCtxMmlOQXlzQUpLclVZQ1U3S3U0S1FqYnpmXC9QVTFiNjVNeGNDYStDTFwvK0ZPdzNuWFJMSXNtZGUzdUg4cGh0dHphbGhsR1N2ekltM1RKNk1PSmFidDgwVnRCbHRDTlkwVnI2Rk03Mk1qQTlmbitzU1YzUGpidXM9IiwidiI6MywiaXYiOiJaamJZOU9pSHVEUHNsQWY5aWQ3TFh3PT0iLCJpYXQiOjE3NDA0NjA3OTMuODUyfQ.xkThng4f_OL917hRnYJqtu0S4LQQTLiPIX9jkvBePbQ',
    }

def construct_header_v1():
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

        # "X-Jike-Access-Token": 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoidjJjdTBFekNxbUxrd0hCSCtJN3FPVGoycUtSdkx3QUlyaDI4NE9aUlNRWGo0amdmZDZzNkZkY240aG1nXC9XbzNaN1VqWEVqMnBQMXQ5V0JqTlN6N2Z4VFplSTNZbGZPOU9QVWszeGpObGdtcnpMS1hZSjYzOXFheTBSNDF4VktDZTh0dUlMRXRvdVdmMjZOZEhyeFNDM0k0ZUR1K05raHdtc2ExK1lmTFRQMkt2WTRHU2FQWHBKS1wvYW1kaFo4eVJmYlJKVlhZVUIzdDJ1cVwvMzVYM05XNU5BRXpnMVwveVdyTDBJYTJPeGVTaFlTemtLY2tadlJSUzVtMDVGUlJ6alFGR0dzR09ZRDRMS1JlYUVQS0MzZGlVRDZMTDZBZnZiWUhjMGlxdVJPbjRMNzBIZjc3b0t1Q1JrMHFacmljTnBHNFJrVTRiTyt5cndvSFM0WlIyYlwvXC80S3F0YnZXTVRMREVWOVQxenVOWENFPSIsInYiOjMsIml2IjoiRVZuOUVEaDBZU2FBekJSVEdHUGJOUT09IiwiaWF0IjoxNzQ3MDM3MjQ1LjUzNH0.7bhTE1cQa4jBLo_MnpvveS1WF7O_yRzVAfTj2T2TloU'

        "X-Jike-Access-Token":
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjoiTlBtMTNRcldoSVc1ejJKZjlPRGpXT3hHNkxFZFBEVjlES2FlRkR4bUhmejZxTFQyREdRRmI3UHUxT0lFMG9xSzJsXC9GanVOMk5OQXpcL2xMMkR6ZkZMaFp0MGVDSitTTE5ybmdkRUV6N3pSOGtvaU14UTg1VjkyRDk0WndhMGxEUzN1UlE1TlpUUlR0eW9iRjFWamlzSHlqamM3RTRuWHZySm9Vb2ZoS09RbllVaTRMZUEzQnBsc2R3ZVlhSm50ZUtVVnErQ3hiTzRlUmkxeWl3REJ6TUxkSGVRc3NCZmVGVTA5bVwvVEorWG41VEVPM2tLVkZtTGVDZ1k2QUNFME41SDBFSG1QTldKbExIK256R0ZxK2pHblFGdkhBRGh1TWN0d2JzQlBIOWk3SndPTDVGclREaHd0Mlpib1pkY3ZJbyswV096NGVyWXFzODkwNWQ0RlwvamM3QU1KamEzMFwvaFBuWDNwU0FzeHpvUHc9IiwidiI6MywiaXYiOiJ2NndDclZwV3F1R2xpVnFSRktOMW53PT0iLCJpYXQiOjE3NDcwNTI2MzQuMDM2fQ.DhWsgMs773tuxY7JUVN9gLihWqG0cZwNc6x_Ro_6LNM'
    }

def construct_payload_v0():
    return load_graphql_query()

def construct_payload_v1(last_id=None):
    res_json = {"limit":20,"username":"wenhao1996"}
    if last_id:
        res_json["loadMoreKey"] = { "lastId": last_id }

    return res_json

def fetch_jike_data(last_id=None):
    """Makes a GraphQL or Restful request to the Jike API.

    Args:
        last_id (str, optional): The last ID for pagination. Defaults to None.

    Returns:
        dict: The JSON response from the API.  Also saves the raw response to
        a file.
    """
    headers = construct_header_v1()
    payload = construct_payload_v1(last_id)
    response = requests.post(constants.JIKE_API_URL, json=payload, headers=headers)

    print('-' * 20)
    print(f'response status code: {response.status_code}')
    print('-' * 20)

    # Dump tmp data for checkpoint
    with open(constants.RAW_RESPONSE_JSON_FILE_FROM_JIKE, 'wt', encoding='utf-8') as f:
        json.dump(response.json(), f, indent=2, ensure_ascii=False)

    return response.json()

def extract_post_content(post_content:str):
    """Extract the content of a post to extract individual brief posts.

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

def extract_data_v0(json_data):
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
        selected_posts = extract_post_content(post_dict["content"])

        user_posts = list(filter(lambda post: post.type == BriefPost.PostType.USER_POST, selected_posts))
        news_posts = list(filter(lambda post: post.type == BriefPost.PostType.NEWS, selected_posts))

        selected_user_post_groups.append(user_posts)
        selected_news_groups.append(news_posts)

    return [selected_user_post_groups, selected_news_groups, last_id]

def extract_data_v1(json_data):
    """Extracts relevant data from the Jike API JSON response.

    Args:
        json_data (dict): The JSON response from the Jike API.

    Returns:
        Tuple[List[List[BriefPost]], List[List[BriefPost]], str]: A tuple containing:
            - A list of lists, where each inner list contains user posts for a single original post.
            - A list of lists, where each inner list contains news posts for a single original post.
            - The last ID for pagination (None if there's no next page).
    """
    post_dict_list = json_data["data"]

    last_id = json_data.get("loadMoreKey", {}).get("lastId", None)

    selected_user_post_groups = []
    selected_news_groups = []
    for post_dict in post_dict_list:
        selected_posts = extract_post_content(post_dict["content"])

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

def crawl_posts(max_date_num: int):
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
        json_data = fetch_jike_data(last_id)
        selected_user_post_groups, _, last_id = extract_data_v1(json_data)

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
    print('Begin to crawl...')
    # crawl_posts(365 + 60)
    crawl_posts(1)
