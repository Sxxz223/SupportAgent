import json
from agents import Agent, Runner
from schemas.state import StateUpdate

def create_extractor_agent(deepseek_model):
    extractor_agent = Agent(
        name="State Extractor",
    
        instructions="""
You extract structured customer support information from the user's message.

Return ONLY valid JSON.

Use exactly this format:

{
  "user_name": null,
  "phone_last4": null,
  "order_no": null,
  "product": null,
  "issue": null
}

Rules:
- Only extract information explicitly present in the user's message.
- Extract a standalone four-digit verification response as phone_last4.
- Extract an order number when the user provides one.
- Do not guess.
- If a field is not mentioned, use null.
- Do not output markdown.
- Do not output explanation.
""",
    
        model=deepseek_model,
    )
    return extractor_agent

def extract_state_update(extractor_agent, user_input: str):
    extract_result = Runner.run_sync(
        extractor_agent,
        user_input,
    )
    
    # 1. LLM 返回的是 JSON 字符串
    raw_output = extract_result.final_output
    
    print("\n[RAW EXTRACTOR OUTPUT]")
    print(raw_output)
    
    # 2. JSON 字符串 -> Python dict
    data = json.loads(raw_output)
    
    # 3. Python dict -> StateUpdate 对象
    update = StateUpdate(**data)
    
    print("\n[STATE UPDATE]")
    print("user_name:", update.user_name)
    print("phone_last4:", update.phone_last4)
    print("order_no:", update.order_no)
    print("product:", update.product)
    print("issue:", update.issue)
    
    return update
