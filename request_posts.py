import json
import time
from enum import Enum
from typing import List

import requests


class BriefPost:

    class PostType(Enum):
        NEWS = "news"
        USER_POST = "user_post"

    def __init__(self, title, link, selected_date):
        self.title = title
        self.link = link
        self.selected_date = selected_date
        self.type = None

        # Sample case:
        # https://m.okjike.com/originalPosts/67bac4b2205950ba34848365
        if 'm.okjike.com' in self.link:
            self.type = self.PostType.USER_POST
        else:
            self.type = self.PostType.NEWS


def load_graphql_query(last_id=None):
    # Load the JSON file
    with open('./graphql_payload.json', 'rt', encoding='utf-8') as file:
        payload = json.load(file)

    if last_id:
        payload['variables']['loadMoreKey'] = {'lastId': str(last_id)}
    return payload

def construct_header():
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
    URL = 'https://web-api.okjike.com/api/graphql'

    # Headers
    headers = construct_header()

    # Request payload
    payload = load_graphql_query(last_id)

    # Make the request
    response = requests.post(URL, json=payload, headers=headers)

    # Dump into the file
    with open('response.json', 'wt', encoding='utf-8') as f:
        json.dump(response.json(), f, indent=2, ensure_ascii=False)

    return response.json()

def parse_post_content(post_content:str):
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
    # Debug
    # print(json_data)
    #
    # user_name = json_data["data"]["userProfile"]["username"]
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
    with open('./user_post_groups.json', 'wt', encoding='utf-8') as f:
        json.dump(
            [{'date': post.selected_date, 'title': post.title, 'link': post.link} for post in posts],
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write('\n')

def request_posts(max_date_num: int):
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
