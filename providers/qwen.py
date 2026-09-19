import os
from functools import lru_cache
from openai import OpenAI

@lru_cache(maxsize=1)
def create_qwen_client():
    qwen_vision_client = OpenAI(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return qwen_vision_client
