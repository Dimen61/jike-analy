from enum import Enum, auto


class PostType(Enum):
    NONE = auto()
    KNOWLEDGE = auto()            # 知识类（技术教程、行业预测、工具测评）
    OPINION = auto()              # 观点类（时事评论、行业观察、书评）
    LIFESTYLE = auto()            # 生活类（成长感悟、随笔、旅行美食）
    ENTERTAINMENT = auto()        # 娱乐类（吐槽搞笑、迷因、段子）
    INTERACTIVE = auto()          # 互动类（投票、接龙挑战、测试）
    PRODUCT_MARKETING = auto()    # 产品营销类（产品介绍、营销活动）

    @classmethod
    def from_string(cls, string_value):
        string_value_upper = string_value.upper()
        try:
            return cls[string_value_upper]
        except KeyError:
            raise ValueError(f"Invalid post type: {string_value}")


class SentimentType(Enum):
    NONE = auto()
    NEUTRAL = auto()
    NEGATIVE = auto()
    POSITIVE = auto()

    @classmethod
    def from_string(cls, string_value):
        string_value_upper = string_value.upper()
        try:
            return cls[string_value_upper]
        except KeyError:
            raise ValueError(f"Invalid sentiment type: {string_value}")


class ContentLengthType(Enum):
    NONE = auto()
    SHORT = auto()
    MEDIUM = auto()
    LONG = auto()
    LONGER = auto()

    @classmethod
    def from_content_length(cls, length):
        if length < 100:
            return cls.SHORT
        elif length < 500:
            return cls.MEDIUM
        elif length < 2000:
            return cls.LONG
        else:
            return cls.LONGER
