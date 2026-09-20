from functools import lru_cache
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled

from . import require_environment_variable

@lru_cache(maxsize=1)
def create_deepseek_model():
    set_tracing_disabled(True)
    deepseek_client = AsyncOpenAI(
        api_key=require_environment_variable("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    deepseek_model = OpenAIChatCompletionsModel(
        model="deepseek-flash",
        openai_client=deepseek_client,
    )
    return deepseek_model
