from functools import lru_cache
from openai import OpenAI

from . import require_environment_variable

@lru_cache(maxsize=1)
def create_qwen_client():
    qwen_vision_client = OpenAI(
        api_key=require_environment_variable("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return qwen_vision_client
