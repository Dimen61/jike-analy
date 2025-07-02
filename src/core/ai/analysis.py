import ast
import traceback
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from core.ai.aiproxy import APIClient
from core.enums import PostType, SentimentType


class PromptManager:
    """Manages prompts for different content analysis tasks."""

    def __init__(self) -> None:
        self._prompts = {
            'init': '我将给你一段文本，然后给你一系列任务，对于现在这个问题，你不用回答.\n 文本内容:\n{content_txt}',

            'tags': "请根据上面给定的文本，总结能代表文本的主题关键词标签，你回答的格式为: ['tag1', 'tag2', 'tag3']",

            'post_type': (
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
            ),

            'sentiment_type': '请根据上面给定的文本，总结能文本情绪偏向，正向、中立还是负向，回答的格式为: NEUTRAL or NEGATIVE or POSITIVE',

            'is_hotspot': '请根据上面给定的文本，判断是否为热点话题，热点话题就是在最近两年内热门讨论的话题。回答的格式为: True or False',

            'is_creative': '请根据上面给定的文本，判断是否为创意内容，创意内容是指具有独特性、新颖性、创新性的内容。回答的格式为: True or False'
        }

    def get_init_prompt(self, content_txt: str) -> str:
        return self._prompts['init'].format(content_txt=content_txt)

    def get_tags_prompt(self) -> str:
        return self._prompts['tags']

    def get_post_type_prompt(self) -> str:
        return self._prompts['post_type']

    def get_sentiment_type_prompt(self) -> str:
        return self._prompts['sentiment_type']

    def get_is_hotspot_prompt(self) -> str:
        return self._prompts['is_hotspot']

    def get_is_creative_prompt(self) -> str:
        return self._prompts['is_creative']


class ContentAnalysisOperation(ABC):
    """Abstract base class for content analysis operations."""

    def __init__(self, api_client: APIClient, prompt_manager: PromptManager):
        self._api_client = api_client
        self._prompt_manager = prompt_manager

    @abstractmethod
    def execute(self) -> Any:
        """Execute the content analysis operation."""
        pass

    @abstractmethod
    def parse_response(self, response_text: str) -> Any:
        """Parse the API response text into the expected format."""
        pass


class TagsAnalysisOperation(ContentAnalysisOperation):
    """Operation for extracting tags from content."""

    def execute(self) -> List[str]:
        prompt = self._prompt_manager.get_tags_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(tags): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> List[str]:
        try:
            return ast.literal_eval(str(response_text).strip())
        except Exception as e:
            print(f"Error parsing tags: {e}")
            traceback.print_exc()
            return []


class PostTypeAnalysisOperation(ContentAnalysisOperation):
    """Operation for determining post type from content."""

    def execute(self) -> PostType:
        prompt = self._prompt_manager.get_post_type_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(PostType): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> PostType:
        try:
            return PostType.from_string(str(response_text).strip())
        except Exception as e:
            print(f"Error parsing post type: {e}")
            traceback.print_exc()
            return PostType.NONE


class SentimentAnalysisOperation(ContentAnalysisOperation):
    """Operation for analyzing sentiment from content."""

    def execute(self) -> SentimentType:
        prompt = self._prompt_manager.get_sentiment_type_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(SentimentType): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> SentimentType:
        try:
            return SentimentType.from_string(str(response_text).strip())
        except Exception as e:
            print(f"Error parsing sentiment type: {e}")
            traceback.print_exc()
            return SentimentType.NONE


class HotspotAnalysisOperation(ContentAnalysisOperation):
    """Operation for determining if content is about hotspot topics."""

    def execute(self) -> Optional[bool]:
        prompt = self._prompt_manager.get_is_hotspot_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(is_hotspot): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> Optional[bool]:
        try:
            response_text = str(response_text).strip().lower()
            return response_text == 'true'
        except Exception as e:
            print(f"Error parsing is_hotspot: {e}")
            traceback.print_exc()
            return None


class CreativeAnalysisOperation(ContentAnalysisOperation):
    """Operation for determining if content is creative."""

    def execute(self) -> Optional[bool]:
        prompt = self._prompt_manager.get_is_creative_prompt()
        response = self._api_client.send_message(prompt)
        print(f'Chat response(is_creative): {response.text}')
        return self.parse_response(str(response.text) if response.text else "")

    def parse_response(self, response_text: str) -> Optional[bool]:
        try:
            response_text = str(response_text).strip().lower()
            return response_text == 'true'
        except Exception as e:
            print(f"Error parsing is_creative: {e}")
            traceback.print_exc()
            return None
