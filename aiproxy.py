import ast
import functools
import os
import time
from typing import List, Optional

from google import genai
from pydantic_core.core_schema import call_schema

from post_types import PostType, SentimentType


def api_decorator(func):

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if AIProxy.call_count == AIProxy.CALL_LIMIT_PER_PERIOD:
            print('API call limit reached')
            print(f'Sleeping for {AIProxy.CALL_PERIOD} seconds...')
            time.sleep(AIProxy.CALL_PERIOD)
            print('Retry API')

            AIProxy.call_count = 0
            return wrapper(self, *args, **kwargs)

        try:
            ret = func(self, *args, **kwargs)
            AIProxy.call_count += 1

            return ret
        except Exception as e:
            print(f'API Error: {e}')

            # Add a delay before retrying
            print(f'Sleeping for {AIProxy.CALL_PERIOD} seconds...')
            time.sleep(AIProxy.CALL_PERIOD)
            print('Retry API')

            AIProxy.call_count = 0
            return wrapper(self, *args, **kwargs)

    return wrapper

class AIProxy:
    CALL_PERIOD = 60 # In second
    CALL_LIMIT_PER_PERIOD = 15
    call_count = 0


    def __init__(self, content_txt):
        self.content_txt = content_txt
        self.model_pools = ["gemini-2.0-flash"]

        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)

        self.chat= None
        self._init_chat()

    @api_decorator
    def _init_chat(self):
        prompt = f"我将给你一段文本，然后给你一系列任务，对于现在这个问题，你不用回答.\n 文本内容:\n{self.content_txt}"
        self.chat = self.client.chats.create(model="gemini-2.0-flash")
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

    @api_decorator
    def get_tags_from_content_text(self) -> List[str]:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，总结能代表文本的主题关键词标签，返回的格式为:'[tag1, tag2, tag3]'"
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

        return ast.literal_eval(str(response.text).strip())

    @api_decorator
    def get_post_type_from_content_text(self) -> PostType:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = (
            "请根据上面给定的文本，总结最代表文本的类型。\n"
            "有以下类型：知识类（技术教程、行业预测、工具测评）、观点类（时事评论、行业观察、书评）、生活类（成长感悟、随笔、旅行美食）、娱乐类（吐槽搞笑、迷因、段子）、互动类（投票、接龙挑战、测试）、产品营销类（产品介绍、营销活动）\n"
            "返回的格式为:KNOWLEDGE or OPINION or LIFESTYLE or ENTERTAINMENT or INTERACTIVE or PRODUCT_MARKETING\n"
            "对返回类型的解释：\n"
            "KNOWLEDGE：知识类，包括技术教程、行业预测、工具测评等。\n"
            "OPINION：观点类，包括时事评论、行业观察、书评等。\n"
            "LIFESTYLE：生活类，包括成长感悟、随笔、旅行美食等。\n"
            "ENTERTAINMENT：娱乐类，包括吐槽搞笑、迷因、段子等。\n"
            "INTERACTIVE：互动类，包括投票、接龙挑战、测试等。\n"
            "PRODUCT_MARKETING：产品营销类，包括产品介绍、营销活动等。\n"
        )
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

        try:
            return PostType.from_string(str(response.text).strip())
        except Exception as e:
            print(f"Error parsing post type: {e}")
            return PostType.NONE

    @api_decorator
    def get_sentiment_type_from_content_text(self) -> SentimentType:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，总结能文本情绪偏向，正向、中立还是负向，返回的格式为: NEUTRAL or NEGATIVE or POSITIVE"
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

        try:
            sentiment_type = SentimentType.from_string(str(response.text).strip())
        except Exception as e:
            print(f"Error parsing sentiment type: {e}")
            sentiment_type = SentimentType.NONE

        return sentiment_type

    @api_decorator
    def is_hotspot_from_content_text(self) -> Optional[bool]:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，判断是否为热点话题，热点话题就是在最近两年内热门讨论的话题。返回的格式为: True or False"
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

        is_hotspot = None
        try:
            is_hotspot = bool(str(response.text).strip())
        except Exception as e:
            print(f"Error parsing is_hotspot: {e}")

        return is_hotspot

    @api_decorator
    def is_creative_from_content_text(self) -> Optional[bool]:
        if not self.chat:
            raise RuntimeError("Chat not initialized")

        prompt = "请根据上面给定的文本，判断是否为创意内容，创意内容是指具有独特性、新颖性、创新性的内容。返回的格式为: True or False"
        response = self.chat.send_message(prompt)
        print(f'Chat response: {response.text}')

        is_creative = None
        try:
            is_creative = bool(str(response.text).strip())
        except Exception as e:
            print(f"Error parsing is_creative: {e}")

        return is_creative

def test():
    pass
    # proxy = AIProxy()
    # assert proxy.get_tags_from_content_text('') == []
    # assert proxy.get_post_types_from_content_text('') == []
    # assert proxy.get_sentiment_type_from_content_text('') == ''


if __name__ == '__main__':
    test()
