import ast
import functools
import os
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from google import genai

import constants
from core.enums import PostType, SentimentType


@dataclass
class AIModel:
    name: str
    max_call_num_per_min: int
    max_call_num_per_day: int


class NoAvailableModelError(Exception):
    """Exception raised when there is no available model in models pool."""
    pass


class AIProxy:

    models_pool = [
        AIModel(name="gemini-2.0-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
        AIModel(name="gemini-2.0-flash-lite", max_call_num_per_min=30, max_call_num_per_day=1500),
        AIModel(name="gemini-2.0-flash-thinking-exp-01-21", max_call_num_per_min=10, max_call_num_per_day=1500),
        AIModel(name="gemini-2.0-flash-exp", max_call_num_per_min=10, max_call_num_per_day=1500),

        AIModel(name="gemini-1.5-flash", max_call_num_per_min=15, max_call_num_per_day=1500),
        AIModel(name="gemini-1.5-flash-8b", max_call_num_per_min=15, max_call_num_per_day=1500),
    ]
    model = models_pool[0]
    model_retry_count = 0

    call_count_per_min = 0
    call_count_per_day = 0
    last_begin_call_time_per_min = datetime.now(timezone.utc)
    last_success_call_time = datetime.now(timezone.utc)

    @classmethod
    def update_model(cls):
        if len(cls.models_pool) <= 1:
            raise NoAvailableModelError(" Available models pool is empty...")

        cls.models_pool.pop(0)
        cls.model = cls.models_pool[0]
        print(f'Updated model: {cls.model.name}')

        cls.model_retry_count = 0
        cls.call_count_per_day = cls.call_count_per_min = 0
        cls.last_begin_call_time_per_min = datetime.now(timezone.utc)

    @staticmethod
    def api_decorator(func):

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            now = datetime.now(timezone.utc)
            time_since_last_call_per_min = now - AIProxy.last_begin_call_time_per_min

            # Model call meets the minute limit
            if (
                AIProxy.call_count_per_min == AIProxy.model.max_call_num_per_min
                and time_since_last_call_per_min.total_seconds() <= 60
            ):
                sleep_time_in_second = 60 - time_since_last_call_per_min.total_seconds()

                print('API call reached minute limit')
                print(f'Sleeping for {sleep_time_in_second} seconds...')
                time.sleep(sleep_time_in_second)
                print('Retry API')

                # print(f'last_call_time_per_min: {AIProxy.last_begin_call_time_per_min}')
                # print(f'time_since_last_call_per_min: {time_since_last_call_per_min}')

                AIProxy.call_count_per_min = 0
                AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc)

                return wrapper(self, *args, **kwargs)

            # Model call meets the day limit
            elif AIProxy.call_count_per_day == AIProxy.model.max_call_num_per_day:
                print('API call reached day limit')
                print('Change model...')

                AIProxy.update_model()
                self._init_chat()

                return wrapper(self, *args, **kwargs)

            # Reset last_begin_call_time_per_min
            elif time_since_last_call_per_min.total_seconds() > 60:
                AIProxy.last_begin_call_time_per_min = now

            try:
                AIProxy.call_count_per_min += 1
                AIProxy.call_count_per_day += 1

                # print(f"Current call API time: {now}")
                print(f"Current call count per minute: {AIProxy.call_count_per_min}")
                print(f"Current call count per day: {AIProxy.call_count_per_day}")

                ret = func(self, *args, **kwargs)

                AIProxy.model_retry_count = 0
                AIProxy.last_success_call_time = datetime.now(timezone.utc)

                return ret
            except Exception as e:
                AIProxy.model_retry_count += 1
                now = datetime.now(timezone.utc)
                time_since_last_success = now - AIProxy.last_success_call_time

                # Update model if retry count exceeds max or time since last success call is more than 2 minutes
                if (
                    AIProxy.model_retry_count >= constants.MODEL_RETRY_MAX_NUM
                    # or time_since_last_success.total_seconds() >= 60 * 2
                ):
                    print('Model retry num meets the limit')
                    print('Change model...')

                    AIProxy.update_model()
                    self._init_chat()

                    return wrapper(self, *args, **kwargs)

                # Sleep for a minute before retrying
                else:
                    print(f'API Error: {e}')
                    print(f'Error type: {type(e).__name__}')
                    traceback.print_exc()

                    # Add a delay before retrying
                    sleep_time_in_second = 60 - time_since_last_call_per_min.total_seconds()

                    print('API call reached minute limit')
                    print(f'Sleeping for {sleep_time_in_second} seconds...')

                    time.sleep(sleep_time_in_second)
                    print('Retry API')

                    AIProxy.call_count_per_min = 0
                    AIProxy.last_begin_call_time_per_min = datetime.now(timezone.utc)

                    return wrapper(self, *args, **kwargs)

        return wrapper

    def __init__(self, content_txt):
        self.content_txt = content_txt

        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)

        self.chat= None
        self._init_chat()

    @api_decorator
    def _init_chat(self):
        if not AIProxy.model:
            raise RuntimeError("Model not initialized")
        print(f'Current model: {AIProxy.model.name}')

        prompt = f"我将给你一段文本，然后给你一系列任务，对于现在这个问题，你不用回答.\n 文本内容:\n{self.content_txt}"
        self.chat = self.client.chats.create(model=AIProxy.model.name)
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

    @api_decorator
    def get_tags_from_content_text(self) -> List[str]:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = """请根据上面给定的文本，总结能代表文本的主题关键词标签，你回答的格式为: ['tag1', 'tag2', 'tag3']"""
        response = self.chat.send_message(prompt)
        print(f'Chat response(tags): {response.text}')

        return ast.literal_eval(str(response.text).strip())

    @api_decorator
    def get_post_type_from_content_text(self) -> PostType:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = (
            "请根据上面给定的文本，总结最代表文本的类型。\n"
            "有以下类型：知识类（技术教程、行业预测、工具测评）、观点类（时事评论、行业观察、书评）、生活类（成长感悟、随笔、旅行美食）、娱乐类（吐槽搞笑、迷因、段子）、互动类（投票、接龙挑战、测试）、产品营销类（产品介绍、营销活动）\n"
            "你回答的格式为:KNOWLEDGE or OPINION or LIFESTYLE or ENTERTAINMENT or INTERACTIVE or PRODUCT_MARKETING\n"
            "对回答类型的解释：\n"
            "KNOWLEDGE：知识类，包括技术教程、行业预测、工具测评等。\n"
            "OPINION：观点类，包括时事评论、行业观察、书评等。\n"
            "LIFESTYLE：生活类，包括成长感悟、随笔、旅行美食等。\n"
            "ENTERTAINMENT：娱乐类，包括吐槽搞笑、迷因、段子等。\n"
            "INTERACTIVE：互动类，包括投票、接龙挑战、测试等。\n"
            "PRODUCT_MARKETING：产品营销类，包括产品介绍、营销活动等。\n"
        )
        response = self.chat.send_message(prompt)
        print(f'Chat response(PostType): {response.text}')

        try:
            return PostType.from_string(str(response.text).strip())
        except Exception as e:
            print(f"Error parsing post type: {e}")
            traceback.print_exc()
            return PostType.NONE

    @api_decorator
    def get_sentiment_type_from_content_text(self) -> SentimentType:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，总结能文本情绪偏向，正向、中立还是负向，回答的格式为: NEUTRAL or NEGATIVE or POSITIVE"
        response = self.chat.send_message(prompt)
        print(f'Chat response(SentimentType): {response.text}')

        try:
            sentiment_type = SentimentType.from_string(str(response.text).strip())
        except Exception as e:
            print(f"Error parsing sentiment type: {e}")
            traceback.print_exc()
            sentiment_type = SentimentType.NONE

        return sentiment_type

    @api_decorator
    def is_hotspot_from_content_text(self) -> Optional[bool]:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，判断是否为热点话题，热点话题就是在最近两年内热门讨论的话题。回答的格式为: True or False"
        response = self.chat.send_message(prompt)
        print(f'Chat response(is_hotspot): {response.text}')

        is_hotspot = None
        try:
            response_text = str(response.text).strip().lower()
            is_hotspot = (response_text == 'true')
        except Exception as e:
            print(f"Error parsing is_hotspot: {e}")
            traceback.print_exc()

        return is_hotspot

    @api_decorator
    def is_creative_from_content_text(self) -> Optional[bool]:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，判断是否为创意内容，创意内容是指具有独特性、新颖性、创新性的内容。回答的格式为: True or False"
        response = self.chat.send_message(prompt)
        print(f'Chat response(is_creative): {response.text}')

        is_creative = None
        try:
            response_text = str(response.text).strip().lower()
            is_creative = (response_text == 'true')
        except Exception as e:
            print(f"Error parsing is_creative: {e}")
            traceback.print_exc()

        return is_creative

def test():
    pass
    # proxy = AIProxy()
    # assert proxy.get_tags_from_content_text('') == []
    # assert proxy.get_post_types_from_content_text('') == []
    # assert proxy.get_sentiment_type_from_content_text('') == ''


if __name__ == '__main__':
    test()
