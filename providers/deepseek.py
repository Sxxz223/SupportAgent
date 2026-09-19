import os
from functools import lru_cache
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled

@lru_cache(maxsize=1)
def create_deepseek_model():
    set_tracing_disabled(True)
    deepseek_client = AsyncOpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )
    deepseek_model = OpenAIChatCompletionsModel(
        model="deepseek-flash",
        openai_client=deepseek_client,
    )
    return deepseek_model
